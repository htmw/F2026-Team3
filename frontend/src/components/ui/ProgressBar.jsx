export default function ProgressBar({ value, color, height = 'h-1.5', label }) {
  const pct = Math.max(0, Math.min(100, value))
  return (
    <div className={`${height} overflow-hidden rounded-full bg-line-soft`}
      role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className="h-full rounded-[inherit]" style={{ width: `${pct}%`, background: color || 'var(--color-accent)' }} />
    </div>
  )
}
