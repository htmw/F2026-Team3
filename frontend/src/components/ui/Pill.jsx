export const PILL_TONES = {
  teal: 'bg-teal-soft text-teal-ink',
  indigo: 'bg-indigo-soft text-indigo-ink',
  amber: 'bg-amber-soft text-amber-ink',
  gray: 'bg-line-soft text-slate',
  pink: 'bg-pink-soft text-pink-ink',
}

export default function Pill({ tone = 'teal', className = '', children }) {
  return (
    <span className={`shrink-0 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ${PILL_TONES[tone]} ${className}`}>
      {children}
    </span>
  )
}

export function Chip({ tone = 'teal', children }) {
  return (
    <span className={`shrink-0 rounded-lg px-2.5 py-1.5 font-display text-xs font-bold ${PILL_TONES[tone]}`}>
      {children}
    </span>
  )
}
