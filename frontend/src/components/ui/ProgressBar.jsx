// `secondary` adds a lighter segment after the main one (e.g. done + in progress).
export default function ProgressBar({ value, secondary, color, height = 'h-1.5', label }) {
  const clamp = (n) => Math.max(0, Math.min(100, n))
  const pct = clamp(value)
  const extra = secondary == null ? 0 : clamp(Math.min(secondary, 100 - pct))
  const fill = color || 'var(--color-accent)'
  return (
    <div className={`${height} flex overflow-hidden rounded-full bg-line-soft`}
      role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className="h-full rounded-[inherit]" style={{ width: `${pct}%`, background: fill }} />
      {extra > 0 && (
        <div className="h-full rounded-r-[inherit]" style={{ width: `${extra}%`, background: `color-mix(in srgb, ${fill} 35%, transparent)` }} />
      )}
    </div>
  )
}
