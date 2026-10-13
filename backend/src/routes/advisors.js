import { Router } from 'express'
import { z } from 'zod'
import { many, one, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { toCsv } from '../lib/csv.js'
import { badRequest, notFound } from '../lib/errors.js'
import { initials, shortName } from '../lib/people.js'
import { timeZone } from '../lib/settings.js'
import { addDays, dayLong, daysBetween, hhmm, localDate, localTime, mondayOf, relativeDay, shortDate, weekday, zonedTime } from '../lib/time.js'
import { requireRole } from '../middleware/auth.js'
import { adviseeStatus, credits, gpaTrend, graduation, loadStudents, riskFlags } from '../services/academics.js'

const router = Router()
router.use(requireRole('advisor', 'admin'))

// Every advisee of the signed-in advisor, with derived status and flags.
export async function advisees(advisorId, now = new Date()) {
  const ids = (await many('SELECT user_id FROM student_profiles WHERE advisor_id = $1', [advisorId])).map((r) => r.user_id)
  const contexts = await loadStudents(ids)
  return [...contexts.values()].map((ctx) => {
    const flags = riskFlags(ctx, now)
    return { ctx, flags, status: adviseeStatus(ctx, now), level: flags.some((f) => f.level === 'High') ? 'High' : flags.length ? 'Medium' : null }
  }).sort((a, b) => a.ctx.user.full_name.localeCompare(b.ctx.user.full_name))
}

async function nextMeetings(advisorId) {
  return many(
    `SELECT DISTINCT ON (student_id) student_id, starts_at FROM meetings
      WHERE staff_id = $1 AND status IN ('confirmed', 'requested') AND starts_at > now() ORDER BY student_id, starts_at`, [advisorId])
}

function officeHourBlocks(hours, from, to, tz) {
  const blocks = []
  for (let i = 0; i <= daysBetween(from, to); i++) {
    const date = addDays(from, i)
    for (const h of hours.filter((x) => x.day === weekday(date))) {
      blocks.push({
        id: `oh-${h.id}-${date}`, kind: 'office_hours', date, day: relativeDay(zonedTime(date, '12:00', tz), tz), time: hhmm(h.start_time),
        end: hhmm(h.end_time), who: 'Drop-in office hours', topic: 'Open to all advisees', format: 'In person', location: h.location,
      })
    }
  }
  return blocks
}

router.get('/me/dashboard', async (req, res) => {
  const tz = await timeZone()
  const today = localDate(new Date(), tz)
  const list = await advisees(req.user.id)
  const monday = mondayOf(today)
  const [pending, weekMeetings, hours] = await Promise.all([
    many(`SELECT a.*, u.full_name FROM approvals a JOIN users u ON u.id = a.student_id WHERE a.advisor_id = $1 AND a.status = 'Pending' ORDER BY a.created_at`, [req.user.id]),
    many(
      `SELECT m.*, u.full_name FROM meetings m LEFT JOIN users u ON u.id = m.student_id
        WHERE m.staff_id = $1 AND m.status IN ('confirmed', 'requested') AND m.starts_at >= $2 AND m.starts_at < $3 ORDER BY m.starts_at`,
      [req.user.id, zonedTime(monday, '00:00', tz), zonedTime(addDays(monday, 7), '00:00', tz)]),
    many('SELECT * FROM office_hours WHERE staff_id = $1', [req.user.id]),
  ])
  const todays = weekMeetings.filter((m) => localDate(m.starts_at, tz) === today)
  const attention = list.filter((a) => a.flags.length)
  const programs = [...new Set(list.map((a) => a.ctx.user.program).filter(Boolean))]
  const gradCounts = new Map()
  for (const a of list) {
    const label = graduation(a.ctx).label
    gradCounts.set(label, (gradCounts.get(label) ?? 0) + 1)
  }
  const gradList = [...gradCounts.entries()].sort((a, b) => b[1] - a[1])

  res.json({
    stats: [
      { label: 'Advisees', value: String(list.length), note: programs.join(' and ') || 'No advisees yet' },
      { label: 'Waiting for you', value: String(pending.length), note: 'Plans, forms and requests', tag: pending.length ? 'Action' : 'Clear' },
      { label: 'Meetings this week', value: String(weekMeetings.length), note: `${todays.length} today` },
      { label: 'Need attention', value: String(attention.length), note: 'Flagged by Acadmate rules', tag: attention.length ? 'Review' : 'Clear' },
    ],
    queue: pending.map((a) => ({
      id: a.id, studentId: a.student_id, name: shortName(a.full_name), av: initials(a.full_name), type: a.type, item: a.title,
      when: shortDate(localDate(a.created_at, tz)), check: a.precheck_text, ok: a.precheck_ok,
    })),
    meetings: [
      ...todays.map((m) => ({ id: m.id, kind: 'meeting', time: localTime(m.starts_at, tz), who: m.full_name ? shortName(m.full_name) : 'Meeting', studentId: m.student_id, topic: `${m.topic} · ${m.format}`, status: m.status, videoLink: m.video_link })),
      ...officeHourBlocks(hours, today, today, tz).map((b) => ({ ...b, topic: `${b.location ?? 'Office'} · until ${b.end}` })),
    ].sort((a, b) => a.time.localeCompare(b.time)),
    attention: attention.sort((a, b) => (a.level === b.level ? 0 : a.level === 'High' ? -1 : 1)).map((a) => ({
      studentId: a.ctx.user.id, name: shortName(a.ctx.user.full_name), av: initials(a.ctx.user.full_name), flag: a.flags[0].text,
      gpa: gpaTrend(a.ctx).cumulative?.toFixed(2) ?? '—', last: a.ctx.user.last_login_at ? shortDate(localDate(a.ctx.user.last_login_at, tz)) : 'Never', level: a.level,
    })),
    caseload: [
      { label: 'On track', n: list.filter((a) => !a.flags.length).length },
      { label: 'Needs attention', n: list.filter((a) => a.level === 'Medium').length },
      { label: 'At risk', n: list.filter((a) => a.level === 'High').length },
    ],
    grad: [...gradList.slice(0, 2).map(([label, n]) => ({ label, n })), ...(gradList.length > 2 ? [{ label: 'Later', n: gradList.slice(2).reduce((s, [, n]) => s + n, 0) }] : [])],
  })
})

router.get('/me/advisees', async (req, res) => {
  const q = z.object({
    status: z.enum(['Needs attention', 'On track', 'Graduating']).optional(),
    q: z.string().trim().max(100).optional(),
  }).parse(req.query)
  const tz = await timeZone()
  const list = await advisees(req.user.id)
  const next = new Map((await nextMeetings(req.user.id)).map((m) => [m.student_id, m.starts_at]))
  const rows = list.map((a) => {
    const pendingPlan = a.ctx.pendingApprovals[0]
    const meeting = next.get(a.ctx.user.id)
    return {
      id: a.ctx.user.id, name: shortName(a.ctx.user.full_name), fullName: a.ctx.user.full_name, av: initials(a.ctx.user.full_name),
      prog: a.ctx.user.program, credits: credits(a.ctx).earned, gpa: gpaTrend(a.ctx).cumulative?.toFixed(2) ?? '—', status: a.status,
      flag: a.flags[0]?.text ?? (pendingPlan ? `${pendingPlan.title} waiting for your approval` : 'No open items'),
      next: meeting ? `${relativeDay(meeting, tz)} · ${localTime(meeting, tz)}` : 'Not booked',
      grad: graduation(a.ctx).label,
    }
  })
  const needle = q.q?.toLowerCase()
  const filtered = rows.filter((r) => (!q.status || r.status === q.status) && (!needle || r.fullName.toLowerCase().includes(needle) || r.prog?.toLowerCase().includes(needle)))
  res.json({
    tabs: [
      { label: 'All', count: rows.length },
      ...['Needs attention', 'On track', 'Graduating'].map((label) => ({ label, count: rows.filter((r) => r.status === label).length })),
    ],
    rows: filtered,
  })
})

router.get('/me/meetings', async (req, res) => {
  const { range } = z.object({ range: z.enum(['today', 'week']).default('today') }).parse(req.query)
  const tz = await timeZone()
  const today = localDate(new Date(), tz)
  const to = range === 'today' ? today : addDays(today, 6)
  const [meetings, requests, hours] = await Promise.all([
    many(
      `SELECT m.*, u.full_name FROM meetings m LEFT JOIN users u ON u.id = m.student_id
        WHERE m.staff_id = $1 AND m.status = 'confirmed' AND m.starts_at >= $2 AND m.starts_at < $3 ORDER BY m.starts_at`,
      [req.user.id, zonedTime(today, '00:00', tz), zonedTime(addDays(to, 1), '00:00', tz)]),
    many(
      `SELECT m.*, u.full_name FROM meetings m LEFT JOIN users u ON u.id = m.student_id
        WHERE m.staff_id = $1 AND m.status IN ('requested', 'proposed') AND m.starts_at > now() ORDER BY m.starts_at`, [req.user.id]),
    many('SELECT * FROM office_hours WHERE staff_id = $1 ORDER BY id', [req.user.id]),
  ])
  const agenda = [
    ...meetings.map((m) => ({
      id: m.id, kind: 'meeting', date: localDate(m.starts_at, tz), day: relativeDay(m.starts_at, tz), time: localTime(m.starts_at, tz),
      who: m.full_name ? shortName(m.full_name) : 'Meeting', studentId: m.student_id, topic: m.topic, format: m.format,
      note: m.student_note, notes: m.notes ?? '', videoLink: m.video_link, location: m.location, attachPlan: m.attach_plan,
    })),
    ...officeHourBlocks(hours, today, to, tz),
  ].sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time))
  res.json({
    range,
    meetings: agenda,
    requests: requests.map((m) => ({
      id: m.id, who: m.full_name ? shortName(m.full_name) : 'Student', studentId: m.student_id, status: m.status,
      when: `${dayLong(localDate(m.starts_at, tz))} · ${localTime(m.starts_at, tz)}`, startsAt: m.starts_at,
      proposed: m.proposed_starts_at ? `${dayLong(localDate(m.proposed_starts_at, tz))} · ${localTime(m.proposed_starts_at, tz)}` : null,
      topic: m.topic, format: m.format, note: m.student_note,
    })),
    officeHours: hours.map((h) => ({ id: h.id, day: h.day, start: hhmm(h.start_time), end: hhmm(h.end_time), location: h.location })),
  })
})

