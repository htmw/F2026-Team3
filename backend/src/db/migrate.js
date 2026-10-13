import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { pool } from './pool.js'

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'migrations')

// Applies every migrations/*.sql file not yet recorded in schema_migrations, in filename order,
// each inside its own transaction. With reset: true, drops the whole public schema first.
export async function migrate({ reset = false, log = console.log } = {}) {
  const client = await pool.connect()
  try {
    if (reset) {
      await client.query('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
      log('Dropped all tables.')
    }
    await client.query(`CREATE TABLE IF NOT EXISTS schema_migrations (
      name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`)
    const { rows } = await client.query('SELECT name FROM schema_migrations')
    const applied = new Set(rows.map((row) => row.name))
    const files = (await readdir(dir)).filter((file) => file.endsWith('.sql')).sort()

    for (const file of files) {
      if (applied.has(file)) continue
      const sql = await readFile(path.join(dir, file), 'utf8')
      await client.query('BEGIN')
      try {
        await client.query(sql)
        await client.query('INSERT INTO schema_migrations (name) VALUES ($1)', [file])
        await client.query('COMMIT')
        log(`Applied ${file}`)
      } catch (err) {
        await client.query('ROLLBACK')
        throw new Error(`Migration ${file} failed: ${err.message}`)
      }
    }
    log('Database schema is up to date.')
  } finally {
    client.release()
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  migrate({ reset: process.argv.includes('--reset') })
    .then(() => pool.end())
    .catch((err) => {
      console.error(err.message)
      process.exitCode = 1
      return pool.end()
    })
}
