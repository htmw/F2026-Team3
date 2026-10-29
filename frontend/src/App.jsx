import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell.jsx'
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
import AdvisorAdvisees from './pages/advisor/Advisees.jsx'
import AdvisorDashboard from './pages/advisor/Dashboard.jsx'
import AdvisorStudentRecord from './pages/advisor/StudentRecord.jsx'
import AdvisorApprovals from './pages/advisor/Approvals.jsx'
import AdvisorMeetings from './pages/advisor/Meetings.jsx'
import AdvisorMessages from './pages/advisor/Messages.jsx'
import AdvisorReports from './pages/advisor/Reports.jsx'
import AdvisorSettings from './pages/advisor/Settings.jsx'
import AdminOverview from './pages/admin/Overview.jsx'
import AdminAiSettings from './pages/admin/AiSettings.jsx'
import AdminUsers from './pages/admin/Users.jsx'
import AdminAdvisors from './pages/admin/Advisors.jsx'
import AdminAuditLog from './pages/admin/AuditLog.jsx'
import AdminCatalog from './pages/admin/Catalog.jsx'
import AdminIntegrations from './pages/admin/Integrations.jsx'
import AdminSettings from './pages/admin/Settings.jsx'

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
        <Route index element={<AdvisorDashboard />} />
        <Route path="advisees" element={<AdvisorAdvisees />} />
        <Route path="advisees/:studentId" element={<AdvisorStudentRecord />} />
        <Route path="approvals" element={<AdvisorApprovals />} />
        <Route path="meetings" element={<AdvisorMeetings />} />
        <Route path="messages" element={<AdvisorMessages />} />
        <Route path="reports" element={<AdvisorReports />} />
        <Route path="settings" element={<AdvisorSettings />} />
      </Route>

      <Route path="/admin" element={<AppShell role="admin" />}>
        <Route index element={<AdminOverview />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="advisors" element={<AdminAdvisors />} />
        <Route path="catalog" element={<AdminCatalog />} />
        <Route path="ai" element={<AdminAiSettings />} />
        <Route path="integrations" element={<AdminIntegrations />} />
        <Route path="audit" element={<AdminAuditLog />} />
        <Route path="settings" element={<AdminSettings />} />
      </Route>

      {UiKit && <Route path="/dev/ui" element={<Suspense fallback={null}><UiKit /></Suspense>} />}

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
