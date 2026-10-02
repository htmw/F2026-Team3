export const student = {
  firstName: 'Amara',
  initials: 'AO',
  term: 'Fall 2026 · Week 6 · M.S. Computer Science',
  today: 'Thu, Oct 1',
}

export const gpaTrend = [
  { term: 'Fall 25', gpa: 3.70 },
  { term: 'Spr 26', gpa: 3.65 },
  { term: 'Sum 26', gpa: 3.85 },
  { term: 'Now', gpa: 3.72 },
]

export const stats = [
  { label: 'On-time submission', value: '94%', pill: 'Good', tone: 'teal', pct: 94, note: '17 of 18 submitted on time' },
  { label: 'Credits earned', value: '21 / 36', pill: '58%', tone: 'indigo', pct: 58, note: '9 in progress · 6 left after this term' },
  { label: 'Attendance', value: '96%', pill: 'Great', tone: 'teal', pct: 96, note: '1 absence this term' },
  { label: 'Expected graduation', value: 'May 2027', pill: 'Confirmed', tone: 'amber', pct: 75, warn: true, note: 'Pending capstone approval' },
]

export const requirements = [
  { label: 'Core courses', count: '4 of 4', pct: 100 },
  { label: 'Electives', count: '1 done · 3 in progress', pct: 20 },
  { label: 'Foundation', count: '2 of 2', pct: 100 },
  { label: 'Capstone', count: '0 of 1', pct: 4, warn: true },
]

export const studyHours = [
  { day: 'Mon', hours: 3.5 }, { day: 'Tue', hours: 4 }, { day: 'Wed', hours: 2 }, { day: 'Thu', hours: 5, today: true },
  { day: 'Fri', hours: 2.5 }, { day: 'Sat', hours: 3 }, { day: 'Sun', hours: 1.5 },
]

export const todayEvents = [
  { time: '10:00', title: 'Data Science (CS 675)', meta: 'Lecture · Room 1201', color: 'var(--color-accent)' },
  { time: '13:30', title: 'Team project sync', meta: 'Study room 3 · 45 min', color: '#6366F1' },
  { time: '15:00', title: 'Advising check-in', meta: 'Online · Dr. [Advisor]', color: '#D97706' },
  { time: '18:10', title: 'Python Programming (CS 661)', meta: 'Lab · Room 318', color: 'var(--color-accent)' },
]

export const tasks = [
  { title: 'Project topic proposal', course: 'CS 675', due: 'Oct 3', status: 'Due soon' },
  { title: 'Week 6 tutorial', course: 'CS 661', due: 'Oct 5', status: 'In progress' },
  { title: 'Capstone pre-approval form', course: 'Advising', due: 'Oct 20', status: 'Not started' },
  { title: 'Dynamic programming set', course: 'CS 608', due: 'Sep 28', status: 'Done' },
]
export const STATUS_TONE = { 'Due soon': 'amber', 'In progress': 'teal', 'Not started': 'indigo', Done: 'gray' }

export const courses = [
  { code: 'CS 675', name: 'Data Science', prof: 'Prof. [Name]', pct: 45, grade: 'A-', tone: 'teal' },
  { code: 'CS 661', name: 'Python Programming', prof: 'Prof. [Name]', pct: 50, grade: 'A', tone: 'indigo' },
  { code: 'CS 608', name: 'Algorithms & Computing Theory', prof: 'Prof. [Name]', pct: 40, grade: 'B+', tone: 'amber' },
]

export const aiPrompts = ['Which electives fit my schedule?', 'Am I on track to graduate?', 'Plan my Spring semester']
