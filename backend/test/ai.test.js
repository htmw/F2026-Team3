import assert from 'node:assert/strict'
import { after, before, describe, it } from 'node:test'
import Anthropic from '@anthropic-ai/sdk'
import request from 'supertest'
import { pool } from '../src/db/pool.js'
import { resetDemo } from '../src/db/seed.js'
import { getSetting } from '../src/lib/settings.js'
import { loadStudent } from '../src/services/academics.js'
import { answer } from '../src/services/ai/index.js'
import { purgeAiHistory } from '../src/services/ai/retention.js'
import { app, signIn } from './helpers.js'

// AI advisor (spec 03) against a freshly seeded test database. Tests have no Anthropic key, so the API
// answers with the rule-based engine; the Claude engine is exercised with a stubbed client.

const ai = '/api/students/me/ai'
let student
let other
let advisor
let admin
const ids = {}
let threadId
let answerId

before(async () => {
  await resetDemo({ log: () => {} })
  student = await signIn('amara@school.edu')
  other = await signIn('dkowalski@school.edu')
  advisor = await signIn('eramirez@school.edu')
  admin = await signIn('admin@school.edu')
  for (const r of (await pool.query('SELECT id, email FROM users')).rows) ids[r.email.split('@')[0]] = r.id
})

after(() => pool.end())

const ask = async (text) => (await student.post(`${ai}/threads/${threadId}/messages`).send({ text })).body.reply

