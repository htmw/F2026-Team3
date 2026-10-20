import { useEffect, useId, useRef } from 'react'
import Icon from './Icon.jsx'

// Modal built on native <dialog>: focus trapping, Esc and the backdrop come from the browser.
export default function Dialog({ open, onClose, title, children, actions }) {
  const ref = useRef(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog ref={ref} aria-labelledby={titleId} onClose={onClose}
      onClick={(event) => { if (event.target === ref.current) onClose() }}
      className="m-auto box-border w-[min(520px,calc(100vw-32px))] rounded-[var(--radius-card)] border-0 bg-surface p-0 text-navy backdrop:bg-navy/50">
      {open && (
        <div className="flex flex-col gap-4 p-6">
          <div className="flex items-start justify-between gap-3">
            <h2 id={titleId} className="m-0 text-lg font-bold">{title}</h2>
            <button type="button" aria-label="Close" onClick={onClose}
              className="hit-44 -m-1.5 flex size-9 cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-muted hover:bg-surface-sunk">
              <Icon name="x" size={18} />
            </button>
          </div>
          {children}
          {actions && <div className="flex flex-wrap justify-end gap-2">{actions}</div>}
        </div>
      )}
    </dialog>
  )
}
