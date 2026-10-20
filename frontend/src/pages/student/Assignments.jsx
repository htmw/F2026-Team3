import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty, ListRow } from '../../components/layout/MasterDetail.jsx'
import Card from '../../components/ui/Card.jsx'
import Pill, { Chip } from '../../components/ui/Pill.jsx'
import StatTile from '../../components/ui/StatTile.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Dialog from '../../components/ui/Dialog.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Field, TextInput, Textarea } from '../../components/ui/Field.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { ASSIGNMENT_STATUS_TONE, DEADLINE_TONE } from '../../lib/status.js'

// Advising forms have no field schema in the database; these match what advisors review.
const FORM_FIELDS = [
  { key: 'Proposed topic', multiline: false },
  { key: 'Project summary', multiline: true },
]

const isClosed = (row) => row.status === 'Submitted' || row.status === 'Graded'
const NOT_GRADED = '—'


function Score({ score }) {
  if (score === NOT_GRADED) return <span className="text-muted" aria-label="Not graded yet">—</span>
  return <span className="font-bold">{score}</span>
}

const ROW_GRID = 'grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 @xl:grid-cols-[minmax(0,1fr)_88px_56px_96px_44px]'

function AssignmentList({ rows, selectedId, onSelect }) {
  return (
    <Card className="@container gap-1">
      <div aria-hidden="true" className={`${ROW_GRID} hidden px-3.5 pb-1 text-xs font-bold uppercase tracking-[0.06em] text-muted @xl:grid`}>
        <span>Assignment</span><span>Course</span><span>Due</span><span>Status</span><span className="text-right">Score</span>
      </div>
      {rows.map((row) => {
        const flag = !isClosed(row) && (row.deadline === 'Overdue' || row.deadline === 'Due soon')
        return (
          <ListRow key={row.id} selected={row.id === selectedId} onSelect={() => onSelect(row.id)}>
            <div className={ROW_GRID}>
              <div className="flex min-w-0 flex-col gap-[3px]">
                <span className="truncate text-sm font-semibold">{row.title}</span>
                <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                  <span className="@xl:hidden">Due {row.due} · {row.course}</span>
                  {flag && <Pill tone={DEADLINE_TONE[row.deadline]} className="px-2 py-0.5 text-[11px]">{row.deadline}</Pill>}
                </span>
              </div>
              <span className="hidden @xl:block"><Chip tone="indigo">{row.course}</Chip></span>
              <span className="hidden text-[13px] @xl:block">{row.due}</span>
              <span className="justify-self-end @xl:justify-self-start"><Pill tone={ASSIGNMENT_STATUS_TONE[row.status] ?? 'gray'}>{row.status}</Pill></span>
              <span className="hidden text-right text-sm @xl:block"><Score score={row.score} /></span>
            </div>
          </ListRow>
        )
      })}
    </Card>
  )
}

function FormDialog({ row, open, onClose, onSubmitted }) {
  const [fields, setFields] = useState(() => Object.fromEntries(FORM_FIELDS.map((f) => [f.key, ''])))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const complete = FORM_FIELDS.every((f) => fields[f.key].trim())
  const close = () => { if (!saving) onClose() }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const body = { fields: Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.trim()])) }
      onSubmitted(await api(`/assignments/${row.id}/submit`, { method: 'POST', body }))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={close} title={row.title}>
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <p className="m-0 text-sm leading-relaxed text-muted">Your advisor reviews this form before it's approved.</p>
        {FORM_FIELDS.map((f, i) => {
          const id = `form-field-${i}`
          const set = (event) => setFields((current) => ({ ...current, [f.key]: event.target.value }))
          return (
            <Field key={f.key} id={id} label={f.key}>
              {f.multiline
                ? <Textarea id={id} rows={4} maxLength={4000} value={fields[f.key]} onChange={set} />
                : <TextInput id={id} maxLength={200} value={fields[f.key]} onChange={set} />}
            </Field>
          )
        })}
        {error && <Notice tone="pink">{error}</Notice>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={close} disabled={saving}>Cancel</Button>
          <Button type="submit" disabled={saving || !complete}>{saving ? 'Sending…' : 'Send to advisor'}</Button>
        </div>
      </form>
    </Dialog>
  )
}

function Fact({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="m-0 text-sm font-bold">{children}</dd>
    </div>
  )
}

