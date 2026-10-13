import assert from 'node:assert/strict'
import { after, before, describe, it } from 'node:test'
import request from 'supertest'
import { pool } from '../src/db/pool.js'
import { resetDemo } from '../src/db/seed.js'
import { outbox } from '../src/lib/mailer.js'
import { generateCode } from '../src/lib/totp.js'
import { PASSWORD, app, resetLink, signIn } from './helpers.js'

// End-to-end tests against a freshly seeded test database (TEST_DATABASE_URL).
// Blocks run in order and share state, like a user session walking through the app.

let student
let advisor
let admin
const ids = {}

before(async () => {
  await resetDemo({ log: () => {} })
  student = await signIn('amara@school.edu')
  advisor = await signIn('eramirez@school.edu')
  admin = await signIn('admin@school.edu')
  const rows = (await pool.query(`SELECT id, email FROM users`)).rows
  for (const r of rows) ids[r.email.split('@')[0]] = r.id
})

after(() => pool.end())

describe('platform', () => {
  it('reports health', async () => {
    const res = await request(app).get('/api/health')
    assert.equal(res.status, 200)
    assert.deepEqual(res.body, { status: 'ok' })
  })
  it('returns JSON errors for unknown routes and bad JSON', async () => {
    assert.equal((await request(app).get('/api/nope')).body.error.code, 'not_found')
    const bad = await request(app).post('/api/auth/login').set('content-type', 'application/json').send('{oops')
    assert.equal(bad.status, 400)
    assert.equal(bad.body.error.code, 'bad_json')
  })
  it('blocks cross-site writes and allows the frontend origin', async () => {
    const evil = await request(app).post('/api/auth/logout').set('Origin', 'https://evil.example')
    assert.equal(evil.status, 403)
    const ok = await request(app).post('/api/auth/logout').set('Origin', 'http://localhost:5173')
    assert.equal(ok.status, 204)
    assert.equal(ok.headers['access-control-allow-origin'], 'http://localhost:5173')
  })
  it('enforces authentication and roles', async () => {
    assert.equal((await request(app).get('/api/students/me/dashboard')).status, 401)
    assert.equal((await student.get('/api/advisors/me/dashboard')).status, 403)
    assert.equal((await advisor.get('/api/students/me/dashboard')).status, 403)
    assert.equal((await advisor.get('/api/admin/overview')).status, 403)
    assert.equal((await student.get('/api/approvals')).status, 403)
  })
})

