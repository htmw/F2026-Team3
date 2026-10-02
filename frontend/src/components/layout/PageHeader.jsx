import Icon from '../ui/Icon.jsx'

export default function PageHeader({ title, subtitle, initials, search, actions }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="m-0 font-display text-[30px] font-bold tracking-[-0.02em]">{title}</h1>
        {subtitle && <span className="text-sm text-muted">{subtitle}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {actions}
        {search && (
          <>
            <label htmlFor="page-search" className="sr-only">{search.label}</label>
            <input id="page-search" type="search" placeholder={search.placeholder}
              className="box-border h-11 w-[280px] max-w-full rounded-xl border border-line bg-surface px-4 text-sm text-navy" />
          </>
        )}
        {initials && (
          <>
            <button type="button" aria-label="Notifications, 3 new"
              className="relative flex size-11 cursor-pointer items-center justify-center rounded-xl border border-line bg-surface">
              <Icon name="bell" color="#13212E" />
              <span className="absolute right-2.5 top-[9px] size-2 rounded-full bg-amber" />
            </button>
            <div className="flex size-11 items-center justify-center rounded-full bg-teal-soft text-[15px] font-extrabold text-teal-ink">
              {initials}
            </div>
          </>
        )}
      </div>
    </header>
  )
}
