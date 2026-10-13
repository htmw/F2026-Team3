import { one, query } from '../db/pool.js'
import { TIME_ZONES } from './time.js'

// Institution-wide settings live in app_settings as one JSON document per key; these are the defaults
// merged under whatever has been saved.
export const DEFAULT_SETTINGS = {
  institution: { name: 'Acadmate University', emailDomain: '', supportEmail: '', timeZone: 'Eastern' },
  security: { googleSignIn: true, staffTwoStep: true, logIp: true, sessionTimeout: '2 hours' },
  retention: { aiHistory: '1 year' },
  branding: { color: 'Teal' },
  ai: {
    features: { advisor: true, planSuggestions: true, gradeInsights: true, proactiveTips: true },
    sources: { catalog: true, audits: true, grades: true, schedules: true },
    style: 'Balanced',
    blockedTopics: ['Visa and immigration', 'Mental health', 'Financial aid', 'Grade appeals'],
    // 'Claude' answers with the Anthropic API when ANTHROPIC_API_KEY is set; 'Rules' never leaves the server.
    engine: 'Claude',
    dailyLimit: 40,
  },
}

export const SESSION_TIMEOUTS = { '30 min': 30, '2 hours': 120, '8 hours': 480 }

export async function getSetting(key, db = { query }) {
  const { rows } = await db.query('SELECT value FROM app_settings WHERE key = $1', [key])
  return { ...DEFAULT_SETTINGS[key], ...(rows[0]?.value ?? {}) }
}

export async function setSetting(key, value, db = { query }) {
  await db.query(
    `INSERT INTO app_settings (key, value) VALUES ($1, $2)
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()`,
    [key, JSON.stringify(value)],
  )
}

export async function timeZone() {
  const institution = await getSetting('institution')
  return TIME_ZONES[institution.timeZone] ?? TIME_ZONES.Eastern
}

export async function currentTerm() {
  return one('SELECT * FROM terms WHERE is_current LIMIT 1')
}
