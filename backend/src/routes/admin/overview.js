import { Router } from 'express'
import { many, one } from '../../db/pool.js'
import { audit } from '../../lib/audit.js'
import { config } from '../../config.js'
import { toCsv } from '../../lib/csv.js'
import { timeZone } from '../../lib/settings.js'
import { localDate, relativeDay, shortDate } from '../../lib/time.js'
import { requireRole } from '../../middleware/auth.js'

const router = Router()
// Percentage, or null when there is nothing to measure yet.
const share = (part, whole) => (whole ? Math.round((part / whole) * 100) : null)

// Per-advisor caseload, pending queue and average days to decide.
export async function advisorWorkload() {
  return many(
    `SELECT u.id, u.full_name, u.status, s.department, s.capacity,
            (SELECT count(*) FROM student_profiles p JOIN users su ON su.id = p.user_id WHERE p.advisor_id = u.id AND su.status <> 'deactivated') AS load,
            (SELECT count(*) FROM approvals a WHERE a.advisor_id = u.id AND a.status = 'Pending') AS pending,
            (SELECT round((avg(EXTRACT(EPOCH FROM a.decided_at - a.created_at)) / 86400)::numeric, 1) FROM approvals a
              WHERE a.advisor_id = u.id AND a.decided_at > now() - interval '120 days') AS resp
       FROM users u JOIN staff_profiles s ON s.user_id = u.id
      WHERE u.role = 'advisor' AND u.status <> 'deactivated' ORDER BY u.full_name`)
}

