export function Logo({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
        <circle
          cx="14"
          cy="14"
          r="12.5"
          stroke="url(#logoGradient)"
          strokeWidth="1.5"
          opacity="0.6"
        />
        <circle
          cx="14"
          cy="14"
          r="7.5"
          stroke="url(#logoGradient)"
          strokeWidth="1.2"
          opacity="0.85"
        />
        <circle cx="14" cy="14" r="2.5" fill="url(#logoGradient)" />
        <defs>
          <linearGradient
            id="logoGradient"
            x1="0"
            y1="0"
            x2="28"
            y2="28"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#F0397A" />
            <stop offset="1" stopColor="#2EE6B8" />
          </linearGradient>
        </defs>
      </svg>
      <span className="font-display text-lg font-semibold tracking-tight text-fg">
        PixelRadar
      </span>
    </div>
  );
}
