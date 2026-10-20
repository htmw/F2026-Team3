import Pill from '../ui/Pill.jsx'

// System status rows (dot, name, detail, status pill). `systems` is [{ key, name, detail, status }] with status
// Healthy / Degraded / Down / Off. Shared by Admin overview and Admin integrations (spec 35).
const STATUS = {
  Healthy: { dot: 'var(--color-teal)', tone: 'teal' },
  Degraded: { dot: 'var(--color-amber)', tone: 'amber' },
  Down: { dot: 'var(--color-pink-ink)', tone: 'pink' },
  Off: { dot: 'var(--color-line-strong)', tone: 'gray' },
}

export default function SystemStatus({ systems }) {
  return (
    <ul className="m-0 flex list-none flex-col p-0">
      {systems.map((system, i) => {
        const look = STATUS[system.status] ?? STATUS.Off
        return (
          <li key={system.key ?? system.name} className={`flex items-center gap-3 py-3 ${i ? 'border-t border-canvas' : ''}`}>
            <span aria-hidden="true" className="size-2.5 shrink-0 rounded-full" style={{ background: look.dot }} />
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-sm font-bold">{system.name}</span>
              <span className="text-[13px] text-muted">{system.detail}</span>
            </div>
            <Pill tone={look.tone}>{system.status}</Pill>
          </li>
        )
      })}
    </ul>
  )
}
