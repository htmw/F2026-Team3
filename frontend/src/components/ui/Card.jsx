export default function Card({ as: Tag = 'div', dark = false, className = '', children, ...rest }) {
  const tone = dark ? 'bg-navy text-frost' : 'bg-surface'
  return (
    <Tag className={`${tone} min-w-0 rounded-[var(--radius-card)] p-6 flex flex-col ${className}`} {...rest}>
      {children}
    </Tag>
  )
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-bold">{title}</h2>
        {subtitle && <span className="text-[13px] text-muted">{subtitle}</span>}
      </div>
      {action}
    </div>
  )
}
