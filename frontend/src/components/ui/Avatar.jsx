import { PILL_TONES } from './Pill.jsx'

const TONE_KEYS = Object.keys(PILL_TONES)
const SIZES = { sm: 'size-8 text-xs', md: 'size-11 text-[15px]', lg: 'size-14 text-lg' }

// 'Amara Okafor' -> 'AO'
export function initialsOf(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts.at(-1)[0] : '')).toUpperCase()
}

// Stable tone per person, so the same id/name always gets the same color.
export function toneFor(key = '') {
  let hash = 0
  for (const char of String(key)) hash = (hash * 31 + char.charCodeAt(0)) | 0
  return TONE_KEYS[Math.abs(hash) % TONE_KEYS.length]
}

export default function Avatar({ name, initials, tone, size = 'md', className = '' }) {
  return (
    <div aria-hidden={name ? undefined : true} title={name}
      className={`flex shrink-0 items-center justify-center rounded-full font-extrabold ${SIZES[size]} ${PILL_TONES[tone ?? toneFor(name)]} ${className}`}>
      {initials ?? initialsOf(name)}
    </div>
  )
}
