// Time slot buttons. `slots` is [{ startsAt, time, taken? }]; taken slots are struck through and disabled.
export default function SlotGrid({ slots, value, onChange }) {
  return (
    <div role="group" aria-label="Choose a time" className="grid grid-cols-3 gap-2 sm:grid-cols-4">
      {slots.map((s) => {
        const active = s.startsAt === value
        return (
          <button key={s.startsAt} type="button" aria-pressed={active} disabled={s.taken} onClick={() => onChange(s.startsAt)}
            aria-label={s.taken ? `${s.time}, taken` : s.time}
            className={`min-h-11 rounded-xl border text-sm font-bold ${
              s.taken ? 'cursor-not-allowed border-line bg-surface-sunk text-muted line-through'
                : active ? 'cursor-pointer border-accent bg-accent text-white'
                  : 'cursor-pointer border-line bg-surface text-navy hover:bg-surface-sunk'}`}>
            {s.time}
          </button>
        )
      })}
    </div>
  )
}
