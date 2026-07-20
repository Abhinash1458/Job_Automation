"""Interactive review checklist (local web app).

Opens at http://127.0.0.1:5000 showing the day's top-50 GCC matches with score
and details. For each row you click:
    ✓ (tick)  -> approve + apply this job
    ✗ (cross) -> skip / reject

A single background worker owns Playwright and processes ticked jobs one at a
time: it opens each job pre-filled with your details + resume. By default it
STOPS at the final Submit so you review and submit yourself (assisted). Flip the
"Auto-submit" switch at the top if you want it to attempt submit too.

Nothing is applied until you tick it.
"""
from __future__ import annotations

import json
import queue
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string

from . import applier, config, resume_parser, tracker

app = Flask(__name__)

_apply_q: "queue.Queue[str]" = queue.Queue()
_state: dict[str, str] = {}          # url -> human status
_url_to_idx: dict[str, str] = {}     # url -> row index (string) for live polling
_auto_submit = {"on": False}
_jobs_cache: list[dict] = []


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _reasons(materials: str | None):
    if not materials:
        return [], [], False
    try:
        d = json.loads(materials)
    except (TypeError, ValueError):
        return [], [], False
    has_packet = "cover_letter" in d
    return d.get("reasons", []), d.get("missing", []), has_packet


def _worker() -> None:
    """Owns Playwright; applies ticked jobs one at a time."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        while True:
            url = _apply_q.get()
            _state[url] = "Playwright not installed — run: playwright install chromium"

    resume = resume_parser.find_resume()
    config.DATA_DIR.joinpath(".browser").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(applier.PROFILE_DIR), headless=False,
            viewport={"width": 1280, "height": 900},
        )
        while True:
            url = _apply_q.get()
            _state[url] = "opening…"
            page = ctx.new_page()
            try:
                status = applier.open_and_fill(page, url, resume, _auto_submit["on"])
                _state[url] = status
                tracker.mark_apply_state(url, "submitted" if status == "submitted" else "assisted_opened")
            except Exception as exc:  # noqa: BLE001
                _state[url] = f"error: {exc}"
                tracker.mark_apply_state(url, "failed")


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review — {{ date }}</title><style>
 body{font:15px/1.5 system-ui,sans-serif;margin:0;background:#0b0f17;color:#e6edf3}
 header{padding:20px 26px;background:#111827;border-bottom:1px solid #30363d;position:sticky;top:0;z-index:5}
 h1{margin:0 0 4px;font-size:20px}.sub{color:#9aa4b2;font-size:13px}
 .toggle{margin-top:10px;font-size:13px;color:#c9d1d9}
 table{width:100%;border-collapse:collapse}
 td,th{padding:11px 14px;border-bottom:1px solid #21262d;vertical-align:top;text-align:left}
 th{position:sticky;top:96px;background:#161b22;font-size:11px;text-transform:uppercase;color:#8b949e;letter-spacing:.04em}
 .score{font-weight:700;font-size:18px}.s-strong{color:#3fb950}.s-good{color:#d29922}.s-weak{color:#8b949e}
 .title{font-weight:600}.company{color:#9aa4b2;font-size:13px;margin:2px 0 6px}
 ul{margin:4px 0;padding-left:16px;font-size:13px;color:#c9d1d9}.miss{color:#d29922;font-size:12px}
 a{color:#58a6ff;text-decoration:none;white-space:nowrap}a:hover{text-decoration:underline}
 .btn{border:0;border-radius:7px;padding:8px 12px;font-size:16px;cursor:pointer;font-weight:700}
 .tick{background:#238636;color:#fff}.cross{background:#30363d;color:#e6edf3;margin-left:6px}
 .stat{font-size:12px;color:#7ee787;margin-top:6px;min-height:16px}
 .done td{opacity:.5}
</style></head><body>
<header>
 <h1>Daily Matches — {{ date }}</h1>
 <div class="sub">{{ jobs|length }} GCC roles · Bangalore &amp; Hyderabad · tick ✓ to apply, ✗ to skip</div>
 <label class="toggle"><input type="checkbox" id="auto" onchange="setAuto()"> Auto-submit after filling
   <span style="color:#8b949e">(off = opens pre-filled, you click Submit)</span></label>
</header>
<table><thead><tr><th>#</th><th>Score</th><th>Role &amp; fit</th><th>Apply</th><th>Decision</th></tr></thead><tbody>
{% for j in jobs %}
<tr id="row{{ loop.index }}">
 <td>{{ loop.index }}</td>
 <td class="score {{ j.cls }}">{{ j.score }}</td>
 <td><div class="title">{{ j.title }}</div><div class="company">{{ j.company }} · {{ j.location }}</div>
   <ul>{% for r in j.reasons %}<li>{{ r }}</li>{% endfor %}</ul>
   {% if j.missing %}<div class="miss">Gaps: {{ j.missing|join('; ') }}</div>{% endif %}
   {% if j.packet %}<div style="color:#3fb950;font-size:12px">✅ tailored packet ready</div>{% endif %}
 </td>
 <td><a href="{{ j.url }}" target="_blank">Open&nbsp;posting →</a></td>
 <td>
   <button class="btn tick" onclick="decide({{ loop.index0 }},'tick',this)">✓</button>
   <button class="btn cross" onclick="decide({{ loop.index0 }},'skip',this)">✗</button>
   <div class="stat" id="stat{{ loop.index0 }}"></div>
 </td>
</tr>
{% endfor %}
</tbody></table>
<script>
 async function setAuto(){await fetch('/auto/'+(document.getElementById('auto').checked?1:0),{method:'POST'})}
 async function decide(i,action,btn){
   btn.disabled=true;
   const r=await fetch('/'+action+'/'+i,{method:'POST'});const d=await r.json();
   document.getElementById('stat'+i).textContent=d.status;
   if(action=='skip'){document.getElementById('row'+(i+1)).classList.add('done')}
 }
 // poll statuses so apply progress shows live
 setInterval(async()=>{const r=await fetch('/status');const d=await r.json();
   for(const[i,s]of Object.entries(d)){const el=document.getElementById('stat'+i);if(el)el.textContent=s}},2000);
</script></body></html>"""


