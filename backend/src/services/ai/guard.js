// Topics the school wants handled by a person (admin AI settings → blocked topics). Checked before any
// answer engine runs, so a blocked question is never sent to an external model.

// Extra wording for the default topics. Custom topics match on their own words.
const TOPIC_WORDS = {
  'visa and immigration': ['visa', 'visas', 'immigration', 'i-20', 'i20', 'opt', 'cpt', 'sevis', 'f-1', 'green card', 'work permit'],
  'mental health': ['mental health', 'anxiety', 'anxious', 'depressed', 'depression', 'stress', 'stressed', 'counseling', 'counselling',
    'counselor', 'therapy', 'therapist', 'suicide', 'suicidal', 'self-harm', 'burnout', 'overwhelmed'],
  'financial aid': ['financial aid', 'fafsa', 'scholarship', 'scholarships', 'loan', 'loans', 'tuition', 'stipend', 'aid'],
  'grade appeals': ['grade appeal', 'appeal', 'appeals', 'appealing', 'dispute my grade', 'dispute a grade', 'grade dispute', 'contest my grade'],
}
const STOPWORDS = new Set(['and', 'with', 'about', 'the', 'for', 'from', 'into', 'your', 'their', 'other'])

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const phrase = (p) => new RegExp(`(^|[^a-z0-9])${escape(p.toLowerCase())}(?=$|[^a-z0-9])`)

function patternsFor(topic) {
  const key = topic.trim().toLowerCase()
  const words = key.split(/[^a-z0-9-]+/).filter((w) => w.length > 3 && !STOPWORDS.has(w))
  return [key, ...words, ...(TOPIC_WORDS[key] ?? [])].map(phrase)
}

// Returns the first blocked topic the question touches, or null.
export function matchBlockedTopic(text, topics = []) {
  const q = ` ${String(text).toLowerCase()} `
  return topics.find((topic) => patternsFor(topic).some((re) => re.test(q))) ?? null
}

export const BOOK_MEETING = { label: 'Book a meeting', to: '/student/book-meeting' }
export const OPEN_PLAN = { label: 'Open degree plan', to: '/student/degree-plan' }

export function handoffReply(text = 'That topic needs a person. Please book a meeting with your advisor, who can help or point you to the right office.') {
  return { kind: 'handoff', text, plan: [], follow: null, actions: [BOOK_MEETING] }
}
