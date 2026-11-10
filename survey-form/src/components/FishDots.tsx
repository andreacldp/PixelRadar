export function FishDots({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 120"
      className={className}
      width="240"
      height="120"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="fishGradient" x1="0" y1="0" x2="240" y2="0" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F0397A" />
          <stop offset="1" stopColor="#2EE6B8" />
        </linearGradient>
      </defs>
      <path
        d="M20 60c20-28 60-44 110-44 36 0 66 14 86 36-20 22-50 36-86 36-50 0-90-16-110-28z"
        stroke="url(#fishGradient)"
        strokeWidth="1"
      />
      <path d="M216 52l24-16-6 24 6 24-24-16" stroke="url(#fishGradient)" strokeWidth="1" />
      <circle cx="70" cy="52" r="2.5" fill="url(#fishGradient)" />
    </svg>
  );
}
