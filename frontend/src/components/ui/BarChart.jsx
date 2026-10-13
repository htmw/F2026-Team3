// Simple vertical div-bar chart. `data` is [{ label, value, highlight? }]; highlighted bars are amber.
export default function BarChart({ data, max, unit = '', label, barHeight = 130 }) {
  const top = Math.max(max ?? 0, ...data.map((item) => item.value)) || 1
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-end gap-2.5 border-b border-line-soft pt-2" style={{ height: barHeight + 50 }} role="img"
        aria-label={`${label ? `${label}: ` : ''}${data.map((item) => `${item.label} ${item.value}${unit}`).join(', ')}`}>
        {data.map((item) => (
          <div key={item.label} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
            <span className="text-[11px] font-bold text-muted">{item.value}{unit}</span>
            <div className="w-full max-w-[34px] rounded-[8px_8px_4px_4px]"
              style={{ height: Math.round((item.value / top) * barHeight), background: item.highlight ? 'var(--color-amber)' : 'var(--color-accent)' }} />
          </div>
        ))}
      </div>
      <div className="flex gap-2.5">
        {data.map((item) => <span key={item.label} className="flex-1 text-center text-xs text-muted">{item.label}</span>)}
      </div>
    </div>
  )
}