async function overview() {
  const tz = await timeZone()
  const [counts, weekly, flags, workload, integrations, nextTerm, ai] = await Promise.all([
    one(`SELECT
          (SELECT count(*) FROM users WHERE role = 'student' AND status = 'active' AND last_login_at > now() - interval '30 days') AS active,
          (SELECT count(*) FROM users WHERE role = 'student' AND status = 'active' AND last_login_at BETWEEN now() - interval '60 days' AND now() - interval '30 days') AS active_before,
          (SELECT count(*) FROM users WHERE role = 'advisor' AND status = 'active') AS advisors,
          (SELECT count(*) FROM users WHERE role = 'advisor' AND status = 'invited') AS invited,
          (SELECT count(*) FROM approvals WHERE status = 'Pending') AS pending,
          (SELECT count(*) FROM meetings WHERE status = 'confirmed' AND starts_at BETWEEN date_trunc('week', now()) AND date_trunc('week', now()) + interval '7 days') AS meetings,
          (SELECT count(*) FROM users WHERE calendar_token IS NOT NULL AND status = 'active') AS calendar_subscribers`),
    many(`SELECT date_trunc('week', created_at) AS week, count(DISTINCT actor_id) AS n FROM audit_log
           WHERE action LIKE 'Signed in%' AND actor_role = 'Student' AND created_at > date_trunc('week', now()) - interval '5 weeks'
           GROUP BY 1 ORDER BY 1`),
    many(`SELECT * FROM ai_flags WHERE status = 'Open' ORDER BY created_at DESC`),
    advisorWorkload(),
    many(`SELECT * FROM integrations ORDER BY id`),
    one(`SELECT name, registration_opens FROM terms WHERE starts_on > (SELECT starts_on FROM terms WHERE is_current) ORDER BY starts_on LIMIT 1`),
    // AI answer quality over the last 30 days.
    one(`SELECT
          (SELECT count(*) FROM ai_messages WHERE role = 'ai' AND created_at >= date_trunc('week', now()))::int AS week,
          count(*)::int AS answers,
          count(*) FILTER (WHERE rating IS NOT NULL)::int AS rated,
          count(*) FILTER (WHERE rating = 1)::int AS helpful,
          count(*) FILTER (WHERE kind = 'handoff')::int AS handoff,
          (SELECT count(DISTINCT message_id) FROM ai_flags WHERE message_id IS NOT NULL AND created_at > now() - interval '30 days')::int AS flagged
         FROM ai_messages WHERE role = 'ai' AND created_at > now() - interval '30 days'`),
  ])
  const csv = integrations.find((i) => i.id === 'csv')
  return {
    stats: [
      { label: 'Active students', value: String(counts.active), note: 'Signed in during the last 30 days', tag: `${counts.active - counts.active_before >= 0 ? '+' : ''}${counts.active - counts.active_before}` },
      { label: 'Advisors', value: String(counts.advisors), note: `${counts.invited} invited, not yet signed in`, tag: 'Faculty' },
      { label: 'Plans awaiting approval', value: String(counts.pending), note: nextTerm?.registration_opens ? `${nextTerm.name} registration opens ${shortDate(nextTerm.registration_opens)}` : 'Across all advisors', tag: 'Queue' },
      { label: 'Meetings this week', value: String(counts.meetings), note: 'Confirmed advising meetings', tag: 'Week' },
    ],
    aiQuestions: { value: ai.week, note: 'Questions answered by the AI advisor this week' },
    aiQuality: [
      { label: 'Rated helpful', pct: share(ai.helpful, ai.rated), note: `${ai.rated} of ${ai.answers} answers rated` },
      { label: 'Handed to an advisor', pct: share(ai.handoff, ai.answers), note: `${ai.handoff} of ${ai.answers} answers` },
      { label: 'Flagged as wrong', pct: share(ai.flagged, ai.answers), note: `${ai.flagged} of ${ai.answers} answers` },
    ],
    weeks: weekly.map((w) => ({ d: shortDate(localDate(w.week, tz)), v: w.n })),
    flags: flags.map((f) => ({ id: f.id, q: f.question, issue: f.issue, source: f.source, when: relativeDay(f.created_at, tz), status: f.status })),
    openCount: `${flags.length} open`,
    systems: [
      { name: 'Database', detail: 'PostgreSQL · reachable', status: 'Healthy' },
      { name: 'CSV data import', detail: csv?.last_sync_at ? `Last import ${relativeDay(csv.last_sync_at, tz).toLowerCase()}` : 'No imports yet', status: csv?.connected ? 'Healthy' : 'Off' },
      { name: 'Calendar feeds (.ics)', detail: `${counts.calendar_subscribers} students have a feed link`, status: 'Healthy' },
      { name: 'Email notifications', detail: config.smtp ? `SMTP via ${config.smtp.host}` : 'SMTP not configured; emails go to the server log', status: config.smtp ? 'Healthy' : 'Degraded' },
    ],
    advisors: workload.map((a) => ({
      id: a.id, name: a.full_name, n: a.load, cap: a.capacity, wait: a.pending, reply: a.resp == null ? '—' : `${a.resp} days`,
      load: a.load > a.capacity ? 'Over' : 'OK',
    })),
  }
}

router.get('/overview', requireRole('admin'), async (req, res) => res.json(await overview()))

// CSV export; also works with an admin API key for scheduled reporting.
router.get('/overview/report', requireRole('admin'), async (req, res) => {
  const data = await overview()
  const csv = toCsv(['Section', 'Name', 'Value', 'Detail'], [
    ...data.stats.map((s) => ['Summary', s.label, s.value, s.note]),
    ...data.advisors.map((a) => ['Advisor workload', a.name, `${a.n}/${a.cap}`, `${a.wait} waiting · reply ${a.reply} · ${a.load}`]),
    ['AI advisor', 'Questions this week', String(data.aiQuestions.value), data.aiQuestions.note],
    ...data.aiQuality.map((q) => ['AI answer quality', q.label, q.pct == null ? '—' : `${q.pct}%`, q.note]),
    ...data.flags.map((f) => ['Flagged AI answer', f.q, f.status, f.issue]),
    ...data.systems.map((s) => ['System', s.name, s.status, s.detail]),
  ])
  if (!req.user.viaApiKey) await audit(req.user, 'Exported the overview report', { req })
  res.type('text/csv').attachment('acadmate-overview.csv').send(csv)
})

export default router