router.put('/me/office-hours', async (req, res) => {
  const slot = z.object({
    day: z.enum(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']),
    start: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/),
    end: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/),
    location: z.string().trim().max(200).optional(),
  }).refine((s) => s.end > s.start, { message: 'End must be after start.', path: ['end'] })
  const { slots } = z.object({ slots: z.array(slot).max(20) }).parse(req.body)
  await transaction(async (db) => {
    await db.query('DELETE FROM office_hours WHERE staff_id = $1', [req.user.id])
    for (const s of slots) {
      await db.query('INSERT INTO office_hours (staff_id, day, start_time, end_time, location) VALUES ($1, $2, $3, $4, $5)', [req.user.id, s.day, s.start, s.end, s.location ?? null])
    }
  })
  await audit(req.user, 'Updated their office hours', { req })
  res.json({ slots, summary: slots.map((s) => `${s.day} · ${s.start}–${s.end}`).join(', ') || 'No office hours' })
})

// ------------------------------------------------------------------ reports

async function reportData(advisorId, termName) {
  const term = termName
    ? await one('SELECT * FROM terms WHERE name = $1', [termName])
    : await one('SELECT * FROM terms WHERE is_current')
  if (!term) throw notFound('Term')
  const previous = await one('SELECT * FROM terms WHERE starts_on < $1 ORDER BY starts_on DESC LIMIT 1', [term.starts_on])
  const list = await advisees(advisorId)
  const response = async (t) => t && one(
    `SELECT avg(EXTRACT(EPOCH FROM decided_at - created_at)) / 86400 AS days FROM approvals
      WHERE advisor_id = $1 AND decided_at IS NOT NULL AND created_at >= $2 AND created_at < $3::date + 1`, [advisorId, t.starts_on, t.ends_on])
  const [approved, pendingCount, now, before, weekly] = await Promise.all([
    one(`SELECT count(*) AS n FROM approvals WHERE advisor_id = $1 AND status = 'Approved' AND decided_at >= $2 AND decided_at < $3::date + 1`, [advisorId, term.starts_on, term.ends_on]),
    one(`SELECT count(*) AS n FROM approvals WHERE advisor_id = $1 AND status = 'Pending'`, [advisorId]),
    response(term),
    response(previous),
    many(
      `SELECT date_trunc('week', starts_at) AS week, count(*) AS n FROM meetings
        WHERE staff_id = $1 AND status = 'confirmed' AND starts_at >= $2 AND starts_at < LEAST($3::date + 1, now())
        GROUP BY 1 ORDER BY 1 DESC LIMIT 6`, [advisorId, term.starts_on, term.ends_on]),
  ])
  const days = (row) => (row?.days == null ? null : Math.round(row.days * 10) / 10)
  return { term, list, approved: approved.n, pending: pendingCount.n, responseDays: days(now), previousResponseDays: days(before), weekly: weekly.reverse() }
}

