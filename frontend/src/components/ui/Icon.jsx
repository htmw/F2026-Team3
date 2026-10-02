const PATHS = {
  cap: ['M2 9l10-5 10 5-10 5z', 'M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5'],
  bell: ['M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9', 'M10.3 21a1.94 1.94 0 0 0 3.4 0'],
  sparkle: ['M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z', 'M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8z'],
  send: ['M22 2L11 13', 'M22 2l-7 20-4-9-9-4z'],
  check: ['M20 6L9 17l-5-5'],
  user: ['M4 21a8 8 0 0 1 16 0'],
  eye: ['M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z'],
  mail: ['M4 4h16v16H4z', 'M4 6l8 7 8-7'],
  alert: ['M12 8v4', 'M12 16h.01'],
}
const CIRCLES = {
  user: [[12, 8, 4]],
  eye: [[12, 12, 3]],
  alert: [[12, 12, 10]],
}

export default function Icon({ name, size = 20, color = 'currentColor', strokeWidth = 2, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      className={className} aria-hidden="true">
      {(CIRCLES[name] || []).map(([cx, cy, r], i) => <circle key={`c${i}`} cx={cx} cy={cy} r={r} />)}
      {(PATHS[name] || []).map((d, i) => <path key={i} d={d} />)}
    </svg>
  )
}
