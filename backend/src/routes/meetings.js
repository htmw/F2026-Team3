import { Router } from 'express'
import { z } from 'zod'
import { many, one, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { badRequest, conflict, forbidden, notFound } from '../lib/errors.js'
import { initials, shortName } from '../lib/people.js'
import { timeZone } from '../lib/settings.js'
import { dayLong, localDate, localTime, mondayOf, shortDate, weekday } from '../lib/time.js'
import { requireAuth, requireRole } from '../middleware/auth.js'
import { SLOT_TIMES, availability } from '../services/calendar.js'
import { notify } from '../services/notify.js'

const router = Router()

const TOPICS = ['Spring plan', 'Capstone topics', 'Add or drop a course', 'Internship or career', 'Something else']
const LIVE = ['requested', 'confirmed', 'proposed']
const describeTime = (date, tz) => `${dayLong(localDate(date, tz))} at ${localTime(date, tz)}`

async function staffProfile(id) {
  const row = await one(
    `SELECT s.*, u.full_name, u.email FROM staff_profiles s JOIN users u ON u.id = s.user_id
      WHERE s.user_id = $1 AND u.status = 'active'`, [id])
  if (!row) throw notFound('Staff member')
  return row
}

router.get('/staff', requireAuth, async (req, res) => {
  const { bookable } = z.object({ bookable: z.enum(['true', 'false']).optional() }).parse(req.query)
  const rows = await many(
    `SELECT u.id, u.full_name, s.title, s.helps, s.office, s.bookable, s.meeting_length, s.booking_window_weeks FROM users u JOIN staff_profiles s ON s.user_id = u.id
      WHERE u.status = 'active' ${bookable === 'true' ? 'AND s.bookable' : ''} ORDER BY u.full_name`)
  const mine = req.user.role === 'student'
    ? (await one('SELECT advisor_id FROM student_profiles WHERE user_id = $1', [req.user.id]))?.advisor_id
    : null
  res.json({
    staff: rows
      .map((s) => ({ id: s.id, name: s.full_name, role: s.title, initials: initials(s.full_name), helps: s.helps, office: s.office, meetingLength: s.meeting_length, bookingWindowWeeks: s.booking_window_weeks, isMyAdvisor: s.id === mine }))
      .sort((a, b) => Number(b.isMyAdvisor) - Number(a.isMyAdvisor)),
    topics: TOPICS,
    formats: ['In person', 'Online'],
  })
})

router.get('/staff/:id/availability', requireAuth, async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const tz = await timeZone()
  const { week } = z.object({ week: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional() }).parse(req.query)
  const staff = await staffProfile(id)
  const weekOf = mondayOf(week ?? localDate(new Date(), tz))
  res.json({ staffId: id, week: weekOf, meetingLength: staff.meeting_length, days: await availability(staff, weekOf, tz) })
})