describe('AI advisor API', () => {
  it('is for students only, and each student sees only their own conversations', async () => {
    assert.equal((await request(app).get(`${ai}/threads`)).status, 401)
    assert.equal((await advisor.get(`${ai}/threads`)).status, 403)
    assert.equal((await admin.post(`${ai}/threads`).send({ text: 'hi' })).status, 403)
    const seeded = (await student.get(`${ai}/threads`)).body.threads
    assert.equal(seeded.length, 1)
    assert.equal(seeded[0].title, 'Am I on track to graduate?')
    assert.equal((await student.get(`${ai}/threads/${seeded[0].id}`)).body.messages.length, 4)
    assert.equal((await other.get(`${ai}/threads`)).body.threads.length, 0)
    assert.equal((await other.get(`${ai}/threads/${seeded[0].id}`)).status, 404)
    assert.equal((await other.post(`${ai}/threads/${seeded[0].id}/messages`).send({ text: 'hi' })).status, 404)
  })

  it('describes what it uses', async () => {
    const ctx = (await student.get(`${ai}/context`)).body
    assert.equal(ctx.enabled, true)
    assert.equal(ctx.engine, 'Rules')
    assert.equal(ctx.goal, 'Graduate May 2027')
    assert.deepEqual(ctx.sources, ['Degree audit', 'Course catalog', 'Grades', 'Schedule'])
    assert.equal(ctx.remainingToday, ctx.dailyLimit)
    assert.equal(ctx.prompts.length, 4)
  })

  it('answers from the student\'s records in a new conversation', async () => {
    const created = await student.post(`${ai}/threads`).send({ text: 'Am I on track to graduate?' })
    assert.equal(created.status, 201)
    const [question, reply] = created.body.messages
    assert.equal(question.role, 'user')
    assert.equal(reply.role, 'ai')
    assert.equal(reply.kind, 'answer')
    assert.match(reply.text, /May 2027/)
    assert.ok(reply.sources.includes('Degree audit'))
    threadId = created.body.thread.id

    const next = await student.post(`${ai}/threads/${threadId}/messages`).send({ text: 'Plan my next semester' })
    assert.equal(next.status, 201)
    assert.deepEqual(next.body.reply.plan.map((p) => p.code), ['CS 640', 'CS 691'])
    assert.equal(next.body.reply.plan[1].fulfills, 'Capstone')
    assert.ok(next.body.reply.actions.some((a) => a.to === '/student/degree-plan'))
    answerId = next.body.reply.id

    assert.equal((await student.get(`${ai}/threads/${threadId}`)).body.messages.length, 4)
    assert.equal((await student.get(`${ai}/threads`)).body.threads[0].id, threadId)
    assert.equal((await student.get(`${ai}/context`)).body.remainingToday, 38)
  })

  it('hands blocked topics to a person and admits what it cannot answer', async () => {
    const visa = await ask('Can you help with my visa paperwork?')
    assert.equal(visa.kind, 'handoff')
    assert.deepEqual(visa.actions, [{ label: 'Book a meeting', to: '/student/book-meeting' }])
    assert.deepEqual(visa.sources, [])
    assert.equal((await ask('What is the meaning of life?')).kind, 'fallback')
  })

  it('validates input', async () => {
    assert.equal((await student.get(`${ai}/threads/not-a-uuid`)).status, 400)
    assert.equal((await student.get(`${ai}/threads/00000000-0000-4000-8000-000000000000`)).status, 404)
    assert.equal((await student.post(`${ai}/threads/${threadId}/messages`).send({ text: '   ' })).status, 400)
    assert.equal((await student.post(`${ai}/threads/${threadId}/messages`).send({ text: 'x'.repeat(1001) })).status, 400)
    assert.equal((await student.post(`${ai}/threads/${threadId}/messages`).send({ text: 'hi', model: 'other' })).status, 400)
  })

  it('follows the school\'s AI settings and the student\'s data choices', async () => {
    await admin.patch('/api/admin/ai/settings').send({ sources: { grades: false } })
    const gpa = await ask('What is my GPA?')
    assert.equal(gpa.kind, 'handoff')
    assert.match(gpa.text, /school/)
    await admin.patch('/api/admin/ai/settings').send({ sources: { grades: true } })
    assert.match((await ask('What is my GPA?')).text, /cumulative GPA/)

    await student.patch('/api/users/me/preferences').send({ ai: { useSchedule: false } })
    const schedule = await ask('What is on my schedule this week?')
    assert.equal(schedule.kind, 'handoff')
    assert.match(schedule.text, /Settings/)
    assert.ok(!(await student.get(`${ai}/context`)).body.sources.includes('Schedule'))
    await student.patch('/api/users/me/preferences').send({ ai: { useSchedule: true } })

    await admin.patch('/api/admin/ai/settings').send({ features: { advisor: false } })
    assert.equal((await student.post(`${ai}/threads/${threadId}/messages`).send({ text: 'Am I on track?' })).status, 503)
    assert.equal((await student.get(`${ai}/context`)).body.enabled, false)
    await admin.patch('/api/admin/ai/settings').send({ features: { advisor: true } })

    await admin.patch('/api/admin/ai/settings').send({ dailyLimit: 1 })
    const limited = await student.post(`${ai}/threads/${threadId}/messages`).send({ text: 'Am I on track?' })
    assert.equal(limited.status, 429)
    assert.equal(limited.body.error.code, 'rate_limited')
    await admin.patch('/api/admin/ai/settings').send({ dailyLimit: 40 })

    assert.equal((await admin.get('/api/admin/ai/settings')).body.claudeAvailable, false)
    assert.equal((await admin.patch('/api/admin/ai/settings').send({ engine: 'Claude' })).status, 400)
    assert.equal((await admin.patch('/api/admin/ai/settings').send({ engine: 'Rules' })).body.engine, 'Rules')
  })

  it('uses the student\'s reply style over the school\'s', async () => {
    await admin.patch('/api/admin/ai/settings').send({ style: 'Concise' })
    assert.equal((await ask('Am I on track to graduate?')).follow, null)
    await student.patch('/api/users/me/preferences').send({ aiStyle: 'Detailed' })
    const detailed = await ask('Am I on track to graduate?')
    assert.match(detailed.text, /credits/)
    assert.ok(detailed.follow)
    await admin.patch('/api/admin/ai/settings').send({ style: 'Balanced' })
  })

  it('collects ratings and reports for admin review', async () => {
    assert.equal((await student.post(`${ai}/messages/${answerId}/rating`).send({ helpful: true })).status, 204)
    assert.equal((await other.post(`${ai}/messages/${answerId}/rating`).send({ helpful: false })).status, 404)
    assert.equal((await student.post(`${ai}/messages/${answerId - 1}/rating`).send({ helpful: true })).status, 404) // a question, not an answer
    const flag = await student.post(`${ai}/messages/${answerId}/flag`).send({ issue: 'CS 691 is not offered in Spring.' })
    assert.equal(flag.status, 201)

    const mine = (await admin.get('/api/admin/ai/flags?status=Open')).body.flags.find((f) => f.id === flag.body.id)
    assert.equal(mine.q, 'Plan my next semester')
    assert.equal(mine.messageId, answerId)
    assert.equal(mine.student, 'Amara Okafor')
    assert.match(mine.answer, /May 2027/)

    const overview = (await admin.get('/api/admin/overview')).body
    assert.ok(overview.aiQuestions.value >= 8)
    assert.equal(overview.aiQuality[0].pct, 100)
    assert.ok(overview.aiQuality[1].pct > 0)
    assert.ok(overview.aiQuality[2].pct > 0)
  })

  it('lets an admin test an answer without storing it', async () => {
    const count = async () => Number((await pool.query('SELECT count(*) FROM ai_messages')).rows[0].count)
    const before = await count()
    await admin.patch('/api/admin/ai/settings').send({ features: { advisor: false } })
    const test = await admin.post('/api/admin/ai/test').send({ question: 'Am I on track to graduate?', studentId: ids.amara, settings: { blockedTopics: [] } })
    assert.equal(test.status, 200)
    assert.match(test.body.reply.text, /May 2027/)
    assert.equal(test.body.engine, 'Rules')
    assert.equal(test.body.advisorOn, false)
    const blocked = await admin.post('/api/admin/ai/test').send({ question: 'What about my thesis?', studentId: ids.amara, settings: { blockedTopics: ['Thesis topics'] } })
    assert.equal(blocked.body.reply.kind, 'handoff')
    await admin.patch('/api/admin/ai/settings').send({ features: { advisor: true } })
    assert.equal(await count(), before)
    assert.equal((await admin.post('/api/admin/ai/test').send({ question: 'hi', studentId: '00000000-0000-4000-8000-000000000000' })).status, 404)
    assert.equal((await advisor.post('/api/admin/ai/test').send({ question: 'hi', studentId: ids.amara })).status, 403)
  })

  it('shares conversations with the advisor only when the student opts in', async () => {
    const url = `/api/students/${ids.amara}/ai/threads`
    assert.deepEqual((await advisor.get(url)).body, { shared: false, threads: [] })
    await student.patch('/api/users/me/preferences').send({ ai: { shareWithAdvisor: true } })
    const shared = (await advisor.get(url)).body
    assert.equal(shared.shared, true)
    assert.ok(shared.threads.find((t) => t.id === threadId).messages.length >= 4)
    const notMine = (await pool.query(`SELECT user_id FROM student_profiles WHERE advisor_id IS DISTINCT FROM $1 LIMIT 1`, [ids.eramirez])).rows[0].user_id
    assert.equal((await advisor.get(`/api/students/${notMine}/ai/threads`)).status, 404)
    assert.equal((await student.get(url)).status, 403)
    await student.patch('/api/users/me/preferences').send({ ai: { shareWithAdvisor: false } })
  })

  it('switches dashboard tips with the school and student settings', async () => {
    assert.ok((await student.get('/api/students/me/dashboard')).body.recommendation.text)
    await admin.patch('/api/admin/ai/settings').send({ features: { proactiveTips: false } })
    assert.equal((await student.get('/api/students/me/dashboard')).body.recommendation, null)
    await admin.patch('/api/admin/ai/settings').send({ features: { proactiveTips: true } })
    await student.patch('/api/users/me/preferences').send({ ai: { dashboardSuggestions: false } })
    assert.equal((await student.get('/api/students/me/dashboard')).body.recommendation, null)
    await student.patch('/api/users/me/preferences').send({ ai: { dashboardSuggestions: true } })
  })

  it('deletes conversations and purges expired history', async () => {
    assert.equal((await student.delete(`${ai}/threads/${threadId}`)).status, 204)
    assert.equal((await student.get(`${ai}/threads/${threadId}`)).status, 404)
    const old = (await other.post(`${ai}/threads`).send({ text: 'What do I still need?' })).body.thread
    await pool.query(`UPDATE ai_threads SET updated_at = now() - interval '2 years' WHERE id = $1`, [old.id])
    assert.ok((await purgeAiHistory()) >= 1)
    assert.equal((await other.get(`${ai}/threads`)).body.threads.length, 0)
    assert.equal((await student.delete(`${ai}/threads`)).status, 204)
    assert.equal((await student.get(`${ai}/threads`)).body.threads.length, 0)
  })
})

