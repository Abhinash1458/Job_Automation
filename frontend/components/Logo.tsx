export default function Logo({ size = 26 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2 select-none">
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
        <defs>
          <linearGradient id="jh" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
            <stop stopColor="#7C87FF" />
            <stop offset="1" stopColor="#35D6A4" />
          </linearGradient>
        </defs>
        <rect x="1" y="1" width="30" height="30" rx="9" fill="url(#jh)" />
        {/* an aim/target notch — the product 'finds the match' */}
        <path
          d="M10 20.5 L16 10 L22 20.5"
          stroke="#0A0D16"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <circle cx="16" cy="21.5" r="1.9" fill="#0A0D16" />
      </svg>
      <span className="font-display text-[17px] font-bold tracking-tight">
        Job<span className="text-brand">Hunt</span>
      </span>
    </span>
  );
}