router.get('/me/reports', async (req, res) => {
  const { term } = z.object({ term: z.string().trim().max(40).optional() }).parse(req.query)
  const data = await reportData(req.user.id, term)
  const terms = await many(`SELECT name FROM terms WHERE starts_on <= now() ORDER BY starts_on DESC LIMIT 4`)
  const attention = data.list.filter((a) => a.status === 'Needs attention')
  const programs = new Set(data.list.map((a) => a.ctx.user.program).filter(Boolean))
  res.json({
    term: data.term.name,
    terms: terms.map((t) => t.name),
    stats: [
      { label: 'Advisees', value: String(data.list.length), note: `Across ${programs.size} program${programs.size === 1 ? '' : 's'}` },
      { label: 'Plans approved', value: String(data.approved), note: `${data.pending} still pending` },
      {
        label: 'Avg. response time', value: data.responseDays == null ? '—' : `${data.responseDays} days`,
        note: data.previousResponseDays == null ? 'No earlier term to compare' : `${data.responseDays != null && data.responseDays <= data.previousResponseDays ? 'Down' : 'Up'} from ${data.previousResponseDays} days`,
      },
      { label: 'Need attention', value: String(attention.length), note: data.list.length ? `${Math.round((attention.length / data.list.length) * 100)}% of advisees` : '—' },
    ],
    byStatus: ['On track', 'Needs attention', 'Graduating'].map((label) => {
      const n = data.list.filter((a) => a.status === label).length
      return { label, n, count: `${n} student${n === 1 ? '' : 's'}` }
    }),
    weeks: data.weekly.map((w, i) => ({ label: `W${i + 1}`, weekOf: w.week, v: w.n })),
    risk: data.list.filter((a) => a.flags.length).map((a) => ({
      studentId: a.ctx.user.id, name: shortName(a.ctx.user.full_name), reason: a.flags[0].text, level: a.level,
      action: a.ctx.pendingApprovals.length ? 'Review request' : 'View advisee',
    })),
  })
})

