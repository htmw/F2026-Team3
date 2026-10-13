import { Router } from 'express'
import { z } from 'zod'
import { many, one, query, transaction } from '../db/pool.js'
import { badRequest, forbidden, notFound } from '../lib/errors.js'
import { initials } from '../lib/people.js'
import { timeZone } from '../lib/settings.js'
import { messageTime } from '../lib/time.js'
import { requireAuth } from '../middleware/auth.js'

const router = Router()
router.use(requireAuth)

// How a person is described to the viewer: staff by title, students by program.
async function describe(viewer, ids) {
  if (ids.length === 0) return new Map()
  const rows = await many(
    `SELECT u.id, u.full_name, u.role, s.title, p.program_id, pr.name AS program, p.advisor_id
       FROM users u LEFT JOIN staff_profiles s ON s.user_id = u.id
       LEFT JOIN student_profiles p ON p.user_id = u.id LEFT JOIN programs pr ON pr.id = p.program_id
      WHERE u.id = ANY($1)`, [ids])
  return new Map(rows.map((u) => [u.id, {
    ...u,
    label: u.role === 'student'
      ? `${u.advisor_id === viewer.id ? 'Advisee' : 'Student'}${u.program ? ` · ${u.program}` : ''}`
      : u.title ?? (u.role === 'admin' ? 'Administrator' : 'Advisor'),
  }]))
}

async function membership(conversationId, userId) {
  const row = await one(
    `SELECT c.*, m.last_read_at FROM conversations c JOIN conversation_members m ON m.conversation_id = c.id
      WHERE c.id = $1 AND m.user_id = $2`, [conversationId, userId])
  if (!row) throw notFound('Conversation')
  return row
}

router.get('/', async (req, res) => {
  const { q } = z.object({ q: z.string().trim().max(100).optional() }).parse(req.query)
  const tz = await timeZone()
  const rows = await many(
    `SELECT c.id, c.kind, c.title, last.body, last.created_at AS last_at, last.sender_id,
            (SELECT count(*) FROM messages x WHERE x.conversation_id = c.id AND x.created_at > m.last_read_at
               AND x.sender_id IS DISTINCT FROM $1) AS unread,
            (SELECT COALESCE(array_agg(o.user_id), '{}') FROM conversation_members o
              WHERE o.conversation_id = c.id AND o.user_id <> $1) AS others
       FROM conversations c
       JOIN conversation_members m ON m.conversation_id = c.id AND m.user_id = $1
       LEFT JOIN LATERAL (SELECT body, created_at, sender_id FROM messages WHERE conversation_id = c.id
                           ORDER BY created_at DESC, id DESC LIMIT 1) last ON true
      ORDER BY last.created_at DESC NULLS LAST`, [req.user.id])
  const people = await describe(req.user, [...new Set(rows.flatMap((r) => r.others))])

  const list = rows.map((r) => {
    const other = r.kind === 'direct' ? people.get(r.others[0]) : null
    const name = r.kind === 'system' ? 'Acadmate' : r.kind === 'group' ? r.title : other?.full_name ?? 'Former user'
    return {
      id: r.id,
      kind: r.kind,
      name,
      role: r.kind === 'system' ? 'Notifications' : r.kind === 'group' ? `${r.others.length + 1} members` : other?.label ?? '',
      initials: r.kind === 'system' ? 'AI' : r.kind === 'group' ? `${r.title?.[0] ?? 'G'}${r.others.length + 1}`.toUpperCase() : initials(name),
      time: r.last_at ? messageTime(r.last_at, tz) : '',
      lastAt: r.last_at,
      unread: r.unread,
      preview: r.body ? `${r.sender_id === req.user.id ? 'You: ' : ''}${r.body}` : '',
      canReply: r.kind !== 'system',
      studentId: other?.role === 'student' ? other.id : null,
    }
  })
  const needle = q?.toLowerCase()
  res.json({ conversations: needle ? list.filter((c) => c.name.toLowerCase().includes(needle) || c.preview.toLowerCase().includes(needle)) : list })
})

// People the user may start a conversation with.
router.get('/contacts', async (req, res) => {
  const { q } = z.object({ q: z.string().trim().max(100).optional() }).parse(req.query)
  const like = `%${q ?? ''}%`
  const rows = req.user.role === 'student'
    ? await many(
      `SELECT u.id, u.full_name, u.role, s.title FROM users u JOIN staff_profiles s ON s.user_id = u.id
        WHERE u.status = 'active' AND u.full_name ILIKE $1 ORDER BY u.full_name LIMIT 50`, [like])
    : await many(
      `SELECT u.id, u.full_name, u.role, s.title FROM users u LEFT JOIN staff_profiles s ON s.user_id = u.id
        WHERE u.status = 'active' AND u.id <> $2 AND (u.full_name ILIKE $1 OR u.email ILIKE $1) ORDER BY u.full_name LIMIT 50`, [like, req.user.id])
  res.json({ contacts: rows.map((u) => ({ id: u.id, name: u.full_name, role: u.role, title: u.title, initials: initials(u.full_name) })) })
})