describe('AI advisor with Claude (stubbed client)', () => {
  const tz = 'America/New_York'
  const today = '2026-10-11'
  let params
  // A fake Anthropic client whose tool runner yields the messages `script` returns.
  const client = (script) => ({
    beta: { messages: { toolRunner: (p) => { params = p; return { async* [Symbol.asyncIterator]() { yield* await script(p) } } } } },
  })
  const message = (content, stop_reason = 'end_turn') => ({ model: 'claude-test', stop_reason, content, usage: { input_tokens: 100, output_tokens: 20, cache_read_input_tokens: 50 } })
  const json = (body) => [{ type: 'text', text: JSON.stringify({ follow: null, handoff: false, plan: [], ...body }) }]
  const engine = (script) => ({ claude: { model: 'claude-test', effort: 'low', client: client(script) } })

  it('grounds plans in real courses and reports the data it read', async () => {
    const ctx = await loadStudent(ids.amara)
    const settings = await getSetting('ai')
    const reply = await answer({ ctx, text: 'Am I on track?', settings, tz, today }, engine(async (p) => {
      await p.tools.find((t) => t.name === 'get_progress_summary').run({})
      return [message(json({ text: 'Yes, May 2027.', plan: [{ code: 'CS 640', why: 'Planned' }, { code: 'ZZ 999', why: 'Made up' }, { code: 'CS 502', why: 'Taken' }] }))]
    }))
    assert.equal(reply.engine, 'claude')
    assert.equal(reply.text, 'Yes, May 2027.')
    assert.deepEqual(reply.plan.map((p) => [p.code, p.name]), [['CS 640', 'Machine Learning']]) // unknown and completed courses dropped
    assert.deepEqual(reply.sources, ['Degree audit'])
    assert.deepEqual(reply.usage, { input: 150, output: 20, cacheRead: 50 })
    assert.equal(params.model, 'claude-test')
    assert.equal(params.system[0].cache_control.type, 'ephemeral')
    assert.equal(params.fallbacks, 'default')
    assert.equal(params.output_config.effort, 'low')
    assert.ok(params.tools.some((t) => t.name === 'get_gpa_trend'))
  })

  it('offers only permitted tools and turns refusals into a handoff', async () => {
    const ctx = await loadStudent(ids.amara)
    const settings = await getSetting('ai')
    const noGrades = { ...settings, sources: { ...settings.sources, grades: false } }
    const refused = await answer({ ctx, text: 'Am I on track?', settings: noGrades, tz, today }, engine(async () => [message([], 'refusal')]))
    assert.equal(refused.kind, 'handoff')
    assert.ok(!params.tools.some((t) => t.name === 'get_gpa_trend'))
  })

  it('never sends blocked topics to Claude', async () => {
    const ctx = await loadStudent(ids.amara)
    const settings = await getSetting('ai')
    const blocked = await answer({ ctx, text: 'I need help with my visa', settings, tz, today }, engine(async () => assert.fail('blocked topics must not reach Claude')))
    assert.equal(blocked.kind, 'handoff')
  })

  it('falls back to rule-based answers when Claude fails', async () => {
    const ctx = await loadStudent(ids.amara)
    const settings = await getSetting('ai')
    const down = await answer({ ctx, text: 'Am I on track to graduate?', settings, tz, today },
      engine(async () => { throw new Anthropic.APIConnectionError({ message: 'network down' }) }))
    assert.equal(down.engine, 'rules')
    assert.match(down.text, /May 2027/)
    const cut = await answer({ ctx, text: 'Am I on track to graduate?', settings, tz, today }, engine(async () => [message(json({ text: 'partial' }), 'max_tokens')]))
    assert.equal(cut.engine, 'rules')
  })
})
