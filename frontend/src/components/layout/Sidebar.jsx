import { NavLink, useNavigate } from 'react-router-dom'
import Logo from '../ui/Logo.jsx'
import Button from '../ui/Button.jsx'
import { NAV } from '../../config/nav.js'
import { useAuth } from '../../auth/AuthContext.jsx'

const ROLE_BADGE = { advisor: 'Advisor', admin: 'Admin' }

export default function Sidebar({ role }) {
  const { user, badges, logout } = useAuth()
  const navigate = useNavigate()

  const signOut = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

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
        {NAV[role].map((item) => {
          const badge = item.badgeKey ? (badges[item.badgeKey] || null) : item.badge
          return (
            <NavLink key={item.to} to={item.to} end={item.end}
              className={({ isActive }) =>
                `flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-sm no-underline ${
                  isActive ? 'bg-navy-raised font-bold text-white hover:text-white' : 'font-medium text-mist hover:bg-navy-raised/60 hover:text-white'
                }`}>
              {({ isActive }) => (
                <>
                  <span className={`size-2 rounded-full ${isActive ? 'bg-teal' : 'bg-navy-line'}`} />
                  <span>{item.label}</span>
                  {badge && <span className="ml-auto text-xs font-bold text-sun">{badge}</span>}
                </>
              )}
            </NavLink>
          )
        })}
      </div>

      {role === 'student' ? (
        <div className="mt-auto flex flex-col gap-2.5 rounded-2xl bg-navy-raised p-[18px]">
          <span className="text-[15px] font-bold text-white">Need a human advisor?</span>
          <span className="text-[13px] leading-normal text-mist">Hand off your AI plan to your faculty advisor for sign-off.</span>
          <Button to="/student/book-meeting" variant="sun">Book a meeting</Button>
        </div>
      ) : (
        <div className="mt-auto flex flex-col gap-1.5 rounded-2xl bg-navy-raised p-[18px]">
          <span className="text-sm font-bold text-white">{user?.fullName}</span>
          <span className="break-all text-[13px] text-mist">{user?.email}</span>
        </div>
      )}

      <button type="button" onClick={signOut}
        className={`hit-44 -mt-4 min-h-10 cursor-pointer rounded-[10px] border border-navy-line bg-transparent px-3 text-left text-[13px] font-semibold text-fog hover:bg-navy-raised hover:text-white`}>
        Sign out
      </button>
    </nav>
  )
}