def _load_jobs() -> list[dict]:
    rows = tracker.top_for_review(_today(), 50)
    out = []
    for r in rows:
        reasons, missing, packet = _reasons(r.get("materials"))
        score = r.get("score") or 0
        out.append({
            "url": r.get("url"), "title": r.get("title") or "", "company": r.get("company") or "",
            "location": r.get("location") or "", "score": score,
            "cls": "s-strong" if score >= 85 else "s-good" if score >= 70 else "s-weak",
            "reasons": reasons[:4], "missing": missing[:3], "packet": packet,
        })
    return out


@app.route("/")
def index():
    global _jobs_cache
    _jobs_cache = _load_jobs()
    return render_template_string(PAGE, jobs=_jobs_cache, date=_today())


@app.route("/tick/<int:i>", methods=["POST"])
def tick(i: int):
    if 0 <= i < len(_jobs_cache):
        url = _jobs_cache[i]["url"]
        tracker.approve(url)
        _url_to_idx[url] = str(i)       # map job -> row for the live poller
        _state[url] = "queued for apply…"
        _apply_q.put(url)
        return jsonify(status="queued for apply…")
    return jsonify(status="?"), 400


@app.route("/skip/<int:i>", methods=["POST"])
def skip(i: int):
    if 0 <= i < len(_jobs_cache):
        tracker.reject(_jobs_cache[i]["url"])
        return jsonify(status="skipped")
    return jsonify(status="?"), 400


@app.route("/auto/<int:on>", methods=["POST"])
def auto(on: int):
    _auto_submit["on"] = bool(on)
    return jsonify(auto=_auto_submit["on"])


@app.route("/status")
def status():
    # translate url-keyed worker states to row-index keyed for the page
    out = {}
    for url, st in _state.items():
        idx = _url_to_idx.get(url)
        if idx is not None:
            out[idx] = st
    return jsonify(out)


def serve(port: int = 5000) -> None:
    config.require_llm()  # ensures profile/config sane; key not strictly needed to review
    threading.Thread(target=_worker, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    print(f"Review checklist: {url}  (Ctrl+C to stop)")
    import webbrowser
    webbrowser.open(url)
    app.run(port=port, debug=False, use_reloader=False)
