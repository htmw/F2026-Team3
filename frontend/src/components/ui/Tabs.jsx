// Segmented filter row. `options` are strings or { value, label, count }.
export default function SegmentedTabs({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const item = typeof option === 'string' ? { value: option, label: option } : option
        const active = value === item.value
        return (
          <button key={item.value} type="button" aria-pressed={active} onClick={() => onChange(item.value)}
            className={`min-h-9 cursor-pointer rounded-full border px-3.5 text-[13px] font-semibold ${
              active ? 'border-navy bg-navy text-white' : 'border-line bg-surface text-navy'}`}>
            {item.label}
            {item.count != null && <span className={active ? 'text-fog' : 'text-muted'}> · {item.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
