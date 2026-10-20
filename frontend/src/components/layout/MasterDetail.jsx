// Two-pane list/detail layout. Stacks below the lg breakpoint. Selection stays in the screen's own state.
// `wideList` gives the list the larger share (tables with several columns).
export default function MasterDetail({ list, detail, wideList = false }) {
  const columns = wideList ? 'lg:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]' : 'lg:grid-cols-[minmax(320px,2fr)_3fr]'
  return (
    <div className={`grid grid-cols-1 items-start gap-4 ${columns}`}>
      <div className="min-w-0">{list}</div>
      <div className="min-w-0">{detail}</div>
    </div>
  )
}

export function ListRow({ selected, onSelect, children }) {
  return (
    <button type="button" aria-current={selected ? 'true' : undefined} onClick={onSelect}
      className={`flex w-full cursor-pointer items-center gap-3 rounded-xl border-0 px-3.5 py-3 text-left text-navy ${
        selected ? 'bg-surface-sunk shadow-[inset_4px_0_0_var(--color-accent)]' : 'bg-transparent hover:bg-surface-sunk'}`}>
      {children}
    </button>
  )
}

export function DetailEmpty({ children = 'Select an item to see details.' }) {
  return <div className="flex min-h-[200px] items-center justify-center text-sm text-muted">{children}</div>
}