router.get('/me/reports.csv', async (req, res) => {
  const { term } = z.object({ term: z.string().trim().max(40).optional() }).parse(req.query)
  const data = await reportData(req.user.id, term)
  const csv = toCsv(
    ['Student', 'Email', 'Program', 'Credits earned', 'GPA', 'Status', 'Expected graduation', 'Flags'],
    data.list.map((a) => [a.ctx.user.full_name, a.ctx.user.email, a.ctx.user.program, credits(a.ctx).earned, gpaTrend(a.ctx).cumulative ?? '', a.status, graduation(a.ctx).label, a.flags.map((f) => f.text).join(' | ')]),
  )
  await audit(req.user, `Exported the ${data.term.name} advising report`, { req })
  res.type('text/csv').attachment(`advising-report-${data.term.name.replace(/\s+/g, '-').toLowerCase()}.csv`).send(csv)
})

// ------------------------------------------------------------------ settings

const SETTINGS_DEFAULTS = {
  notify: { approvals: true, bookings: true, messages: true, weeklyDigest: true },
  precheck: true,
  remindOld: true,
  videoLink: '',
}

async function settingsView(userId) {
  const row = await one(
    `SELECT u.full_name, u.email, s.* FROM users u JOIN staff_profiles s ON s.user_id = u.id WHERE u.id = $1`, [userId])
  if (!row) throw notFound('Staff profile')
  const settings = { ...SETTINGS_DEFAULTS, ...row.settings, notify: { ...SETTINGS_DEFAULTS.notify, ...row.settings?.notify } }
  return {
    fullName: row.full_name, title: row.title, office: row.office, email: row.email,
    notify: settings.notify, precheck: settings.precheck, remindOld: settings.remindOld, videoLink: settings.videoLink,
    meetingLength: row.meeting_length, bookingWindowWeeks: row.booking_window_weeks, bookable: row.bookable, helps: row.helps,
  }
}

