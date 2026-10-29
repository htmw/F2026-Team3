import Button from '../ui/Button.jsx'
import Notice from '../ui/Notice.jsx'

// Sticky Save / Discard bar for a settings draft. `label` comes from useSaveState (Save changes / Saving… / Saved).
export default function SaveBar({ dirty, saving, label, error, onSave, onDiscard }) {
  return (
    <div className="sticky bottom-4 z-10 flex flex-col gap-2.5 rounded-[var(--radius-card)] border border-line bg-surface px-5 py-3.5 shadow-sm">
      {error && <Notice tone="pink" role="alert">{error}</Notice>}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onSave} disabled={saving || !dirty} aria-live="polite">{label}</Button>
        {dirty && !saving && <Button variant="secondary" onClick={onDiscard}>Discard</Button>}
        {dirty && !saving && <span className="text-[13px] text-muted">You have unsaved changes.</span>}
      </div>
    </div>
  )
}
