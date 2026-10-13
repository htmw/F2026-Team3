import { query } from '../db/pool.js'

// Posts a message from "Acadmate" into the user's system conversation (their Notifications thread),
// creating that conversation on first use.
export async function notify(userId, text, db = { query }) {
  const { rows } = await db.query(
    `SELECT c.id FROM conversations c JOIN conversation_members m ON m.conversation_id = c.id
      WHERE c.kind = 'system' AND m.user_id = $1 LIMIT 1`,
    [userId],
  )
  let conversationId = rows[0]?.id
  if (!conversationId) {
    const created = await db.query(`INSERT INTO conversations (kind, title) VALUES ('system', 'Acadmate') RETURNING id`)
    conversationId = created.rows[0].id
    await db.query('INSERT INTO conversation_members (conversation_id, user_id) VALUES ($1, $2)', [conversationId, userId])
  }
  await db.query(
    `INSERT INTO messages (conversation_id, sender_id, sender_name, body) VALUES ($1, NULL, 'Acadmate', $2)`,
    [conversationId, text],
  )
}