router.get('/me/settings', async (req, res) => res.json(await settingsView(req.user.id)))

router.patch('/me/settings', async (req, res) => {
  const body = z.object({
    fullName: z.string().trim().min(1).max(120).optional(),
    title: z.string().trim().max(120).optional(),
    office: z.string().trim().max(200).optional(),
    helps: z.string().trim().max(300).optional(),
    notify: z.object({ approvals: z.boolean(), bookings: z.boolean(), messages: z.boolean(), weeklyDigest: z.boolean() }).partial().strict().optional(),
    precheck: z.boolean().optional(),
    remindOld: z.boolean().optional(),
    videoLink: z.union([z.url({ protocol: /^https$/ }), z.literal('')]).optional(),
    meetingLength: z.union([z.literal(15), z.literal(30), z.literal(45), z.literal(60)]).optional(),
    bookingWindowWeeks: z.union([z.literal(1), z.literal(2), z.literal(4)]).optional(),
    bookable: z.boolean().optional(),
  }).strict().parse(req.body)
  if (Object.keys(body).length === 0) throw badRequest('Nothing to update.')
  const current = await settingsView(req.user.id)
  const settings = {
    notify: { ...current.notify, ...body.notify },
    precheck: body.precheck ?? current.precheck,
    remindOld: body.remindOld ?? current.remindOld,
    videoLink: body.videoLink ?? current.videoLink,
  }
  await transaction(async (db) => {
    if (body.fullName) await db.query('UPDATE users SET full_name = $1, updated_at = now() WHERE id = $2', [body.fullName, req.user.id])
    await db.query(
      `UPDATE staff_profiles SET title = COALESCE($1, title), office = COALESCE($2, office), helps = COALESCE($3, helps),
              meeting_length = COALESCE($4, meeting_length), booking_window_weeks = COALESCE($5, booking_window_weeks),
              bookable = COALESCE($6, bookable), settings = $7 WHERE user_id = $8`,
      [body.title ?? null, body.office ?? null, body.helps ?? null, body.meetingLength ?? null, body.bookingWindowWeeks ?? null, body.bookable ?? null, JSON.stringify(settings), req.user.id])
  })
  await audit(req.user, 'Updated their advisor settings', { req })
  res.json(await settingsView(req.user.id))
})

export default router
