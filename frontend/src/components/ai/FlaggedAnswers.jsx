import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import Card, { CardHeader } from '../ui/Card.jsx'
import Button from '../ui/Button.jsx'
import Pill from '../ui/Pill.jsx'
import Switch from '../ui/Switch.jsx'
import { Empty, ErrorState, Loading } from '../ui/Status.jsx'
import { useToast } from '../ui/Toast.jsx'
import { api } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { optimisticAction } from '../../lib/optimistic.js'

const COMPACT_ROWS = 4
const STATUS_TONE = { Open: 'pink', Resolved: 'teal', Dismissed: 'gray' }
const COUNT_KEY = { Open: 'open', Resolved: 'resolved', Dismissed: 'dismissed' }

// Moves one flag between status counts.
const shift = (counts, from, to) => counts && { ...counts, [COUNT_KEY[from]]: counts[COUNT_KEY[from]] - 1, [COUNT_KEY[to]]: counts[COUNT_KEY[to]] + 1 }

// Open flagged AI answers with Fix / Dismiss. Full list on Admin AI settings (`#flags`), where *Show resolved*
// adds closed flags with Reopen; `compact` is the Admin overview card: first 4 flags, open / resolved counts and
// a View all link.
export default function FlaggedAnswers({ compact = false }) {
  const toast = useToast()
  const location = useLocation()
  const cardRef = useRef(null)
  const [showResolved, setShowResolved] = useState(false)
  const all = showResolved && !compact
  const { data, error, reload, setData } = useApi(`/admin/ai/flags?status=${all ? 'All' : 'Open'}`)

  // Arriving from the overview's View all link: scroll to the list once it has loaded.
  const loaded = Boolean(data)
  useEffect(() => {
    if (!compact && loaded && location.hash === '#flags') cardRef.current?.scrollIntoView({ block: 'start' })
  }, [compact, loaded, location.hash])

  // Optimistic status change; Undo reverses it. With only open flags shown, closed ones leave the list (and come
  // back where they were on Undo); with Show resolved on, the row stays and its status changes.
  const change = (flag, to, request, undo, message) => {
    const index = data.flags.findIndex((f) => f.id === flag.id)
    const from = flag.status
    const move = (current, status) => {
      if (!all && status !== 'Open') return { ...current, flags: current.flags.filter((f) => f.id !== flag.id) }
      if (!all) return { ...current, flags: current.flags.toSpliced(index, 0, flag) }
      return { ...current, flags: current.flags.map((f) => (f.id === flag.id ? { ...f, status } : f)) }
    }
    optimisticAction({
      setData, toast, request, undo, message,
      apply: (current) => ({ ...move(current, to), counts: shift(current.counts, from, to) }),
      revert: (current) => ({ ...move(current, from), counts: shift(current.counts, to, from) }),
    })
  }

  const resolve = (flag, resolution) => change(flag, resolution,
    () => api(`/admin/ai/flags/${flag.id}/resolve`, { method: 'POST', body: { resolution } }),
    () => api(`/admin/ai/flags/${flag.id}/reopen`, { method: 'POST' }),
    resolution === 'Resolved' ? 'Marked as fixed' : 'Flag dismissed')

  const reopen = (flag) => change(flag, 'Open',
    () => api(`/admin/ai/flags/${flag.id}/reopen`, { method: 'POST' }),
    () => api(`/admin/ai/flags/${flag.id}/resolve`, { method: 'POST', body: { resolution: flag.status } }),
    'Flag reopened')

  const flags = compact ? data?.flags.slice(0, COMPACT_ROWS) : data?.flags
  const header = compact ? (
    <CardHeader title="Flagged AI answers"
      subtitle={data?.counts && `${data.counts.open} open · ${data.counts.resolved} resolved`}
      action={<Link to="/admin/ai#flags" className="text-[13px] font-bold">View all</Link>} />
  ) : (
    <CardHeader title="Flagged answers" subtitle="Reported by students, advisors or automatic checks"
      action={(
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-[13px] font-semibold text-slate">
            <Switch checked={showResolved} onChange={setShowResolved} label="Show resolved" />
            Show resolved
          </label>
          {data?.counts && <Pill tone={data.counts.open ? 'amber' : 'teal'}>{data.counts.open} open</Pill>}
        </div>
      )} />
  )

  return (
    <Card as="section" id={compact ? undefined : 'flags'} ref={cardRef} className="scroll-mt-6 gap-3">
      {header}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!data && !error && <Loading label="Loading flagged answers…" />}
      {data?.flags.length === 0 && <Empty>{all ? 'No flags yet.' : 'No open flags. Nice.'}</Empty>}
      {flags?.map((flag) => (
        <div key={flag.id} className="flex flex-col gap-2 border-t border-canvas pt-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <span className="text-sm font-bold">“{flag.q}”</span>
            {compact
              ? <Pill tone="pink">Open</Pill>
              : (
                <span className="flex items-center gap-2 text-xs text-muted">
                  {flag.when} · {flag.student ?? flag.source}
                  {all && <Pill tone={STATUS_TONE[flag.status]}>{flag.status}</Pill>}
                </span>
              )}
          </div>
          {compact ? (
            <>
              <span className="text-[13px] text-slate">{flag.why}</span>
              <span className="text-xs text-muted">{flag.source} · {flag.when}</span>
            </>
          ) : (
            <>
              <span className="text-[13px] text-slate"><strong>Why flagged:</strong> {flag.why}</span>
              {flag.answer && <p className="m-0 whitespace-pre-wrap rounded-xl bg-surface-sunk px-3.5 py-2.5 text-[13px] leading-normal text-slate">{flag.answer}</p>}
            </>
          )}
          <div className="flex flex-wrap gap-2">
            {flag.status === 'Open' ? (
              <>
                <Button size="sm" onClick={() => resolve(flag, 'Resolved')}>Mark fixed</Button>
                <Button size="sm" variant="secondary" onClick={() => resolve(flag, 'Dismissed')}>Dismiss</Button>
              </>
            ) : <Button size="sm" variant="secondary" onClick={() => reopen(flag)}>Reopen</Button>}
          </div>
        </div>
      ))}
    </Card>
  )
}
