import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import BookForStudentDialog from '../../components/meetings/BookForStudentDialog.jsx'
import OptionPills from '../../components/meetings/OptionPills.jsx'
import SlotGrid from '../../components/meetings/SlotGrid.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import ConfirmInline from '../../components/ui/ConfirmInline.jsx'
import { Field, Textarea, TextInput } from '../../components/ui/Field.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { addDays } from '../../lib/dates.js'
import { useApi } from '../../lib/useApi.js'
import { FORMAT_TONE, MEETING_STATUS_LABEL, MEETING_STATUS_TONE } from '../../lib/status.js'

const RANGES = [{ value: 'today', label: 'Today' }, { value: 'week', label: 'Next 7 days' }]
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
const PRESETS = ['12:00–13:00', '14:00–15:00', '16:30–17:30', '18:00–19:00']
const CUSTOM = 'Custom'
const BOOKING_DAYS = 13

// Advisor meetings (spec 24): agenda with office hours, booking requests, office hours editor and meeting details.
export default function AdvisorMeetings() {
  const { user: me } = useAuth()
  const [params, setParams] = useSearchParams()
  const [range, setRange] = useState('today')
  const [selectedId, setSelectedId] = useState(null)
  const bookId = Number(params.get('book')) || null
  const [booking, setBooking] = useState(bookId ? { studentId: bookId } : null)
  const { data, error, reload } = useApi(`/advisor/meetings?range=${range}`)

  const openBooking = (studentId = null) => setBooking({ studentId })
  const closeBooking = () => {
    setBooking(null)
    if (params.has('book')) {
      setParams((current) => { const next = new URLSearchParams(current); next.delete('book'); return next }, { replace: true })
    }
  }

  if (error && !data) {
    return (
      <>
        <PageHeader title="Meetings" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading meetings…" />

  const meetings = data.agenda.filter((row) => row.kind === 'meeting')
  const selected = meetings.find((row) => row.id === selectedId) ?? meetings[0] ?? null

  return (
    <>
      <PageHeader title="Meetings" subtitle="Your agenda, booking requests and office hours" initials={me?.initials}
        actions={(
          <>
            <Button variant="secondary" href="#office-hours">Office hours</Button>
            <Button onClick={() => openBooking()}>Book with an advisee</Button>
          </>
        )} />

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col gap-4">
          <Agenda rows={data.agenda} range={range} onRange={setRange} selectedId={selected?.id} onSelect={setSelectedId} />
          <BookingRequests requests={data.requests} today={data.today} onChanged={reload} />
          <OfficeHours value={data.officeHours} onSaved={reload} />
        </div>
        <aside aria-label="Meeting details" className="min-w-0 lg:sticky lg:top-4">
          {selected ? <MeetingDetail key={selected.id} meeting={selected} onChanged={reload} />
            : <Card><Empty>Select a meeting to see its details.</Empty></Card>}
        </aside>
      </div>

      {booking && (
        <BookForStudentDialog key={booking.studentId ?? 'new'} open studentId={booking.studentId} today={data.today}
          onClose={closeBooking} onBooked={() => { closeBooking(); reload() }} />
      )}
    </>
  )
}

function Agenda({ rows, range, onRange, selectedId, onSelect }) {
  return (
    <Card as="section" aria-label="Meetings" className="gap-4">
      <CardHeader title="Agenda" action={<SegmentedTabs label="Range" options={RANGES} value={range} onChange={onRange} />} />
      {rows.length === 0 ? <Empty>Nothing scheduled.</Empty> : (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {rows.map((row) => (
            <li key={row.id}>
              {row.kind === 'meeting' ? (
                <button type="button" aria-pressed={row.id === selectedId} onClick={() => onSelect(row.id)}
                  className={`flex w-full cursor-pointer items-center gap-4 rounded-xl border-0 px-3.5 py-3 text-left text-navy ${
                    row.id === selectedId ? 'bg-teal-soft' : 'bg-transparent hover:bg-surface-sunk'}`}>
                  <AgendaRow row={row} />
                </button>
              ) : (
                <div className="flex items-center gap-4 rounded-xl border border-dashed border-line px-3.5 py-3">
                  <AgendaRow row={row} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function AgendaRow({ row }) {
  return (
    <>
      <span className="flex w-20 shrink-0 flex-col">
        <span className="text-xs font-semibold text-muted">{row.day}</span>
        <span className="font-display text-lg font-bold">{row.time}</span>
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="truncate text-sm font-bold">{row.who}</span>
        <span className="truncate text-[13px] text-muted">{row.topic}</span>
      </span>
      <span className="flex shrink-0 flex-wrap justify-end gap-1.5">
        {row.kind === 'meeting' && row.status !== 'confirmed' && (
          <Pill tone={MEETING_STATUS_TONE[row.status]}>{MEETING_STATUS_LABEL[row.status]}</Pill>
        )}
        <Pill tone={row.kind === 'meeting' ? FORMAT_TONE[row.format] : 'teal'}>{row.kind === 'meeting' ? row.format : 'Drop-in'}</Pill>
      </span>
    </>
  )
}

function BookingRequests({ requests, today, onChanged }) {
  const toast = useToast()
  // Answered requests leave the list on reload; keep them here so their result pill stays visible.
  const [done, setDone] = useState({}) // id → { row, result: 'accepted' | 'proposed' }
  const [suggesting, setSuggesting] = useState(null)
  const [busy, setBusy] = useState(null)
  const rows = [...requests, ...Object.values(done).map((d) => d.row).filter((row) => !requests.some((r) => r.id === row.id))]

  const act = async (request, action, body) => {
    setBusy(request.id)
    try {
      await api(`/meetings/${request.id}/${action}`, { method: 'POST', body })
      setDone((current) => ({ ...current, [request.id]: { row: request, result: action === 'accept' ? 'accepted' : 'proposed' } }))
      setSuggesting(null)
      onChanged()
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card as="section" aria-label="Booking requests" className="gap-3">
      <CardHeader title="Booking requests" />
      {rows.length === 0 ? <Empty>No requests waiting.</Empty> : (
        <ul className="m-0 flex list-none flex-col p-0">
          {rows.map((request) => (
            <li key={request.id} className="flex flex-col gap-3 border-t border-canvas py-3 first:border-t-0">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-[2px]">
                  <span className="text-sm font-bold">{request.who} · {request.when}</span>
                  <span className="text-[13px] text-muted">{request.topic}</span>
                </div>
                {done[request.id] ? (
                  <Pill tone={done[request.id].result === 'accepted' ? 'teal' : 'amber'}>
                    {done[request.id].result === 'accepted' ? 'Accepted · added to agenda' : 'New time suggested'}
                  </Pill>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => act(request, 'accept')} disabled={busy === request.id}>Accept</Button>
                    <Button size="sm" variant="secondary" aria-expanded={suggesting === request.id}
                      onClick={() => setSuggesting(suggesting === request.id ? null : request.id)}>
                      Suggest another time
                    </Button>
                  </div>
                )}
              </div>
              {suggesting === request.id && !done[request.id] && (
                <SuggestTime request={request} today={today} busy={busy === request.id}
                  onSend={(startsAt) => act(request, 'propose', { startsAt })} />
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function SuggestTime({ request, today, busy, onSend }) {
  const [day, setDay] = useState(addDays(today, 1))
  const [startsAt, setStartsAt] = useState(null)
  const { data, error } = useApi(day ? `/advisor/meetings/free-slots?date=${day}&studentId=${request.studentId}&meetingId=${request.id}` : null)
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-surface-sunk p-3">
      <Field id={`suggest-day-${request.id}`} label="Day">
        <TextInput id={`suggest-day-${request.id}`} type="date" min={today} max={addDays(today, BOOKING_DAYS)} value={day}
          onChange={(event) => { setDay(event.target.value); setStartsAt(null) }} />
      </Field>
      {error ? <Notice tone="pink">{error.message}</Notice>
        : !data ? <Loading label="Loading your open times…" />
          : data.slots.length === 0 ? <Empty>No open times that day.</Empty>
            : <SlotGrid slots={data.slots} value={startsAt} onChange={setStartsAt} />}
      <div><Button size="sm" onClick={() => onSend(startsAt)} disabled={!startsAt || busy}>{busy ? 'Sending…' : 'Send'}</Button></div>
    </div>
  )
}

function OfficeHours({ value, onSaved }) {
  const preset = value.start ? `${value.start}–${value.end}` : PRESETS[2]
  const [days, setDays] = useState(value.days)
  const [time, setTime] = useState(PRESETS.includes(preset) ? preset : CUSTOM)
  const [start, setStart] = useState(value.start ?? '16:30')
  const [end, setEnd] = useState(value.end ?? '17:30')
  const [location, setLocation] = useState(value.location ?? '')
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState(null)
  const [errors, setErrors] = useState({})

  const publish = async (event) => {
    event.preventDefault()
    const [from, to] = time === CUSTOM ? [start, end] : time.split('–')
    setSaving(true)
    setStatus(null)
    setErrors({})
    try {
      await api('/advisor/office-hours', { method: 'PUT', body: { days, start: from, end: to, location: location.trim() || null } })
      setStatus({ tone: 'teal', text: 'Published. Students see these times on Book a meeting.' })
      onSaved()
    } catch (err) {
      const fields = Object.fromEntries((err.details ?? []).map((d) => [d.field, d.message]))
      setErrors(fields)
      setStatus({ tone: 'pink', text: errorText(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card as="section" id="office-hours" aria-labelledby="office-hours-title" className="scroll-mt-4 gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="office-hours-title" className="m-0 text-lg font-bold">Office hours</h2>
        <span className="text-[13px] text-muted">{value.summary}</span>
      </div>
      <form className="flex flex-col gap-4" onSubmit={publish}>
        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-bold">Days</span>
          <OptionPills multiple label="Office hour days" options={WEEKDAYS} value={days} onChange={setDays} />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-bold">Time</span>
          <OptionPills label="Office hour time" options={[...PRESETS, CUSTOM]} value={time} onChange={setTime} />
          {time === CUSTOM && (
            <div className="grid grid-cols-2 gap-3">
              <Field id="office-start" label="Start" error={errors.start}>
                <TextInput id="office-start" type="time" value={start} onChange={(event) => setStart(event.target.value)} />
              </Field>
              <Field id="office-end" label="End" error={errors.end}>
                <TextInput id="office-end" type="time" value={end} onChange={(event) => setEnd(event.target.value)} />
              </Field>
            </div>
          )}
        </div>
        <Field id="office-location" label="Location" error={errors.location}>
          <TextInput id="office-location" maxLength={120} value={location} onChange={(event) => setLocation(event.target.value)} />
        </Field>
        {status && <Notice tone={status.tone} role="status">{status.text}</Notice>}
        <div><Button type="submit" disabled={saving}>{saving ? 'Publishing…' : 'Publish office hours'}</Button></div>
      </form>
    </Card>
  )
}

function MeetingDetail({ meeting, onChanged }) {
  const toast = useToast()
  const [notes, setNotes] = useState(meeting.notes ?? '')
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(null)

  const saveNotes = async () => {
    setBusy('notes')
    try {
      await api(`/advisor/meetings/${meeting.id}`, { method: 'PATCH', body: { notes } })
      setStatus('Notes saved.')
      onChanged()
    } catch (err) {
      setStatus(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const act = async (action) => {
    setBusy(action)
    try {
      await api(`/meetings/${meeting.id}/${action}`, { method: 'POST' })
      onChanged()
      return true
    } catch (err) {
      toast.show({ message: errorText(err) })
      return false
    } finally {
      setBusy(null)
    }
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(meeting.videoUrl)
      setStatus(`Video link copied: ${meeting.videoUrl}`)
    } catch {
      setStatus(`Video link: ${meeting.videoUrl}`)
    }
  }

  return (
    <Card as="section" aria-labelledby="meeting-title" className="gap-4">
      <div className="flex flex-col gap-1">
        <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">Selected meeting</span>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 id="meeting-title" className="m-0 text-xl font-bold">{meeting.who}</h2>
          <Pill tone={MEETING_STATUS_TONE[meeting.status]}>{MEETING_STATUS_LABEL[meeting.status]}</Pill>
        </div>
        <span className="text-sm text-muted">{meeting.day} · {meeting.time} · {meeting.format}</span>
        <span className="text-sm font-semibold">{meeting.topic}</span>
        {meeting.proposedTime && <span className="text-[13px] text-muted">New time proposed: {meeting.proposedTime}</span>}
      </div>
      {meeting.note && (
        <div className="flex flex-col gap-1 rounded-xl bg-surface-sunk px-4 py-3">
          <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">Student&apos;s note</span>
          <p className="m-0 text-sm text-slate">{meeting.note}</p>
        </div>
      )}

      <Field id="meeting-notes" label="Meeting notes (private)">
        <Textarea id="meeting-notes" rows={5} maxLength={4000} placeholder="Agenda, decisions, follow-ups…" value={notes}
          onChange={(event) => { setNotes(event.target.value); setStatus(null) }} />
      </Field>
      <div className="flex flex-wrap gap-2">
        <Button onClick={saveNotes} disabled={busy != null}>{busy === 'notes' ? 'Saving…' : 'Save notes'}</Button>
        {meeting.format === 'Online' && meeting.videoUrl
          ? <Button variant="secondary" onClick={copyLink}>Copy video link</Button>
          : <Button variant="secondary" onClick={() => setStatus(meeting.location ?? 'In person')}>Show room</Button>}
      </div>
      {status && <p role="status" className="m-0 break-words text-[13px] text-slate">{status}</p>}

      {meeting.canComplete && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => act('complete')} disabled={busy != null}>Mark completed</Button>
          <Button variant="secondary" onClick={() => act('no-show')} disabled={busy != null}>No-show</Button>
        </div>
      )}
      {meeting.canCancel && (
        <ConfirmInline label="Cancel meeting" warning={`${meeting.who} gets a message that the meeting is cancelled.`}
          confirmLabel="Yes, cancel it" busyLabel="Cancelling…" busy={busy === 'cancel'} onConfirm={() => act('cancel')} />
      )}
      <div className="flex flex-wrap gap-2 border-t border-canvas pt-3">
        <Button variant="secondary" size="sm" to={`/advisor/advisees/${meeting.studentId}`}>Open student</Button>
        <Button variant="secondary" size="sm" to={`/advisor/messages?to=${meeting.userId}`}>Message</Button>
      </div>
    </Card>
  )
}