describe('auth', () => {
  it('exposes sign-in configuration', async () => {
    const res = await request(app).get('/api/auth/config')
    assert.deepEqual(res.body, { googleEnabled: false, emailDomain: 'school.edu' })
    assert.equal((await request(app).get('/api/auth/google')).status, 503)
  })
  it('signs up students with a school email only', async () => {
    const wrong = await request(app).post('/api/auth/signup').send({ name: 'New Student', email: 'new@gmail.com', password: 'long-enough-1' })
    assert.equal(wrong.status, 400)
    assert.match(wrong.body.error.message, /school\.edu/)
    const short = await request(app).post('/api/auth/signup').send({ name: 'New Student', email: 'new@school.edu', password: 'short' })
    assert.equal(short.body.error.code, 'validation_error')

    const agent = request.agent(app)
    const ok = await agent.post('/api/auth/signup').send({ name: 'New Student', email: 'New@School.edu', password: 'long-enough-1' })
    assert.equal(ok.status, 201)
    assert.equal(ok.body.user.role, 'student')
    assert.equal(ok.body.user.email, 'new@school.edu')
    assert.equal((await agent.get('/api/auth/me')).body.user.fullName, 'New Student')
    assert.equal((await agent.get('/api/students/me/dashboard')).status, 200)
    const dup = await request(app).post('/api/auth/signup').send({ name: 'Again', email: 'new@school.edu', password: 'long-enough-1' })
    assert.equal(dup.status, 400)
  })
  it('rejects bad credentials without revealing which part was wrong', async () => {
    const a = await request(app).post('/api/auth/login').send({ email: 'amara@school.edu', password: 'wrong-password' })
    const b = await request(app).post('/api/auth/login').send({ email: 'nobody@school.edu', password: 'wrong-password' })
    assert.equal(a.status, 401)
    assert.equal(a.body.error.message, b.body.error.message)
  })
  it('logs out by revoking the session', async () => {
    const agent = await signIn('jpark@school.edu')
    assert.equal((await agent.get('/api/auth/me')).status, 200)
    assert.equal((await agent.post('/api/auth/logout')).status, 204)
    assert.equal((await agent.get('/api/auth/me')).status, 401)
  })
  it('requires a TOTP code for staff and enrols the authenticator on first use', async () => {
    const agent = request.agent(app)
    const first = await agent.post('/api/auth/login').send({ email: 'mchen@school.edu', password: PASSWORD })
    assert.equal(first.body.mfaRequired, true)
    assert.match(first.body.setup.otpauthUrl, /^otpauth:\/\/totp\//)
    const wrong = await agent.post('/api/auth/2fa/verify').send({ challenge: first.body.challenge, code: '000000' })
    assert.equal(wrong.status, 400)
    const ok = await agent.post('/api/auth/2fa/verify').send({ challenge: first.body.challenge, code: generateCode(first.body.setup.secret) })
    assert.equal(ok.status, 200)
    assert.equal(ok.body.home, '/advisor')
    // Second sign-in: already enrolled, so no setup secret is shown again.
    const second = await request(app).post('/api/auth/login').send({ email: 'mchen@school.edu', password: PASSWORD })
    assert.equal(second.body.setup, null)
    // A used challenge can't be replayed.
    const replay = await request(app).post('/api/auth/2fa/verify').send({ challenge: first.body.challenge, code: generateCode(first.body.setup.secret) })
    assert.equal(replay.status, 401)
  })
  it('resets a password through an emailed one-time link', async () => {
    outbox.length = 0
    assert.equal((await request(app).post('/api/auth/password-reset').send({ email: 'nobody@school.edu' })).status, 200)
    assert.equal(outbox.length, 0)
    await request(app).post('/api/auth/password-reset').send({ email: 'kasante@school.edu' })
    assert.equal(outbox.length, 1)
    const token = resetLink(outbox[0])
    assert.equal((await request(app).get(`/api/auth/password-reset/${token}`)).body.purpose, 'reset')
    const done = await request(app).post('/api/auth/password-reset/confirm').send({ token, password: 'brand-new-pass' })
    assert.equal(done.status, 200)
    assert.equal((await request(app).post('/api/auth/password-reset/confirm').send({ token, password: 'another-pass-1' })).status, 400)
    assert.equal((await request(app).post('/api/auth/login').send({ email: 'kasante@school.edu', password: 'brand-new-pass' })).status, 200)
  })
})

describe('student', () => {
  it('returns the dashboard computed from the record', async () => {
    const { body, status } = await student.get('/api/students/me/dashboard')
    assert.equal(status, 200)
    assert.equal(body.student.firstName, 'Amara')
    assert.equal(body.stats.find((s) => s.key === 'credits').value, '21 / 36')
    assert.equal(body.stats.find((s) => s.key === 'graduation').value, 'May 2027')
    assert.equal(body.stats.find((s) => s.key === 'graduation').pill, 'Pending')
    assert.deepEqual(body.requirements.map((r) => r.count), ['2 of 2', '4 of 4', '1 done · 3 in progress', '0 of 1'])
    assert.equal(body.courses.length, 3)
    assert.equal(body.gpa.trend.at(-1).term, 'Now')
    assert.equal(body.studyHours.days.length, 7)
    assert.ok(body.tasks.length > 0)
  })
  it('lists courses, the degree audit and the plan', async () => {
    const courses = (await student.get('/api/students/me/courses')).body
    assert.deepEqual(courses.counts, { current: 3, completed: 7, planned: 2 })
    assert.equal(courses.current.find((c) => c.code === 'CS 675').parts.length, 4)
    assert.equal(courses.week.length, 5)
    assert.equal((await student.get('/api/students/me/courses?status=planned')).body.planned[0].status, 'Pending approval')
    assert.equal((await student.get('/api/students/me/courses?status=bogus')).status, 400)

    const audit = (await student.get('/api/students/me/degree-audit')).body
    assert.equal(audit.groups.length, 4)
    assert.equal(audit.stats[2].value, '6')
    assert.deepEqual(audit.stats.map((s) => s.pct), [58, 25, 83, 83])
    assert.equal(audit.stats[3].warn, true)

    const plan = (await student.get('/api/students/me/plan')).body
    assert.deepEqual(plan.terms.map((t) => t.tag), ['Done', 'Done', 'Done', 'Current', 'Planned'])
    assert.ok(plan.available.some((c) => c.code === 'CS 645'))
  })
  it('adds and removes planned courses', async () => {
    const added = await student.post('/api/students/me/plan').send({ courseCode: 'CS 645' })
    assert.equal(added.status, 201)
    assert.equal(added.body.term, 'Spring 2027')
    assert.equal((await student.post('/api/students/me/plan').send({ courseCode: 'CS 645' })).status, 409)
    assert.equal((await student.post('/api/students/me/plan').send({ courseCode: 'XX 999' })).status, 404)
    assert.equal((await student.delete(`/api/students/me/plan/${added.body.enrollmentId}`)).status, 204)
    const pending = (await student.get('/api/students/me/courses?status=planned')).body.planned[0]
    assert.equal((await student.delete(`/api/students/me/plan/${pending.enrollmentId}`)).status, 409)
  })
  it('manages calendar events and exports the calendar', async () => {
    const week = (await student.get('/api/students/me/events')).body
    assert.equal(week.days.length, 7)
    assert.ok(week.days.some((d) => d.events.some((e) => e.type === 'Class')))
    const bad = await student.post('/api/students/me/events').send({ title: 'x', type: 'Study', date: week.from, start: '14:00', end: '13:00' })
    assert.equal(bad.status, 400)
    const created = await student.post('/api/students/me/events').send({ title: 'Library session', type: 'Study', date: week.from, start: '08:00', end: '09:30', location: 'Library' })
    assert.equal(created.status, 201)
    const patched = await student.patch(`/api/students/me/events/${created.body.id}`).send({ title: 'Library session (moved)', end: '10:00' })
    assert.equal(patched.body.end, '10:00')
    const after = (await student.get(`/api/students/me/events?from=${week.from}&to=${week.from}`)).body
    assert.ok(after.days[0].events.some((e) => e.title === 'Library session (moved)'))
    assert.equal((await student.delete(`/api/students/me/events/${created.body.id}`)).status, 204)
    assert.equal((await student.delete(`/api/students/me/events/${created.body.id}`)).status, 404)

    const ics = await student.get('/api/students/me/calendar.ics')
    assert.equal(ics.status, 200)
    assert.match(ics.headers['content-type'], /text\/calendar/)
    assert.match(ics.text, /BEGIN:VCALENDAR[\s\S]*BEGIN:VEVENT/)
    const { url } = (await student.get('/api/students/me/calendar')).body
    const feed = await request(app).get(new URL(url).pathname)
    assert.equal(feed.status, 200)
    assert.match(feed.text, /X-WR-CALNAME:Acadmate/)
    const rotated = (await student.post('/api/students/me/calendar/rotate')).body.url
    assert.notEqual(rotated, url)
    assert.equal((await request(app).get(new URL(url).pathname)).status, 404)
  })
  it('lists assignments, tracks progress and submits', async () => {
    const list = (await student.get('/api/students/me/assignments')).body
    assert.equal(list.tabs[0].label, 'All')
    assert.ok(list.rows.length >= 9)
    const toDo = (await student.get('/api/students/me/assignments?status=To%20do')).body.rows
    assert.ok(toDo.every((r) => r.status === 'To do'))
    const ps4 = list.rows.find((r) => r.title === 'Problem set 4')
    const detail = (await student.get(`/api/assignments/${ps4.id}`)).body
    assert.equal(detail.steps.length, 4)
    const progress = await student.patch(`/api/assignments/${ps4.id}/progress`).send({ stepsDone: [0, 1] })
    assert.deepEqual(progress.body, { id: ps4.id, status: 'In progress', stepsDone: [0, 1] })
    assert.equal((await student.post(`/api/assignments/${ps4.id}/submit`)).body.status, 'Submitted')
    assert.equal((await student.post(`/api/assignments/${ps4.id}/submit`)).status, 409)
    // Another student's private form is invisible.
    const foreign = (await pool.query(`SELECT id FROM assignments WHERE student_id = $1`, [ids.dkowalski])).rows[0].id
    assert.equal((await student.get(`/api/assignments/${foreign}`)).status, 404)
  })
  it('submits the capstone form to the advisor with a pre-check', async () => {
    const form = (await student.get('/api/students/me/assignments')).body.rows.find((r) => r.type === 'Form')
    assert.equal((await student.post(`/api/assignments/${form.id}/submit`).send({})).status, 400)
    const res = await student.post(`/api/assignments/${form.id}/submit`).send({ fields: { 'Proposed topic': 'Course recommender', 'Project summary': 'A recommender for electives.' } })
    assert.equal(res.status, 200)
    assert.equal(res.body.precheck.ok, true)
  })
  it('shows grades and the published catalog', async () => {
    const courseId = (await student.get('/api/students/me/dashboard')).body.courses[0].courseId
    const grades = (await student.get(`/api/courses/${courseId}/grades`)).body
    assert.ok(grades.parts.length > 0)
    assert.equal((await student.get('/api/courses/99999/grades')).status, 404)
    assert.ok((await student.get('/api/catalog')).body.courses.length >= 10)
  })
})

describe('messages', () => {
  it('lists conversations, reads and replies', async () => {
    const list = (await student.get('/api/conversations')).body.conversations
    const adv = list.find((c) => c.name === 'Dr. Elena Ramirez')
    assert.ok(adv)
    const thread = (await student.get(`/api/conversations/${adv.id}/messages`)).body
    assert.equal(thread.messages.length, 3)
    assert.equal(thread.canReply, true)
    const sent = await student.post(`/api/conversations/${adv.id}/messages`).send({ text: 'See you Thursday!' })
    assert.equal(sent.status, 201)
    const advisorView = (await advisor.get('/api/conversations')).body.conversations.find((c) => c.id === adv.id)
    assert.equal(advisorView.unread, 1)
    assert.equal(advisorView.preview, 'See you Thursday!')

    const system = list.find((c) => c.kind === 'system')
    assert.equal((await student.post(`/api/conversations/${system.id}/messages`).send({ text: 'hi' })).status, 403)
    assert.equal((await student.post(`/api/conversations/${adv.id}/messages`).send({ text: '  ' })).status, 400)
    const other = (await advisor.get('/api/conversations')).body.conversations.find((c) => c.name === 'CS advising team')
    assert.equal((await student.get(`/api/conversations/${other.id}/messages`)).status, 404)
  })
  it('starts conversations within the allowed contacts', async () => {
    assert.equal((await student.post('/api/conversations').send({ recipientIds: [ids.gliu] })).status, 403)
    const contacts = (await student.get('/api/conversations/contacts?q=Jordan')).body.contacts
    const res = await student.post('/api/conversations').send({ recipientIds: [contacts[0].id], text: 'Can we talk about internships?' })
    assert.equal(res.status, 201)
    const again = await student.post('/api/conversations').send({ recipientIds: [contacts[0].id] })
    assert.equal(again.body.id, res.body.id)
  })
})

describe('meetings', () => {
  let meetingId
  it('books an open slot, prevents double-booking and runs the request flow', async () => {
    const staff = (await student.get('/api/staff?bookable=true')).body.staff
    assert.equal(staff[0].isMyAdvisor, true)
    assert.ok(staff[0].office)
    assert.ok([1, 2, 4].includes(staff[0].bookingWindowWeeks))
    const week = (await student.get(`/api/staff/${ids.eramirez}/availability`)).body
    let days = week.days
    if (!days.some((d) => d.slots.some((s) => !s.taken))) {
      const next = new Date(`${week.week}T12:00:00Z`)
      next.setUTCDate(next.getUTCDate() + 7)
      days = (await student.get(`/api/staff/${ids.eramirez}/availability?week=${next.toISOString().slice(0, 10)}`)).body.days
    }
    const slot = days.flatMap((d) => d.slots).find((s) => !s.taken)
    const body = { staffId: ids.eramirez, startsAt: slot.startsAt, format: 'Online', topic: 'Capstone topics', attachPlan: true }
    const booked = await student.post('/api/meetings').send(body)
    assert.equal(booked.status, 201)
    assert.equal(booked.body.status, 'requested')
    meetingId = booked.body.id
    const clash = await (await signIn('pshah@school.edu')).post('/api/meetings').send(body)
    assert.equal(clash.status, 409)
    assert.equal((await student.post('/api/meetings').send({ ...body, startsAt: '2020-01-01T10:00:00Z' })).status, 400)

    const requests = (await advisor.get('/api/advisors/me/meetings?range=week')).body.requests
    assert.ok(requests.some((r) => r.id === meetingId))
    const later = new Date(new Date(slot.startsAt).getTime() + 86_400_000).toISOString()
    assert.equal((await advisor.post(`/api/bookings/${meetingId}/propose`).send({ startsAt: later })).body.status, 'proposed')
    assert.equal((await student.post(`/api/meetings/${meetingId}/accept`)).body.status, 'confirmed')
    assert.equal((await advisor.post(`/api/bookings/${meetingId}/accept`)).status, 409)
    assert.equal((await advisor.put(`/api/meetings/${meetingId}/notes`).send({ notes: 'Discussed three topics.' })).body.notes, 'Discussed three topics.')
    assert.equal((await student.put(`/api/meetings/${meetingId}/notes`).send({ notes: 'x' })).status, 403)
    const mine = (await student.get('/api/students/me/meetings')).body.meetings
    assert.ok(mine.some((m) => m.id === meetingId))
    assert.equal((await student.post(`/api/meetings/${meetingId}/cancel`)).body.status, 'cancelled')
  })
  it('lets advisors accept or decline new requests', async () => {
    const requests = (await advisor.get('/api/advisors/me/meetings?range=week')).body.requests.filter((r) => r.status === 'requested')
    assert.equal((await advisor.post(`/api/bookings/${requests[0].id}/accept`)).body.status, 'confirmed')
    assert.equal((await advisor.post(`/api/bookings/${requests[1].id}/decline`).send({ reason: 'Please pick a Wednesday.' })).body.status, 'declined')
  })
})

describe('account settings', () => {
  it('reads and updates profile and preferences', async () => {
    const me = (await student.get('/api/users/me')).body
    assert.equal(me.profile.program, 'M.S. Computer Science')
    assert.equal(me.google.available, false)
    assert.equal(me.preferences.aiStyle, 'Concise')
    assert.equal((await student.patch('/api/users/me').send({ preferredName: 'Mara' })).body.user.firstName, 'Mara')
    assert.equal((await student.patch('/api/users/me').send({ email: 'amara@gmail.com' })).status, 400)
    const prefs = (await student.patch('/api/users/me/preferences').send({ notify: { sms: true }, aiStyle: 'Detailed' })).body.preferences
    assert.equal(prefs.notify.sms, true)
    assert.equal(prefs.notify.deadlines, true)
    assert.equal((await student.patch('/api/users/me/preferences').send({ notify: { bogus: true } })).status, 400)
    assert.equal((await student.post('/api/users/me/google/connect')).status, 400)
  })
  it('changes the password and signs out other devices', async () => {
    const other = await signIn('gliu@school.edu')
    const self = await signIn('gliu@school.edu')
    assert.equal((await self.post('/api/users/me/password').send({ currentPassword: 'nope', newPassword: 'another-pass-1' })).status, 400)
    assert.equal((await self.post('/api/users/me/password').send({ currentPassword: PASSWORD, newPassword: 'another-pass-1' })).status, 200)
    assert.equal((await self.get('/api/auth/me')).status, 200)
    assert.equal((await other.get('/api/auth/me')).status, 401)
  })
  it('exports data, shows badges and deletes a student account', async () => {
    const exported = await student.post('/api/users/me/export')
    assert.match(exported.headers['content-disposition'], /acadmate-export\.json/)
    assert.equal(exported.body.user.email, 'amara@school.edu')
    const badges = (await student.get('/api/users/me/badges')).body.badges
    assert.equal(typeof badges.messages, 'number')
    assert.equal(typeof badges.assignments, 'number')
    assert.equal((await advisor.get('/api/users/me/badges')).body.badges.advisees, 8)

    const doomed = await signIn('nkim@school.edu')
    assert.equal((await doomed.delete('/api/users/me').send({ password: 'wrong' })).status, 401)
    assert.equal((await doomed.delete('/api/users/me').send({ password: PASSWORD })).status, 204)
    assert.equal((await request(app).post('/api/auth/login').send({ email: 'nkim@school.edu', password: PASSWORD })).status, 401)
    assert.equal((await advisor.delete('/api/users/me').send({ password: PASSWORD })).status, 403)
  })
})

describe('advisor', () => {
  it('shows the dashboard, advisees and a student record', async () => {
    const dash = (await advisor.get('/api/advisors/me/dashboard')).body
    assert.equal(dash.stats[0].value, '8')
    assert.ok(dash.queue.length >= 5)
    assert.ok(dash.attention.some((a) => a.name === 'Marcus T.'))
    const lina = dash.queue.find((q) => q.name === 'Lina H.')
    assert.equal(lina.ok, false)
    assert.match(lina.check, /CS 691 requires CS 610/)

    const advisees = (await advisor.get('/api/advisors/me/advisees')).body
    assert.equal(advisees.tabs[0].count, 8)
    assert.ok((await advisor.get('/api/advisors/me/advisees?status=Graduating')).body.rows.some((r) => r.name === 'Sofia R.'))
    assert.equal((await advisor.get('/api/advisors/me/advisees?q=priya')).body.rows.length, 1)

    const record = (await advisor.get(`/api/students/${ids.amara}/record`)).body
    assert.equal(record.student.name, 'Amara Okafor')
    assert.equal(record.approval.status, 'Pending')
    assert.ok(record.notes.length >= 1)
    assert.equal((await advisor.get(`/api/students/${ids.gliu}/record`)).status, 404)
    assert.equal((await advisor.post(`/api/students/${ids.amara}/notes`).send({ text: 'Follow up on capstone form.' })).status, 201)
  })
  it('approves, requests changes and reopens with side effects on the student record', async () => {
    const pending = (await advisor.get('/api/approvals')).body
    assert.equal(pending.tabs[0].label, 'Pending')
    const amaraPlan = pending.rows.find((r) => r.name === 'Amara O.' && r.type === 'Course plan')
    assert.equal(amaraPlan.ok, true)

    const approved = await advisor.post(`/api/approvals/${amaraPlan.id}/approve`).send({})
    assert.equal(approved.body.status, 'Approved')
    const dash = (await student.get('/api/students/me/dashboard')).body
    assert.equal(dash.stats.find((s) => s.key === 'graduation').pill, 'Confirmed')
    assert.equal((await advisor.post(`/api/approvals/${amaraPlan.id}/approve`)).status, 409)
    assert.equal((await advisor.post(`/api/approvals/${amaraPlan.id}/reopen`)).body.status, 'Pending')
    assert.equal((await student.get('/api/students/me/dashboard')).body.stats.find((s) => s.key === 'graduation').pill, 'Pending')

    const marcus = pending.rows.find((r) => r.name === 'Marcus T.')
    assert.equal((await advisor.post(`/api/approvals/${marcus.id}/request-changes`).send({})).status, 400)
    const changed = await advisor.post(`/api/approvals/${marcus.id}/request-changes`).send({ comment: 'Let’s talk about full-time status first.' })
    assert.equal(changed.body.status, 'Changes requested')
    assert.equal((await advisor.get('/api/approvals?status=Changes%20requested')).body.rows.length, 1)
    assert.equal((await (await signIn('mchen@school.edu')).get(`/api/approvals/${marcus.id}`)).status, 404)
  })
  it('manages office hours, reports and settings', async () => {
    const hours = await advisor.put('/api/advisors/me/office-hours').send({ slots: [{ day: 'Wed', start: '16:30', end: '17:30' }, { day: 'Fri', start: '12:00', end: '13:00' }] })
    assert.equal(hours.body.summary, 'Wed · 16:30–17:30, Fri · 12:00–13:00')
    assert.equal((await advisor.put('/api/advisors/me/office-hours').send({ slots: [{ day: 'Wed', start: '17:00', end: '16:00' }] })).status, 400)

    const report = (await advisor.get('/api/advisors/me/reports')).body
    assert.equal(report.term, 'Fall 2026')
    assert.equal(report.stats[0].value, '8')
    assert.ok(report.weeks.length > 0)
    const csv = await advisor.get('/api/advisors/me/reports.csv')
    assert.match(csv.text, /^Student,Email,Program/)

    const settings = (await advisor.get('/api/advisors/me/settings')).body
    assert.equal(settings.meetingLength, 30)
    const updated = (await advisor.patch('/api/advisors/me/settings').send({ meetingLength: 45, notify: { weeklyDigest: false } })).body
    assert.equal(updated.meetingLength, 45)
    assert.equal(updated.notify.weeklyDigest, false)
    assert.equal((await advisor.patch('/api/advisors/me/settings').send({ meetingLength: 50 })).status, 400)
  })
})

describe('admin', () => {
  it('shows the overview and exports it', async () => {
    const overview = (await admin.get('/api/admin/overview')).body
    assert.equal(overview.stats.length, 4)
    assert.ok(overview.flags.length >= 4)
    assert.ok(overview.advisors.some((a) => a.name === 'Dr. Elena Ramirez'))
    const csv = await admin.get('/api/admin/overview/report')
    assert.match(csv.text, /^Section,Name,Value,Detail/)
  })
  it('manages users, invites and CSV imports', async () => {
    const list = (await admin.get('/api/admin/users?role=student')).body
    assert.ok(list.rows.every((r) => r.role === 'Student'))
    assert.ok((await admin.get('/api/admin/users?q=okafor')).body.rows.some((r) => r.email === 'amara@school.edu'))

    const patched = await admin.patch(`/api/admin/users/${ids.srivera}`).send({ advisorId: ids.eramirez })
    assert.equal(patched.body.advisor, 'Dr. Elena Ramirez')
    assert.equal((await admin.patch(`/api/admin/users/${ids.admin}`).send({ role: 'student' })).status, 400)
    const deactivated = await admin.patch(`/api/admin/users/${ids.jpark}`).send({ status: 'deactivated' })
    assert.equal(deactivated.body.status, 'Deactivated')
    assert.equal((await request(app).post('/api/auth/login').send({ email: 'jpark@school.edu', password: PASSWORD })).status, 401)

    outbox.length = 0
    const invites = (await admin.post('/api/admin/invites').send({ emails: ['fresh.person@school.edu', 'amara@school.edu'], role: 'student' })).body
    assert.deepEqual(invites, { invited: ['fresh.person@school.edu'], skipped: ['amara@school.edu'] })
    const token = resetLink(outbox[0])
    assert.equal((await request(app).get(`/api/auth/password-reset/${token}`)).body.purpose, 'invite')
    await request(app).post('/api/auth/password-reset/confirm').send({ token, password: 'invited-pass-1' })
    assert.equal((await request(app).post('/api/auth/login').send({ email: 'fresh.person@school.edu', password: 'invited-pass-1' })).status, 200)

    const imported = await admin.post('/api/admin/imports/users').set('content-type', 'text/csv')
      .send('email,name,role,program,advisor_email\nimported@school.edu,Imported Person,student,M.S. Data Science,mchen@school.edu\nbad-email,,student,,\n')
    assert.equal(imported.body.created, 1)
    assert.equal(imported.body.errors.length, 1)
    assert.equal((await admin.post(`/api/admin/users/${ids.amara}/password-reset`)).body.sent, 'reset')
  })
  it('manages advisors and reassigns advisees', async () => {
    const added = await admin.post('/api/admin/advisors').send({ name: 'Dr. New Advisor', email: 'newadvisor@school.edu', department: 'Data Science', capacity: 30 })
    assert.equal(added.status, 201)
    assert.equal((await admin.post('/api/admin/advisors').send({ name: 'Dup', email: 'newadvisor@school.edu', department: 'X' })).status, 409)
    const moved = await admin.post(`/api/admin/advisors/${ids.eramirez}/reassign`).send({ targetId: ids.ladeyemi, count: 1 })
    assert.equal(moved.body.moved, 1)
    const rows = (await admin.get('/api/admin/advisors')).body.rows
    assert.equal(rows.find((r) => r.name === 'Dr. Lola Adeyemi').load, 1)
  })
  it('edits the catalog, requirements and term dates, then publishes', async () => {
    const courses = (await admin.get('/api/admin/courses?type=Core')).body.courses
    assert.ok(courses.every((c) => c.type === 'Core'))
    const patched = await admin.patch(`/api/admin/courses/${encodeURIComponent('CS 612')}`).send({ offered: true, offerTerm: 'Spring 2027' })
    assert.equal(patched.body.offer, 'Spring 2027')
    const created = await admin.post('/api/admin/courses').send({ code: 'CS 699', name: 'Independent Study', type: 'Elective', prereqs: ['CS 610'] })
    assert.deepEqual(created.body.prereqs, ['CS 610'])
    assert.equal((await admin.post('/api/admin/courses').send({ code: 'CS 698', name: 'X', type: 'Elective', prereqs: ['NOPE 1'] })).status, 400)

    const programs = (await admin.get('/api/admin/programs')).body.programs
    assert.equal(programs[0].totalCredits, 36)
    const req = await admin.put(`/api/admin/programs/${programs[0].id}/requirements`).send({ groups: [{ courseType: 'Elective', requiredCount: 6 }] })
    assert.equal(req.body.totalCredits, 39)

    const terms = (await admin.get('/api/admin/terms')).body.terms
    const spring = terms.find((t) => t.name === 'Spring 2027')
    const dates = await admin.put(`/api/admin/terms/${spring.id}/dates`).send({ registrationOpens: '2026-11-04', lastAdd: '2027-01-29', lastDrop: '2027-03-12', classesBegin: '2027-01-20' })
    assert.equal(dates.body.dates[0].value, '2026-11-04')
    assert.equal((await admin.put(`/api/admin/terms/${spring.id}/dates`).send({ registrationOpens: null, lastAdd: '2027-03-01', lastDrop: '2027-01-01', classesBegin: null })).status, 400)

    const published = await admin.post('/api/admin/catalog/publish')
    assert.equal(published.status, 201)
    assert.ok((await student.get('/api/catalog')).body.courses.some((c) => c.code === 'CS 699'))

    const csv = await admin.post('/api/admin/imports/courses').set('content-type', 'text/csv').send('code,name,type,credits\nCS 700,Thesis,Capstone,6\n')
    assert.equal(csv.body.created, 1)
    const grades = await admin.post('/api/admin/imports/grades').set('content-type', 'text/csv')
      .send('student_email,course_code,term,status,grade\ngliu@school.edu,CS 630,Fall 2026,completed,A\nnobody@school.edu,CS 630,Fall 2026,completed,A\n')
    assert.equal(grades.body.created, 1)
    assert.equal(grades.body.errors.length, 1)
  })
  it('manages AI settings, flags, integrations and API keys', async () => {
    const ai = (await admin.patch('/api/admin/ai/settings').send({ features: { proactiveTips: false }, blockedTopics: ['Visa and immigration'] })).body
    assert.equal(ai.features.proactiveTips, false)
    assert.equal(ai.features.advisor, true)
    assert.deepEqual(ai.blockedTopics, ['Visa and immigration'])
    const flags = (await admin.get('/api/admin/ai/flags?status=Open')).body.flags
    assert.equal((await admin.post(`/api/admin/ai/flags/${flags[0].id}/resolve`).send({ resolution: 'Dismissed' })).body.status, 'Dismissed')
    assert.equal((await admin.post(`/api/admin/ai/flags/${flags[0].id}/resolve`).send({})).status, 404)

    const integrations = (await admin.post('/api/admin/integrations/gcal/connect')).body
    assert.equal(integrations.apps.find((a) => a.id === 'gcal').connected, true)
    assert.equal((await admin.post('/api/admin/integrations/mail/connect')).status, 400)
    assert.equal((await admin.post('/api/admin/integrations/mail/sync')).body.test.ok, false)

    const key = (await admin.post('/api/admin/api-keys').send({ name: 'Reporting export' })).body
    assert.match(key.key, /^acm_/)
    const viaKey = await request(app).get('/api/admin/audit.csv').set('Authorization', `Bearer ${key.key}`)
    assert.equal(viaKey.status, 200)
    assert.match(viaKey.text, /^Time \(UTC\),Actor/)
    assert.equal((await request(app).get('/api/admin/users').set('Authorization', `Bearer ${key.key}`)).status, 403)
    assert.equal((await admin.delete(`/api/admin/api-keys/${key.id}`)).status, 204)
    assert.equal((await request(app).get('/api/admin/audit.csv').set('Authorization', `Bearer ${key.key}`)).status, 401)
  })
  it('filters the audit log and shows event details', async () => {
    const log = (await admin.get('/api/admin/audit?role=Advisor&since=7d')).body
    assert.ok(log.rows.length > 0)
    assert.ok(log.rows.every((r) => r.role === 'Advisor'))
    assert.ok((await admin.get('/api/admin/audit?q=Approved')).body.rows.some((r) => /Approved/.test(r.action)))
    const detail = (await admin.get(`/api/admin/audit/${log.rows[0].id}`)).body
    assert.equal(detail.detail[3].k, 'Event ID')
  })
  it('updates institution settings and guards the demo reset', async () => {
    const settings = (await admin.get('/api/admin/settings')).body
    assert.equal(settings.institution.emailDomain, 'school.edu')
    const updated = (await admin.patch('/api/admin/settings').send({ security: { sessionTimeout: '8 hours' }, institution: { timeZone: 'Pacific' } })).body
    assert.equal(updated.security.sessionTimeout, '8 hours')
    assert.equal(updated.security.staffTwoStep, true)
    assert.equal(updated.institution.timeZone, 'Pacific')
    assert.equal((await admin.patch('/api/admin/settings').send({ institution: { emailDomain: 'not a domain' } })).status, 400)
    assert.equal((await admin.post('/api/admin/demo/reset').send({ confirm: 'RESET' })).status, 403)
  })
})
