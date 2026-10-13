import { useState } from 'react'
import PageHeader from '../../components/layout/PageHeader.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Pill, { Chip } from '../../components/ui/Pill.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Dialog from '../../components/ui/Dialog.jsx'
import Switch from '../../components/ui/Switch.jsx'
import { Field, Select, Textarea } from '../../components/ui/Field.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { COURSE_STATUS_TONE, courseStatusLabel } from '../../lib/status.js'

const TERM_TAG_TONE = { Done: 'gray', Current: 'teal', Planned: 'indigo' }
const TERM_BORDER = { Done: 'border-2 border-transparent', Current: 'border-2 border-accent', Planned: 'border-2 border-dashed border-line-strong' }
const SENDABLE = ['Needs approval', 'Recommended']

function StatTile({ stat }) {
  return (
    <div className="box-border flex min-w-0 flex-[1_1_200px] flex-col gap-2.5 rounded-[var(--radius-tile)] bg-surface p-5">
      <span className="text-sm font-semibold text-muted">{stat.label}</span>
      <span className="font-display text-[28px] font-bold tracking-[-0.02em]">{stat.value}</span>
      <ProgressBar value={stat.pct ?? 0} color={stat.warn ? 'var(--color-amber)' : undefined} label={stat.label} />
      <span className="text-[13px] text-muted">{stat.note}</span>
    </div>
  )
}

function CourseRow({ code, name, meta, status, action }) {
  return (
    <div className="flex items-center gap-3 border-t border-canvas py-2.5">
      <Chip tone="gray">{code}</Chip>
      <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="text-sm font-semibold">{name}</span>
        {meta && <span className="text-xs text-muted">{meta}</span>}
      </div>
      <Pill tone={COURSE_STATUS_TONE[status] ?? 'gray'}>{status}</Pill>
      {action}
    </div>
  )
}

function RequirementGroups({ groups }) {
  const [onlyRemaining, setOnlyRemaining] = useState(false)
  const visible = groups
    .filter((group) => !onlyRemaining || !group.allDone)
    .map((group) => ({ ...group, shown: onlyRemaining ? group.items.filter((item) => item.status !== 'Completed') : group.items }))

  return (
    <Card className="gap-5">
      <CardHeader title="Requirements" action={(
        <label className="flex cursor-pointer items-center gap-2.5 text-[13px] font-semibold">
          Only show remaining
          <Switch checked={onlyRemaining} onChange={setOnlyRemaining} />
        </label>
      )} />
      {visible.map((group) => {
        const done = Math.min(group.items.filter((item) => item.status === 'Completed').length, group.required)
        const inProgress = group.items.filter((item) => item.status === 'In progress').length
        const pct = (n) => (group.required ? (n / group.required) * 100 : 100)
        return (
          <section key={group.title} aria-label={group.title} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="m-0 text-[15px] font-bold">{group.title}</h3>
              <span className="text-[13px] text-muted">{group.count}</span>
            </div>
            <ProgressBar value={pct(done)} secondary={pct(inProgress)} height="h-2.5" label={`${group.title}: ${group.count}`} />
            <div className="mt-1 flex flex-col">
              {group.shown.map((item) => (
                <CourseRow key={item.enrollmentId} code={item.code} name={item.name} meta={item.term} status={item.status} />
              ))}
              {group.shown.length === 0 && <Empty>No courses here yet — add one to your plan.</Empty>}
            </div>
          </section>
        )
      })}
      {visible.length === 0 && <Empty>Every requirement is complete.</Empty>}
    </Card>
  )
}

