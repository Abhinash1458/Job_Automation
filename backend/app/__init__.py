"""SaaS backend package (Phase 1).

A FastAPI layer that turns the single-user CLI pipeline in ``src/`` into a
multi-user web product: signup/login, per-user CV upload + parsed profile,
and background job matching with scored results.

Business logic (resume parsing, scraping, scoring) is NOT reimplemented here —
it is imported from the existing ``src/`` package via ``app.services.pipeline``.
"""
