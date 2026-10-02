import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell.jsx'
import Placeholder from './pages/Placeholder.jsx'
import NotFound from './pages/NotFound.jsx'
import Login from './pages/auth/Login.jsx'
import StudentDashboard from './pages/student/Dashboard.jsx'

const todo = (title) => <Placeholder title={title} />

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />

      <Route path="/student" element={<AppShell role="student" />}>
        <Route index element={<StudentDashboard />} />
        <Route path="courses" element={todo('My courses')} />
        <Route path="degree-plan" element={todo('Degree plan')} />
        <Route path="ai-advisor" element={todo('AI advisor')} />
        <Route path="schedule" element={todo('Schedule')} />
        <Route path="assignments" element={todo('Assignments')} />
        <Route path="messages" element={todo('Messages')} />
        <Route path="settings" element={todo('Settings')} />
        <Route path="book-meeting" element={todo('Book a meeting')} />
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
        <Route index element={todo('Overview')} />
        <Route path="users" element={todo('Users')} />
        <Route path="advisors" element={todo('Advisors')} />
        <Route path="catalog" element={todo('Courses & catalog')} />
        <Route path="ai" element={todo('AI settings')} />
        <Route path="integrations" element={todo('Integrations')} />
        <Route path="audit" element={todo('Audit log')} />
        <Route path="settings" element={todo('Settings')} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