// A student asks for a meeting in one of the staff member's open slots.
router.post('/meetings', requireRole('student'), async (req, res) => {
  const body = z.object({
    staffId: z.uuid(),
    startsAt: z.iso.datetime({ offset: true }),
    format: z.enum(['In person', 'Online']),
    topic: z.string().trim().min(1, 'Pick a topic.').max(200),
    note: z.string().trim().max(2000).optional(),
    attachPlan: z.boolean().default(false),
  }).parse(req.body)
  const tz = await timeZone()
  const staff = await staffProfile(body.staffId)
  if (!staff.bookable) throw badRequest('This person is not taking bookings.')
  const startsAt = new Date(body.startsAt)
  const date = localDate(startsAt, tz)
  const slot = (await availability(staff, date, tz)).find((d) => d.date === date)?.slots.find((s) => s.startsAt === startsAt.toISOString())
  if (!slot || !SLOT_TIMES.includes(localTime(startsAt, tz))) throw badRequest('Pick one of the listed times.')

  const meeting = await transaction(async (db) => {
    // Serialise bookings per staff member so two students can't take the same slot.
    await db.query('SELECT pg_advisory_xact_lock(hashtext($1))', [staff.user_id])
    const endsAt = new Date(startsAt.getTime() + staff.meeting_length * 60_000)
    const clash = await db.query(
      `SELECT 1 FROM meetings WHERE staff_id = $1 AND status = ANY($4) AND starts_at < $3 AND ends_at > $2`,
      [staff.user_id, startsAt, endsAt, LIVE])
    if (clash.rowCount || slot.taken) throw conflict('That time was just taken. Pick another slot.')
    const { rows } = await db.query(
      `INSERT INTO meetings (student_id, staff_id, starts_at, ends_at, format, topic, student_note, attach_plan, status, location, video_link)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'requested', $9, $10) RETURNING *`,
      [req.user.id, staff.user_id, startsAt, endsAt, body.format, body.topic, body.note ?? null, body.attachPlan,
        body.format === 'In person' ? staff.office : null, body.format === 'Online' ? staff.settings?.videoLink ?? null : null])
    await notify(req.user.id, `Meeting request sent: ${body.topic} with ${staff.full_name}, ${describeTime(startsAt, tz)} (${body.format.toLowerCase()}). You'll get a message when it's confirmed.`, db)
    await notify(staff.user_id, `${shortName(req.user.full_name)} asked to meet ${describeTime(startsAt, tz)} about ${body.topic.toLowerCase()}.`, db)
    return rows[0]
  })
  await audit(req.user, `Booked a meeting with ${staff.full_name} for ${shortDate(date)}`, { req, target: { type: 'meeting', id: meeting.id }, subjectUserId: req.user.id })
  res.status(201).json({
    id: meeting.id, status: meeting.status, staffName: staff.full_name, startsAt: meeting.starts_at, endsAt: meeting.ends_at,
    format: meeting.format, topic: meeting.topic, location: meeting.location,
    summary: `${staff.full_name} on ${weekday(date)}, ${shortDate(date)} at ${localTime(startsAt, tz)} (${meeting.format.toLowerCase()}) about ${meeting.topic.toLowerCase()}.`,
  })
})

async function partyMeeting(req) {
  const id = z.uuid().parse(req.params.id)
  const meeting = await one(
    `SELECT m.*, s.full_name AS staff_name, st.full_name AS student_name FROM meetings m
       JOIN users s ON s.id = m.staff_id LEFT JOIN users st ON st.id = m.student_id WHERE m.id = $1`, [id])
  if (!meeting) throw notFound('Meeting')
  const isStaff = meeting.staff_id === req.user.id
  const isStudent = meeting.student_id === req.user.id
  if (!isStaff && !isStudent) throw notFound('Meeting')
  return { meeting, isStaff, isStudent }
}

router.post('/meetings/:id/cancel', requireAuth, async (req, res) => {
  const { meeting, isStaff } = await partyMeeting(req)
  if (!LIVE.includes(meeting.status)) throw conflict('This meeting is no longer active.')
  const tz = await timeZone()
  await transaction(async (db) => {
    await db.query(`UPDATE meetings SET status = 'cancelled' WHERE id = $1`, [meeting.id])
    const other = isStaff ? meeting.student_id : meeting.staff_id
    if (other) await notify(other, `${req.user.full_name} cancelled "${meeting.topic}" on ${describeTime(meeting.starts_at, tz)}.`, db)
  })
  await audit(req.user, `Cancelled the meeting "${meeting.topic}"`, { req, target: { type: 'meeting', id: meeting.id }, subjectUserId: meeting.student_id })
  res.json({ id: meeting.id, status: 'cancelled' })
})

