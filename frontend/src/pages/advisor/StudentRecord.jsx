import { useState } from 'react'
import { useParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import RequirementBars from '../../components/academics/RequirementBars.jsx'
import Breadcrumb from '../../components/ui/Breadcrumb.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Dialog from '../../components/ui/Dialog.jsx'
import { Field, Textarea, TextInput } from '../../components/ui/Field.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill, { Chip } from '../../components/ui/Pill.jsx'
import StatTile from '../../components/ui/StatTile.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { relativeDate } from '../../lib/dates.js'
import { useApi } from '../../lib/useApi.js'
import { REVIEW_STATUS_TONE } from '../../lib/status.js'

const STATUS_LABEL = { pending: 'Waiting for you', approved: 'Approved', changes_requested: 'Changes requested' }
const MAX_COMMENT = 1000 // matches schemas/advisor.Comment
const MAX_NOTE = 1000

const coursesPhrase = (n) => (n === 1 ? 'the course' : n === 2 ? 'both courses' : `all ${n} courses`)

// Advisor → student record (spec 22): summary, plan review, degree progress, meetings, private notes and shared activity.
export default function AdvisorStudentRecord() {
  const { studentId } = useParams()
  const { user: me } = useAuth()
  const { data, error, reload } = useApi(`/advisor/advisees/${studentId}`)

  if (error && !data) {
    const message = error.status === 404 ? "We couldn't find that student."
      : error.status === 403 ? "This student isn't one of your advisees." : error.message
    const known = error.status === 404 || error.status === 403
    return (
      <>
        <Breadcrumb items={[{ label: 'Advisees', to: '/advisor/advisees' }, { label: 'Student record' }]} />
        <ErrorState message={message} onRetry={known ? undefined : reload} />
        {known && <div><Button variant="secondary" to="/advisor/advisees">Back to advisees</Button></div>}
      </>
    )
  }
  if (!data) return <Loading label="Loading student record…" />

  const { student } = data
  return (
    <>
      <div className="flex flex-col gap-3">
        <Breadcrumb items={[{ label: 'Advisees', to: '/advisor/advisees' }, { label: student.name }]} />
        <PageHeader title={student.name} subtitle={student.subtitle} initials={me?.initials}
          actions={(
            <>
              <Button variant="secondary" to={`/advisor/messages?to=${student.userId}`}>Message {student.firstName}</Button>
              <Button to={`/advisor/meetings?book=${student.id}`}>Schedule follow-up</Button>
            </>
          )} />
      </div>

      <section aria-label="Summary" className="flex flex-wrap gap-4">
        {data.stats.map((stat) => (
          <StatTile key={stat.label} label={stat.label} value={stat.value} pill={{ tone: stat.tone, text: stat.tag }} note={stat.note} />
        ))}
      </section>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-4">
          <PlanReview key={data.review?.requestId ?? 'none'} review={data.review} plannedTerm={data.plannedTerm}
            firstName={student.firstName} onChanged={reload} />
          <Card as="section" aria-label="Degree progress" className="gap-5">
            <CardHeader title="Degree progress" />
            {data.groups.length ? <RequirementBars groups={data.groups} /> : <Empty>No requirements on file.</Empty>}
          </Card>
        </div>

        <aside aria-label={`${student.fullName} details`} className="flex min-w-0 flex-col gap-4">
          <MeetingsList meetings={data.meetings} />
          <PrivateNotes key={student.id} notes={data.notes} studentId={student.id} />
          <SharedActivity items={data.activity} aiShared={data.aiShared} studentId={student.id} firstName={student.firstName} />
        </aside>
      </div>
    </>
  )
}

function PlanRow({ row }) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-canvas py-2.5">
      <Chip tone="gray">{row.code}</Chip>
      <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="text-sm font-semibold">{row.name}</span>
        <span className="text-xs text-muted">{row.when}</span>
      </div>
      {row.fulfills && <Pill tone="indigo">Fulfills {row.fulfills}</Pill>}
    </div>
  )
}

function Check({ check }) {
  const ok = check.ok
  return (
    <li className="flex items-start gap-2.5 text-sm text-slate">
      <span aria-hidden="true" className={`flex size-6 shrink-0 items-center justify-center rounded-full ${ok ? 'bg-teal-soft' : 'bg-amber-soft'}`}>
        <Icon name={ok ? 'check' : 'alert'} size={14} strokeWidth={2.4} color={ok ? 'var(--color-teal-ink)' : 'var(--color-amber-ink)'} />
      </span>
      <span className="pt-0.5"><span className="sr-only">{ok ? 'Passed: ' : 'Needs attention: '}</span>{check.text}</span>
    </li>
  )
}

