// Date helpers. Wall-clock dates are 'YYYY-MM-DD' strings and times are 'HH:MM' strings, both interpreted
// in the institution's time zone; instants are Date objects / timestamptz.

export const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const TIME_ZONES = { Eastern: 'America/New_York', Central: 'America/Chicago', Pacific: 'America/Los_Angeles' }

const formatters = new Map()
function formatter(tz) {
  if (!formatters.has(tz)) {
    formatters.set(tz, new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
    }))
  }
  return formatters.get(tz)
}

export function zoneParts(date, tz) {
  const parts = Object.fromEntries(formatter(tz).formatToParts(date).map((part) => [part.type, part.value]))
  return { year: +parts.year, month: +parts.month, day: +parts.day, hour: +parts.hour % 24, minute: +parts.minute, second: +parts.second }
}

const pad = (n) => String(n).padStart(2, '0')
export const localDate = (date, tz) => { const p = zoneParts(date, tz); return `${p.year}-${pad(p.month)}-${pad(p.day)}` }
export const localTime = (date, tz) => { const p = zoneParts(date, tz); return `${pad(p.hour)}:${pad(p.minute)}` }

// The instant at which the wall clock in tz reads dateStr timeStr.
export function zonedTime(dateStr, timeStr, tz) {
  const [y, m, d] = dateStr.split('-').map(Number)
  const [hh, mm] = timeStr.split(':').map(Number)
  const target = Date.UTC(y, m - 1, d, hh, mm)
  let guess = target
  for (let i = 0; i < 2; i++) {
    const p = zoneParts(new Date(guess), tz)
    const seen = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute)
    guess += target - seen
  }
  return new Date(guess)
}

export function addDays(dateStr, n) {
  const [y, m, d] = dateStr.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d + n))
  return date.toISOString().slice(0, 10)
}

export function weekday(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number)
  return DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]
}

export const mondayOf = (dateStr) => addDays(dateStr, -WEEKDAYS.indexOf(weekday(dateStr)))

export function daysBetween(fromStr, toStr) {
  const toUtc = (s) => { const [y, m, d] = s.split('-').map(Number); return Date.UTC(y, m - 1, d) }
  return Math.round((toUtc(toStr) - toUtc(fromStr)) / 86_400_000)
}

export const shortDate = (dateStr) => `${MONTHS[+dateStr.slice(5, 7) - 1]} ${+dateStr.slice(8, 10)}`
export const monthYear = (dateStr) => `${new Intl.DateTimeFormat('en-US', { month: 'long' }).format(new Date(`${dateStr}T12:00:00Z`))} ${dateStr.slice(0, 4)}`
export const monthName = (dateStr) => MONTHS[+dateStr.slice(5, 7) - 1]
export const dayLong = (dateStr) => `${weekday(dateStr)}, ${shortDate(dateStr)}`

// 'Today' / 'Yesterday' / 'Tomorrow' / 'Oct 3' relative to now in tz.
export function relativeDay(date, tz, now = new Date()) {
  const diff = daysBetween(localDate(now, tz), localDate(date, tz))
  if (diff === 0) return 'Today'
  if (diff === -1) return 'Yesterday'
  if (diff === 1) return 'Tomorrow'
  return shortDate(localDate(date, tz))
}

// Chat-style stamp: '9:42' today, 'Yesterday 16:05', otherwise 'Sep 29'.
export function messageTime(date, tz, now = new Date()) {
  const day = relativeDay(date, tz, now)
  const time = localTime(date, tz).replace(/^0/, '')
  if (day === 'Today') return time
  if (day === 'Yesterday') return `Yesterday ${localTime(date, tz)}`
  return day
}

export const toMinutes = (timeStr) => { const [h, m] = timeStr.split(':').map(Number); return h * 60 + m }
export const fromMinutes = (mins) => `${pad(Math.floor(mins / 60))}:${pad(mins % 60)}`
export const hhmm = (time) => (time ? String(time).slice(0, 5) : null)
