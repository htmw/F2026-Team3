import Pill, { Chip } from '../ui/Pill.jsx'

// Courses an AI answer proposes or discusses. Every row comes from the student's record or the catalog.
// `term` (the answer's planTerm) titles it as a proposed schedule for that term.
export default function PlanBlock({ plan, term }) {
  const onPlan = plan.every((item) => item.onPlan)
  const title = term ? `Proposed ${term} schedule` : onPlan ? 'Your plan' : 'Courses to consider'
  return (
    <div className="flex flex-col gap-1 rounded-[14px] border border-line p-4">
      <span className="text-xs font-bold uppercase tracking-[0.06em] text-muted">{title}</span>
      {plan.map((item) => (
        <div key={item.code} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-canvas py-2.5 first-of-type:border-t-0">
          <Chip tone="teal">{item.code}</Chip>
          <div className="flex min-w-0 flex-1 basis-[180px] flex-col gap-0.5">
            <span className="text-sm font-semibold">{item.name}</span>
            <span className="text-xs text-muted">{item.meta}</span>
            {item.why && <span className="text-xs text-slate">{item.why}</span>}
          </div>
          <Pill tone="indigo">Fulfills {item.fulfills}</Pill>
        </div>
      ))}
    </div>
  )
}
