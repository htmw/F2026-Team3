import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import { DetailEmpty } from '../../components/layout/MasterDetail.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Pill, { Chip } from '../../components/ui/Pill.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Dialog from '../../components/ui/Dialog.jsx'
import { Field, INPUT, Select, Textarea, TextInput } from '../../components/ui/Field.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, apiUrl, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { addDays, mondayOf, shortDay } from '../../lib/dates.js'
import { EVENT_COLOR, EVENT_TYPES } from '../../lib/status.js'

const ROW = 56 // px per hour in the week grid
const PERSONAL_TYPES = ['Study', 'Office hours', 'Advising', 'Team'] // types a student can add (classes come from enrollments)
const MEETING_TONE = { requested: 'amber', confirmed: 'teal', proposed: 'indigo' }
const DEADLINE_TONE = { 'To do': 'indigo', 'In progress': 'teal' }
const FIELDS = ['title', 'type', 'date', 'start', 'end', 'location', 'note']

const minutes = (time) => { const [h, m] = time.split(':').map(Number); return h * 60 + m }
const colorOf = (type) => EVENT_COLOR[type] ?? 'var(--color-accent)'

// Side-by-side lanes for overlapping events in one day column: each item gets a lane index and
// the lane count of the cluster of events it overlaps with.
function layoutDay(items) {
  const sorted = [...items].sort((a, b) => minutes(a.start) - minutes(b.start) || minutes(b.end) - minutes(a.end))
  const placed = []
  let cluster = []
  let lanes = [] // end minute of the last item in each lane
  let clusterEnd = -1
  const flush = () => { for (const p of cluster) p.lanes = lanes.length; cluster = []; lanes = [] }
  for (const item of sorted) {
    const start = minutes(item.start)
    const end = minutes(item.end)
    if (start >= clusterEnd) { flush(); clusterEnd = -1 }
    let lane = lanes.findIndex((laneEnd) => laneEnd <= start)
    if (lane === -1) { lane = lanes.length; lanes.push(end) } else lanes[lane] = end
    const p = { item, lane }
    cluster.push(p)
    placed.push(p)
    clusterEnd = Math.max(clusterEnd, end)
  }
  flush()
  return placed
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Event types">
      {EVENT_TYPES.map((type) => (
        <span key={type} className="flex items-center gap-1.5 text-[13px] text-muted">
          <span className="size-2.5 rounded-full" style={{ background: colorOf(type) }} />{type}
        </span>
      ))}
    </div>
  )
}

function EventBlock({ item, day, lane, lanes, gridStart, selected, onSelect }) {
  const top = (minutes(item.start) / 60 - gridStart) * ROW
  const height = Math.max(((minutes(item.end) - minutes(item.start)) / 60) * ROW, 24)
  const width = 100 / lanes
  const requested = item.status === 'requested'
  return (
    <button type="button" aria-pressed={selected} onClick={() => onSelect(item.id)}
      aria-label={`${item.title}, ${day.name} ${item.start}–${item.end}${requested ? ', waiting for confirmation' : ''}`}
      className={`absolute box-border flex cursor-pointer flex-col overflow-hidden rounded-lg px-2 py-1 text-left text-navy ${
        requested ? 'border border-dashed border-amber' : 'border-0'} ${
        selected ? 'z-10 bg-surface ring-2 ring-accent/40' : 'bg-surface-sunk hover:bg-line-soft'}`}
      style={{ top, height, left: `calc(${lane * width}% + 2px)`, width: `calc(${width}% - 4px)`, boxShadow: `inset 3px 0 0 ${colorOf(item.type)}` }}>
      <span className="truncate text-xs font-bold">{item.title}</span>
      {height >= 40 && <span className="truncate text-[11px] text-muted">{item.start}–{item.end}</span>}
      {height >= 64 && item.location && <span className="truncate text-[11px] text-muted">{item.location}</span>}
    </button>
  )
}

