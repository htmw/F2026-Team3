import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import RequireRole from '../../auth/RequireRole.jsx'

export default function AppShell({ role }) {
  return (
    <RequireRole role={role}>
      <div className="box-border min-h-screen bg-canvas p-5 font-sans text-navy">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-start gap-5">
          <Sidebar role={role} />
          <main className="flex min-w-0 flex-[999_1_640px] flex-col gap-5">
            <Outlet />
          </main>
        </div>
      </div>
    </RequireRole>
  )
}
