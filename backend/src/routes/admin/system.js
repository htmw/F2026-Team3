import { Router } from 'express'
import { z } from 'zod'
import { config } from '../../config.js'
import { many, one, query, transaction } from '../../db/pool.js'
import { audit } from '../../lib/audit.js'
import { randomToken, sha256 } from '../../lib/crypto.js'
import { toCsv } from '../../lib/csv.js'
import { badRequest, forbidden, notFound } from '../../lib/errors.js'
import { verifyTransport } from '../../lib/mailer.js'
import { DEFAULT_SETTINGS, getSetting, setSetting, timeZone } from '../../lib/settings.js'
import { localDate, localTime, relativeDay, TIME_ZONES } from '../../lib/time.js'
import { requireRole } from '../../middleware/auth.js'
import { loadStudent } from '../../services/academics.js'
import { answer } from '../../services/ai/index.js'

const router = Router()

// ------------------------------------------------------------------ AI settings & flagged answers

const aiSettingsView = async () => ({ ...(await getSetting('ai')), claudeAvailable: Boolean(config.anthropic) })

router.get('/ai/settings', requireRole('admin'), async (req, res) => res.json(await aiSettingsView()))

const flagSet = (keys) => z.object(Object.fromEntries(keys.map((k) => [k, z.boolean()]))).partial().strict()
const aiSettingsBody = z.object({
  features: flagSet(Object.keys(DEFAULT_SETTINGS.ai.features)).optional(),
  sources: flagSet(Object.keys(DEFAULT_SETTINGS.ai.sources)).optional(),
  style: z.enum(['Concise', 'Balanced', 'Detailed']).optional(),
  blockedTopics: z.array(z.string().trim().min(1).max(80)).max(50).optional(),
  engine: z.enum(['Claude', 'Rules']).optional(),
  dailyLimit: z.number().int().min(1).max(500).optional(),
}).strict()

function mergeAiSettings(current, body) {
  return {
    features: { ...current.features, ...body.features },
    sources: { ...current.sources, ...body.sources },
    style: body.style ?? current.style,
    blockedTopics: body.blockedTopics ? [...new Set(body.blockedTopics)] : current.blockedTopics,
    engine: body.engine ?? current.engine,
    dailyLimit: body.dailyLimit ?? current.dailyLimit,
  }
}

router.patch('/ai/settings', requireRole('admin'), async (req, res) => {
  const body = aiSettingsBody.parse(req.body)
  if (body.engine === 'Claude' && !config.anthropic) throw badRequest('Set ANTHROPIC_API_KEY on the server before switching answers to Claude.')
  const next = mergeAiSettings(await getSetting('ai'), body)
  await setSetting('ai', next)
  await audit(req.user, `Changed AI settings (${Object.keys(body).join(', ')})`, { req })
  res.json(await aiSettingsView())
})

// Runs one question through the AI advisor as a chosen student, with optional unsaved settings, so an admin
// can check a change before saving it. Nothing is stored except an audit entry (it reads student data).
router.post('/ai/test', requireRole('admin'), async (req, res) => {
  const body = z.object({
    question: z.string().trim().min(1, 'Type a test question.').max(1000),
    studentId: z.uuid(),
    settings: aiSettingsBody.optional(),
  }).strict().parse(req.body)
  const ctx = await loadStudent(body.studentId)
  if (!ctx) throw notFound('Student')
  const settings = mergeAiSettings(await getSetting('ai'), body.settings ?? {})
  // The test checks answers even while the advisor is switched off for students.
  const tz = await timeZone()
  const reply = await answer({ ctx, text: body.question, settings: { ...settings, features: { ...settings.features, advisor: true } }, tz, today: localDate(new Date(), tz) })
  await audit(req.user, `Ran an AI advisor test answer as ${ctx.user.full_name}`, { req, subjectUserId: ctx.user.id })
  res.json({
    reply: { role: 'ai', text: reply.text, kind: reply.kind, plan: reply.plan, follow: reply.follow, sources: reply.sources, actions: reply.actions },
    engine: reply.engine === 'claude' ? 'Claude' : 'Rules',
    advisorOn: Boolean(settings.features.advisor),
  })
})

