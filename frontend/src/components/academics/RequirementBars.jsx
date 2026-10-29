import ProgressBar from '../ui/ProgressBar.jsx'

// One requirement group: title, "1 of 5 · 3 in progress" and a stacked bar (done accent, in progress teal-bright).
// `children` renders under the bar (the student degree plan lists the group's courses there).
export function RequirementBar({ title, count, done, inProgress, required, children }) {
  const pct = (n) => (required ? (n / required) * 100 : 100)
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="m-0 text-[15px] font-bold">{title}</h3>
        <span className="text-[13px] text-muted">{count}</span>
      </div>
      <ProgressBar value={pct(done)} secondary={pct(inProgress)} secondaryColor="var(--color-teal-bright)" height="h-2.5"
        label={`${title}: ${count}`} />
      {children}
    </section>
  )
}

// `groups`: [{ title, count, done, inProgress, required }] (the advisor student record's degree progress).
export default function RequirementBars({ groups }) {
  return groups.map((group) => <RequirementBar key={group.title} {...group} />)
}
