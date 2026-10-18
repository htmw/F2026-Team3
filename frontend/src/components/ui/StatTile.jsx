import Pill from './Pill.jsx'
import ProgressBar from './ProgressBar.jsx'

// Summary tile: label (+ optional pill), big value, optional 6 px bar (amber when `warn`), note.
// `pill` is { tone, text }; the bar only renders when `pct` is given. `basis` is the flex-basis before wrapping.
const BAR_COLORS = { violet: 'var(--color-violet)', amber: 'var(--color-amber)' }

export default function StatTile({ label, value, pill, pct, warn = false, color, note, basis = '170px' }) {
  return (
    <div className="box-border flex min-w-0 flex-1 flex-col gap-2.5 rounded-[var(--radius-tile)] bg-surface p-5" style={{ flexBasis: basis }}>
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <span className="text-sm font-semibold text-muted">{label}</span>
        {pill && <Pill tone={pill.tone}>{pill.text}</Pill>}
      </div>
      <span className="font-display text-[28px] font-bold tracking-[-0.02em]">{value}</span>
      {pct != null && <ProgressBar value={pct} color={warn ? 'var(--color-amber)' : BAR_COLORS[color]} label={label} />}
      {note && <span className="text-[13px] text-muted">{note}</span>}
    </div>
  )
}
