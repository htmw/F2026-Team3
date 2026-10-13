import pg from 'pg'
import { config } from '../config.js'
import { logger } from '../lib/logger.js'

// Return DATE columns as 'YYYY-MM-DD' strings instead of local-midnight Date objects.
pg.types.setTypeParser(1082, (value) => value)
// NUMERIC as JS numbers; values here are grades, weights and credits, well inside double precision.
pg.types.setTypeParser(1700, (value) => (value === null ? null : Number(value)))
pg.types.setTypeParser(20, (value) => Number(value))

export const pool = new pg.Pool({ connectionString: config.databaseUrl, max: 10 })

pool.on('error', (err) => logger.error('postgres pool error', { error: err.message }))

export const query = (text, params) => pool.query(text, params)

export async function one(text, params) {
  const { rows } = await pool.query(text, params)
  return rows[0] ?? null
}

export async function many(text, params) {
  const { rows } = await pool.query(text, params)
  return rows
}

// Runs fn(client) inside BEGIN/COMMIT, rolling back on any error.
export async function transaction(fn) {
  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    const result = await fn(client)
    await client.query('COMMIT')
    return result
  } catch (err) {
    await client.query('ROLLBACK')
    throw err
  } finally {
    client.release()
  }
}
