import { NavLink, Link } from 'react-router-dom'
import Logo from '../ui/Logo.jsx'
import Button from '../ui/Button.jsx'
import { NAV, HOME } from '../../config/nav.js'

const ROLE_BADGE = { advisor: 'Advisor', admin: 'Admin' }

export default function Sidebar({ role }) {
  return (
    <nav aria-label="Main"
      className="box-border flex min-w-[220px] max-w-none lg:max-w-[260px] flex-[1_1_220px] flex-col gap-7 self-stretch rounded-[var(--radius-card)] bg-navy px-4 py-6 text-frost lg:min-h-[860px]">
      <div className="px-2"><Logo /></div>

      {ROLE_BADGE[role] && (
        <span className="-mt-3.5 ml-2 self-start rounded-full bg-sun px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.08em] text-navy">
          {ROLE_BADGE[role]}
        </span>
      )}

      <div className="flex flex-col gap-1">
        {NAV[role].map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end}
            className={({ isActive }) =>
              `flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-sm no-underline ${
                isActive ? 'bg-navy-raised font-bold text-white hover:text-white' : 'font-medium text-mist hover:bg-navy-raised/60 hover:text-white'
              }`}>
            {({ isActive }) => (
              <>
                <span className={`size-2 rounded-full ${isActive ? 'bg-teal' : 'bg-navy-line'}`} />
                <span>{item.label}</span>
                {item.badge && <span className="ml-auto text-xs font-bold text-sun">{item.badge}</span>}
              </>
            )}
          </NavLink>
        ))}
      </div>

      {role === 'student' ? (
        <div className="mt-auto flex flex-col gap-2.5 rounded-2xl bg-navy-raised p-[18px]">
          <span className="text-[15px] font-bold text-white">Need a human advisor?</span>
          <span className="text-[13px] leading-normal text-mist">Hand off your AI plan to your faculty advisor for sign-off.</span>
          <Button to="/student/book-meeting" variant="sun">Book a meeting</Button>
        </div>
      ) : (
        <div className="mt-auto flex flex-col gap-2.5 rounded-2xl bg-navy-raised p-[18px]">
          <span className="text-sm font-bold text-white">Preview other views</span>
          {Object.entries(HOME).map(([r, to]) => (
            <Link key={r} to={to}
              className="flex min-h-10 items-center rounded-[10px] bg-navy px-3 text-[13px] font-semibold capitalize text-fog no-underline hover:text-white">
              {r} view
            </Link>
          ))}
        </div>
      )}
    </nav>
  )
}
