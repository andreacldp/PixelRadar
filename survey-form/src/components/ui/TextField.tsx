export function TextField({
  label,
  value,
  onChange,
  placeholder,
  optional,
  error,
  type = 'text',
}: {
  label: string;
  value?: string;
  onChange: (v: string) => void;
  placeholder?: string;
  optional?: boolean;
  error?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="mb-2 block font-display text-base font-medium text-fg">
        {label}
        {optional && (
          <span className="ml-2 font-mono text-[11px] uppercase tracking-wider text-muted">
            Opcional
          </span>
        )}
      </span>
      <input
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl2 border border-white/15 bg-white/[0.03] px-4 py-3 text-sm text-fg placeholder:text-muted/70 focus:border-teal"
      />
      {error && <p className="mt-2 text-sm text-pink">{error}</p>}
    </label>
  );
}
