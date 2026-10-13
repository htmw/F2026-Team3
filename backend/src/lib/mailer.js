import nodemailer from 'nodemailer'
import { config } from '../config.js'
import { logger } from './logger.js'

const transport = config.smtp
  ? nodemailer.createTransport({
      host: config.smtp.host,
      port: config.smtp.port,
      secure: config.smtp.secure,
      auth: config.smtp.user ? { user: config.smtp.user, pass: config.smtp.pass } : undefined,
    })
  : null

// Tests read this to pick up reset / invite links without a mail server.
export const outbox = []

// Checks the SMTP connection and credentials without sending anything.
export async function verifyTransport() {
  if (!transport) return { ok: false, error: 'SMTP is not configured (set SMTP_HOST).' }
  try {
    await transport.verify()
    return { ok: true }
  } catch (err) {
    return { ok: false, error: err.message }
  }
}

export async function sendMail({ to, subject, text }) {
  if (config.isTest) {
    outbox.push({ to, subject, text })
    return
  }
  if (!transport) {
    // No SMTP configured: print the email so links can still be followed in local development.
    logger.info('email (SMTP not configured, not sent)', { to, subject, text })
    return
  }
  try {
    await transport.sendMail({ from: config.mailFrom, to, subject, text })
  } catch (err) {
    // A mail outage must not break the request that triggered it; log so it can be retried by hand.
    logger.error('email send failed', { to, subject, error: err.message })
  }
}
