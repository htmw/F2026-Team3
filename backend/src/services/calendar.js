import { many } from '../db/pool.js'
import { addDays, daysBetween, hhmm, localDate, localTime, mondayOf, shortDate, toMinutes, weekday, zonedTime } from '../lib/time.js'

export const SLOT_TIMES = ['09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00', '17:00']
const ACTIVE_MEETING = ['requested', 'confirmed', 'proposed']

const rangeDates = (from, to) => Array.from({ length: daysBetween(from, to) + 1 }, (_, i) => addDays(from, i))

// Weekly class meetings generated from each current section's days and times.
export function classMeetings(ctx, from, to) {
  const items = []
  for (const e of ctx.enrollments) {
    if (e.status !== 'current' || !e.days?.length || !e.start_time) continue
    for (const date of rangeDates(from, to)) {
      if (date < (e.classes_begin ?? e.starts_on) || date > e.ends_on || !e.days.includes(weekday(date))) continue
      items.push({
        id: `class-${e.id}-${date}`,
        kind: 'class',
        type: 'Class',
        title: `${e.code} ${e.name}`,
        courseCode: e.code,
        date,
        start: hhmm(e.start_time),
        end: hhmm(e.end_time),
        location: e.room,
        note: e.instructor ? `Lecture with ${e.instructor}.` : 'Lecture.',
        editable: false,
      })
    }
  }
  return items
}

// Everything on a student's calendar between two local dates (inclusive), sorted by start.
export async function studentCalendar(ctx, from, to, tz) {
  const start = zonedTime(from, '00:00', tz)
  const end = zonedTime(addDays(to, 1), '00:00', tz)
  const [events, meetings] = await Promise.all([
    many(`SELECT * FROM events WHERE owner_id = $1 AND starts_at < $3 AND ends_at > $2 ORDER BY starts_at`, [ctx.user.id, start, end]),
    many(
      `SELECT m.*, u.full_name AS staff_name FROM meetings m JOIN users u ON u.id = m.staff_id
        WHERE m.student_id = $1 AND m.status = ANY($4) AND m.starts_at < $3 AND m.ends_at > $2 ORDER BY m.starts_at`,
      [ctx.user.id, start, end, ACTIVE_MEETING]),
  ])
  const items = [
    ...classMeetings(ctx, from, to),
    ...events.map((e) => ({
      id: e.id, kind: 'event', type: e.type, title: e.title, date: localDate(e.starts_at, tz),
      start: localTime(e.starts_at, tz), end: localTime(e.ends_at, tz), location: e.location, note: e.note, editable: true,
    })),
    ...meetings.map((m) => ({
      id: m.id, kind: 'meeting', type: 'Advising', title: m.topic, date: localDate(m.starts_at, tz),
      start: localTime(m.starts_at, tz), end: localTime(m.ends_at, tz),
      location: m.format === 'Online' ? `Online · ${m.staff_name}` : `${m.location ?? 'In person'} · ${m.staff_name}`,
      note: m.status === 'requested' ? 'Waiting for your advisor to confirm.' : m.student_note, status: m.status, editable: false,
    })),
  ]
  return items.sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start))
}

export function deadlinesBetween(ctx, from, to, tz) {
  return ctx.work
    .filter((w) => { const d = localDate(w.due_at, tz); return d >= from && d <= to })
    .map((w) => ({ id: w.id, date: localDate(w.due_at, tz), title: w.title, course: w.course_code ?? 'Advising', status: w.status, type: w.type }))
}

// Largest free block (>= 90 min, between 08:00 and 22:00) before the nearest open deadline, to suggest a study session.
export function studySuggestion(items, deadlines, today) {
  const next = deadlines.find((d) => d.date > today && !['Submitted', 'Graded'].includes(d.status))
  if (!next) return null
  let best = null
  for (const date of rangeDates(addDays(today, 1), addDays(next.date, -1))) {
    const busy = items.filter((i) => i.date === date).map((i) => [toMinutes(i.start), toMinutes(i.end)]).sort((a, b) => a[0] - b[0])
    let cursor = 8 * 60
    for (const [s, e] of [...busy, [22 * 60, 22 * 60]]) {
      const gap = Math.min(s, 22 * 60) - cursor
      if (gap >= 90 && (!best || gap > best.minutes)) best = { date, start: cursor, minutes: Math.min(gap, 120) }
      cursor = Math.max(cursor, e)
    }
    if (best?.minutes === 120) break
  }
  if (!best) return null
  const pad = (n) => String(n).padStart(2, '0')
  const t = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`
  return {
    date: best.date,
    start: t(best.start),
    end: t(best.start + best.minutes),
    title: `Study · ${next.title}`,
    text: `You have a free ${best.minutes / 60 >= 2 ? '2-hour' : `${best.minutes}-minute`} window on ${weekday(best.date)} at ${t(best.start)}. Blocking it for ${next.title} gives you time before the ${shortDate(next.date)} deadline.`,
    deadline: next,
  }
}

// Bookable slots for a staff member in the Mon–Fri week containing `weekOf`.
export async function availability(staff, weekOf, tz, now = new Date()) {
  const monday = mondayOf(weekOf)
  const friday = addDays(monday, 4)
  const windowEnd = new Date(now.getTime() + staff.booking_window_weeks * 7 * 86_400_000)
  const start = zonedTime(monday, '00:00', tz)
  const end = zonedTime(addDays(friday, 1), '00:00', tz)
  const busy = await many(
    `SELECT starts_at, ends_at FROM meetings WHERE staff_id = $1 AND status = ANY($4) AND starts_at < $3 AND ends_at > $2
     UNION ALL
     SELECT proposed_starts_at, proposed_starts_at + (ends_at - starts_at) FROM meetings
      WHERE staff_id = $1 AND status = 'proposed' AND proposed_starts_at < $3 AND proposed_starts_at > $2
     UNION ALL
     SELECT starts_at, ends_at FROM events WHERE owner_id = $1 AND starts_at < $3 AND ends_at > $2`,
    [staff.user_id, start, end, ACTIVE_MEETING])

  return rangeDates(monday, friday).map((date) => {
    const slots = SLOT_TIMES.map((time) => {
      const slotStart = zonedTime(date, time, tz)
      const slotEnd = new Date(slotStart.getTime() + staff.meeting_length * 60_000)
      const taken = slotStart <= now || slotStart > windowEnd || busy.some((b) => b.starts_at < slotEnd && b.ends_at > slotStart)
      return { time, startsAt: slotStart.toISOString(), taken }
    })
    const open = slots.filter((s) => !s.taken).length
    return { date, dow: weekday(date), day: Number(date.slice(8)), open, free: open ? `${open} open` : 'Full', slots }
  })
}