function TermCard({ term, termId, removing, sending, error, onRemove, onAdd, onSend }) {
  const sendable = term.courses.some((course) => SENDABLE.includes(course.planStatus))
  return (
    <div className={`box-border flex w-[280px] shrink-0 flex-col gap-3 rounded-[var(--radius-tile)] bg-surface p-5 ${TERM_BORDER[term.tag]}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-[3px]">
          <span className="text-[15px] font-bold">{term.name}</span>
          <span className="text-xs text-muted">{term.credits}</span>
        </div>
        <Pill tone={TERM_TAG_TONE[term.tag]}>{term.tag}</Pill>
      </div>
      <div className="flex flex-col">
        {term.courses.map((course) => {
          const canRemove = course.status === 'planned' && course.planStatus !== 'Pending approval'
          return (
            <CourseRow key={course.enrollmentId} code={course.code} name={course.name} status={courseStatusLabel(course)}
              action={canRemove && (
                <button type="button" aria-label={`Remove ${course.code} from plan`} disabled={removing === course.enrollmentId}
                  onClick={() => onRemove(course)}
                  className="-mr-1.5 flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-muted hover:bg-surface-sunk disabled:opacity-40">
                  <Icon name="x" size={16} />
                </button>
              )} />
          )
        })}
      </div>
      {error && <Notice tone="pink">{error}</Notice>}
      {termId && (
        <div className="mt-auto flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => onAdd(termId)}><Icon name="plus" size={16} />Add course</Button>
          {sendable && (
            <Button size="sm" disabled={sending} onClick={() => onSend(termId, term.name)}>
              {sending ? 'Sending…' : 'Send for approval'}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

function PrecheckResult({ result, onDismiss }) {
  const { precheck, term } = result
  return (
    <Card className="gap-3.5" role="status">
      <CardHeader title={`${term} plan sent`} subtitle="Sent to your advisor. They'll see this pre-check with your plan."
        action={(
          <button type="button" aria-label="Dismiss" onClick={onDismiss}
            className="flex size-9 cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-muted hover:bg-surface-sunk">
            <Icon name="x" size={18} />
          </button>
        )} />
      {precheck ? (
        <>
          <Notice tone={precheck.ok ? 'teal' : 'amber'}>{precheck.text}</Notice>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {precheck.checks.map((check) => {
              const color = check.ok ? 'var(--color-teal-ink)' : check.blocking ? 'var(--color-pink-ink)' : 'var(--color-amber-ink)'
              return (
                <li key={check.text} className="flex items-start gap-2.5 text-sm">
                  <Icon name={check.ok ? 'check' : 'alert'} size={18} color={color} strokeWidth={2.4} className="mt-px shrink-0" />
                  <span>{check.text}</span>
                  <span className="sr-only">{check.ok ? '(passed)' : check.blocking ? '(failed)' : '(warning)'}</span>
                </li>
              )
            })}
          </ul>
        </>
      ) : (
        <Notice tone="teal">Sent to your advisor for approval.</Notice>
      )}
    </Card>
  )
}

function AddCourseDialog({ open, onClose, available, futureTerms, initialTermId, onAdded }) {
  const [courseCode, setCourseCode] = useState('')
  const [termId, setTermId] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  // Reset the form each time the dialog opens.
  const [openedFor, setOpenedFor] = useState(null)
  if (open && openedFor !== initialTermId) {
    setOpenedFor(initialTermId)
    setCourseCode(available[0]?.code ?? '')
    setTermId(String(initialTermId ?? futureTerms[0]?.id ?? ''))
    setNote('')
    setError(null)
  }
  if (!open && openedFor !== null) setOpenedFor(null)

  const types = [...new Set(available.map((course) => course.type))]
  const close = () => { if (!saving) onClose() }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const added = await api('/students/me/plan', { method: 'POST', body: { courseCode, termId: Number(termId), note: note.trim() || undefined } })
      onAdded(added)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={close} title="Add a course to your plan">
      {available.length === 0 ? (
        <Empty>Every catalog course is already on your record or plan.</Empty>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <Field id="add-course" label="Course">
            <Select id="add-course" value={courseCode} onChange={(event) => setCourseCode(event.target.value)}>
              {types.map((type) => (
                <optgroup key={type} label={type}>
                  {available.filter((course) => course.type === type).map((course) => (
                    <option key={course.code} value={course.code}>
                      {course.code} · {course.name}{course.offered ? '' : ' (not offered next term)'}
                    </option>
                  ))}
                </optgroup>
              ))}
            </Select>
          </Field>
          <Field id="add-term" label="Term">
            <Select id="add-term" value={termId} onChange={(event) => setTermId(event.target.value)}>
              {futureTerms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}
            </Select>
          </Field>
          <Field id="add-note" label="Note for your advisor (optional)">
            <Textarea id="add-note" rows={3} maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
          </Field>
          {error && <Notice tone="pink">{error}</Notice>}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={close} disabled={saving}>Cancel</Button>
            <Button type="submit" disabled={saving || !courseCode || !termId}>{saving ? 'Adding…' : 'Add to plan'}</Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}

export default function StudentDegreePlan() {
  const { user, refreshBadges } = useAuth()
  const toast = useToast()
  const audit = useApi('/students/me/degree-audit')
  const plan = useApi('/students/me/plan')
  const [adding, setAdding] = useState(null) // null = closed, otherwise { termId }
  const [removing, setRemoving] = useState(null)
  const [sending, setSending] = useState(null)
  const [termErrors, setTermErrors] = useState({})
  const [result, setResult] = useState(null)

  const refresh = () => { audit.reload(); plan.reload() }

  const error = audit.error ?? plan.error
  if (error) {
    return (
      <>
        <PageHeader title="Degree plan" />
        <ErrorState message={error.message} onRetry={refresh} />
      </>
    )
  }
  if (!audit.data || !plan.data) return <Loading label="Loading your degree plan…" />

  const { stats, groups, graduation } = audit.data
  const { terms, available, futureTerms } = plan.data
  const termIdOf = (name) => futureTerms.find((term) => term.name === name)?.id

  const remove = async (course) => {
    setRemoving(course.enrollmentId)
    try {
      await api(`/students/me/plan/${course.enrollmentId}`, { method: 'DELETE' })
      toast.show({ message: `Removed ${course.code} from your plan` })
      refresh()
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setRemoving(null)
    }
  }

  const send = async (termId, termName) => {
    setSending(termId)
    setTermErrors((current) => ({ ...current, [termId]: null }))
    try {
      const response = await api('/students/me/plan/submit', { method: 'POST', body: { termId } })
      setResult({ term: termName, precheck: response.precheck })
      refresh()
      refreshBadges()
    } catch (err) {
      setTermErrors((current) => ({ ...current, [termId]: errorText(err) }))
    } finally {
      setSending(null)
    }
  }

  const added = (course) => {
    setAdding(null)
    toast.show({ message: `Added ${course.code} to ${course.term}` })
    refresh()
  }

  return (
    <>
      <PageHeader title="Degree plan" subtitle={`Expected graduation · ${graduation.label}`} initials={user?.initials}
        actions={futureTerms.length > 0 && (
          <Button onClick={() => setAdding({ termId: futureTerms[0].id })}><Icon name="plus" size={18} />Add course</Button>
        )} />

      <section aria-label="Degree progress" className="flex flex-wrap gap-4">
        {stats.map((stat) => <StatTile key={stat.label} stat={stat} />)}
      </section>

      {result && <PrecheckResult result={result} onDismiss={() => setResult(null)} />}

      <section aria-label="Term plan" className="flex flex-col gap-3">
        <h2 className="m-0 text-lg font-bold">Term by term</h2>
        <div className="flex gap-4 overflow-x-auto pb-2">
          {terms.map((term) => {
            const termId = term.tag === 'Planned' ? termIdOf(term.name) : undefined
            return (
              <TermCard key={term.name} term={term} termId={termId} removing={removing}
                sending={sending === termId} error={termId && termErrors[termId]}
                onRemove={remove} onAdd={(id) => setAdding({ termId: id })} onSend={send} />
            )
          })}
          {terms.length === 0 && <Empty>No courses on your record yet.</Empty>}
        </div>
      </section>

      <RequirementGroups groups={groups} />

      <AddCourseDialog open={adding != null} onClose={() => setAdding(null)} available={available} futureTerms={futureTerms}
        initialTermId={adding?.termId ?? null} onAdded={added} />
    </>
  )
}
