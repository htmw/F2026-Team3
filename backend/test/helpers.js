import request from 'supertest'
import { createApp } from '../src/app.js'
import { pool } from '../src/db/pool.js'
import { generateCode } from '../src/lib/totp.js'

export const app = createApp()
export const PASSWORD = process.env.SEED_PASSWORD

// Returns a supertest agent holding a session cookie. Staff sign-ins complete the TOTP step,
// reading the enrolled secret from the test database when the API no longer shows it.
export async function signIn(email, password = PASSWORD) {
  const agent = request.agent(app)
  const res = await agent.post('/api/auth/login').send({ email, password })
  if (res.status !== 200) throw new Error(`login failed for ${email}: ${res.status} ${JSON.stringify(res.body)}`)
  if (res.body.mfaRequired) {
    const secret = res.body.setup?.secret ?? (await pool.query('SELECT totp_secret FROM users WHERE email = $1', [email])).rows[0].totp_secret
    const verified = await agent.post('/api/auth/2fa/verify').send({ challenge: res.body.challenge, code: generateCode(secret) })
    if (verified.status !== 200) throw new Error(`2FA failed for ${email}: ${JSON.stringify(verified.body)}`)
  }
  return agent
}

export const resetLink = (mail) => new URL(/(http\S+reset-password\?token=\S+)/.exec(mail.text)[1]).searchParams.get('token')
