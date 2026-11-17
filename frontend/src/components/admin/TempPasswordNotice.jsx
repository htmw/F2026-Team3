import { useRef, useState } from 'react'
import Button from '../ui/Button.jsx'

// A temporary password an admin just issued (spec 31): shown once, with Copy. `note` replaces the default line.
export default function TempPasswordNotice({ password, firstName, note }) {
  const text = useRef(null)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // No clipboard access (e.g. plain http): select the text so the admin can copy it by hand.
      const range = document.createRange()
      range.selectNodeContents(text.current)
      const selection = window.getSelection()
      selection.removeAllRanges()
      selection.addRange(range)
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl bg-surface-sunk px-4 py-3">
      <span className="text-[13px] font-bold">Temporary password</span>
      <div className="flex flex-wrap items-center gap-3">
        <code ref={text} className="select-all break-all font-display text-lg tracking-[0.06em] text-navy">{password}</code>
        <Button variant="secondary" size="sm" onClick={copy}>
          <span aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
        </Button>
      </div>
      <span className="text-[13px] leading-normal text-muted">
        {note ?? `Shown once. ${firstName || 'They'} will choose a new password at first sign-in.`}
      </span>
    </div>
  )
}
