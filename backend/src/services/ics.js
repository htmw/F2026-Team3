import { addDays, localDate, zonedTime } from '../lib/time.js'
import { deadlinesBetween, studentCalendar } from './calendar.js'

const stamp = (date) => date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')
const text = (value = '') => String(value).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n')

// Lines over 75 octets must be folded (RFC 5545 3.1).
function fold(line) {
  const out = []
  let rest = line
  while (Buffer.byteLength(rest) > 75) {
    let cut = 75
    while (Buffer.byteLength(rest.slice(0, cut)) > 75) cut--
    out.push(rest.slice(0, cut))
    rest = ` ${rest.slice(cut)}`
  }
  out.push(rest)
  return out.join('\r\n')
}

// Next 10 weeks of a student's classes, events, meetings and deadlines. Times are written in UTC so no
// VTIMEZONE block is needed; class meetings are expanded individually so daylight-saving changes stay correct.
export async function buildIcs(ctx, tz) {
  const today = localDate(new Date(), tz)
  const to = addDays(today, 70)
  const now = stamp(new Date())
  const items = await studentCalendar(ctx, addDays(today, -7), to, tz)
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Acadmate//Student calendar//EN', 'CALSCALE:GREGORIAN', 'X-WR-CALNAME:Acadmate']
  for (const item of items) {
    lines.push(
      'BEGIN:VEVENT',
      `UID:${item.id}@acadmate`,
      `DTSTAMP:${now}`,
      `DTSTART:${stamp(zonedTime(item.date, item.start, tz))}`,
      `DTEND:${stamp(zonedTime(item.date, item.end, tz))}`,
      `SUMMARY:${text(item.title)}`,
      `CATEGORIES:${text(item.type)}`,
      ...(item.location ? [`LOCATION:${text(item.location)}`] : []),
      ...(item.note ? [`DESCRIPTION:${text(item.note)}`] : []),
      'END:VEVENT',
    )
  }
  for (const due of deadlinesBetween(ctx, today, to, tz)) {
    const work = ctx.work.find((w) => w.id === due.id)
    lines.push(
      'BEGIN:VEVENT',
      `UID:due-${due.id}@acadmate`,
      `DTSTAMP:${now}`,
      `DTSTART:${stamp(work.due_at)}`,
      `DTEND:${stamp(work.due_at)}`,
      `SUMMARY:${text(`Due: ${due.title} (${due.course})`)}`,
      'END:VEVENT',
    )
  }
  lines.push('END:VCALENDAR')
  return lines.map(fold).join('\r\n') + '\r\n'
}
