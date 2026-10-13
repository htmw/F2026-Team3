// Per-user preferences stored in users.preferences (jsonb), merged over these defaults.
export const DEFAULT_PREFERENCES = {
  notify: { deadlines: true, messages: true, suggestions: true, weeklySummary: false, sms: false },
  ai: { useGrades: true, useSchedule: true, dashboardSuggestions: true, shareWithAdvisor: false },
  reminderTiming: '1 day before',
  aiStyle: 'Concise',
}

export function mergedPreferences(stored = {}) {
  return {
    notify: { ...DEFAULT_PREFERENCES.notify, ...stored?.notify },
    ai: { ...DEFAULT_PREFERENCES.ai, ...stored?.ai },
    reminderTiming: stored?.reminderTiming ?? DEFAULT_PREFERENCES.reminderTiming,
    aiStyle: stored?.aiStyle ?? DEFAULT_PREFERENCES.aiStyle,
  }
}

// Reply style for the AI advisor: the student's own choice if they made one, otherwise the school's.
export function replyStyle(stored, schoolStyle) {
  return stored?.aiStyle ?? schoolStyle ?? 'Balanced'
}
