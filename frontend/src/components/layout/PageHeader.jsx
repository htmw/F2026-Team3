import { Link } from 'react-router-dom'
import Icon from '../ui/Icon.jsx'
import Avatar from '../ui/Avatar.jsx'
import SearchInput from '../ui/SearchInput.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { HOME } from '../../config/nav.js'

// `search` is { label, placeholder, value?, onChange? }; it's controlled when `value` is passed.
export default function PageHeader({ title, subtitle, initials, search, actions }) {
  const { user, badges } = useAuth()
  const unread = badges.messages ?? 0
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="m-0 font-display text-[30px] font-bold tracking-[-0.02em]">{title}</h1>
        {subtitle && <span className="text-sm text-muted">{subtitle}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {actions}
        {search && <SearchInput {...search} />}
        {initials && (
          <>
            <Link to={`${HOME[user?.role] ?? ''}/messages`} aria-label={`Notifications, ${unread} new`}
              className="relative flex size-11 cursor-pointer items-center justify-center rounded-xl border border-line bg-surface">
              <Icon name="bell" color="var(--color-navy)" />
              {unread > 0 && <span className="absolute right-2.5 top-[9px] size-2 rounded-full bg-amber" />}
            </Link>
            <Avatar initials={initials} tone="teal" />
          </>
        )}
      </div>
    </header>
  )
}
