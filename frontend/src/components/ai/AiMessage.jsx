import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Dialog from '../ui/Dialog.jsx'
import { Field, Textarea } from '../ui/Field.jsx'
import Icon from '../ui/Icon.jsx'
import Notice from '../ui/Notice.jsx'
import PlanBlock from './PlanBlock.jsx'

export function SparkleTile({ size = 'size-8' }) {
  return (
    <div className={`flex ${size} shrink-0 items-center justify-center rounded-[10px] bg-teal`}>
      <Icon name="sparkle" size={16} color="var(--color-navy)" strokeWidth={2.2} />
    </div>
  )
}

function ReportDialog({ open, onClose, onSubmit }) {
  const [issue, setIssue] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const close = () => { if (!saving) { setIssue(''); setError(null); onClose() } }
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSubmit(issue.trim())
      setIssue('')
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }
  return (
    <Dialog open={open} onClose={close} title="Report this answer">
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <p className="m-0 text-sm text-muted">An administrator reviews reported answers to improve Acadmate.</p>
        <Field id="ai-report" label="What was wrong?">
          <Textarea id="ai-report" rows={3} maxLength={500} value={issue} onChange={(event) => setIssue(event.target.value)} />
        </Field>
        {error && <Notice tone="pink">{error}</Notice>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={close} disabled={saving}>Cancel</Button>
          <Button type="submit" disabled={saving || !issue.trim()}>{saving ? 'Sending…' : 'Send report'}</Button>
        </div>
      </form>
    </Dialog>
  )
}

// An AI advisor answer: text, optional plan, follow-up tip, actions, the data it used, and feedback controls.
// Without `onRate`/`onReport` (e.g. the admin test box) it renders read-only.
export default function AiMessage({ message, time, onRate, onReport }) {
  const [reporting, setReporting] = useState(false)
  const rate = (helpful) => onRate(message.rating === (helpful ? 1 : -1) ? null : helpful)
  return (
    <div className="flex items-start gap-3">
      <SparkleTile />
      <div className="flex min-w-0 max-w-[620px] flex-1 flex-col gap-2.5">
        <div className={`whitespace-pre-wrap rounded-[16px_16px_16px_4px] px-4 py-3 text-sm leading-[1.55] ${
          message.kind === 'handoff' ? 'bg-amber-soft text-amber-deep' : 'bg-surface-sunk text-navy'}`}>
          {message.text}
        </div>
        {message.plan?.length > 0 && <PlanBlock plan={message.plan} term={message.planTerm} />}
        {message.follow && <div className="rounded-2xl bg-surface-sunk px-4 py-3 text-[13px] leading-normal text-slate">{message.follow}</div>}
        {onRate && message.actions?.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {message.actions.map((action, i) => (
              <Button key={action.to} to={action.to} variant={i === 0 ? 'primary' : 'secondary'} size="sm">{action.label}</Button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {message.sources?.length > 0 && (
            <>
              <span>Based on</span>
              {message.sources.map((source) => <span key={source} className="rounded-full bg-canvas px-2.5 py-1 font-semibold text-slate">{source}</span>)}
            </>
          )}
          {time && <span>{time}</span>}
          {onRate && (
            <span className="ml-auto flex items-center gap-3">
              <button type="button" aria-label="Helpful" aria-pressed={message.rating === 1} onClick={() => rate(true)}
                className={`hit-44 flex size-8 cursor-pointer items-center justify-center rounded-lg border-0 ${message.rating === 1 ? 'bg-teal-soft text-teal-ink' : 'bg-transparent text-muted hover:bg-surface-sunk'}`}>
                <Icon name="thumbUp" size={15} />
              </button>
              <button type="button" aria-label="Not helpful" aria-pressed={message.rating === -1} onClick={() => rate(false)}
                className={`hit-44 flex size-8 cursor-pointer items-center justify-center rounded-lg border-0 ${message.rating === -1 ? 'bg-pink-soft text-pink-ink' : 'bg-transparent text-muted hover:bg-surface-sunk'}`}>
                <Icon name="thumbDown" size={15} />
              </button>
              <button type="button" onClick={() => setReporting(true)}
                className="hit-44 flex min-h-8 cursor-pointer items-center gap-1 rounded-lg border-0 bg-transparent px-2 text-xs font-semibold text-muted hover:bg-surface-sunk">
                <Icon name="flag" size={14} />Report
              </button>
            </span>
          )}
        </div>
      </div>
      {onReport && <ReportDialog open={reporting} onClose={() => setReporting(false)} onSubmit={onReport} />}
    </div>
  )
}
