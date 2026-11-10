export function ScaleField({
  value,
  onChange,
  minLabel,
  maxLabel,
}: {
  value?: number;
  onChange: (v: number) => void;
  minLabel: string;
  maxLabel: string;
}) {
  return (
    <div role="radiogroup">
      <div className="flex justify-between gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            onClick={() => onChange(n)}
            className={`flex h-11 w-11 items-center justify-center rounded-full border font-mono text-sm transition-colors duration-200 ${
              value === n
                ? 'border-teal bg-teal/10 text-teal'
                : 'border-white/15 text-fg/70 hover:border-white/30'
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <div className="mt-2 flex justify-between font-mono text-[11px] uppercase tracking-wider text-muted">
        <span>{minLabel}</span>
        <span>{maxLabel}</span>
      </div>
    </div>
  );
}
