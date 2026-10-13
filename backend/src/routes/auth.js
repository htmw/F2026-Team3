import { Router } from 'express'
import { z } from 'zod'
import { config } from '../config.js'
import { one, query, transaction } from '../db/pool.js'
import { audit } from '../lib/audit.js'
import { DUMMY_HASH, hashPassword, randomToken, sha256, verifyPassword } from '../lib/crypto.js'
import { badRequest, unauthorized, unavailable } from '../lib/errors.js'
import { logger } from '../lib/logger.js'
import { sendMail } from '../lib/mailer.js'
import { publicUser } from '../lib/people.js'
import { getSetting } from '../lib/settings.js'
import { generateSecret, otpauthUrl, verifyCode } from '../lib/totp.js'
import { endSession, requireAuth, startSession } from '../middleware/auth.js'
import { authLimiter } from '../middleware/security.js'

const router = Router()

export const emailSchema = z.email('Enter a valid email address.').max(254).transform((value) => value.trim().toLowerCase())
export const passwordSchema = z.string().min(8, 'Use at least 8 characters for your password.').max(128, 'Use 128 characters or fewer.')
const HOME = { student: '/student', advisor: '/advisor', admin: '/admin' }
const RESET_MINUTES = 30
const INVITE_DAYS = 7
const CHALLENGE_MINUTES = 10

export async function checkEmailDomain(email) {
  const { emailDomain } = await getSetting('institution')
  if (emailDomain && !email.endsWith(`@${emailDomain.toLowerCase()}`)) {
    throw badRequest(`Use your school email address (@${emailDomain}).`)
  }
}

async function needsSecondStep(user) {
  if (user.role === 'student') return false
  const security = await getSetting('security')
  return security.staffTwoStep
}

// Password (or Google) is verified; for staff with two-step on, issue a challenge instead of a session.
async function createChallenge(user, remember) {
  const token = randomToken()
  await query(
    `INSERT INTO login_challenges (user_id, token_hash, remember, expires_at)
     VALUES ($1, $2, $3, now() + interval '${CHALLENGE_MINUTES} minutes')`,
    [user.id, sha256(token), remember],
  )
  let setup = null
  if (!user.totp_enabled) {
    // First staff sign-in: enrol an authenticator app. The secret is confirmed by the first valid code.
    const secret = user.totp_secret ?? generateSecret()
    if (!user.totp_secret) await query('UPDATE users SET totp_secret = $1 WHERE id = $2', [secret, user.id])
    setup = { secret, otpauthUrl: otpauthUrl(secret, user.email) }
  }
  return { mfaRequired: true, challenge: token, setup }
}

export async function issueOneTimeLink(userId, purpose, db = { query }) {
  const token = randomToken()
  const interval = purpose === 'invite' ? `${INVITE_DAYS} days` : `${RESET_MINUTES} minutes`
  await db.query(`UPDATE auth_tokens SET used_at = now() WHERE user_id = $1 AND purpose = $2 AND used_at IS NULL`, [userId, purpose])
  await db.query(
    `INSERT INTO auth_tokens (user_id, purpose, token_hash, expires_at) VALUES ($1, $2, $3, now() + interval '${interval}')`,
    [userId, purpose, sha256(token)],
  )
  return `${config.appUrl}/reset-password?token=${token}`
}

export async function sendResetEmail(user) {
  const link = await issueOneTimeLink(user.id, 'reset')
  await sendMail({
    to: user.email,
    subject: 'Reset your Acadmate password',
    text: `Hi ${user.full_name},\n\nUse this link to choose a new Acadmate password. It expires in ${RESET_MINUTES} minutes.\n\n${link}\n\nIf you didn't ask for this, you can ignore this email.`,
  })
}

export async function sendInviteEmail(user, db) {
  const link = await issueOneTimeLink(user.id, 'invite', db)
  await sendMail({
    to: user.email,
    subject: "You're invited to Acadmate",
    text: `Hi ${user.full_name},\n\nAn administrator created an Acadmate account for you. Choose a password to activate it (the link expires in ${INVITE_DAYS} days):\n\n${link}`,
  })
}