router.get('/ai/flags', requireRole('admin'), async (req, res) => {
  const { status } = z.object({ status: z.enum(['Open', 'Resolved', 'Dismissed']).optional() }).parse(req.query)
  const tz = await timeZone()
  const rows = await many(
    `SELECT f.*, m.body AS answer, u.full_name AS student FROM ai_flags f
       LEFT JOIN ai_messages m ON m.id = f.message_id
       LEFT JOIN users u ON u.id = f.student_id
      WHERE ($1::text IS NULL OR f.status = $1) ORDER BY f.created_at DESC`, [status ?? null])
  res.json({
    flags: rows.map((f) => ({
      id: f.id, q: f.question, why: f.issue, source: f.source, status: f.status, when: relativeDay(f.created_at, tz), open: f.status === 'Open',
      answer: f.answer ?? null, messageId: f.message_id == null ? null : Number(f.message_id), student: f.student ?? null,
    })),
  })
})

router.post('/ai/flags/:id/resolve', requireRole('admin'), async (req, res) => {
  const id = z.coerce.number().int().positive().parse(req.params.id)
  const { resolution } = z.object({ resolution: z.enum(['Resolved', 'Dismissed']).default('Resolved') }).parse(req.body ?? {})
  const flag = await one(
    `UPDATE ai_flags SET status = $2, resolved_by = $3, resolved_at = now() WHERE id = $1 AND status = 'Open' RETURNING *`, [id, resolution, req.user.id])
  if (!flag) throw notFound('Open flag')
  await audit(req.user, `${resolution} a flagged AI answer: "${flag.question}"`, { req, target: { type: 'ai_flag', id } })
  res.json({ id, status: flag.status })
})

// ------------------------------------------------------------------ integrations & API keys

async function integrationsView() {
  const tz = await timeZone()
  const [apps, keys] = await Promise.all([
    many('SELECT * FROM integrations ORDER BY id'),
    many('SELECT * FROM api_keys WHERE revoked_at IS NULL ORDER BY created_at DESC'),
  ])
  return {
    apps: apps.map((a) => {
      // Email is configured through SMTP_* environment variables, not from the UI.
      const connected = a.id === 'mail' ? Boolean(config.smtp) : a.connected
      return {
        id: a.id, name: a.name, desc: a.description, connected, status: connected ? 'Connected' : 'Off',
        sync: a.id === 'mail' ? (config.smtp ? `SMTP via ${config.smtp.host}` : 'Not configured (set SMTP_HOST)')
          : a.last_sync_at ? `Last activity ${relativeDay(a.last_sync_at, tz).toLowerCase()} ${localTime(a.last_sync_at, tz)}` : connected ? 'Connected' : 'Not connected',
        log: (a.log ?? []).slice(0, 10).map((l) => ({ a: l.a, b: l.b ? `${relativeDay(new Date(l.b), tz)} ${localTime(new Date(l.b), tz)}` : '' })),
      }
    }),
    keys: keys.map((k) => ({ id: k.id, name: `${k.name} · created ${localDate(k.created_at, tz)}`, mask: `acm_••••••••${k.last4}` })),
  }
}

router.get('/integrations', requireRole('admin'), async (req, res) => res.json(await integrationsView()))

router.post('/integrations/:id/:action', requireRole('admin'), async (req, res) => {
  const { id, action } = z.object({ id: z.string().max(40), action: z.enum(['connect', 'disconnect', 'sync']) }).parse(req.params)
  const app = await one('SELECT * FROM integrations WHERE id = $1', [id])
  if (!app) throw notFound('Integration')
  if (id === 'mail') {
    if (action !== 'sync') throw badRequest('Email is configured with the SMTP_* environment variables on the server.')
    const result = await verifyTransport()
    await query(`UPDATE integrations SET last_sync_at = now(), log = jsonb_build_array(jsonb_build_object('a', $1::text, 'b', now())) || log WHERE id = 'mail'`,
      [result.ok ? 'Connection test passed' : `Connection test failed: ${result.error}`])
    return res.json({ ...(await integrationsView()), test: result })
  }
  if (action === 'sync') {
    throw badRequest(id === 'csv' ? 'CSV data is pushed with POST /api/admin/imports/{users|courses|grades}.' : 'Calendars sync through each student\'s .ics feed; there is nothing to pull.')
  }
  const connected = action === 'connect'
  await query(
    `UPDATE integrations SET connected = $2, log = jsonb_build_array(jsonb_build_object('a', $3::text, 'b', now())) || log WHERE id = $1`,
    [id, connected, connected ? `Connected by ${req.user.full_name}` : `Disconnected by ${req.user.full_name}`])
  await audit(req.user, `${connected ? 'Connected' : 'Disconnected'} ${app.name}`, { req, target: { type: 'integration', id } })
  res.json(await integrationsView())
})

