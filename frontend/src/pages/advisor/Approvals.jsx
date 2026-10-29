import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty } from '../../components/layout/MasterDetail.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import { Field, Textarea } from '../../components/ui/Field.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { APPROVAL_STATUS_TONE } from '../../lib/status.js'

const TABS = ['Pending', 'Approved', 'Changes requested']
const MAX_COMMENT = 1000 // matches schemas/approvals.Comment
const STACKED = '(max-width: 1023px)' // MasterDetail stacks below lg

// Advisor approvals (spec 23): course plans, forms and requests from advisees, with approve / request changes / reopen.
export default function AdvisorApprovals() {
  const { user: me, refreshBadges } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const detailRef = useRef(null)
  const tab = TABS.includes(params.get('tab')) ? params.get('tab') : 'Pending'
  const wantedId = Number(params.get('id')) || null
  const { data, error, reload, setData } = useApi(`/advisor/approvals?status=${encodeURIComponent(tab)}`)

  const rows = data?.rows ?? []
  const inList = rows.find((r) => r.id === wantedId)
  // A deep link (?id=) to a request that isn't in this tab loads it on its own.
  const { data: linked } = useApi(data && wantedId && !inList ? `/advisor/approvals/${wantedId}` : null)
  const selected = inList ?? (linked?.id === wantedId ? linked : null) ?? rows[0] ?? null

  const update = (changes) => setParams((current) => {
    const next = new URLSearchParams(current)
    for (const [key, value] of Object.entries(changes)) {
      if (value == null || (key === 'tab' && value === 'Pending')) next.delete(key)
      else next.set(key, String(value))
    }
    return next
  }, { replace: true })

  const pick = (row) => {
    update({ id: row.id })
    if (window.matchMedia?.(STACKED).matches) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }

  const reopen = async (request) => {
    try {
      await api(`/advisor/approvals/${request.id}/reopen`, { method: 'POST' })
      toast.show({ message: `${request.item} is back in Pending.` })
      refreshBadges()
      reload()
    } catch (err) {
      toast.show({ message: errorText(err) })
    }
  }

  // Takes the decided row out of this tab and moves the counts, then offers Undo (reopen).
  const decided = (request, result) => {
    setData((current) => {
      if (!current) return current
      const rest = current.rows.filter((r) => r.id !== request.id)
      return {
        tabs: current.tabs.map((t) => ({
          ...t,
          count: t.count + (t.label === result.status ? 1 : 0) - (t.label === request.status ? 1 : 0),
        })),
        rows: tab === request.status ? rest : current.rows,
      }
    })
    const next = rows[rows.findIndex((r) => r.id === request.id) + 1] ?? rows.find((r) => r.id !== request.id)
    update({ id: next?.id ?? null })
    refreshBadges()
    toast.show({
      message: result.status === 'Approved' ? `Approved ${request.item} for ${request.name}.` : `Sent your change request to ${request.name}.`,
      actionLabel: 'Undo',
      onAction: () => reopen(result),
    })
  }

  if (error && !data) {
    return (
      <>
        <PageHeader title="Approvals" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading approvals…" />

  // The advisor's "Run Acadmate pre-checks" setting (spec 27); off hides the check pill and box.
  const prechecks = data.prechecks !== false
  const tabs = data.tabs.map((t) => ({ value: t.label, label: t.label, count: t.count }))

  return (
    <>
      <PageHeader title="Approvals" subtitle="Course plans, forms and requests from your advisees" initials={me?.initials}
        actions={<Button variant="secondary" to="/advisor/settings#approvals">Approval settings</Button>} />

      <SegmentedTabs label="Filter approvals" options={tabs} value={tab} onChange={(value) => update({ tab: value, id: null })} />

      <MasterDetail
        list={(
          <Card as="section" aria-label="Requests" className="gap-2 p-3 sm:p-4">
            {rows.length === 0 ? <Empty>Nothing in this list.</Empty> : rows.map((row) => (
              <RequestCard key={row.id} row={row} prechecks={prechecks} selected={row.id === selected?.id} onSelect={() => pick(row)} />
            ))}
          </Card>
        )}
        detail={(
          <div ref={detailRef} className="scroll-mt-4">
            {selected ? <RequestDetail key={selected.id} request={selected} prechecks={prechecks} onDecided={decided} onReopen={reopen} />
              : <Card><DetailEmpty>Select a request to see its details.</DetailEmpty></Card>}
          </div>
        )} />
    </>
  )
}

function CheckPill({ ok }) {
  return <Pill tone={ok ? 'teal' : 'amber'}>{ok ? 'Pre-check passed' : 'Needs a look'}</Pill>
}

function RequestCard({ row, prechecks, selected, onSelect }) {
  return (
    <button type="button" aria-pressed={selected} onClick={onSelect}
      className={`flex w-full cursor-pointer flex-col gap-2 rounded-xl bg-surface px-4 py-3 text-left text-navy ${
        selected ? 'border-2 border-accent' : 'border-2 border-line hover:bg-surface-sunk'}`}>
      <span className="flex w-full items-baseline justify-between gap-3">
        <span className="text-sm font-bold">{row.name}</span>
        <span className="shrink-0 text-xs text-muted">{row.when}</span>
      </span>
      <span className="text-sm text-slate">{row.item}</span>
      <span className="flex flex-wrap gap-1.5">
        <Pill tone="gray">{row.type}</Pill>
        {prechecks && <CheckPill ok={row.ok} />}
      </span>
    </button>
  )
}

function RequestDetail({ request, prechecks, onDecided, onReopen }) {
  const toast = useToast()
  const [comment, setComment] = useState('')
  const [hint, setHint] = useState(null)
  const [sending, setSending] = useState(null)
  const pending = request.status === 'Pending'

  const decide = async (action) => {
    const text = comment.trim()
    if (action === 'request-changes' && !text) {
      setHint(`Add a comment so ${request.firstName} knows what to change.`)
      return
    }
    setSending(action)
    try {
      const result = await api(`/advisor/approvals/${request.id}/${action}`, { method: 'POST', body: { comment: text || null } })
      onDecided(request, result)
    } catch (err) {
      toast.show({ message: errorText(err) })
      setSending(null)
    }
  }

  return (
    <Card as="section" aria-labelledby="request-title" className="gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <span><Pill tone="gray">{request.type}</Pill></span>
          <h2 id="request-title" className="m-0 text-xl font-bold">{request.item}</h2>
          <span className="text-sm text-muted">{request.name} · submitted {request.when}</span>
        </div>
        <Pill tone={APPROVAL_STATUS_TONE[request.status] ?? 'gray'}>{request.status}</Pill>
      </div>

      {prechecks && (
        <Notice tone={request.ok ? 'teal' : 'amber'} icon={request.ok ? 'shield' : 'alert'}>
          <strong>Acadmate pre-check</strong>
          <span className="block">{request.check}</span>
        </Notice>
      )}

      <div className="flex flex-col gap-2">
        <h3 className="m-0 text-[15px] font-bold">What&apos;s being requested</h3>
        {request.lines.length === 0 ? <Empty>No details were attached.</Empty> : (
          <dl className="m-0 flex flex-col">
            {request.lines.map((line) => (
              <div key={line.a} className="grid grid-cols-1 gap-1 border-t border-canvas py-2.5 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:gap-4">
                <dt className="text-sm font-semibold">{line.a}</dt>
                <dd className={`m-0 text-sm ${line.b === 'Missing' ? 'font-semibold text-pink-ink' : 'text-slate'}`}>{line.b}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {pending ? (
        <>
          <Field id="approval-comment" label="Comment to the student" error={hint}>
            <Textarea id="approval-comment" rows={3} maxLength={MAX_COMMENT} placeholder="Required when requesting changes."
              value={comment} onChange={(event) => { setComment(event.target.value); setHint(null) }} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => decide('approve')} disabled={sending != null}>
              {sending === 'approve' ? 'Approving…' : 'Approve'}
            </Button>
            <Button variant="danger" className="border border-pink-ink disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => decide('request-changes')} disabled={sending != null || !comment.trim()}>
              {sending === 'request-changes' ? 'Sending…' : 'Request changes'}
            </Button>
            <Button variant="secondary" to={`/advisor/advisees/${request.studentId}`}>Open student</Button>
          </div>
        </>
      ) : (
        <div role="status" className="flex flex-col gap-3">
          <p className="m-0 text-sm text-slate">
            Decision sent to {request.name}.{request.comment && <> Your comment: “{request.comment}”</>}
          </p>
          <div className="flex flex-wrap gap-2">
            {request.canUndo && <Button variant="secondary" onClick={() => onReopen(request)}>Reopen</Button>}
            <Button variant="secondary" to={`/advisor/advisees/${request.studentId}`}>Open student</Button>
          </div>
        </div>
      )}
    </Card>
  )
}
