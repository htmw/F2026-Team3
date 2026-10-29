import { useId } from 'react'
import Icon from './Icon.jsx'

// Search box with a visually hidden label. Controlled when `value` is passed; `onSubmit(text)` runs on Enter.
export default function SearchInput({ label, placeholder, value, onChange, onSubmit, className = 'w-[280px]' }) {
  const id = useId()
  return (
    <div className={`relative max-w-full ${className}`}>
      <label htmlFor={id} className="sr-only">{label}</label>
      <Icon name="search" size={18} color="var(--color-muted)" className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2" />
      <input id={id} type="search" placeholder={placeholder}
        {...(value !== undefined ? { value, onChange: (event) => onChange(event.target.value) } : {})}
        onKeyDown={onSubmit && ((event) => { if (event.key === 'Enter') onSubmit(event.currentTarget.value.trim()) })}
        className="box-border h-11 w-full rounded-xl border border-line bg-surface pl-10 pr-4 text-sm text-navy" />
    </div>
  )
}