router.post('/api-keys', requireRole('admin'), async (req, res) => {
  if (req.user.viaApiKey) throw forbidden()
  const { name } = z.object({ name: z.string().trim().min(1).max(80) }).parse(req.body)
  const key = `acm_${randomToken(30)}`
  const row = await one(
    `INSERT INTO api_keys (name, key_hash, last4, created_by) VALUES ($1, $2, $3, $4) RETURNING id`, [name, sha256(key), key.slice(-4), req.user.id])
  await audit(req.user, `Created API key "${name}"`, { req, target: { type: 'api_key', id: row.id } })
  // The full key is shown once; only its hash is stored.
  res.status(201).json({ id: row.id, name, key })
})

router.delete('/api-keys/:id', requireRole('admin'), async (req, res) => {
  const id = z.uuid().parse(req.params.id)
  const row = await one('UPDATE api_keys SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL RETURNING name', [id])
  if (!row) throw notFound('API key')
  await audit(req.user, `Revoked API key "${row.name}"`, { req, target: { type: 'api_key', id } })
  res.status(204).end()
})

// ------------------------------------------------------------------ audit log

const auditQuery = z.object({
  role: z.enum(['Admin', 'Advisor', 'Student', 'System']).optional(),
  since: z.enum(['today', '7d', '30d', 'all']).default('30d'),
  q: z.string().trim().max(100).optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(500).default(100),
})

async function auditRows(params, limit, offset) {
  const tz = await timeZone()
  const since = { today: `date_trunc('day', now() AT TIME ZONE '${tz}') AT TIME ZONE '${tz}'`, '7d': "now() - interval '7 days'", '30d': "now() - interval '30 days'", all: "'-infinity'::timestamptz" }[params.since]
  const where = `created_at >= ${since} AND ($1::text IS NULL OR actor_role = $1) AND ($2::text IS NULL OR actor_name ILIKE $2 OR action ILIKE $2)`
  const args = [params.role ?? null, params.q ? `%${params.q}%` : null]
  const [rows, total] = await Promise.all([
    many(`SELECT * FROM audit_log WHERE ${where} ORDER BY created_at DESC, id DESC LIMIT ${limit} OFFSET ${offset}`, args),
    one(`SELECT count(*) AS n FROM audit_log WHERE ${where}`, args),
  ])
  return { rows, total: total.n, tz }
}

const auditView = (e, tz) => ({
  id: e.id, when: `${relativeDay(e.created_at, tz)} ${localTime(e.created_at, tz)}`, at: e.created_at, who: e.actor_name, role: e.actor_role,
  action: e.action, targetType: e.target_type, targetId: e.target_id, subjectUserId: e.subject_user_id, result: e.result,
})

router.get('/audit', requireRole('admin'), async (req, res) => {
  const params = auditQuery.parse(req.query)
  const { rows, total, tz } = await auditRows(params, params.pageSize, (params.page - 1) * params.pageSize)
  res.json({ rows: rows.map((e) => auditView(e, tz)), total, page: params.page, pageSize: params.pageSize })
})

router.get('/audit.csv', requireRole('admin'), async (req, res) => {
  const params = auditQuery.parse(req.query)
  const { rows } = await auditRows(params, 50_000, 0)
  const csv = toCsv(['Time (UTC)', 'Actor', 'Role', 'Action', 'Target', 'IP address', 'Result'],
    rows.map((e) => [e.created_at.toISOString(), e.actor_name, e.actor_role, e.action, e.target_type ? `${e.target_type}:${e.target_id}` : '', e.ip ?? '', e.result]))
  if (!req.user.viaApiKey) await audit(req.user, 'Exported the audit log', { req })
  res.type('text/csv').attachment('acadmate-audit.csv').send(csv)
})

