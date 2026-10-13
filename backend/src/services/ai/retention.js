import { query } from '../../db/pool.js'
import { audit } from '../../lib/audit.js'
import { getSetting } from '../../lib/settings.js'

const AGE = { '30 days': '30 days', '1 year': '1 year' }

// Deletes AI advisor conversations past the school's retention period (Admin → Settings → AI history).
// "Until graduation" keeps conversations while the student's account is active.
export async function purgeAiHistory(db = { query }) {
  const { aiHistory } = await getSetting('retention', db)
  const { rowCount } = AGE[aiHistory]
    ? await db.query(`DELETE FROM ai_threads WHERE updated_at < now() - $1::interval`, [AGE[aiHistory]])
    : await db.query(`DELETE FROM ai_threads t USING users u WHERE u.id = t.student_id AND u.status = 'deactivated'`)
  if (rowCount) {
    await audit(null, `Deleted ${rowCount} AI advisor conversation${rowCount === 1 ? '' : 's'} past the retention period (${aiHistory})`, { db })
  }
  return rowCount
}
