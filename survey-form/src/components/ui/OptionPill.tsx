export function OptionPill({
  label,
  selected,
  onClick,
  type = 'radio',
  name,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  type?: 'radio' | 'checkbox';
  name: string;
}) {
  return (
    <button
      type="button"
      role={type}
      aria-checked={selected}
      name={name}
      onClick={onClick}
      className={`rounded-full border px-4 py-2 text-left text-sm font-medium transition-colors duration-200 ${
        selected
          ? 'border-teal bg-teal/10 text-teal'
          : 'border-white/15 bg-white/[0.03] text-fg/80 hover:border-white/30'
      }`}
    >
      {label}
    </button>
  );
}