router.post('/', async (req, res) => {
  const body = z.object({
    recipientIds: z.array(z.uuid()).min(1).max(50),
    title: z.string().trim().min(1).max(120).optional(),
    text: z.string().trim().min(1).max(4000).optional(),
  }).parse(req.body)
  const ids = [...new Set(body.recipientIds.filter((id) => id !== req.user.id))]
  if (ids.length === 0) throw badRequest('Pick at least one other person.')
  const recipients = await many(`SELECT id, role FROM users WHERE id = ANY($1) AND status = 'active'`, [ids])
  if (recipients.length !== ids.length) throw badRequest('Some recipients were not found.')
  if (req.user.role === 'student' && (ids.length > 1 || recipients.some((r) => r.role === 'student'))) {
    throw forbidden('Students can message advisors and staff one at a time.')
  }
  if (ids.length > 1 && !body.title) throw badRequest('Give the group conversation a name.')

  const conversationId = await transaction(async (db) => {
    if (ids.length === 1) {
      const existing = await db.query(
        `SELECT c.id FROM conversations c
           JOIN conversation_members a ON a.conversation_id = c.id AND a.user_id = $1
           JOIN conversation_members b ON b.conversation_id = c.id AND b.user_id = $2
          WHERE c.kind = 'direct' LIMIT 1`, [req.user.id, ids[0]])
      if (existing.rows[0]) return existing.rows[0].id
    }
    const { rows } = await db.query(
      `INSERT INTO conversations (kind, title) VALUES ($1, $2) RETURNING id`, [ids.length > 1 ? 'group' : 'direct', ids.length > 1 ? body.title : null])
    for (const id of [req.user.id, ...ids]) {
      await db.query('INSERT INTO conversation_members (conversation_id, user_id) VALUES ($1, $2)', [rows[0].id, id])
    }
    return rows[0].id
  })
  if (body.text) {
    await query('INSERT INTO messages (conversation_id, sender_id, sender_name, body) VALUES ($1, $2, $3, $4)', [conversationId, req.user.id, req.user.full_name, body.text])
    await query('UPDATE conversation_members SET last_read_at = now() WHERE conversation_id = $1 AND user_id = $2', [conversationId, req.user.id])
  }
  res.status(201).json({ id: conversationId })
})

router.get('/:id/messages', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const conversation = await membership(id, req.user.id)
  const tz = await timeZone()
  const rows = await many(
    `SELECT m.id, m.sender_id, COALESCE(u.full_name, m.sender_name, 'Former user') AS sender, m.body, m.created_at
       FROM messages m LEFT JOIN users u ON u.id = m.sender_id
      WHERE m.conversation_id = $1 ORDER BY m.created_at, m.id LIMIT 500`, [id])
  await query('UPDATE conversation_members SET last_read_at = now() WHERE conversation_id = $1 AND user_id = $2', [id, req.user.id])
  res.json({
    id,
    kind: conversation.kind,
    canReply: conversation.kind !== 'system',
    messages: rows.map((m) => ({
      id: m.id,
      from: m.sender_id === req.user.id ? 'You' : m.sender,
      mine: m.sender_id === req.user.id,
      text: m.body,
      time: messageTime(m.created_at, tz),
      sentAt: m.created_at,
      showName: conversation.kind === 'group' && m.sender_id !== req.user.id,
    })),
  })
})

router.post('/:id/messages', async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const { text } = z.object({ text: z.string().trim().min(1, 'Write a message first.').max(4000) }).parse(req.body)
  const conversation = await membership(id, req.user.id)
  if (conversation.kind === 'system') throw forbidden("Notifications can't be replied to.")
  const row = await one(
    `INSERT INTO messages (conversation_id, sender_id, sender_name, body) VALUES ($1, $2, $3, $4) RETURNING id, created_at`,
    [id, req.user.id, req.user.full_name, text])
  await query('UPDATE conversation_members SET last_read_at = now() WHERE conversation_id = $1 AND user_id = $2', [id, req.user.id])
  res.status(201).json({ id: row.id, from: 'You', mine: true, text, time: messageTime(row.created_at, await timeZone()), sentAt: row.created_at })
})

export default router
