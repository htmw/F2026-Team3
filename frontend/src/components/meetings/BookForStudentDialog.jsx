import { useState } from 'react'
import Button from '../ui/Button.jsx'
import Dialog from '../ui/Dialog.jsx'
import { Field, Textarea, TextInput } from '../ui/Field.jsx'
import Notice from '../ui/Notice.jsx'
import SearchInput from '../ui/SearchInput.jsx'
import { Empty, Loading } from '../ui/Status.jsx'
import { useToast } from '../ui/Toast.jsx'
import OptionPills from './OptionPills.jsx'
import SlotGrid from './SlotGrid.jsx'
import { api, errorText } from '../../lib/api.js'
import { addDays } from '../../lib/dates.js'
import { useApi } from '../../lib/useApi.js'
import { useDebounced } from '../../lib/useDebounced.js'

const FORMATS = ['In person', 'Online']
const BOOKING_DAYS = 13 // the spec 18 window: this week and next

// Advisor books a confirmed meeting with an advisee (spec 24): pick the student, a day, one of the advisor's open slots
// that the student can take too, the format and a topic → POST /advisor/meetings. Render with a `key` to reset it.
export default function BookForStudentDialog({ open, onClose, onBooked, today, studentId: initialId = null }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [studentId, setStudentId] = useState(initialId)
  const [day, setDay] = useState(today)
  const [startsAt, setStartsAt] = useState(null)
  const [format, setFormat] = useState('In person')
  const [topic, setTopic] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const q = useDebounced(search.trim())

  const advisees = useApi(open ? `/advisor/advisees${q ? `?q=${encodeURIComponent(q)}` : ''}` : null)
  const slots = useApi(open && studentId && day ? `/advisor/meetings/free-slots?date=${day}&studentId=${studentId}` : null)
  const rows = advisees.data?.rows ?? []
  const student = rows.find((r) => r.studentId === studentId)

  const pickDay = (value) => { setDay(value); setStartsAt(null) }
  const pickStudent = (id) => { setStudentId(id); setStartsAt(null) }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const row = await api('/advisor/meetings', {
        method: 'POST',
        body: { studentId, startsAt, format, topic: topic.trim(), note: note.trim() || null },
      })
      toast.show({ message: `Booked ${row.topic} with ${row.who}.` })
      onBooked(row)
    } catch (err) {
      setError(err.code === 'SLOT_TAKEN' ? 'That time was just taken. Pick another.' : errorText(err))
      if (err.code === 'SLOT_TAKEN') {
        setStartsAt(null)
        slots.reload()
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={() => { if (!saving) onClose() }} title="Book with an advisee">
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-bold">Advisee</span>
          <SearchInput label="Search advisees" placeholder="Search by name…" value={search} onChange={setSearch} />
          <div role="group" aria-label="Choose an advisee" className="flex max-h-40 flex-col gap-1 overflow-y-auto">
            {!advisees.data ? <Loading label="Loading advisees…" />
              : rows.length === 0 ? <Empty>No advisees match.</Empty>
                : rows.map((r) => (
                  <button key={r.studentId} type="button" aria-pressed={r.studentId === studentId} onClick={() => pickStudent(r.studentId)}
                    className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left text-sm text-navy ${
                      r.studentId === studentId ? 'border-accent bg-teal-soft/50' : 'border-line bg-surface hover:bg-surface-sunk'}`}>
                    <span className="font-semibold">{r.fullName}</span>
                    <span className="text-xs text-muted">{r.program}</span>
                  </button>
                ))}
          </div>
        </div>

        <Field id="book-day" label="Day">
          <TextInput id="book-day" type="date" min={today} max={addDays(today, BOOKING_DAYS)} value={day}
            onChange={(event) => pickDay(event.target.value)} />
        </Field>

        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-bold">Time</span>
          {!studentId ? <Empty>Pick an advisee to see your open times.</Empty>
            : slots.error ? <Notice tone="pink">{slots.error.message}</Notice>
              : !slots.data ? <Loading label="Loading open times…" />
                : slots.data.slots.length === 0 ? <Empty>No open times that day.</Empty>
                  : <SlotGrid slots={slots.data.slots} value={startsAt} onChange={setStartsAt} />}
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-bold">Format</span>
          <OptionPills label="Meeting format" options={FORMATS} value={format} onChange={setFormat} />
        </div>
        <Field id="book-topic" label="Topic">
          <TextInput id="book-topic" maxLength={80} placeholder="For example: Spring plan follow-up" value={topic}
            onChange={(event) => setTopic(event.target.value)} />
        </Field>
        <Field id="book-note" label="Note to the student (optional)">
          <Textarea id="book-note" rows={2} maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
        </Field>

        {error && <Notice tone="pink" role="alert">{error}</Notice>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button type="submit" disabled={saving || !studentId || !startsAt || !topic.trim()}>
            {saving ? 'Booking…' : student ? `Book with ${student.name}` : 'Book'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