function AssignmentDetail({ row, busy, notice, onToggleStep, onStart, onSubmit, onAsk }) {
  const closed = isClosed(row)
  const doneCount = row.steps.filter((step) => step.done).length
  return (
    <Card className="gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone="indigo">{row.course}</Chip>
          <Pill tone={ASSIGNMENT_STATUS_TONE[row.status] ?? 'gray'}>{row.status}</Pill>
        </div>
        <h2 className="m-0 text-lg font-bold">{row.title}</h2>
        <dl className="m-0 grid grid-cols-3 gap-3">
          <Fact label="Due">{row.due}</Fact>
          <Fact label="Weight">{row.weight}</Fact>
          <Fact label="Type">{row.type}</Fact>
        </dl>
        <div className="flex flex-wrap items-center gap-3 text-[13px] text-muted">
          {!closed && row.deadline !== 'In progress' && row.deadline !== 'Not started' && (
            <Pill tone={DEADLINE_TONE[row.deadline]}>{row.deadline}</Pill>
          )}
          <span>Score {row.score === NOT_GRADED ? 'not graded yet' : <strong className="text-navy">{row.score}</strong>}</span>
        </div>
      </div>

      {row.desc && <p className="m-0 whitespace-pre-line text-sm leading-relaxed">{row.desc}</p>}

      {row.steps.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-canvas pt-4">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="m-0 flex items-center gap-2 text-[15px] font-bold">
              <Icon name="sparkle" size={16} color="var(--color-accent)" />Acadmate step plan
            </h3>
            <span className="text-[13px] text-muted">{doneCount} of {row.steps.length} done</span>
          </div>
          {row.steps.map((step, i) => {
            const id = `step-${row.id}-${i}`
            return (
              <label key={id} htmlFor={id}
                className={`flex min-h-11 items-center gap-3 rounded-xl px-3 ${closed || busy ? 'cursor-default' : 'cursor-pointer hover:bg-surface-sunk'}`}>
                <input id={id} type="checkbox" checked={step.done} disabled={closed || busy} onChange={() => onToggleStep(i)}
                  className="size-[18px] shrink-0 cursor-pointer accent-[var(--color-accent)] disabled:cursor-default" />
                <span className={`text-sm ${step.done ? 'text-muted line-through' : ''}`}>{step.text}</span>
              </label>
            )
          })}
        </div>
      )}

      {notice && <Notice tone={notice.tone} role={notice.tone === 'pink' ? 'alert' : 'status'}>{notice.text}</Notice>}

      <div className="flex flex-wrap gap-2 border-t border-canvas pt-4">
        {row.status === 'To do' && row.steps.length === 0 && (
          <Button variant="secondary" size="sm" onClick={onStart} disabled={busy}>Start</Button>
        )}
        <Button size="sm" onClick={onSubmit} disabled={closed || busy}>
          {closed ? 'Submitted' : row.type === 'Form' ? 'Fill in form' : busy ? 'Saving…' : 'Mark as submitted'}
        </Button>
        {row.submissionUrl && (
          <Button href={row.submissionUrl} target="_blank" rel="noreferrer" variant="secondary" size="sm">
            Open submission page<Icon name="external" size={14} />
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={onAsk}><Icon name="sparkle" size={14} />Ask Acadmate</Button>
      </div>
    </Card>
  )
}

export default function StudentAssignments() {
  const { user, refreshBadges } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const { data, error, reload, setData } = useApi('/students/me/assignments')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('All')
  const [course, setCourse] = useState('All')
  const [selectedId, setSelectedId] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [notice, setNotice] = useState(null) // { id, tone, text }, shown in that assignment's detail pane
  const [formOpen, setFormOpen] = useState(false)

  if (error) {
    return (
      <>
        <PageHeader title="Assignments" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading your assignments…" />

  const query = search.trim().toLowerCase()
  const visible = data.rows.filter((row) => (status === 'All' || row.status === status) && (course === 'All' || row.course === course)
    && (!query || `${row.title} ${row.course}`.toLowerCase().includes(query)))
  const selected = visible.find((row) => row.id === selectedId) ?? visible[0]

  const updateRow = (id, change) => setData((current) => current && {
    ...current, rows: current.rows.map((row) => (row.id === id ? change(row) : row)),
  })

  const saveProgress = async (row, body, optimistic) => {
    setBusyId(row.id)
    setNotice(null)
    updateRow(row.id, optimistic)
    try {
      const saved = await api(`/assignments/${row.id}/progress`, { method: 'PATCH', body })
      updateRow(row.id, (current) => ({
        ...current,
        status: saved.status,
        steps: current.steps.map((step, i) => ({ ...step, done: saved.stepsDone.includes(i) })),
      }))
      if (saved.status !== row.status) reload() // tab counts and stats move with the status
    } catch (err) {
      updateRow(row.id, () => row)
      setNotice({ id: row.id, tone: 'pink', text: errorText(err) })
    } finally {
      setBusyId(null)
    }
  }

  const toggleStep = (row, index) => {
    const steps = row.steps.map((step, i) => (i === index ? { ...step, done: !step.done } : step))
    const stepsDone = steps.flatMap((step, i) => (step.done ? [i] : []))
    saveProgress(row, { stepsDone }, (current) => ({
      ...current, steps, status: current.status === 'To do' && stepsDone.length ? 'In progress' : current.status,
    }))
  }

  const start = (row) => saveProgress(row, { status: 'In progress' }, (current) => ({ ...current, status: 'In progress' }))

  const afterSubmit = (row) => {
    reload()
    refreshBadges()
    toast.show({ message: `Submitted ${row.title}.` })
  }

  const submit = async (row) => {
    if (row.type === 'Form') {
      setNotice(null)
      setFormOpen(true)
      return
    }
    setBusyId(row.id)
    setNotice(null)
    try {
      await api(`/assignments/${row.id}/submit`, { method: 'POST' })
      afterSubmit(row)
    } catch (err) {
      setNotice({ id: row.id, tone: 'pink', text: errorText(err) })
    } finally {
      setBusyId(null)
    }
  }

  const formSubmitted = (row, result) => {
    setFormOpen(false)
    if (result.precheck) setNotice({ id: row.id, tone: result.precheck.ok ? 'teal' : 'amber', text: `Sent to your advisor. ${result.precheck.text}` })
    afterSubmit(row)
  }

  const clearFilters = () => { setStatus('All'); setCourse('All'); setSearch('') }

  return (
    <>
      <PageHeader title="Assignments" initials={user?.initials} subtitle={data.subtitle}
        search={{ label: 'Search assignments', placeholder: 'Search assignments…', value: search, onChange: setSearch }}
        actions={<Button to="/student/schedule" variant="secondary">Plan my week</Button>} />

      <section aria-label="Assignment summary" className="flex flex-wrap gap-4">
        {data.stats.map((stat) => <StatTile key={stat.label} label={stat.label} value={stat.value} note={stat.note} />)}
      </section>

      <div className="flex flex-col gap-2.5">
        <SegmentedTabs label="Filter by status" value={status} onChange={setStatus}
          options={data.tabs.map((tab) => ({ value: tab.label, label: tab.label, count: tab.count }))} />
        {data.courses.length > 1 && (
          <SegmentedTabs label="Filter by course" value={course} onChange={setCourse}
            options={[{ value: 'All', label: 'All courses' }, ...data.courses]} />
        )}
      </div>

      {data.rows.length === 0 ? (
        <Card><Empty>No assignments this term.</Empty></Card>
      ) : (
        <MasterDetail wideList
          list={visible.length === 0 ? (
            <Card className="items-start gap-2">
              <Empty>No assignments match these filters.</Empty>
              <Button variant="secondary" size="sm" onClick={clearFilters}>Clear filters</Button>
            </Card>
          ) : (
            <AssignmentList rows={visible} selectedId={selected?.id} onSelect={(id) => { setSelectedId(id); setNotice(null) }} />
          )}
          detail={selected ? (
            <AssignmentDetail row={selected} busy={busyId === selected.id}
              notice={notice?.id === selected.id ? notice : null}
              onToggleStep={(i) => toggleStep(selected, i)} onStart={() => start(selected)} onSubmit={() => submit(selected)}
              onAsk={() => navigate('/student/ai-advisor', { state: { question: `Help me plan ${selected.title}` } })} />
          ) : <Card><DetailEmpty /></Card>} />
      )}

      {selected?.type === 'Form' && (
        <FormDialog key={selected.id} row={selected} open={formOpen} onClose={() => setFormOpen(false)}
          onSubmitted={(result) => formSubmitted(selected, result)} />
      )}
    </>
  )
}
