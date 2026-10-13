import { config } from '../config.js'

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40, silent: 99 }
const threshold = LEVELS[config.logLevel]

// One JSON object per line, so logs stay greppable locally and parseable by any log collector.
function write(level, message, fields = {}) {
  if (LEVELS[level] < threshold) return
  const line = JSON.stringify({ time: new Date().toISOString(), level, message, ...fields })
  if (LEVELS[level] >= LEVELS.warn) process.stderr.write(`${line}\n`)
  else process.stdout.write(`${line}\n`)
}

export const logger = {
  debug: (message, fields) => write('debug', message, fields),
  info: (message, fields) => write('info', message, fields),
  warn: (message, fields) => write('warn', message, fields),
  error: (message, fields) => write('error', message, fields),
}

export function requestLogger(req, res, next) {
  const start = process.hrtime.bigint()
  res.on('finish', () => {
    const ms = Number(process.hrtime.bigint() - start) / 1e6
    const level = res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'info'
    write(level, 'request', {
      method: req.method,
      path: req.originalUrl.split('?')[0],
      status: res.statusCode,
      ms: Math.round(ms),
      user: req.user?.id,
    })
  })
  next()
}
