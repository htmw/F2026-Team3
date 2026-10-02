export const NAV = {
  student: [
    { label: 'Dashboard', to: '/student', end: true },
    { label: 'My courses', to: '/student/courses' },
    { label: 'Degree plan', to: '/student/degree-plan' },
    { label: 'AI advisor', to: '/student/ai-advisor', badge: 'New' },
    { label: 'Schedule', to: '/student/schedule' },
    { label: 'Assignments', to: '/student/assignments', badge: '3' },
    { label: 'Messages', to: '/student/messages', badge: '2' },
    { label: 'Settings', to: '/student/settings' },
  ],
  advisor: [
    { label: 'Dashboard', to: '/advisor', end: true },
    { label: 'Advisees', to: '/advisor/advisees', badge: '42' },
    { label: 'Approvals', to: '/advisor/approvals', badge: '5' },
    { label: 'Meetings', to: '/advisor/meetings' },
    { label: 'Messages', to: '/advisor/messages', badge: '3' },
    { label: 'Reports', to: '/advisor/reports' },
    { label: 'Settings', to: '/advisor/settings' },
  ],
  admin: [
    { label: 'Overview', to: '/admin', end: true },
    { label: 'Users', to: '/admin/users' },
    { label: 'Advisors', to: '/admin/advisors' },
    { label: 'Courses & catalog', to: '/admin/catalog' },
    { label: 'AI settings', to: '/admin/ai' },
    { label: 'Integrations', to: '/admin/integrations' },
    { label: 'Audit log', to: '/admin/audit' },
    { label: 'Settings', to: '/admin/settings' },
  ],
}

export const HOME = { student: '/student', advisor: '/advisor', admin: '/admin' }
