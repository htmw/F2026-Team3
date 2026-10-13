export function initials(name = '') {
  const words = name.replace(/[[\]().]/g, ' ').split(/\s+/).filter((w) => w && !/^(dr|prof|mr|ms|mrs)$/i.test(w))
  if (words.length === 0) return '?'
  return (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase()
}

// 'Amara Okafor' -> 'Amara O.'; staff names with titles are kept as-is.
export function shortName(name = '') {
  if (/^(dr|prof)\.?\s/i.test(name)) return name
  const words = name.trim().split(/\s+/)
  return words.length > 1 ? `${words[0]} ${words[words.length - 1][0]}.` : name
}

export const firstName = (user) => user.preferred_name || user.full_name.split(/\s+/)[0]

// The shape of the signed-in user sent to the frontend.
export function publicUser(user) {
  return {
    id: user.id,
    email: user.email,
    fullName: user.full_name,
    preferredName: user.preferred_name,
    firstName: firstName(user),
    initials: initials(user.full_name),
    role: user.role,
    status: user.status,
  }
}