router.get('/audit/:id', requireRole('admin'), async (req, res) => {
  const id = z.coerce.number().int().positive().parse(req.params.id)
  const e = await one('SELECT * FROM audit_log WHERE id = $1', [id])
  if (!e) throw notFound('Audit event')
  const tz = await timeZone()
  res.json({
    ...auditView(e, tz),
    detail: [
      { k: 'Time', v: `${localDate(e.created_at, tz)} ${localTime(e.created_at, tz)}` },
      { k: 'Actor', v: `${e.actor_name} (${e.actor_role})` },
      { k: 'Action', v: e.action },
      { k: 'Event ID', v: `evt_${e.id}` },
      { k: 'IP address', v: e.ip ?? 'Not logged' },
      { k: 'Result', v: e.result },
    ],
  })
})

// ------------------------------------------------------------------ institution settings

async function settingsView() {
  const [institution, security, retention, branding, terms] = await Promise.all([
    getSetting('institution'), getSetting('security'), getSetting('retention'), getSetting('branding'),
    many('SELECT id, name, is_current FROM terms ORDER BY starts_on'),
  ])
  return {
    institution, security, retention, branding,
    currentTermId: terms.find((t) => t.is_current)?.id ?? null,
    terms: terms.map((t) => ({ id: t.id, name: t.name })),
    options: {
      timeZones: Object.keys(TIME_ZONES), sessionTimeouts: ['30 min', '2 hours', '8 hours'],
      retention: ['30 days', '1 year', 'Until graduation'], colors: ['Teal', 'Blue', 'Purple', 'Amber'],
    },
    demoResetAllowed: config.allowDemoReset,
  }
}

router.get('/settings', requireRole('admin'), async (req, res) => res.json(await settingsView()))

router.patch('/settings', requireRole('admin'), async (req, res) => {
  const body = z.object({
    institution: z.object({
      name: z.string().trim().min(1).max(120),
      emailDomain: z.string().trim().toLowerCase().regex(/^$|^[a-z0-9-]+(\.[a-z0-9-]+)+$/, 'Enter a domain like school.edu, or leave it blank.'),
      supportEmail: z.union([z.email(), z.literal('')]),
      timeZone: z.enum(Object.keys(TIME_ZONES)),
    }).partial().strict().optional(),
    security: z.object({
      googleSignIn: z.boolean(), staffTwoStep: z.boolean(), logIp: z.boolean(), sessionTimeout: z.enum(['30 min', '2 hours', '8 hours']),
    }).partial().strict().optional(),
    retention: z.object({ aiHistory: z.enum(['30 days', '1 year', 'Until graduation']) }).partial().strict().optional(),
    branding: z.object({ color: z.enum(['Teal', 'Blue', 'Purple', 'Amber']) }).partial().strict().optional(),
    currentTermId: z.number().int().positive().optional(),
  }).strict().parse(req.body)

  await transaction(async (db) => {
    for (const key of ['institution', 'security', 'retention', 'branding']) {
      if (body[key]) await setSetting(key, { ...(await getSetting(key, db)), ...body[key] }, db)
    }
    if (body.currentTermId) {
      const term = await db.query('SELECT id FROM terms WHERE id = $1', [body.currentTermId])
      if (!term.rowCount) throw notFound('Term')
      await db.query('UPDATE terms SET is_current = false WHERE is_current')
      await db.query('UPDATE terms SET is_current = true WHERE id = $1', [body.currentTermId])
    }
  })
  await audit(req.user, `Changed institution settings (${Object.keys(body).join(', ')})`, { req })
  res.json(await settingsView())
})

// Wipes the database and reloads the demo data. Only when ALLOW_DEMO_RESET=true.
router.post('/demo/reset', requireRole('admin'), async (req, res) => {
  if (!config.allowDemoReset) throw forbidden('Demo reset is turned off on this server (ALLOW_DEMO_RESET).')
  const { confirm } = z.object({ confirm: z.literal('RESET', { message: 'Type RESET to confirm.' }) }).parse(req.body ?? {})
  void confirm
  const { resetDemo } = await import('../../db/seed.js')
  await resetDemo()
  res.clearCookie('acadmate_session', { path: '/' })
  res.json({ ok: true, message: 'Demo data restored. Sign in again.' })
})

export default router
