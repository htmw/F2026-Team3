import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell.jsx'
import Placeholder from './pages/Placeholder.jsx'
import NotFound from './pages/NotFound.jsx'
import Login from './pages/auth/Login.jsx'
import StudentDashboard from './pages/student/Dashboard.jsx'
import StudentCourses from './pages/student/Courses.jsx'
import StudentDegreePlan from './pages/student/DegreePlan.jsx'
import StudentAiAdvisor from './pages/student/AiAdvisor.jsx'
import StudentSchedule from './pages/student/Schedule.jsx'
import StudentAssignments from './pages/student/Assignments.jsx'
import StudentMessages from './pages/student/Messages.jsx'
import StudentSettings from './pages/student/Settings.jsx'
import StudentBookMeeting from './pages/student/BookMeeting.jsx'
import AdminOverview from './pages/admin/Overview.jsx'
import AdminAiSettings from './pages/admin/AiSettings.jsx'

const todo = (title) => <Placeholder title={title} />
// Dev-only component showcase; the dynamic import is dropped from production builds.
const UiKit = import.meta.env.DEV ? lazy(() => import('./pages/dev/UiKit.jsx')) : null

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/reset-password" element={<Login />} />

      <Route path="/student" element={<AppShell role="student" />}>
        <Route index element={<StudentDashboard />} />
        <Route path="courses" element={<StudentCourses />} />
        <Route path="degree-plan" element={<StudentDegreePlan />} />
        <Route path="ai-advisor" element={<StudentAiAdvisor />} />
        <Route path="schedule" element={<StudentSchedule />} />
        <Route path="assignments" element={<StudentAssignments />} />
        <Route path="messages" element={<StudentMessages />} />
        <Route path="settings" element={<StudentSettings />} />
        <Route path="book-meeting" element={<StudentBookMeeting />} />
      </Route>

      <Route path="/advisor" element={<AppShell role="advisor" />}>
        <Route index element={todo('Advisor dashboard')} />
        <Route path="advisees" element={todo('Advisees')} />
        <Route path="advisees/:studentId" element={todo('Student record')} />
        <Route path="approvals" element={todo('Approvals')} />
        <Route path="meetings" element={todo('Meetings')} />
        <Route path="messages" element={todo('Messages')} />
        <Route path="reports" element={todo('Reports')} />
        <Route path="settings" element={todo('Settings')} />
      </Route>

      <Route path="/admin" element={<AppShell role="admin" />}>
        <Route index element={<AdminOverview />} />
        <Route path="users" element={todo('Users')} />
        <Route path="advisors" element={todo('Advisors')} />
        <Route path="catalog" element={todo('Courses & catalog')} />
        <Route path="ai" element={<AdminAiSettings />} />
        <Route path="integrations" element={todo('Integrations')} />
        <Route path="audit" element={todo('Audit log')} />
        <Route path="settings" element={todo('Settings')} />
      </Route>

      {UiKit && <Route path="/dev/ui" element={<Suspense fallback={null}><UiKit /></Suspense>} />}

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
