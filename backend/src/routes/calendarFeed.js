import { Router } from 'express'
import { one } from '../db/pool.js'
import { notFound } from '../lib/errors.js'
import { timeZone } from '../lib/settings.js'
import { loadStudent } from '../services/academics.js'
import { buildIcs } from '../services/ics.js'

const router = Router()

// Public, token-protected .ics feed for Google Calendar / Outlook subscriptions.
router.get('/:file', async (req, res) => {
  const match = /^([A-Za-z0-9_-]{20,64})\.ics$/.exec(req.params.file)
  if (!match) throw notFound('Calendar')
  const user = await one(`SELECT id FROM users WHERE calendar_token = $1 AND status = 'active' AND role = 'student'`, [match[1]])
  if (!user) throw notFound('Calendar')
  const ctx = await loadStudent(user.id)
  res.set('cache-control', 'private, max-age=300')
  res.type('text/calendar').send(await buildIcs(ctx, await timeZone()))
})

export default router
