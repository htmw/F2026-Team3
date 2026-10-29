import { useEffect, useState } from 'react'

// Highlights the section nearest the top of the viewport. `sections` is [{ id, label }].
function useActiveSection(sections) {
  const [active, setActive] = useState(sections[0].id)
  useEffect(() => {
    const visible = new Set()
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => (entry.isIntersecting ? visible.add(entry.target.id) : visible.delete(entry.target.id)))
      const first = sections.find((section) => visible.has(section.id))
      if (first) setActive(first.id)
    }, { rootMargin: '0px 0px -60% 0px' })
    sections.forEach((section) => {
      const element = document.getElementById(section.id)
      if (element) observer.observe(element)
    })
    return () => observer.disconnect()
  }, [sections])
  return active
}

// Settings section links (sticky column on wide screens, a wrapped row on narrow ones). Student and advisor settings.
export default function SectionNav({ sections }) {
  const active = useActiveSection(sections)
  return (
    <nav aria-label="Settings sections" className="flex flex-wrap gap-1.5 lg:sticky lg:top-6 lg:flex-col lg:self-start">
      {sections.map((section) => {
        const current = section.id === active
        return (
          <a key={section.id} href={`#${section.id}`} aria-current={current ? 'true' : undefined}
            className={`flex min-h-11 items-center rounded-xl px-3.5 text-sm text-navy no-underline hover:bg-surface-sunk lg:min-h-11 ${
              current ? 'bg-teal-soft font-bold' : 'bg-surface font-medium lg:bg-transparent'}`}>
            {section.label}
          </a>
        )
      })}
    </nav>
  )
}
