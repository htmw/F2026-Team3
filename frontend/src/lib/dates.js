const DAY = 86_400_000
const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()

// "Today", "Yesterday", "Sep 14" or "Sep 14, 2025" for a timestamp, in the viewer's time zone.
export function relativeDate(value, now = new Date()) {
  const date = new Date(value)
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  const sameYear = date.getFullYear() === now.getFullYear()
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(sameYear ? {} : { year: 'numeric' }) })
}

// "15:04" for a timestamp.
export function clockTime(value) {
  return new Date(value).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

// Calendar arithmetic on "YYYY-MM-DD" strings (UTC-based, so DST never shifts the day).
export function addDays(ymd, days) {
  const date = new Date(`${ymd}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

// Monday of the week containing a "YYYY-MM-DD" date.
export function mondayOf(ymd) {
  return addDays(ymd, -((new Date(`${ymd}T00:00:00Z`).getUTCDay() + 6) % 7))
}

// "Oct 14" (or "Tue, Oct 14" with weekday) for a "YYYY-MM-DD" date.
export function shortDay(ymd, { weekday = false } = {}) {
  return new Date(`${ymd}T00:00:00Z`).toLocaleDateString('en-US', {
    timeZone: 'UTC', month: 'short', day: 'numeric', ...(weekday ? { weekday: 'short' } : {}),
  })
}