function WeekGrid({ data, selectedId, onSelect, loading }) {
  // Mon–Fri always; the weekend only when something is on it.
  const days = data.days.filter((day, i) => i < 5 || day.events.length > 0)
  const items = days.flatMap((day) => day.events)
  const gridStart = Math.min(8, ...items.map((item) => Math.floor(minutes(item.start) / 60)))
  const gridEnd = Math.max(18, ...items.map((item) => Math.ceil(minutes(item.end) / 60)))
  const hours = Array.from({ length: gridEnd - gridStart }, (_, i) => gridStart + i)
  const height = hours.length * ROW
  const lines = { backgroundImage: `repeating-linear-gradient(to bottom, var(--color-line-soft) 0 1px, transparent 1px ${ROW}px)` }

  return (
    <Card className="gap-4">
      <Legend />
      <div className={`overflow-x-auto transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
        <div className="grid min-w-[640px]" style={{ gridTemplateColumns: `44px repeat(${days.length}, minmax(0, 1fr))` }}>
          <div />
          {days.map((day) => {
            const today = day.date === data.today
            return (
              <div key={day.date} className="flex min-w-0 flex-col items-center gap-1 px-1 pb-3">
                <span className={`text-xs font-bold uppercase ${today ? 'text-accent' : 'text-muted'}`}>{day.name}</span>
                <span aria-current={today ? 'date' : undefined}
                  className={`flex size-8 items-center justify-center rounded-full font-display text-[15px] font-bold ${today ? 'bg-accent text-white' : ''}`}>
                  {day.day}
                </span>
                {day.due.map((due) => (
                  <span key={due} title={due} className="w-full truncate rounded-md bg-amber-soft px-1.5 py-0.5 text-center text-[11px] font-semibold text-amber-ink">
                    {due}
                  </span>
                ))}
              </div>
            )
          })}

          <div className="relative" style={{ height }} aria-hidden="true">
            {hours.map((hour, i) => (
              <span key={hour} className="absolute right-2 -translate-y-1/2 text-[11px] text-muted" style={{ top: i * ROW }}>
                {i === 0 ? '' : `${String(hour).padStart(2, '0')}:00`}
              </span>
            ))}
          </div>
          {days.map((day) => (
            <div key={day.date} className={`relative border-l border-line-soft ${day.date === data.today ? 'bg-teal-soft/30' : ''}`}
              style={{ height, ...lines }}>
              {layoutDay(day.events).map(({ item, lane, lanes }) => (
                <EventBlock key={item.id} item={item} day={day} lane={lane} lanes={lanes} gridStart={gridStart}
                  selected={item.id === selectedId} onSelect={onSelect} />
              ))}
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function DetailLine({ icon, children }) {
  return (
    <span className="flex items-start gap-2 text-sm">
      <Icon name={icon} size={16} color="var(--color-muted)" className="mt-0.5 shrink-0" />
      <span className="min-w-0">{children}</span>
    </span>
  )
}

function EventDetail({ item, onEdit, onDelete, onRemind, deleting }) {
  if (!item) return <Card><DetailEmpty>Select an event to see details.</DetailEmpty></Card>
  return (
    <Card className="gap-3">
      <div className="flex items-center gap-2">
        <span className="size-2.5 rounded-full" style={{ background: colorOf(item.type) }} />
        <span className="text-[13px] font-bold text-muted">{item.type}</span>
        {item.status && <Pill tone={MEETING_TONE[item.status] ?? 'gray'} className="ml-auto capitalize">{item.status}</Pill>}
      </div>
      <h2 className="m-0 text-lg font-bold">{item.title}</h2>
      <DetailLine icon="clock">{shortDay(item.date, { weekday: true })} · {item.start}–{item.end}</DetailLine>
      {item.location && <DetailLine icon="pin">{item.location}</DetailLine>}
      {item.note && <p className="m-0 text-sm leading-relaxed text-muted">{item.note}</p>}
      {item.reminderMinutes != null && <DetailLine icon="bell">Reminder · {item.reminderMinutes} min before</DetailLine>}

      {item.editable && (
        <div className="flex flex-wrap gap-2 pt-1">
          <Button variant="secondary" size="sm" onClick={() => onEdit(item)}><Icon name="edit" size={16} />Edit</Button>
          {item.reminderMinutes == null && (
            <Button variant="secondary" size="sm" onClick={() => onRemind(item)}><Icon name="bell" size={16} />Set reminder</Button>
          )}
          <Button variant="danger" size="sm" onClick={() => onDelete(item)} disabled={deleting}>
            <Icon name="trash" size={16} />{deleting ? 'Deleting…' : 'Delete'}
          </Button>
        </div>
      )}
      {item.kind === 'class' && <Link to="/student/courses" className="text-[13px] font-semibold">Open in My courses</Link>}
    </Card>
  )
}

// Acadmate's study-block suggestion; after the block is saved it shows what was added (`added`).
function StudySuggestion({ suggestion, added, onAdd }) {
  return (
    <Card dark className="gap-3">
      <div className="flex items-center gap-2.5">
        <div className="flex size-9 items-center justify-center rounded-[10px] bg-teal">
          <Icon name="sparkle" color="var(--color-navy)" strokeWidth={2.2} />
        </div>
        <h2 className="m-0 text-base font-bold text-white">Acadmate suggestion</h2>
      </div>
      <p className="m-0 text-sm leading-relaxed text-frost">{added ?? suggestion.text}</p>
      <div>
        {added
          ? <Button size="sm" disabled className="bg-navy-raised! text-teal-bright!"><Icon name="check" size={16} />Added to your week</Button>
          : <Button variant="sun" size="sm" onClick={onAdd}><Icon name="plus" size={16} />Add study block</Button>}
      </div>
    </Card>
  )
}

function UpcomingDeadlines({ deadlines }) {
  return (
    <Card className="gap-1">
      <CardHeader title="Coming deadlines" action={<Link to="/student/assignments" className="text-[13px] font-semibold">View all</Link>} />
      <div className="mt-2 flex flex-col">
        {deadlines.slice(0, 5).map((d) => (
          <div key={d.id} className="flex items-center gap-3 border-t border-canvas py-3">
            <Chip tone="gray">{d.course}</Chip>
            <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
              <span className="truncate text-sm font-semibold">{d.title}</span>
              <span className="text-xs text-muted">Due {d.label}</span>
            </div>
            <Pill tone={DEADLINE_TONE[d.status] ?? 'gray'}>{d.status}</Pill>
          </div>
        ))}
        {deadlines.length === 0 && <Empty>Nothing due in the next two weeks.</Empty>}
      </div>
    </Card>
  )
}

function CalendarFeed() {
  const toast = useToast()
  const [url, setUrl] = useState(null)
  const [busy, setBusy] = useState(false)

  const copy = async () => {
    setBusy(true)
    try {
      const feed = url ?? (await api('/students/me/calendar')).url
      setUrl(feed)
      try {
        await navigator.clipboard.writeText(feed)
        toast.show({ message: 'Feed link copied' })
      } catch {
        toast.show({ message: "Couldn't copy automatically — copy the link below." })
      }
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="gap-3">
      <CardHeader title="Calendar apps" subtitle="Subscribe to your schedule in Google Calendar or Outlook." />
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={copy} disabled={busy}><Icon name="external" size={16} />Copy feed link</Button>
        <Button variant="secondary" size="sm" href={apiUrl('/students/me/calendar.ics')} download><Icon name="download" size={16} />Download .ics</Button>
      </div>
      {url && <input readOnly value={url} aria-label="Calendar feed link" onFocus={(event) => event.target.select()} className={`${INPUT} h-10 text-[13px]`} />}
      <Link to="/student/settings#set-privacy" className="text-[13px] font-semibold">Reset the link in Settings</Link>
    </Card>
  )
}

const EMPTY_FORM = { title: '', type: 'Study', date: '', start: '14:00', end: '15:00', location: '', note: '' }
const formOf = (item) => ({ title: item.title, type: item.type, date: item.date, start: item.start, end: item.end, location: item.location ?? '', note: item.note ?? '' })
const bodyOf = (form) => ({ ...form, title: form.title.trim(), location: form.location.trim() || null, note: form.note.trim() || null })

// Add (editing = { mode: 'add', initial }) or edit (editing = { mode: 'edit', item }) a personal event.
function EventDialog({ editing, onClose, onSaved }) {
  const open = editing != null
  const [form, setForm] = useState(EMPTY_FORM)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [saving, setSaving] = useState(false)

  // Reset the form each time the dialog opens.
  const [openedFor, setOpenedFor] = useState(null)
  if (open && openedFor !== editing) {
    setOpenedFor(editing)
    setForm({ ...EMPTY_FORM, ...(editing.mode === 'edit' ? formOf(editing.item) : editing.initial) })
    setErrors({})
    setFormError(null)
  }
  if (!open && openedFor !== null) setOpenedFor(null)

  const isEdit = editing?.mode === 'edit'
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))
  const close = () => { if (!saving) onClose() }

  const submit = async (event) => {
    event.preventDefault()
    setErrors({})
    setFormError(null)
    if (form.end <= form.start) {
      setErrors({ end: 'The end time must be after the start time.' })
      return
    }
    let body = bodyOf(form)
    if (isEdit) {
      const original = bodyOf(formOf(editing.item))
      body = Object.fromEntries(Object.entries(body).filter(([key, value]) => value !== original[key]))
      if (Object.keys(body).length === 0) { onClose(); return }
    }
    setSaving(true)
    try {
      const saved = isEdit
        ? await api(`/students/me/events/${editing.item.id}`, { method: 'PATCH', body })
        : await api('/students/me/events', { method: 'POST', body })
      onSaved(saved, isEdit)
    } catch (err) {
      const fieldErrors = {}
      for (const detail of Array.isArray(err.details) ? err.details : []) {
        if (FIELDS.includes(detail.path)) fieldErrors[detail.path] = detail.message
      }
      setErrors(fieldErrors)
      if (Object.keys(fieldErrors).length === 0) setFormError(errorText(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={close} title={isEdit ? 'Edit event' : 'Add an event'}>
      <form className="flex flex-col gap-4" onSubmit={submit} noValidate>
        <Field id="event-title" label="Title" error={errors.title}>
          <TextInput id="event-title" required maxLength={200} value={form.title} onChange={set('title')} placeholder="e.g. Library study session" />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="event-type" label="Type" error={errors.type}>
            <Select id="event-type" value={form.type} onChange={set('type')}>
              {PERSONAL_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </Select>
          </Field>
          <Field id="event-date" label="Date" error={errors.date}>
            <TextInput id="event-date" type="date" required value={form.date} onChange={set('date')} />
          </Field>
          <Field id="event-start" label="Starts" error={errors.start}>
            <TextInput id="event-start" type="time" required value={form.start} onChange={set('start')} />
          </Field>
          <Field id="event-end" label="Ends" error={errors.end}>
            <TextInput id="event-end" type="time" required value={form.end} onChange={set('end')} />
          </Field>
        </div>
        <Field id="event-location" label="Location (optional)" error={errors.location}>
          <TextInput id="event-location" maxLength={200} value={form.location} onChange={set('location')} placeholder="e.g. Library, 3rd floor" />
        </Field>
        <Field id="event-note" label="Note (optional)" error={errors.note}>
          <Textarea id="event-note" rows={3} maxLength={1000} value={form.note} onChange={set('note')} />
        </Field>
        {formError && <Notice tone="pink">{formError}</Notice>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={close} disabled={saving}>Cancel</Button>
          <Button type="submit" disabled={saving || !form.title.trim() || !form.date}>
            {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Add event'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

export default function StudentSchedule() {
  const { user } = useAuth()
  const toast = useToast()
  const [weekFrom, setWeekFrom] = useState(null) // null = this week, as the school's time zone sees it
  const path = weekFrom ? `/students/me/events?from=${weekFrom}&to=${addDays(weekFrom, 6)}` : '/students/me/events'
  const { data, error, loading, reload } = useApi(path)
  const [selectedId, setSelectedId] = useState(null)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [added, setAdded] = useState(null) // { week, text } after adding the suggested study block
  // Toast actions can fire after the week changed; always reload whatever week is showing then.
  const reloadRef = useRef(reload)
  reloadRef.current = reload

  if (error) {
    return (
      <>
        <PageHeader title="Schedule" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading your schedule…" />

  const items = data.days.flatMap((day) => day.events)
  const selected = items.find((item) => item.id === selectedId) ?? items.find((item) => item.date === data.today) ?? items[0] ?? null
  const shownFrom = weekFrom ?? data.from
  const go = (weeks) => setWeekFrom(addDays(shownFrom, weeks * 7))

  const showWeekOf = (date) => {
    const monday = mondayOf(date)
    if (monday === shownFrom) reloadRef.current()
    else setWeekFrom(monday)
  }

  const saved = (event, isEdit) => {
    if (editing?.fromSuggestion) {
      setAdded({ week: mondayOf(event.date), text: `Added a study block on ${shortDay(event.date, { weekday: true })} ${event.start}–${event.end}. It's on your week now.` })
    }
    setEditing(null)
    setSelectedId(event.id)
    toast.show({ message: isEdit ? 'Event updated' : `Added "${event.title}"` })
    showWeekOf(event.date)
  }

  const remind = async (item) => {
    try {
      await api(`/students/me/events/${item.id}`, { method: 'PATCH', body: { reminderMinutes: 30 } })
      toast.show({ message: 'Reminder set for 30 minutes before' })
      reloadRef.current()
    } catch (err) {
      toast.show({ message: errorText(err) })
    }
  }

  const remove = async (item) => {
    setDeleting(true)
    try {
      await api(`/students/me/events/${item.id}`, { method: 'DELETE' })
      reloadRef.current()
      const { title, type, date, start, end, location, note } = item
      toast.show({
        message: `Deleted "${title}"`,
        actionLabel: 'Undo',
        onAction: async () => {
          try {
            const restored = await api('/students/me/events', { method: 'POST', body: { title, type, date, start, end, location, note } })
            setSelectedId(restored.id)
            reloadRef.current()
          } catch (err) {
            toast.show({ message: errorText(err) })
          }
        },
      })
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setDeleting(false)
    }
  }

  const defaultDate = data.today >= data.from && data.today <= data.to ? data.today : data.from
  const { suggestion } = data
  const addedHere = added?.week === shownFrom ? added : null

  return (
    <>
      <PageHeader title="Schedule" initials={user?.initials}
        subtitle={`${shortDay(data.from)} – ${shortDay(data.to)}${loading ? ' · Loading…' : ''}`}
        actions={(
          <>
            <div className="flex items-center gap-1.5">
              <Button variant="secondary" size="sm" aria-label="Previous week" onClick={() => go(-1)}><Icon name="chevronLeft" size={16} /></Button>
              <Button variant="secondary" size="sm" onClick={() => setWeekFrom(null)} disabled={weekFrom === null}>Today</Button>
              <Button variant="secondary" size="sm" aria-label="Next week" onClick={() => go(1)}><Icon name="chevronRight" size={16} /></Button>
            </div>
            <Button onClick={() => setEditing({ mode: 'add', initial: { date: defaultDate } })}><Icon name="plus" size={18} />Add event</Button>
          </>
        )} />

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
        <WeekGrid data={data} selectedId={selected?.id} onSelect={setSelectedId} loading={loading} />
        <div className="flex min-w-0 flex-col gap-4">
          <EventDetail item={selected} deleting={deleting} onDelete={remove} onRemind={remind} onEdit={(item) => setEditing({ mode: 'edit', item })} />
          {(addedHere || suggestion) && (
            <StudySuggestion suggestion={suggestion} added={addedHere?.text} onAdd={() => setEditing({
              mode: 'add', fromSuggestion: true,
              initial: { type: 'Study', title: suggestion.title, date: suggestion.date, start: suggestion.start, end: suggestion.end },
            })} />
          )}
          <UpcomingDeadlines deadlines={data.deadlines} />
          <CalendarFeed />
        </div>
      </div>

      <EventDialog editing={editing} onClose={() => setEditing(null)} onSaved={saved} />
    </>
  )
}
