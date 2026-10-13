import cookieParser from 'cookie-parser'
import cors from 'cors'
import express from 'express'
import helmet from 'helmet'
import { config } from './config.js'
import { query } from './db/pool.js'
import { errorHandler, notFoundHandler } from './lib/errors.js'
import { requestLogger } from './lib/logger.js'
import { apiKeyAuth, apiKeyScope, loadSession } from './middleware/auth.js'
import { apiLimiter, originCheck } from './middleware/security.js'
import adminCatalog from './routes/admin/catalog.js'
import adminOverview from './routes/admin/overview.js'
import adminSystem from './routes/admin/system.js'
import adminUsers from './routes/admin/users.js'
import advisors from './routes/advisors.js'
import approvals from './routes/approvals.js'
import assignments from './routes/assignments.js'
import auth from './routes/auth.js'
import calendarFeed from './routes/calendarFeed.js'
import conversations from './routes/conversations.js'
import courses from './routes/courses.js'
import meetings from './routes/meetings.js'
import records from './routes/records.js'
import studentAi from './routes/studentAi.js'
import students from './routes/students.js'
import users from './routes/users.js'

export function createApp() {
  const app = express()
  app.disable('x-powered-by')
  if (config.trustProxy) app.set('trust proxy', 1)

  app.use(helmet({ crossOriginResourcePolicy: { policy: 'same-site' } }))
  app.use(cors({ origin: config.corsOrigins, credentials: true }))
  app.use(requestLogger)
  app.use(express.json({ limit: '100kb' }))
  app.use(cookieParser())

  app.get('/api/health', async (req, res) => {
    await query('SELECT 1')
    res.json({ status: 'ok' })
  })

  app.use('/api', apiLimiter, originCheck)
  app.use('/api/calendar', calendarFeed)
  app.use('/api', loadSession)
  app.use('/api/admin', apiKeyAuth, apiKeyScope)

  app.use('/api/auth', auth)
  app.use('/api/users', users)
  app.use('/api/students/me/ai', studentAi)
  app.use('/api/students', records)
  app.use('/api/students', students)
  app.use('/api/assignments', assignments)
  app.use('/api/conversations', conversations)
  app.use('/api/advisors', advisors)
  app.use('/api/approvals', approvals)
  app.use('/api', courses)
  app.use('/api', meetings)
  app.use('/api/admin', adminOverview)
  app.use('/api/admin', adminUsers)
  app.use('/api/admin', adminCatalog)
  app.use('/api/admin', adminSystem)

  app.use(notFoundHandler)
  app.use(errorHandler)
  return app
}
