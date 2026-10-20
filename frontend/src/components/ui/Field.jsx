import { cloneElement, isValidElement } from 'react'

export const INPUT = 'box-border h-12 w-full rounded-xl border border-line bg-surface px-3.5 text-[15px] text-navy'

// Label above a control, with optional help or error text below. A single child control
// gets aria-describedby / aria-invalid wired to that text.
export function Field({ id, label, children, aside, hint, error }) {
  const helpId = error || hint ? `${id}-help` : undefined
  const control = helpId && isValidElement(children)
    ? cloneElement(children, { 'aria-describedby': helpId, 'aria-invalid': error ? true : undefined })
    : children
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-[13px] font-bold">{label}</label>
        {aside}
      </div>
      {control}
      {helpId && (
        <span id={helpId} className={`text-[13px] ${error ? 'font-semibold text-pink-ink' : 'text-muted'}`}>{error || hint}</span>
      )}
    </div>
  )
}

export function TextInput({ className = '', ...rest }) {
  return <input type="text" className={`${INPUT} ${className}`} {...rest} />
}

export function Select({ className = '', children, ...rest }) {
  return <select className={`${INPUT} cursor-pointer ${className}`} {...rest}>{children}</select>
}

export function Textarea({ className = '', rows = 4, ...rest }) {
  return <textarea rows={rows} className={`${INPUT} h-auto py-3 leading-relaxed ${className}`} {...rest} />
}