router.get('/config', async (req, res) => {
  const security = await getSetting('security')
  const institution = await getSetting('institution')
  res.json({ googleEnabled: Boolean(config.google) && security.googleSignIn, emailDomain: institution.emailDomain || null })
})

router.get('/me', requireAuth, (req, res) => {
  res.json({ user: publicUser(req.user) })
})

router.post('/signup', authLimiter, async (req, res) => {
  const body = z.object({
    name: z.string().trim().min(1, 'Enter your name.').max(120),
    email: emailSchema,
    password: passwordSchema,
  }).parse(req.body)
  await checkEmailDomain(body.email)

  const existing = await one('SELECT id FROM users WHERE email = $1', [body.email])
  if (existing) throw badRequest('An account with this email already exists. Sign in instead.')

  const passwordHash = await hashPassword(body.password)
  const user = await transaction(async (db) => {
    const { rows } = await db.query(
      `INSERT INTO users (email, password_hash, full_name, role) VALUES ($1, $2, $3, 'student') RETURNING *`,
      [body.email, passwordHash, body.name],
    )
    const program = await db.query('SELECT id FROM programs ORDER BY id LIMIT 1')
    await db.query('INSERT INTO student_profiles (user_id, program_id) VALUES ($1, $2)', [rows[0].id, program.rows[0]?.id ?? null])
    return rows[0]
  })
  await startSession(req, res, user, { remember: true })
  await audit(user, 'Created a student account', { req, target: { type: 'user', id: user.id }, subjectUserId: user.id })
  res.status(201).json({ user: publicUser(user), home: HOME.student })
})

router.post('/login', authLimiter, async (req, res) => {
  const body = z.object({
    email: emailSchema,
    password: z.string().min(1, 'Enter your password.').max(128),
    remember: z.boolean().default(false),
  }).parse(req.body)

  const user = await one('SELECT * FROM users WHERE email = $1', [body.email])
  const valid = await verifyPassword(body.password, user?.password_hash ?? DUMMY_HASH)
  if (!user || !valid || user.status !== 'active') {
    if (user) await audit(user, 'Failed sign-in attempt', { req, subjectUserId: user.id, result: 'Failure' })
    throw unauthorized(user?.status === 'deactivated' && valid
      ? 'This account is deactivated. Contact your administrator.'
      : 'Email or password is incorrect.')
  }

  if (await needsSecondStep(user)) return res.json(await createChallenge(user, body.remember))
  await startSession(req, res, user, { remember: body.remember })
  await audit(user, 'Signed in', { req, subjectUserId: user.id })
  res.json({ user: publicUser(user), home: HOME[user.role] })
})

router.post('/2fa/verify', authLimiter, async (req, res) => {
  const body = z.object({
    challenge: z.string().min(10).max(200),
    code: z.string().trim().regex(/^\d{6}$/, 'Enter all 6 digits.'),
  }).parse(req.body)

  const challenge = await one(
    `SELECT c.id AS challenge_id, c.remember, c.attempts, c.expires_at, u.*
       FROM login_challenges c JOIN users u ON u.id = c.user_id WHERE c.token_hash = $1`,
    [sha256(body.challenge)],
  )
  if (!challenge || challenge.expires_at < new Date() || challenge.attempts >= 5) {
    throw unauthorized('This sign-in attempt expired. Sign in again.')
  }
  if (!challenge.totp_secret || !verifyCode(challenge.totp_secret, body.code)) {
    await query('UPDATE login_challenges SET attempts = attempts + 1 WHERE id = $1', [challenge.challenge_id])
    throw badRequest('That code is not correct. Check your authenticator app and try again.')
  }

  const { challenge_id: challengeId, remember, attempts: _a, expires_at: _e, ...user } = challenge
  await query('DELETE FROM login_challenges WHERE id = $1', [challengeId])
  if (!user.totp_enabled) await query('UPDATE users SET totp_enabled = true WHERE id = $1', [user.id])
  await startSession(req, res, user, { remember })
  await audit(user, 'Signed in with two-step verification', { req, subjectUserId: user.id })
  res.json({ user: publicUser(user), home: HOME[user.role] })
})

