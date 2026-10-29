import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty, ListRow } from '../../components/layout/MasterDetail.jsx'
import Avatar from '../../components/ui/Avatar.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import Dialog from '../../components/ui/Dialog.jsx'
import { Field, Textarea, TextInput } from '../../components/ui/Field.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import SearchInput from '../../components/ui/SearchInput.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useDebounced } from '../../lib/useDebounced.js'
import { ADVISEE_STATUS_TONE } from '../../lib/status.js'

const STATUSES = ['All', 'Needs attention', 'On track', 'Graduating', 'At risk']
const MAX_RECIPIENTS = 30 // matches schemas/messages.StartIn
const STACKED = '(max-width: 1023px)' // MasterDetail stacks below lg
const COLUMNS = 'sm:grid sm:grid-cols-[minmax(0,2.4fr)_0.8fr_0.6fr_1.1fr_1.1fr] sm:items-center sm:gap-3'

const credits = (row) => `${row.credits} / ${row.requiredCredits}`

// Advisor advisees (spec 21): filterable caseload list with a preview of the selected student.
export default function AdvisorAdvisees() {
  const { user: me } = useAuth()
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') ?? '')
  const [selectedId, setSelectedId] = useState(null)
  const detailRef = useRef(null)
  const status = STATUSES.includes(params.get('status')) ? params.get('status') : 'All'
  const q = useDebounced(search.trim())

  // Keep ?q= and ?status= in the URL so a filtered view can be shared or reloaded.
  useEffect(() => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (q) next.set('q', q)
      else next.delete('q')
      return next
    }, { replace: true })
  }, [q, setParams])

  const query = new URLSearchParams({ status, ...(q ? { q } : {}) })
  const { data, error, reload } = useApi(`/advisor/advisees?${query}`)

  const setStatus = (value) => setParams((current) => {
    const next = new URLSearchParams(current)
    if (value === 'All') next.delete('status')
    else next.set('status', value)
    return next
  }, { replace: true })

  const rows = data?.rows ?? []
  const selected = rows.find((r) => r.studentId === selectedId) ?? rows[0] ?? null

  const pick = (row) => {
    setSelectedId(row.studentId)
    if (window.matchMedia?.(STACKED).matches) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }

  if (error && !data) {
    return (
      <>
        <PageHeader title="Advisees" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading advisees…" />

  const tabs = data.tabs.map((t) => ({ value: t.label, label: t.label, count: t.count }))
  const shown = data.total > rows.length && rows.length > 0 ? `Showing ${rows.length} of ${data.total}` : null

  return (
    <>
      <PageHeader title="Advisees" subtitle={data.subtitle} initials={me?.initials}
        search={<SearchInput label="Search advisees" placeholder="Search by name…" value={search} onChange={setSearch} />}
        actions={<MessageGroupButton rows={rows} status={status} />} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedTabs label="Filter advisees" options={tabs} value={status} onChange={setStatus} />
        {shown && <span className="text-sm text-muted">{shown}</span>}
      </div>

      <MasterDetail wideList
        list={(
          <Card as="section" aria-label="Advisee list" className="gap-1 p-3 sm:p-4">
            <div className={`hidden px-3.5 pb-1 text-xs font-bold uppercase tracking-[0.06em] text-muted ${COLUMNS}`} aria-hidden="true">
              <span>Student</span><span>Credits</span><span>GPA</span><span>Status</span><span>Next meeting</span>
            </div>
            {rows.length === 0 ? <Empty>No advisees match.</Empty> : rows.map((row) => (
              <AdviseeRow key={row.studentId} row={row} selected={row.studentId === selected?.studentId} onSelect={() => pick(row)} />
            ))}
          </Card>
        )}
        detail={(
          <div ref={detailRef} className="scroll-mt-4">
            {selected ? <AdviseePreview row={selected} />
              : <Card><DetailEmpty>Select an advisee to see their summary.</DetailEmpty></Card>}
          </div>
        )} />
    </>
  )
}

function AdviseeRow({ row, selected, onSelect }) {
  const tone = ADVISEE_STATUS_TONE[row.status]
  return (
    <ListRow selected={selected} onSelect={onSelect}>
      <span className={`flex min-w-0 flex-1 items-center justify-between gap-3 ${COLUMNS}`}>
        <span className="flex min-w-0 items-center gap-3">
          <Avatar name={row.fullName} initials={row.initials} tone={tone} size="sm" />
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-bold">{row.name}</span>
            <span className="truncate text-xs text-muted">{row.program}</span>
          </span>
        </span>
        <span className="hidden text-sm text-slate sm:block">{credits(row)}</span>
        <span className="hidden text-sm text-slate sm:block">{row.gpa}</span>
        <span><Pill tone={tone}>{row.status}</Pill></span>
        <span className="hidden text-sm text-slate sm:block">{row.next}</span>
      </span>
    </ListRow>
  )
}

function Fact({ label, value }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">{label}</span>
      <span className="text-lg font-bold text-navy">{value}</span>
    </div>
  )
}

