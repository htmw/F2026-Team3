export const NAV = {
  student: [
    { label: 'Dashboard', to: '/student', end: true },
    { label: 'My courses', to: '/student/courses' },
    { label: 'Degree plan', to: '/student/degree-plan' },
    { label: 'AI advisor', to: '/student/ai-advisor', badge: 'New' },
    { label: 'Schedule', to: '/student/schedule' },
    { label: 'Assignments', to: '/student/assignments', badgeKey: 'assignments' },
    { label: 'Messages', to: '/student/messages', badgeKey: 'messages' },
    { label: 'Settings', to: '/student/settings' },
  ],
  advisor: [
    { label: 'Dashboard', to: '/advisor', end: true },
    { label: 'Advisees', to: '/advisor/advisees', badgeKey: 'advisees' },
    { label: 'Approvals', to: '/advisor/approvals', badgeKey: 'approvals' },
    { label: 'Meetings', to: '/advisor/meetings' },
    { label: 'Messages', to: '/advisor/messages', badgeKey: 'messages' },
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
