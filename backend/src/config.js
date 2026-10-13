import 'dotenv/config'
import { z } from 'zod'

const bool = z.enum(['true', 'false', '1', '0', '']).default('false').transform((value) => value === 'true' || value === '1')
const optional = z.string().trim().optional().transform((value) => value || undefined)

const schema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().positive().default(4000),
  CORS_ORIGINS: z.string().default('http://localhost:5173'),
  APP_URL: z.url().default('http://localhost:5173'),
  API_URL: z.url().default('http://localhost:4000'),
  TRUST_PROXY: bool,
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error', 'silent']).default('info'),
  DATABASE_URL: z.string().min(1, 'DATABASE_URL is required'),
  TEST_DATABASE_URL: optional,
  SEED_PASSWORD: optional,
  ALLOW_DEMO_RESET: bool,
  GOOGLE_CLIENT_ID: optional,
  GOOGLE_CLIENT_SECRET: optional,
  SMTP_HOST: optional,
  SMTP_PORT: z.coerce.number().int().positive().default(587),
  SMTP_SECURE: bool,
  SMTP_USER: optional,
  SMTP_PASS: optional,
  MAIL_FROM: z.string().default('Acadmate <no-reply@localhost>'),
  ANTHROPIC_API_KEY: optional,
  AI_MODEL: z.string().trim().min(1).default('claude-opus-5-5'),
  AI_EFFORT: z.enum(['low', 'medium', 'high']).default('medium'),
  AI_TIMEOUT_MS: z.coerce.number().int().positive().default(60_000),
})

const env = { ...process.env }
// Tests always run against the separate test database so they can never wipe dev data.
if (env.NODE_ENV === 'test') {
  if (!env.TEST_DATABASE_URL) throw new Error('TEST_DATABASE_URL must be set to run the tests')
  env.DATABASE_URL = env.TEST_DATABASE_URL
}

const parsed = schema.safeParse(env)
if (!parsed.success) {
  const problems = parsed.error.issues.map((issue) => `  ${issue.path.join('.')}: ${issue.message}`).join('\n')
  throw new Error(`Invalid environment configuration (see backend/.env.example):\n${problems}`)
}

const c = parsed.data
export const config = {
  env: c.NODE_ENV,
  isProd: c.NODE_ENV === 'production',
  isTest: c.NODE_ENV === 'test',
  port: c.PORT,
  corsOrigins: c.CORS_ORIGINS.split(',').map((origin) => origin.trim()).filter(Boolean),
  appUrl: c.APP_URL.replace(/\/$/, ''),
  apiUrl: c.API_URL.replace(/\/$/, ''),
  trustProxy: c.TRUST_PROXY,
  logLevel: c.NODE_ENV === 'test' ? 'silent' : c.LOG_LEVEL,
  databaseUrl: c.DATABASE_URL,
  seedPassword: c.SEED_PASSWORD,
  allowDemoReset: c.ALLOW_DEMO_RESET,
  google: c.GOOGLE_CLIENT_ID && c.GOOGLE_CLIENT_SECRET
    ? { clientId: c.GOOGLE_CLIENT_ID, clientSecret: c.GOOGLE_CLIENT_SECRET }
    : null,
  smtp: c.SMTP_HOST
    ? { host: c.SMTP_HOST, port: c.SMTP_PORT, secure: c.SMTP_SECURE, user: c.SMTP_USER, pass: c.SMTP_PASS }
    : null,
  mailFrom: c.MAIL_FROM,
  // The AI advisor answers with Claude only when a key is set; tests never call the API.
  anthropic: c.ANTHROPIC_API_KEY && c.NODE_ENV !== 'test'
    ? { apiKey: c.ANTHROPIC_API_KEY, model: c.AI_MODEL, effort: c.AI_EFFORT, timeoutMs: c.AI_TIMEOUT_MS }
    : null,
}
