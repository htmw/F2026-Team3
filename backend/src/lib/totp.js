import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto'

// RFC 6238 time-based one-time passwords (SHA-1, 6 digits, 30 s), compatible with Google Authenticator,
// Microsoft Authenticator, 1Password, etc.
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'

export function base32Encode(buffer) {
  let bits = 0
  let value = 0
  let out = ''
  for (const byte of buffer) {
    value = (value << 8) | byte
    bits += 8
    while (bits >= 5) {
      out += ALPHABET[(value >>> (bits - 5)) & 31]
      bits -= 5
    }
  }
  if (bits > 0) out += ALPHABET[(value << (5 - bits)) & 31]
  return out
}

export function base32Decode(text) {
  const clean = text.replace(/=+$/, '').replace(/\s/g, '').toUpperCase()
  let bits = 0
  let value = 0
  const out = []
  for (const char of clean) {
    const index = ALPHABET.indexOf(char)
    if (index === -1) throw new Error('Invalid base32 character')
    value = (value << 5) | index
    bits += 5
    if (bits >= 8) {
      out.push((value >>> (bits - 8)) & 255)
      bits -= 8
    }
  }
  return Buffer.from(out)
}

export const generateSecret = () => base32Encode(randomBytes(20))

export function generateCode(secret, time = Date.now(), step = 30) {
  const counter = Math.floor(time / 1000 / step)
  const buf = Buffer.alloc(8)
  buf.writeBigUInt64BE(BigInt(counter))
  const hmac = createHmac('sha1', base32Decode(secret)).update(buf).digest()
  const offset = hmac[hmac.length - 1] & 0xf
  const binary = ((hmac[offset] & 0x7f) << 24) | (hmac[offset + 1] << 16) | (hmac[offset + 2] << 8) | hmac[offset + 3]
  return String(binary % 1_000_000).padStart(6, '0')
}

// Accepts the current code and one step either side to absorb clock drift.
export function verifyCode(secret, code, time = Date.now()) {
  if (!/^\d{6}$/.test(code)) return false
  for (const drift of [-1, 0, 1]) {
    const expected = generateCode(secret, time + drift * 30_000)
    if (timingSafeEqual(Buffer.from(expected), Buffer.from(code))) return true
  }
  return false
}

export function otpauthUrl(secret, account, issuer = 'Acadmate') {
  const label = encodeURIComponent(`${issuer}:${account}`)
  return `otpauth://totp/${label}?secret=${secret}&issuer=${encodeURIComponent(issuer)}&algorithm=SHA1&digits=6&period=30`
}
