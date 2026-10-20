import { useRef } from 'react'

// Radio-like colour picker (spec 37 branding). `options` are [{ value: '#hex', label }] (e.g. ACCENTS from
// lib/theme.js); the hex is data, so it is the one inline style here. Arrow keys move and select, like radios.
export default function ColorSwatches({ label, value, onChange, options }) {
  const refs = useRef([])
  const index = Math.max(0, options.findIndex((o) => o.value.toLowerCase() === String(value).toLowerCase()))

  const onKeyDown = (event) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key]
    if (!step) return
    event.preventDefault()
    const next = (index + step + options.length) % options.length
    onChange(options[next].value)
    refs.current[next]?.focus()
  }

  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-3" onKeyDown={onKeyDown}>
      {options.map((option, i) => {
        const selected = i === index
        return (
          <button key={option.value} ref={(el) => { refs.current[i] = el }} type="button" role="radio"
            aria-checked={selected} aria-label={selected ? `${option.label} (selected)` : option.label}
            tabIndex={selected ? 0 : -1} onClick={() => onChange(option.value)}
            style={{ background: option.value }}
            className={`size-10 cursor-pointer rounded-full border-0 p-0 ring-offset-2 ring-offset-surface ${
              selected ? 'ring-4 ring-navy' : 'hover:ring-2 hover:ring-line-strong'}`} />
        )
      })}
    </div>
  )
}