// Student accepts a new time the staff member proposed.
router.post('/meetings/:id/accept', requireRole('student'), async (req, res) => {
  const { meeting, isStudent } = await partyMeeting(req)
  if (!isStudent) throw forbidden()
  if (meeting.status !== 'proposed') throw conflict('There is no new time to accept.')
  const tz = await timeZone()
  const length = meeting.ends_at - meeting.starts_at
  const updated = await transaction(async (db) => {
    const { rows } = await db.query(
      `UPDATE meetings SET status = 'confirmed', starts_at = proposed_starts_at, ends_at = proposed_starts_at + $2 * interval '1 millisecond', proposed_starts_at = NULL
        WHERE id = $1 RETURNING *`, [meeting.id, length])
    await notify(meeting.staff_id, `${shortName(req.user.full_name)} accepted ${describeTime(rows[0].starts_at, tz)} for "${meeting.topic}".`, db)
    return rows[0]
  })
  res.json({ id: updated.id, status: updated.status, startsAt: updated.starts_at })
})

router.put('/meetings/:id/notes', requireRole('advisor', 'admin'), async (req, res) => {
  const { notes } = z.object({ notes: z.string().max(10_000) }).parse(req.body)
  const { meeting, isStaff } = await partyMeeting(req)
  if (!isStaff) throw forbidden()
  await one('UPDATE meetings SET notes = $1 WHERE id = $2 RETURNING id', [notes, meeting.id])
  res.json({ id: meeting.id, notes })
})

// ------------------------------------------------------------------ staff side of booking requests

async function ownBooking(req) {
  const { meeting, isStaff } = await partyMeeting(req)
  if (!isStaff) throw forbidden()
  return meeting
}

router.post('/bookings/:id/accept', requireRole('advisor', 'admin'), async (req, res) => {
  const meeting = await ownBooking(req)
  if (meeting.status !== 'requested') throw conflict('Only new requests can be accepted.')
  const tz = await timeZone()
  await transaction(async (db) => {
    await db.query(`UPDATE meetings SET status = 'confirmed' WHERE id = $1`, [meeting.id])
    if (meeting.student_id) await notify(meeting.student_id, `Confirmed: "${meeting.topic}" with ${meeting.staff_name}, ${describeTime(meeting.starts_at, tz)} (${meeting.format.toLowerCase()}).`, db)
  })
  await audit(req.user, `Accepted a meeting with ${meeting.student_name}`, { req, target: { type: 'meeting', id: meeting.id }, subjectUserId: meeting.student_id })
  res.json({ id: meeting.id, status: 'confirmed' })
})

router.post('/bookings/:id/propose', requireRole('advisor', 'admin'), async (req, res) => {
  const { startsAt } = z.object({ startsAt: z.iso.datetime({ offset: true }) }).parse(req.body)
  const meeting = await ownBooking(req)
  if (!['requested', 'proposed'].includes(meeting.status)) throw conflict('This meeting can no longer be moved.')
  const when = new Date(startsAt)
  if (when <= new Date()) throw badRequest('Suggest a time in the future.')
  const tz = await timeZone()
  await transaction(async (db) => {
    await db.query(`UPDATE meetings SET status = 'proposed', proposed_starts_at = $2 WHERE id = $1`, [meeting.id, when])
    if (meeting.student_id) await notify(meeting.student_id, `${meeting.staff_name} suggested a new time for "${meeting.topic}": ${describeTime(when, tz)}. Accept it in Book a meeting.`, db)
  })
  await audit(req.user, `Suggested a new meeting time to ${meeting.student_name}`, { req, target: { type: 'meeting', id: meeting.id }, subjectUserId: meeting.student_id })
  res.json({ id: meeting.id, status: 'proposed', proposedStartsAt: when })
})

router.post('/bookings/:id/decline', requireRole('advisor', 'admin'), async (req, res) => {
  const { reason } = z.object({ reason: z.string().trim().max(500).optional() }).parse(req.body ?? {})
  const meeting = await ownBooking(req)
  if (!['requested', 'proposed'].includes(meeting.status)) throw conflict('Only open requests can be declined.')
  await transaction(async (db) => {
    await db.query(`UPDATE meetings SET status = 'declined' WHERE id = $1`, [meeting.id])
    if (meeting.student_id) await notify(meeting.student_id, `${meeting.staff_name} declined "${meeting.topic}".${reason ? ` ${reason}` : ''}`, db)
  })
  res.json({ id: meeting.id, status: 'declined' })
})

export default router