router.post('/logout', async (req, res) => {
  await endSession(req, res)
  res.status(204).end()
})

router.post('/password-reset', authLimiter, async (req, res) => {
  const { email } = z.object({ email: emailSchema }).parse(req.body)
  const user = await one(`SELECT * FROM users WHERE email = $1 AND status = 'active'`, [email])
  if (user) {
    await sendResetEmail(user)
    await audit(user, 'Requested a password reset', { req, subjectUserId: user.id })
  }
  // Same answer whether or not the account exists, so this can't be used to discover emails.
  res.json({ ok: true })
})

async function findLinkToken(token) {
  return one(
    `SELECT t.id AS token_id, t.purpose, u.* FROM auth_tokens t JOIN users u ON u.id = t.user_id
      WHERE t.token_hash = $1 AND t.used_at IS NULL AND t.expires_at > now() AND u.status <> 'deactivated'`,
    [sha256(token)],
  )
}

router.get('/password-reset/:token', authLimiter, async (req, res) => {
  const row = await findLinkToken(req.params.token)
  if (!row) throw badRequest('This link is invalid or has expired. Request a new one.')
  res.json({ purpose: row.purpose, email: row.email })
})

router.post('/password-reset/confirm', authLimiter, async (req, res) => {
  const body = z.object({ token: z.string().min(10).max(200), password: passwordSchema }).parse(req.body)
  const row = await findLinkToken(body.token)
  if (!row) throw badRequest('This link is invalid or has expired. Request a new one.')

  const passwordHash = await hashPassword(body.password)
  await transaction(async (db) => {
    await db.query('UPDATE auth_tokens SET used_at = now() WHERE id = $1', [row.token_id])
    await db.query(
      `UPDATE users SET password_hash = $1, status = 'active', updated_at = now() WHERE id = $2`,
      [passwordHash, row.id],
    )
    // A reset signs out every existing session.
    await db.query('DELETE FROM sessions WHERE user_id = $1', [row.id])
  })
  await audit(row, row.purpose === 'invite' ? 'Accepted an invite and set a password' : 'Reset their password', { req, subjectUserId: row.id })
  res.json({ ok: true })
})

// ------------------------------------------------------------------ Google (OpenID Connect)

const GOOGLE_STATE_COOKIE = 'acadmate_google'

