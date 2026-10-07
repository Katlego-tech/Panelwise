// A progress meter (projects.css `.meter`).

export function Meter({ value, label }: { value: number; label: string }) {
  const now = Math.round(Math.min(100, Math.max(0, value)));
  return (
    <span
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={now}
      className="mt-2.5 block h-1.5 overflow-hidden rounded-[3px] bg-desk-2"
    >
      <span className="block h-full bg-pencil" style={{ width: `${now}%` }} />
    </span>
  );
}