function PlanReview({ review, plannedTerm, firstName, onChanged }) {
  const { refreshBadges } = useAuth()
  const [comment, setComment] = useState('')
  const [hint, setHint] = useState(null)
  // The status being sent and the one it replaces; shown until the reloaded review moves off `from`.
  const [optimistic, setOptimistic] = useState(null)
  const [error, setError] = useState(null)
  const sending = optimistic && review && review.status === optimistic.from ? optimistic.status : null

  if (!review) {
    return (
      <Card as="section" aria-label="Plan review" className="gap-4">
        <CardHeader title={plannedTerm?.title ?? 'Plan review'} subtitle="No plan waiting for review." />
        {plannedTerm && <div className="flex flex-col">{plannedTerm.plan.map((row) => <PlanRow key={row.code} row={row} />)}</div>}
      </Card>
    )
  }

  const status = sending ?? review.status
  const send = async (path, next, body) => {
    setOptimistic({ status: next, from: review.status })
    setError(null)
    try {
      await api(`/advisor/approvals/${review.requestId}/${path}`, { method: 'POST', body })
      setComment('')
      refreshBadges()
      onChanged()
    } catch (err) {
      setOptimistic(null)
      setError(errorText(err))
    }
  }
  const approve = () => send('approve', 'approved', { comment: comment.trim() || null })
  const requestChanges = () => {
    if (!comment.trim()) {
      setHint(`Tell ${firstName} what to change.`)
      return
    }
    send('request-changes', 'changes_requested', { comment: comment.trim() })
  }
  const undo = () => send('reopen', 'pending')

  const opens = review.registrationOpens ? `when registration opens ${review.registrationOpens}` : 'when registration opens'

  return (
    <Card as="section" aria-labelledby="plan-review-title" className="gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id="plan-review-title" className="m-0 text-lg font-bold">{review.title}</h2>
          <span className="text-[13px] text-muted">{review.subtitle}</span>
        </div>
        <Pill tone={REVIEW_STATUS_TONE[status]}>{STATUS_LABEL[status]}</Pill>
      </div>

      <div className="flex flex-col">
        {review.plan.length ? review.plan.map((row) => <PlanRow key={row.code} row={row} />) : <Empty>No courses in this plan.</Empty>}
      </div>

      {review.checks.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="m-0 text-[15px] font-bold">Acadmate checks</h3>
          <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
            {review.checks.map((check) => <Check key={check.text} check={check} />)}
          </ul>
        </div>
      )}

      {review.studentNote && (
        <div className="flex flex-col gap-1 rounded-xl bg-surface-sunk px-4 py-3">
          <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">{firstName}&apos;s note</span>
          <p className="m-0 text-sm leading-relaxed text-slate">{review.studentNote}</p>
        </div>
      )}

      {error && <Notice tone="pink" role="alert">{error}</Notice>}

      {review.status === 'pending' ? (
        <div className="flex flex-col gap-3">
          <Field id="review-comment" label={`Comment to ${firstName} (optional)`} error={hint}>
            <Textarea id="review-comment" rows={3} maxLength={MAX_COMMENT} value={comment}
              placeholder="For example: Approved. Please send the capstone form before Oct 20."
              onChange={(event) => { setComment(event.target.value); setHint(null) }} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button onClick={approve} disabled={sending != null}>{sending === 'approved' ? 'Approving…' : 'Approve plan'}</Button>
            <Button variant="secondary" onClick={requestChanges} disabled={sending != null}>
              {sending === 'changes_requested' ? 'Sending…' : 'Request changes'}
            </Button>
          </div>
        </div>
      ) : (
        <div role="status" className={`flex flex-wrap items-start justify-between gap-3 rounded-xl px-4 py-3 ${review.status === 'approved' ? 'bg-teal-soft text-teal-ink' : 'bg-pink-soft text-pink-ink'}`}>
          <div className="flex min-w-0 flex-col gap-1 text-sm">
            <strong>{review.status === 'approved' ? 'Plan approved' : 'Changes requested'}</strong>
            <span>
              {review.status === 'approved'
                ? `${firstName} can register for ${coursesPhrase(review.plan.length)} ${opens}.`
                : `${firstName} will see your request in Acadmate and can revise the plan.`}
            </span>
            {review.comment && <span>Your comment: “{review.comment}”</span>}
          </div>
          {review.canUndo && (
            <Button variant="secondary" size="sm" onClick={undo} disabled={sending != null}>
              {sending === 'pending' ? 'Undoing…' : 'Undo'}
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}

function MeetingsList({ meetings }) {
  return (
    <Card as="section" aria-label="Meetings" className="gap-3">
      <CardHeader title="Meetings" />
      {meetings.length === 0 ? <Empty>No meetings yet.</Empty> : (
        <ul className="m-0 flex list-none flex-col p-0">
          {meetings.map((meeting) => (
            <li key={meeting.id} className="flex flex-col gap-[2px] border-t border-canvas py-2.5 first:border-t-0">
              <span className={`text-sm font-semibold ${meeting.past ? 'text-muted' : ''}`}>{meeting.title}</span>
              <span className="text-xs text-muted">{meeting.past ? `Past · ${meeting.meta}` : meeting.meta}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function PrivateNotes({ notes: initial, studentId }) {
  const toast = useToast()
  const [notes, setNotes] = useState(initial)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const add = async (event) => {
    event.preventDefault()
    if (!text.trim()) return
    setSaving(true)
    setError(null)
    try {
      const note = await api(`/advisor/advisees/${studentId}/notes`, { method: 'POST', body: { text: text.trim() } })
      setNotes((current) => [note, ...current])
      setText('')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (note) => {
    setNotes((current) => current.filter((n) => n.id !== note.id))
    try {
      await api(`/advisor/notes/${note.id}`, { method: 'DELETE' })
    } catch (err) {
      setNotes((current) => [note, ...current.filter((n) => n.id !== note.id)].sort((a, b) => b.id - a.id))
      toast.show({ message: errorText(err) })
    }
  }

  return (
    <Card as="section" aria-label="Private notes" className="gap-3">
      <CardHeader title="Private notes" subtitle="Only advisors can see these." />
      {notes.length === 0 ? <Empty>No notes yet.</Empty> : (
        <ul className="m-0 flex list-none flex-col p-0">
          {notes.map((note) => (
            <li key={note.id} className="flex items-start gap-2 border-t border-canvas py-2.5 first:border-t-0">
              <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
                <span className="whitespace-pre-line break-words text-sm text-slate">{note.text}</span>
                <span className="text-xs text-muted">{note.when}</span>
              </div>
              {note.mine && (
                <button type="button" aria-label="Delete note" onClick={() => remove(note)}
                  className="hit-44 flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent hover:bg-surface-sunk">
                  <Icon name="x" size={16} color="var(--color-muted)" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <form className="flex gap-2" onSubmit={add}>
        <label htmlFor="new-note" className="sr-only">Add a private note</label>
        <TextInput id="new-note" placeholder="Add a note…" maxLength={MAX_NOTE} value={text}
          onChange={(event) => setText(event.target.value)} />
        <Button type="submit" variant="secondary" disabled={saving || !text.trim()}>{saving ? 'Adding…' : 'Add'}</Button>
      </form>
      {error && <Notice tone="pink" role="alert">{error}</Notice>}
    </Card>
  )
}

function SharedActivity({ items, aiShared, studentId, firstName }) {
  const [open, setOpen] = useState(false)
  const subtitle = `Only what ${firstName} chose to share. ${aiShared ? 'Their AI chats are shared with you.' : 'Their AI chats stay private.'}`
  return (
    <Card as="section" aria-label="Shared activity" className="gap-3">
      <CardHeader title="Shared activity" subtitle={subtitle} />
      {items.length === 0 ? <Empty>Nothing shared yet.</Empty> : (
        <ul className="m-0 flex list-none flex-col p-0">
          {items.map((item, index) => (
            <li key={`${item.when}-${index}`} className="flex gap-3 border-t border-canvas py-2.5 text-sm first:border-t-0">
              <span className="w-12 shrink-0 text-xs font-semibold text-muted">{item.when}</span>
              <span className="min-w-0 text-slate">{item.text}</span>
            </li>
          ))}
        </ul>
      )}
      {aiShared && (
        <div><Button variant="secondary" size="sm" onClick={() => setOpen(true)}>View AI conversations</Button></div>
      )}
      {aiShared && <AiThreadsDialog open={open} onClose={() => setOpen(false)} studentId={studentId} firstName={firstName} />}
    </Card>
  )
}

function AiThreadsDialog({ open, onClose, studentId, firstName }) {
  const { data, error, reload } = useApi(open ? `/advisor/advisees/${studentId}/ai-threads` : null)
  return (
    <Dialog open={open} onClose={onClose} title={`${firstName}'s AI conversations`}>
      {error ? <ErrorState message={error.message} onRetry={reload} />
        : !data ? <Loading label="Loading conversations…" />
          : data.threads.length === 0 ? <Empty>No AI conversations yet.</Empty> : (
            <ul className="m-0 flex list-none flex-col p-0">
              {data.threads.map((thread) => (
                <li key={thread.id} className="flex items-baseline justify-between gap-3 border-t border-canvas py-2.5 first:border-t-0">
                  <span className="min-w-0 text-sm font-semibold">{thread.title}</span>
                  <span className="shrink-0 text-xs text-muted">{relativeDate(thread.updatedAt)}</span>
                </li>
              ))}
            </ul>
          )}
    </Dialog>
  )
}
