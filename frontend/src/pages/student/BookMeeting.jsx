import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import OptionPills from '../../components/meetings/OptionPills.jsx'
import SlotGrid from '../../components/meetings/SlotGrid.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Avatar from '../../components/ui/Avatar.jsx'
import Pill from '../../components/ui/Pill.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import { Field, Textarea, TextInput } from '../../components/ui/Field.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { addDays, clockTime, shortDay } from '../../lib/dates.js'

const OTHER = 'Something else'
const STATUS = { requested: ['amber', 'Requested'], confirmed: ['teal', 'Confirmed'], proposed: ['indigo', 'New time proposed'] }
const ZONE_NAMES = { 'America/New_York': 'Eastern Time', 'America/Chicago': 'Central Time', 'America/Denver': 'Mountain Time',
  'America/Los_Angeles': 'Pacific Time' }

function Step({ n, title, action, children }) {
  return (
    <Card as="section" className="gap-4" aria-label={title}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-navy text-[13px] font-bold text-white" aria-hidden="true">{n}</span>
        <h2 className="m-0 text-lg font-bold">{title}</h2>
        {action && <div className="ml-auto">{action}</div>}
      </div>
      {children}
    </Card>
  )
}

function PersonPicker({ staff, value, onChange }) {
  return (
    <div role="group" aria-label="Choose who to meet" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {staff.map((s) => {
        const active = s.id === value
        return (
          <button key={s.id} type="button" aria-pressed={active} onClick={() => onChange(s.id)}
            className={`flex cursor-pointer flex-col items-start gap-1.5 rounded-2xl border-2 p-4 text-left text-navy ${
              active ? 'border-accent bg-teal-soft/40' : 'border-transparent bg-surface-sunk hover:bg-line-soft'}`}>
            <div className="flex w-full items-start justify-between gap-2">
              <Avatar name={s.name} initials={s.initials} />
              {s.isMyAdvisor && <Pill tone="teal">Your advisor</Pill>}
            </div>
            <span className="text-[15px] font-bold">{s.name}</span>
            <span className="text-[13px] text-muted">{s.role}</span>
            {s.helps && <span className="text-xs text-muted">{s.helps}</span>}
          </button>
        )
      })}
    </div>
  )
}

function DayStrip({ days, value, onChange }) {
  return (
    <div role="group" aria-label="Choose a day" className="grid grid-cols-5 gap-2">
      {days.map((d) => {
        const active = d.date === value
        const full = d.open === 0
        return (
          <button key={d.date} type="button" aria-pressed={active} disabled={full} onClick={() => onChange(d.date)}
            aria-label={`${shortDay(d.date, { weekday: true })}, ${d.free}`}
            className={`flex flex-col items-center gap-0.5 rounded-2xl border py-2.5 ${
              active ? 'cursor-pointer border-navy bg-navy text-white'
                : full ? 'cursor-not-allowed border-line bg-surface-sunk text-muted'
                  : 'cursor-pointer border-line bg-surface text-navy hover:bg-surface-sunk'}`}>
            <span className="text-xs font-bold uppercase">{d.dow}</span>
            <span className="font-display text-lg font-bold">{d.day}</span>
            <span className={`text-[11px] font-semibold ${active ? 'text-fog' : 'text-muted'}`}>{d.free}</span>
          </button>
        )
      })}
    </div>
  )
}

function SummaryRow({ label, children, pending = false }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted">{label}</span>
      <span className={`text-[15px] font-bold ${pending ? 'text-amber-deep' : ''}`}>{children}</span>
    </div>
  )
}

