import { Router } from 'express'
import { z } from 'zod'
import { many, one, query, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { ApiError, notFound } from '../lib/errors.js'
import { mergedPreferences, replyStyle } from '../lib/preferences.js'
import { getSetting, timeZone } from '../lib/settings.js'
import { localDate, zonedTime } from '../lib/time.js'
import { requireRole } from '../middleware/auth.js'
import { aiLimiter } from '../middleware/security.js'
import { credits, graduation, loadStudent } from '../services/academics.js'
import { answer, threadTitle, usesClaude } from '../services/ai/index.js'
import { SOURCE_LABELS, sourceBlock } from '../services/ai/tools.js'

// The student's AI advisor (spec 03). Mounted at /api/students/me/ai, ahead of the main student router.
const router = Router()
router.use(requireRole('student'))
router.use(async (req, res, next) => {
  req.ctx = await loadStudent(req.user.id)
  if (!req.ctx) throw notFound('Student profile')
  req.tz = await timeZone()
  req.today = localDate(new Date(), req.tz)
  next()
})

const PROMPTS = ['Am I on track to graduate?', 'Plan my next semester', 'Compare my elective options', 'What do I still need?']
const questionText = z.string().trim().min(1, 'Type a question first.').max(1000, 'Keep questions under 1000 characters.')
const threadId = (req) => z.uuid().parse(req.params.id)
const messageId = (req) => z.coerce.number().int().positive().parse(req.params.id)

const toThread = (t) => ({ id: t.id, title: t.title, updatedAt: t.updated_at })
export function toMessage(m) {
  const a = m.attachments ?? {}
  return {
    id: Number(m.id), role: m.role, text: m.body, kind: m.kind,
    plan: a.plan ?? [], follow: a.follow ?? null, sources: a.sources ?? [], actions: a.actions ?? [],
    rating: m.rating ?? null, createdAt: m.created_at,
  }
}

async function ownThread(req) {
  const thread = await one('SELECT * FROM ai_threads WHERE id = $1 AND student_id = $2', [threadId(req), req.user.id])
  if (!thread) throw notFound('Conversation')
  return thread
}

async function askedToday(req) {
  const since = zonedTime(req.today, '00:00', req.tz)
  const row = await one(
    `SELECT count(*)::int AS n FROM ai_messages m JOIN ai_threads t ON t.id = m.thread_id
      WHERE t.student_id = $1 AND m.role = 'user' AND m.created_at >= $2`, [req.user.id, since])
  return row.n
}

// Answers one question in a thread (creating the thread when `thread` is null) and stores both messages.
async function ask(req, thread, text) {
  const settings = await getSetting('ai')
  if (settings.features.advisor && (await askedToday(req)) >= settings.dailyLimit) {
    throw new ApiError(429, 'rate_limited', `You've reached today's limit of ${settings.dailyLimit} questions. Try again tomorrow, or message your advisor.`)
  }
  const history = thread ? await many('SELECT role, body FROM ai_messages WHERE thread_id = $1 ORDER BY id', [thread.id]) : []
  const reply = await answer({ ctx: req.ctx, text, history, settings, tz: req.tz, today: req.today })

  return transaction(async (db) => {
    const saved = thread ?? (await db.query('INSERT INTO ai_threads (student_id, title) VALUES ($1, $2) RETURNING *', [req.user.id, threadTitle(text)])).rows[0]
    const question = (await db.query(
      `INSERT INTO ai_messages (thread_id, role, body) VALUES ($1, 'user', $2) RETURNING *`, [saved.id, text])).rows[0]
    const stored = (await db.query(
      `INSERT INTO ai_messages (thread_id, role, body, kind, attachments, engine, model, input_tokens, output_tokens, latency_ms)
       VALUES ($1, 'ai', $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *`,
      [saved.id, reply.text, reply.kind, JSON.stringify({ plan: reply.plan, follow: reply.follow, sources: reply.sources, actions: reply.actions }),
        reply.engine, reply.model, reply.usage?.input ?? null, reply.usage?.output ?? null, reply.latencyMs ?? null])).rows[0]
    const updated = (await db.query('UPDATE ai_threads SET updated_at = now() WHERE id = $1 RETURNING *', [saved.id])).rows[0]
    return { thread: toThread(updated), userMessage: toMessage(question), reply: toMessage(stored) }
  })
}

// ------------------------------------------------------------------ context

router.get('/context', async (req, res) => {
  const { ctx } = req
  const [settings, retention] = await Promise.all([getSetting('ai'), getSetting('retention')])
  const prefs = mergedPreferences(ctx.user.preferences)
  const credit = credits(ctx)
  const grad = graduation(ctx)
  const used = settings.features.advisor ? await askedToday(req) : 0
  res.json({
    enabled: Boolean(settings.features.advisor),
    engine: usesClaude(settings) ? 'Claude' : 'Rules',
    program: ctx.user.program,
    progress: `${credit.earned} credits earned · ${credit.inProgress} in progress`,
    goal: grad.covered ? `Graduate ${grad.label}` : 'Plan not complete yet',
    preferences: [
      ctx.user.preferences?.classTime,
      `${replyStyle(ctx.user.preferences, settings.style)} answers`,
    ].filter(Boolean),
    sources: Object.keys(SOURCE_LABELS).filter((s) => !sourceBlock(s, { settings, prefs })).map((s) => SOURCE_LABELS[s]),
    advisor: ctx.user.advisor_name ? { name: ctx.user.advisor_name } : null,
    prompts: PROMPTS,
    dailyLimit: settings.dailyLimit,
    remainingToday: Math.max(0, settings.dailyLimit - used),
    retention: retention.aiHistory,
  })
})

// ------------------------------------------------------------------ threads

router.get('/threads', async (req, res) => {
  const rows = await many('SELECT * FROM ai_threads WHERE student_id = $1 ORDER BY updated_at DESC LIMIT 50', [req.user.id])
  res.json({ threads: rows.map(toThread) })
})

router.post('/threads', aiLimiter, async (req, res) => {
  const { text } = z.object({ text: questionText.optional() }).strict().parse(req.body ?? {})
  if (!text) {
    const thread = await one('INSERT INTO ai_threads (student_id, title) VALUES ($1, $2) RETURNING *', [req.user.id, 'New conversation'])
    return res.status(201).json({ thread: toThread(thread), messages: [] })
  }
  const result = await ask(req, null, text)
  res.status(201).json({ thread: result.thread, messages: [result.userMessage, result.reply] })
})

router.get('/threads/:id', async (req, res) => {
  const thread = await ownThread(req)
  const messages = await many('SELECT * FROM ai_messages WHERE thread_id = $1 ORDER BY id', [thread.id])
  res.json({ thread: toThread(thread), messages: messages.map(toMessage) })
})

router.post('/threads/:id/messages', aiLimiter, async (req, res) => {
  const thread = await ownThread(req)
  const { text } = z.object({ text: questionText }).strict().parse(req.body ?? {})
  const result = await ask(req, thread, text)
  res.status(201).json({ thread: result.thread, userMessage: result.userMessage, reply: result.reply })
})

router.delete('/threads/:id', async (req, res) => {
  const thread = await ownThread(req)
  await query('DELETE FROM ai_threads WHERE id = $1', [thread.id])
  res.status(204).end()
})

router.delete('/threads', async (req, res) => {
  const { rowCount } = await query('DELETE FROM ai_threads WHERE student_id = $1', [req.user.id])
  if (rowCount) await audit(req.user, `Cleared their AI advisor history (${rowCount} conversation${rowCount === 1 ? '' : 's'})`, { req, subjectUserId: req.user.id })
  res.status(204).end()
})

// ------------------------------------------------------------------ feedback on answers

async function ownAnswer(req) {
  const row = await one(
    `SELECT m.* FROM ai_messages m JOIN ai_threads t ON t.id = m.thread_id
      WHERE m.id = $1 AND t.student_id = $2 AND m.role = 'ai'`, [messageId(req), req.user.id])
  if (!row) throw notFound('Answer')
  return row
}

router.post('/messages/:id/rating', async (req, res) => {
  const message = await ownAnswer(req)
  const { helpful } = z.object({ helpful: z.boolean().nullable() }).strict().parse(req.body ?? {})
  await query('UPDATE ai_messages SET rating = $2 WHERE id = $1', [message.id, helpful == null ? null : helpful ? 1 : -1])
  res.status(204).end()
})

router.post('/messages/:id/flag', async (req, res) => {
  const message = await ownAnswer(req)
  const { issue } = z.object({ issue: z.string().trim().min(1, 'Say what was wrong.').max(500) }).strict().parse(req.body ?? {})
  const question = await one(
    `SELECT body FROM ai_messages WHERE thread_id = $1 AND role = 'user' AND id < $2 ORDER BY id DESC LIMIT 1`, [message.thread_id, message.id])
  const flag = await one(
    `INSERT INTO ai_flags (question, issue, source, message_id, student_id) VALUES ($1, $2, 'Reported by student', $3, $4) RETURNING id`,
    [question?.body ?? '(no question)', issue, message.id, req.user.id])
  await audit(req.user, 'Reported an AI advisor answer for review', { req, target: { type: 'ai_flag', id: flag.id }, subjectUserId: req.user.id })
  res.status(201).json({ id: flag.id })
})

export default router