function AdviseePreview({ row }) {
  const tone = ADVISEE_STATUS_TONE[row.status]
  const pct = row.requiredCredits ? Math.min(100, (row.credits / row.requiredCredits) * 100) : 0
  return (
    <Card as="aside" aria-label={`${row.fullName} summary`} className="gap-5">
      <div className="flex items-center gap-4">
        <Avatar name={row.fullName} initials={row.initials} tone={tone} size="lg" />
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="m-0 truncate text-xl font-bold">{row.fullName}</h2>
          <span className="text-sm text-muted">{row.program}</span>
          <span><Pill tone={tone}>{row.status}</Pill></span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Fact label="GPA" value={row.gpa} />
        <Fact label="Credits" value={credits(row)} />
        <Fact label="Graduates" value={row.graduates ?? '—'} />
      </div>
      <ProgressBar value={pct} height="h-2" label={`Credits ${credits(row)}`} />

      {row.flag && (
        <p className="m-0 flex items-start gap-2 text-sm text-slate">
          <Icon name="alert" size={18} color="var(--color-amber-ink)" className="mt-px shrink-0" />
          <span>{row.flag}</span>
        </p>
      )}
      <p className="m-0 text-sm text-slate">Next meeting: <strong className="text-navy">{row.next}</strong></p>

      <div className="flex flex-wrap gap-2">
        <Button to={`/advisor/advisees/${row.studentId}`}>Open full record</Button>
        <Button variant="secondary" to={`/advisor/messages?to=${row.userId}`}>Message</Button>
        <Button variant="secondary" to={`/advisor/meetings?book=${row.studentId}`}>Book meeting</Button>
      </div>
    </Card>
  )
}

// One message to every advisee currently shown (the active tab and search).
function MessageGroupButton({ rows, status }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const tooMany = rows.length > MAX_RECIPIENTS

  const start = () => {
    setTitle(`Advisees · ${status}`)
    setText('')
    setError(null)
    setOpen(true)
  }
  const close = () => { if (!saving) setOpen(false) }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const { id } = await api('/conversations', {
        method: 'POST',
        body: { recipientIds: rows.map((r) => r.userId), title: title.trim() || undefined, text: text.trim() },
      })
      setOpen(false)
      toast.show({ message: `Message sent to ${rows.length} advisee${rows.length === 1 ? '' : 's'}.` })
      navigate(`/advisor/messages?conversation=${id}`)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={start} disabled={rows.length === 0}>Message a group</Button>
      <Dialog open={open} onClose={close} title={`Message ${rows.length} advisee${rows.length === 1 ? '' : 's'}`}>
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <p className="m-0 text-sm text-muted">{rows.map((r) => r.name).join(', ')}</p>
          {tooMany && <Notice tone="amber">A group message can go to {MAX_RECIPIENTS} people at most. Narrow the list first.</Notice>}
          {rows.length > 1 && (
            <Field id="group-title" label="Group name">
              <TextInput id="group-title" maxLength={80} value={title} onChange={(event) => setTitle(event.target.value)} />
            </Field>
          )}
          <Field id="group-text" label="Message">
            <Textarea id="group-text" rows={4} maxLength={4000} value={text} onChange={(event) => setText(event.target.value)} />
          </Field>
          {error && <Notice tone="pink" role="alert">{error}</Notice>}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={close} disabled={saving}>Cancel</Button>
            <Button type="submit" disabled={saving || tooMany || !text.trim()}>{saving ? 'Sending…' : 'Send'}</Button>
          </div>
        </form>
      </Dialog>
    </>
  )
}
