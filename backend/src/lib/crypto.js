import { createHash, randomBytes, scrypt, timingSafeEqual } from 'node:crypto'
import { promisify } from 'node:util'

const scryptAsync = promisify(scrypt)
const KEY_LENGTH = 64
const COST = { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 }

// Stored format: scrypt$N$r$p$saltB64$hashB64, so cost parameters can be raised later.
export async function hashPassword(password) {
  const salt = randomBytes(16)
  const hash = await scryptAsync(password.normalize('NFKC'), salt, KEY_LENGTH, COST)
  return ['scrypt', COST.N, COST.r, COST.p, salt.toString('base64'), hash.toString('base64')].join('$')
}

export async function verifyPassword(password, stored) {
  if (!stored) return false
  const [scheme, N, r, p, saltB64, hashB64] = stored.split('$')
  if (scheme !== 'scrypt') return false
  const expected = Buffer.from(hashB64, 'base64')
  const actual = await scryptAsync(password.normalize('NFKC'), Buffer.from(saltB64, 'base64'), expected.length,
    { N: Number(N), r: Number(r), p: Number(p), maxmem: COST.maxmem })
  return timingSafeEqual(actual, expected)
}

// A hash to compare against when the account doesn't exist, so response time doesn't reveal which emails are registered.
export const DUMMY_HASH = await hashPassword(randomBytes(16).toString('hex'))

export const randomToken = (bytes = 32) => randomBytes(bytes).toString('base64url')
export const sha256 = (value) => createHash('sha256').update(value).digest('hex')
