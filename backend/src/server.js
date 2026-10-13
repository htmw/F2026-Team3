import { createApp } from './app.js'
import { config } from './config.js'
import { pool } from './db/pool.js'
import { logger } from './lib/logger.js'
import { purgeAiHistory } from './services/ai/retention.js'

const server = createApp().listen(config.port, () => {
  logger.info('Acadmate API listening', { port: config.port, env: config.env, corsOrigins: config.corsOrigins })
  if (!config.smtp) logger.warn('SMTP is not configured; emails will be written to this log instead of sent')
  if (!config.google) logger.info('Google sign-in is disabled (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set)')
  logger.info(config.anthropic ? 'AI advisor can answer with Claude' : 'AI advisor uses rule-based answers (ANTHROPIC_API_KEY not set)', config.anthropic ? { model: config.anthropic.model } : {})
})

// Daily clean-up of AI advisor conversations past the school's retention period.
function purge() {
  purgeAiHistory()
    .then((n) => n && logger.info('deleted expired AI conversations', { count: n }))
    .catch((err) => logger.error('AI history clean-up failed', { error: err.message }))
}
purge()
setInterval(purge, 24 * 3_600_000).unref()

server.on('error', (err) => {
  logger.error('server failed to start', { error: err.message, port: config.port })
  process.exit(1)
})

function shutdown(signal) {
  logger.info('shutting down', { signal })
  server.close(() => pool.end().then(() => process.exit(0)))
  setTimeout(() => process.exit(1), 10_000).unref()
}
process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)
