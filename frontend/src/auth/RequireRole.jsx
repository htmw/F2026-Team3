import { Navigate, useLocation } from 'react-router-dom'
import { HOME } from '../config/nav.js'
import { Loading } from '../components/ui/Status.jsx'
import { useAuth } from './AuthContext.jsx'

// Sends signed-out visitors to /login and users of another role to their own home.
export default function RequireRole({ role, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="min-h-screen bg-canvas"><Loading /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== role) return <Navigate to={HOME[user.role]} replace />
  return children
}
