import { Link } from 'react-router-dom'

// Trail above a page title. `items` is [{ label, to? }]; the last item is the current page.
export default function Breadcrumb({ items }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="m-0 flex list-none flex-wrap items-center gap-1.5 p-0 text-[13px]">
        {items.map((item, index) => {
          const last = index === items.length - 1
          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
              {last || !item.to
                ? <span aria-current={last ? 'page' : undefined} className="font-semibold text-navy">{item.label}</span>
                : <Link to={item.to} className="font-semibold text-muted hover:text-navy">{item.label}</Link>}
              {!last && <span aria-hidden="true" className="text-muted">/</span>}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