router.get('/google', authLimiter, async (req, res) => {
  const security = await getSetting('security')
  if (!config.google || !security.googleSignIn) throw unavailable('Google sign-in is not configured.')
  const intent = req.query.intent === 'connect' ? 'connect' : 'login'
  if (intent === 'connect' && !req.user) throw unauthorized()

  const state = randomToken(16)
  const nonce = randomToken(16)
  res.cookie(GOOGLE_STATE_COOKIE, JSON.stringify({ state, nonce, intent, remember: req.query.remember !== 'false' }), {
    httpOnly: true, secure: config.isProd, sameSite: 'lax', maxAge: 10 * 60_000, path: '/api/auth/google',
  })
  const params = new URLSearchParams({
    client_id: config.google.clientId,
    redirect_uri: `${config.apiUrl}/api/auth/google/callback`,
    response_type: 'code',
    scope: 'openid email profile',
    state,
    nonce,
    prompt: 'select_account',
  })
  res.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params}`)
})

async function googleIdentity(code, nonce) {
  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: config.google.clientId,
      client_secret: config.google.clientSecret,
      redirect_uri: `${config.apiUrl}/api/auth/google/callback`,
      grant_type: 'authorization_code',
    }),
  })
  if (!response.ok) throw new Error(`token exchange failed (${response.status})`)
  const { id_token: idToken } = await response.json()
  // The ID token came straight from Google's token endpoint over TLS, so per OIDC Core 3.1.3.7 its
  // claims can be trusted without re-checking the signature; the claim checks below are still required.
  const claims = JSON.parse(Buffer.from(idToken.split('.')[1], 'base64url').toString('utf8'))
  if (claims.aud !== config.google.clientId) throw new Error('wrong audience')
  if (!['accounts.google.com', 'https://accounts.google.com'].includes(claims.iss)) throw new Error('wrong issuer')
  if (claims.exp * 1000 < Date.now()) throw new Error('token expired')
  if (claims.nonce !== nonce) throw new Error('nonce mismatch')
  if (!claims.email_verified) throw new Error('email not verified')
  return { sub: claims.sub, email: claims.email.toLowerCase(), name: claims.name || claims.email }
}

router.get('/google/callback', async (req, res) => {
  const fail = (code) => res.redirect(`${config.appUrl}/login?error=${code}`)
  let saved
  try { saved = JSON.parse(req.cookies?.[GOOGLE_STATE_COOKIE] ?? 'null') } catch { saved = null }
  res.clearCookie(GOOGLE_STATE_COOKIE, { path: '/api/auth/google' })
  if (!config.google || !saved || typeof req.query.state !== 'string' || req.query.state !== saved.state || typeof req.query.code !== 'string') {
    return fail('google_state')
  }

  let identity
  try {
    identity = await googleIdentity(req.query.code, saved.nonce)
  } catch (err) {
    logger.warn('google sign-in failed', { error: err.message })
    return fail('google_failed')
  }

  if (saved.intent === 'connect') {
    if (!req.user) return fail('google_session')
    const taken = await one('SELECT id FROM users WHERE google_sub = $1 AND id <> $2', [identity.sub, req.user.id])
    if (taken) return res.redirect(`${config.appUrl}${HOME[req.user.role]}/settings?google=taken`)
    await query('UPDATE users SET google_sub = $1, google_email = $2, updated_at = now() WHERE id = $3', [identity.sub, identity.email, req.user.id])
    await audit(req.user, 'Connected a Google account', { req, subjectUserId: req.user.id })
    return res.redirect(`${config.appUrl}${HOME[req.user.role]}/settings?google=connected`)
  }

  let user = await one('SELECT * FROM users WHERE google_sub = $1', [identity.sub])
    ?? await one('SELECT * FROM users WHERE email = $1', [identity.email])
  if (user?.status === 'deactivated') return fail('deactivated')
  if (!user) {
    try { await checkEmailDomain(identity.email) } catch { return fail('google_domain') }
    user = await transaction(async (db) => {
      const { rows } = await db.query(
        `INSERT INTO users (email, full_name, role, google_sub, google_email) VALUES ($1, $2, 'student', $3, $1) RETURNING *`,
        [identity.email, identity.name, identity.sub],
      )
      const program = await db.query('SELECT id FROM programs ORDER BY id LIMIT 1')
      await db.query('INSERT INTO student_profiles (user_id, program_id) VALUES ($1, $2)', [rows[0].id, program.rows[0]?.id ?? null])
      return rows[0]
    })
    await audit(user, 'Created a student account with Google', { req, subjectUserId: user.id })
  } else {
    user = await one(
      `UPDATE users SET google_sub = $1, google_email = $2, status = 'active', updated_at = now() WHERE id = $3 RETURNING *`,
      [identity.sub, identity.email, user.id],
    )
  }

  if (await needsSecondStep(user)) {
    const challenge = await createChallenge(user, saved.remember)
    return res.redirect(`${config.appUrl}/login?mfa=${encodeURIComponent(challenge.challenge)}`)
  }
  await startSession(req, res, user, { remember: saved.remember })
  await audit(user, 'Signed in with Google', { req, subjectUserId: user.id })
  res.redirect(`${config.appUrl}${HOME[user.role]}`)
})

// Lets the frontend resume a two-step sign-in started by the Google redirect.
router.get('/2fa/challenge/:token', authLimiter, async (req, res) => {
  const row = await one(
    `SELECT u.* FROM login_challenges c JOIN users u ON u.id = c.user_id
      WHERE c.token_hash = $1 AND c.expires_at > now() AND c.attempts < 5`,
    [sha256(req.params.token)],
  )
  if (!row) throw unauthorized('This sign-in attempt expired. Sign in again.')
  res.json({
    mfaRequired: true,
    challenge: req.params.token,
    setup: row.totp_enabled ? null : { secret: row.totp_secret, otpauthUrl: otpauthUrl(row.totp_secret, row.email) },
  })
})

export default router
