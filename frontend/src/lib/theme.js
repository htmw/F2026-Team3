// Accent colours an admin can pick in Settings → Branding (spec 37). Hex values live here as data,
// not styling: components read the accent through the `accent` token / var(--color-accent).
export const ACCENTS = [
  { value: '#0F766E', label: 'Teal' },
  { value: '#1D4ED8', label: 'Blue' },
  { value: '#7C3AED', label: 'Purple' },
  { value: '#B45309', label: 'Amber' },
]

// Sets --accent for the whole app. Unknown values are ignored, which keeps the default from index.css.
export function applyAccent(hex) {
  const match = ACCENTS.find((accent) => accent.value.toLowerCase() === String(hex).toLowerCase())
  if (match) document.documentElement.style.setProperty('--accent', match.value)
}
