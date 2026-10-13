import { query } from '../db/pool.js'
import { getSetting } from './settings.js'
import { logger } from './logger.js'

const ROLE_LABEL = { student: 'Student', advisor: 'Advisor', admin: 'Admin' }

// Records a user-visible audit event. `actor` is a user row ({ id, full_name, role }) or null for the system.
// Audit failures are logged, never thrown: they must not undo the action being recorded.
export async function audit(actor, action, { req, target, subjectUserId, result = 'Success', systemName = 'Acadmate', db = { query } } = {}) {
  try {
    const security = await getSetting('security', db)
    await db.query(
      `INSERT INTO audit_log (actor_id, actor_name, actor_role, action, target_type, target_id, subject_user_id, ip, result)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [
        actor?.id ?? null,
        actor?.full_name ?? systemName,
        actor ? ROLE_LABEL[actor.role] : 'System',
        action,
        target?.type ?? null,
        target?.id != null ? String(target.id) : null,
        subjectUserId ?? null,
        security.logIp && req ? req.ip : null,
        result,
      ],
    )
  } catch (err) {
    logger.error('audit write failed', { action, error: err.message })
  }
}
