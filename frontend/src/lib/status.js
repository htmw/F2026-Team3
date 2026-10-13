// Pill tones for course / plan statuses, shared by My courses and Degree plan.
export const COURSE_STATUS_TONE = {
  Completed: 'teal',
  'In progress': 'indigo',
  Planned: 'gray',
  Approved: 'teal',
  Recommended: 'teal',
  'Needs approval': 'amber',
  'Pending approval': 'indigo',
}

// Maps a /students/me/plan course ({ status, planStatus }) to the label the degree audit uses.
export function courseStatusLabel({ status, planStatus }) {
  if (status === 'completed') return 'Completed'
  if (status === 'current') return 'In progress'
  if (!planStatus || planStatus === 'Approved') return 'Planned'
  return planStatus
}

// Calendar event colors by type, shared by the Dashboard "Today" card and the Schedule grid.
export const EVENT_TYPES = ['Class', 'Office hours', 'Advising', 'Study', 'Team']
export const EVENT_COLOR = {
  Class: 'var(--color-accent)',
  'Office hours': 'var(--color-pink-ink)',
  Advising: 'var(--color-amber)',
  Study: 'var(--color-teal)',
  Team: 'var(--color-violet)',
}

// Pill tones for an assignment's deadline status (Dashboard deadlines, Assignments list).
export const DEADLINE_TONE = { 'Due soon': 'amber', 'In progress': 'teal', 'Not started': 'indigo', Done: 'gray', Overdue: 'pink' }

// Pill tones for an assignment's submission status.
export const ASSIGNMENT_STATUS_TONE = { 'To do': 'gray', 'In progress': 'indigo', Submitted: 'amber', Graded: 'teal' }
