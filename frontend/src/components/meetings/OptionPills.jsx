// Row of choice buttons (topic, format, office-hour times), styled like the mockup's option pills.
// `multiple` makes it a multi-select: `value` is then an array and `onChange` gets the next array.
export default function OptionPills({ options, value, onChange, label, multiple = false }) {
  const isActive = (option) => (multiple ? value.includes(option) : option === value)
  const toggle = (option) => {
    if (!multiple) return onChange(option)
    return onChange(isActive(option) ? value.filter((v) => v !== option) : options.filter((o) => o === option || value.includes(o)))
  }
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const active = isActive(option)
        return (
          <button key={option} type="button" aria-pressed={active} onClick={() => toggle(option)}
            className={`min-h-11 cursor-pointer rounded-xl border px-3.5 text-sm font-semibold text-navy ${
              active ? 'border-accent bg-teal-soft/50' : 'border-line bg-surface hover:bg-surface-sunk'}`}>
            {option}
          </button>
        )
      })}
    </div>
  )
}