function UpcomingMeetings({ meetings, onChanged, onReschedule }) {
  const toast = useToast()
  const [busyId, setBusyId] = useState(null)
  const [confirmId, setConfirmId] = useState(null) // meeting whose Cancel was clicked once
  const { data, error, reload } = meetings

  // Reschedule = cancel, then pick a new time with the same person in the form.
  const act = async (meeting, action) => {
    setBusyId(meeting.id)
    try {
      await api(`/meetings/${meeting.id}/${action === 'reschedule' ? 'cancel' : action}`, { method: 'POST' })
      toast.show({ message: { cancel: 'Meeting cancelled', accept: 'New time accepted', reschedule: 'Meeting cancelled. Pick a new time.' }[action] })
      setConfirmId(null)
      onChanged(meeting)
      if (action === 'reschedule') onReschedule(meeting.staffId)
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Card as="section" className="gap-1" aria-label="Upcoming meetings">
      <CardHeader title="Upcoming meetings" />
      {error ? (
        <div className="mt-2 flex flex-col gap-2">
          <Notice tone="pink">{error.message}</Notice>
          <div><Button variant="secondary" size="sm" onClick={reload}>Try again</Button></div>
        </div>
      ) : !data ? (
        <Empty>Loading…</Empty>
      ) : data.meetings.length === 0 ? (
        <Empty>No upcoming meetings.</Empty>
      ) : (
        <div className="mt-2 flex flex-col">
          {data.meetings.map((m) => {
            const [tone, label] = STATUS[m.status] ?? ['gray', m.status]
            const busy = busyId === m.id
            return (
              <div key={m.id} className="flex flex-col gap-2 border-t border-canvas py-3">
                <div className="flex items-start gap-3">
                  <div className="flex w-11 shrink-0 flex-col items-center rounded-xl bg-surface-sunk py-1.5">
                    <span className="text-[11px] font-bold uppercase text-muted">{m.mon}</span>
                    <span className="font-display text-lg font-bold leading-tight">{m.day}</span>
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate text-sm font-semibold">{m.title}</span>
                    <span className="text-xs text-muted">{m.meta}</span>
                    {m.status === 'proposed' && m.proposedStartsAt && (
                      <span className="text-xs font-semibold text-indigo-ink">
                        Suggested: {new Date(m.proposedStartsAt).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })} at {clockTime(m.proposedStartsAt)}
                      </span>
                    )}
                  </div>
                  <Pill tone={tone}>{label}</Pill>
                </div>
                <div className="flex flex-wrap justify-end gap-2">
                  {confirmId === m.id ? (
                    <>
                      <Button variant="secondary" size="sm" disabled={busy} onClick={() => setConfirmId(null)}>Keep it</Button>
                      <Button variant="danger" size="sm" disabled={busy} onClick={() => act(m, 'cancel')}>Confirm cancel</Button>
                    </>
                  ) : (
                    <>
                      {m.status === 'proposed' && (
                        <Button size="sm" disabled={busy} onClick={() => act(m, 'accept')}><Icon name="check" size={16} />Accept new time</Button>
                      )}
                      <Button variant="secondary" size="sm" disabled={busy} onClick={() => act(m, 'reschedule')}>Reschedule</Button>
                      <Button variant="danger" size="sm" disabled={busy} onClick={() => setConfirmId(m.id)}>Cancel</Button>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function BookedConfirmation({ booked, onAnother }) {
  const confirmed = booked.status === 'confirmed'
  return (
    <Card as="section" className="gap-4" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-teal-soft">
          <Icon name="check" size={22} color="var(--color-teal-ink)" strokeWidth={2.4} />
        </span>
        <div className="flex flex-col gap-1">
          <h2 className="m-0 text-lg font-bold">{confirmed ? 'Meeting booked' : 'Request sent'}</h2>
          {!confirmed && <div><Pill tone="amber">Waiting for confirmation</Pill></div>}
        </div>
      </div>
      <p className="m-0 text-sm leading-relaxed">{booked.summary}</p>
      {!confirmed && (
        <p className="m-0 text-sm text-muted">We posted a copy to your Messages. You'll get another message there when it's confirmed.</p>
      )}
      <div className="flex flex-wrap gap-2">
        {confirmed
          ? <Button to="/student/schedule"><Icon name="calendar" size={18} />View in schedule</Button>
          : <Button to="/student/messages"><Icon name="chat" size={18} />Open Messages</Button>}
        <Button variant="secondary" onClick={onAnother}>Book another</Button>
      </div>
    </Card>
  )
}

// ?with={staffId}&topic=… from links elsewhere (Messages' "Schedule meeting"); unknown values are ignored.
function initialChoice(params, staff, topics) {
  const withId = Number(params.get('with'))
  const topic = params.get('topic')
  return {
    personId: staff.some((s) => s.id === withId) ? withId : staff[0].id,
    topic: topics.includes(topic) ? topic : topics[0],
  }
}

function BookingForm({ data }) {
  const { refreshBadges } = useAuth()
  const { staff, topics, formats, firstWeek } = data // firstWeek comes from the server's date, not the browser's
  const [params] = useSearchParams()
  const [initial] = useState(() => initialChoice(params, staff, topics))

  const [personId, setPersonId] = useState(initial.personId)
  const [topic, setTopic] = useState(initial.topic)
  const [otherTopic, setOtherTopic] = useState('')
  const [format, setFormat] = useState(formats[0])
  const [week, setWeek] = useState(firstWeek)
  const [day, setDay] = useState(null)
  const [slot, setSlot] = useState(null)
  const [note, setNote] = useState('')
  const [attachPlan, setAttachPlan] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [booked, setBooked] = useState(null)

  const person = staff.find((s) => s.id === personId)
  const availability = useApi(`/staff/${personId}/availability?week=${week}`)
  const meetings = useApi('/students/me/meetings')

  // Ignore a response left over from the previous person/week while the new one loads.
  const avail = availability.data?.staffId === personId && availability.data.week === week ? availability.data : null
  const selectedDay = avail && (avail.days.find((d) => d.date === day && d.open > 0) ?? avail.days.find((d) => d.open > 0))
  const pickedSlot = selectedDay?.slots.find((s) => s.startsAt === slot && !s.taken) ?? null
  const lastWeek = addDays(firstWeek, 7 * ((person.bookingWindowWeeks ?? 2) - 1)) // the window includes firstWeek
  const topicText = topic === OTHER ? otherTopic.trim() : topic

  const pickPerson = (id) => { setPersonId(id); setWeek(firstWeek); setDay(null); setSlot(null); setSubmitError(null) }
  const pickWeek = (next) => { setWeek(next); setDay(null); setSlot(null) }
  const pickDay = (date) => { setDay(date); setSlot(null) }

  const submit = async () => {
    if (!pickedSlot) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const result = await api('/meetings', {
        method: 'POST',
        body: { staffId: personId, startsAt: pickedSlot.startsAt, format, topic: topicText || OTHER, note: note.trim() || undefined, attachPlan },
      })
      setBooked(result)
      setSlot(null)
      refreshBadges()
      meetings.reload()
      availability.reload()
    } catch (err) {
      setSubmitError(errorText(err))
      if (err.status === 409) { setSlot(null); availability.reload() }
    } finally {
      setSubmitting(false)
    }
  }

  const another = () => { setBooked(null); setNote(''); setOtherTopic(''); setSubmitError(null) }

  const meetingChanged = (meeting) => {
    meetings.reload()
    refreshBadges()
    if (meeting.staffId === personId) availability.reload()
  }

  const canConfirm = pickedSlot && !submitting && (topic !== OTHER || otherTopic.trim())

  return (
    <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
      <div className="flex min-w-0 flex-col gap-4">
        {booked ? <BookedConfirmation booked={booked} onAnother={another} /> : (
          <>
            <Step n={1} title="Who do you want to meet?">
              <PersonPicker staff={staff} value={personId} onChange={pickPerson} />
            </Step>

            <Step n={2} title="What's it about?">
              <OptionPills options={topics} value={topic} onChange={setTopic} label="Meeting topic" />
              {topic === OTHER && (
                <Field id="bk-topic" label="Topic">
                  <TextInput id="bk-topic" maxLength={80} value={otherTopic} onChange={(e) => setOtherTopic(e.target.value)}
                    placeholder="What would you like to talk about?" />
                </Field>
              )}
              <Field id="bk-note" label="Anything they should know beforehand? (optional)">
                <Textarea id="bk-note" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="For example: I'd like to compare two capstone ideas." />
              </Field>
              <label htmlFor="bk-attach" className="flex cursor-pointer items-center gap-2.5 text-sm font-semibold">
                <input id="bk-attach" type="checkbox" className="size-5 cursor-pointer accent-accent" checked={attachPlan}
                  onChange={(e) => setAttachPlan(e.target.checked)} />
                Attach my Acadmate plan
              </label>
            </Step>

            <Step n={3} title="Pick a time" action={<OptionPills options={formats} value={format} onChange={setFormat} label="Meeting format" />}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold">{shortDay(week)} – {shortDay(addDays(week, 4))}</span>
                <div className="flex items-center gap-1.5">
                  <Button variant="secondary" size="sm" aria-label="Previous week" disabled={week <= firstWeek}
                    onClick={() => pickWeek(addDays(week, -7))}><Icon name="chevronLeft" size={16} /></Button>
                  <Button variant="secondary" size="sm" aria-label="Next week" disabled={week >= lastWeek}
                    onClick={() => pickWeek(addDays(week, 7))}><Icon name="chevronRight" size={16} /></Button>
                </div>
              </div>

              {availability.error ? (
                <div className="flex flex-col gap-2">
                  <Notice tone="pink">{availability.error.message}</Notice>
                  <div><Button variant="secondary" size="sm" onClick={availability.reload}>Try again</Button></div>
                </div>
              ) : !avail ? (
                <Loading label="Loading open times…" />
              ) : (
                <div className={`flex flex-col gap-4 transition-opacity ${availability.loading ? 'opacity-60' : ''}`} aria-busy={availability.loading}>
                  <DayStrip days={avail.days} value={selectedDay?.date} onChange={pickDay} />
                  {selectedDay
                    ? <SlotGrid slots={selectedDay.slots} value={pickedSlot?.startsAt} onChange={setSlot} />
                    : <Empty>No open times this week. Try the next week.</Empty>}
                </div>
              )}
              <span className="text-xs text-muted">
                Times shown in {ZONE_NAMES[avail?.timeZone] ?? "the school's local time"}. Greyed-out times are taken or clash with your classes.
                {person.meetingLength ? ` Meetings are ${person.meetingLength} minutes.` : ''}
              </span>
            </Step>
          </>
        )}
      </div>

      <aside className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-6">
        {!booked && (
          <Card as="section" className="gap-4" aria-label="Booking summary">
            <h2 className="m-0 text-lg font-bold">Your booking</h2>
            <SummaryRow label="With">{person.name} · {person.role}</SummaryRow>
            <SummaryRow label="When" pending={!pickedSlot}>
              {pickedSlot ? `${shortDay(selectedDay.date, { weekday: true })} at ${pickedSlot.time}` : 'Pick a time'}
            </SummaryRow>
            <SummaryRow label="Format">{format === 'In person' && person.office ? `${format} · ${person.office}` : format}</SummaryRow>
            <SummaryRow label="Topic" pending={!topicText}>
              {topicText || 'Describe your topic'}{attachPlan ? ' · plan attached' : ''}
            </SummaryRow>
            {submitError && <Notice tone="pink" role="alert">{submitError}</Notice>}
            <Button size="lg" variant={canConfirm ? 'primary' : 'disabled'} disabled={!canConfirm} onClick={submit}
              className={canConfirm ? '' : 'cursor-not-allowed'}>
              {submitting ? 'Booking…' : 'Confirm booking'}
            </Button>
            <span className="text-xs text-muted">You'll get a confirmation in Messages.</span>
          </Card>
        )}
        <UpcomingMeetings meetings={meetings} onChanged={meetingChanged}
          onReschedule={(staffId) => { setBooked(null); if (staff.some((s) => s.id === staffId)) pickPerson(staffId) }} />
      </aside>
    </div>
  )
}

export default function StudentBookMeeting() {
  const { user } = useAuth()
  const { data, error, reload } = useApi('/staff?bookable=true')

  const header = (
    <PageHeader title="Book a meeting" subtitle="Meet your advisor or student services, in person or online" initials={user?.initials}
      actions={<Button variant="secondary" to="/student/messages">Message advisor instead</Button>} />
  )

  if (error) return <>{header}<ErrorState message={error.message} onRetry={reload} /></>
  if (!data) return <Loading label="Loading advisors…" />

  return (
    <>
      {header}
      {data.staff.length === 0
        ? <Card><Empty>No one is taking bookings right now. Try messaging your advisor instead.</Empty></Card>
        : <BookingForm data={data} />}
    </>
  )
}
