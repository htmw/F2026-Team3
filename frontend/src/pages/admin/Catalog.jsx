import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty } from '../../components/layout/MasterDetail.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import { Field, Select, Textarea, TextInput } from '../../components/ui/Field.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import SearchInput from '../../components/ui/SearchInput.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { SwitchRow } from '../../components/ui/Switch.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { COURSE_TYPE_TONE } from '../../lib/status.js'

const TABS = [
  { value: 'courses', label: 'Courses' },
  { value: 'requirements', label: 'Degree requirements' },
  { value: 'terms', label: 'Terms' },
]
const TYPES = ['Foundation', 'Core', 'Elective', 'Capstone']
const CODE = /^[A-Z]{2,4} \d{3}[A-Z]?$/ // matches schemas/catalog.CODE_PATTERN
const MAX_GROUP_COURSES = 20
const STACKED = '(max-width: 1023px)' // MasterDetail stacks below lg
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`
const normalizeCode = (raw) => raw.trim().replace(/\s+/g, ' ').toUpperCase()
const fieldErrors = (err) => Object.fromEntries((err.details ?? []).map((d) => [d.field, d.message]))

// Admin courses & catalog (spec 33). Every save is a draft; Publish applies them all at once.
export default function AdminCatalog() {
  const { user: me } = useAuth()
  const [params, setParams] = useSearchParams()
  const tab = TABS.some((t) => t.value === params.get('tab')) ? params.get('tab') : 'courses'
  const summary = useApi('/admin/catalog/summary')
  const [version, setVersion] = useState(0) // remounts the tabs after a publish so they reload
  const [result, setResult] = useState(null)
  const [publishing, setPublishing] = useState(false)
  const [published, setPublished] = useState(false)

  const setParam = (key, value) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (value == null || value === '') next.delete(key)
      else next.set(key, String(value))
      return next
    }, { replace: true })
  }
  const setTab = (value) => {
    setResult(null)
    setParams(value === 'courses' ? {} : { tab: value }, { replace: true })
  }

  const saved = (text) => {
    setResult({ tone: 'teal', text })
    setPublished(false)
    summary.reload()
  }

  const publish = async () => {
    setPublishing(true)
    setResult(null)
    try {
      const data = await api('/admin/catalog/publish', { method: 'POST' })
      setResult({ tone: 'teal', text: data.message })
      setPublished(true)
      setVersion((v) => v + 1)
      summary.reload()
    } catch (err) {
      setResult({ tone: 'pink', text: errorText(err) })
    } finally {
      setPublishing(false)
    }
  }

  if (summary.error && !summary.data) {
    return (
      <>
        <PageHeader title="Courses & catalog" />
        <ErrorState message={summary.error.message} onRetry={summary.reload} />
      </>
    )
  }
  if (!summary.data) return <Loading label="Loading the catalog…" />

  const { draftCount, nextTerm } = summary.data
  const publishLabel = publishing ? 'Publishing…' : draftCount === 0 && published ? 'Published' : 'Publish catalog'

  return (
    <>
      <PageHeader title="Courses & catalog" subtitle="The courses, requirements and dates Acadmate plans with"
        initials={me?.initials}
        actions={(
          <Button onClick={publish} disabled={publishing || draftCount === 0}>
            {publishLabel}
            {draftCount > 0 && !publishing && (
              <span className="ml-2 rounded-full bg-white/25 px-2 py-0.5 text-xs font-bold">{plural(draftCount, 'change')}</span>
            )}
          </Button>
        )} />

      <div className="flex flex-col gap-4">
        <SegmentedTabs label="Catalog section" value={tab} onChange={setTab} options={TABS} />
        {result && <Notice tone={result.tone} role="status">{result.text}</Notice>}
        <div key={`${tab}-${version}`}>
          {tab === 'courses' && (
            <CoursesTab nextTerm={nextTerm} selectedCode={params.get('course')}
              onSelect={(code) => setParam('course', code)} onSaved={saved} />
          )}
          {tab === 'requirements' && (
            <RequirementsTab programId={params.get('program')} onProgram={(id) => setParam('program', id)} onSaved={saved} />
          )}
          {tab === 'terms' && <TermsTab onSaved={saved} />}
        </div>
      </div>
    </>
  )
}

// --- courses -----------------------------------------------------------------------------------------------------

function CoursesTab({ nextTerm, selectedCode, onSelect, onSaved }) {
  const { data, error, reload } = useApi('/admin/catalog/courses')
  const [q, setQ] = useState('')
  const [adding, setAdding] = useState(false)
  const detailRef = useRef(null)

  const rows = data?.courses ?? []
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return rows
    const compact = needle.replace(/\s+/g, '')
    return rows.filter((r) => r.name.toLowerCase().includes(needle) || r.code.toLowerCase().replace(/\s+/g, '').includes(compact))
  }, [rows, q])
  const selected = rows.find((r) => r.code === selectedCode) ?? shown[0] ?? null

  const pick = (row) => {
    onSelect(row.code)
    if (window.matchMedia?.(STACKED).matches) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }

  if (error && !data) return <ErrorState message={error.message} onRetry={reload} />
  if (!data) return <Loading label="Loading courses…" />

  const changed = (row, text) => {
    onSelect(row.code)
    onSaved(text)
    reload()
  }

  return (
    <div className="flex flex-col gap-4">
      {adding && (
        <AddCoursePanel onCancel={() => setAdding(false)}
          onAdded={(row) => { setAdding(false); changed(row, `${row.code} added as a draft.`) }} />
      )}
      <MasterDetail wideList
        list={(
          <Card as="section" aria-label="Courses" className="gap-3 p-4 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <SearchInput label="Search courses" placeholder="Search by code or name…" value={q} onChange={setQ}
                className="w-full sm:w-[280px]" />
              <Button variant="secondary" size="sm" onClick={() => setAdding((on) => !on)} aria-expanded={adding}>
                Add course
              </Button>
            </div>
            {shown.length === 0 ? <Empty>{q ? 'No courses match your search.' : 'No courses yet.'}</Empty> : (
              <ul className="m-0 flex list-none flex-col p-0">
                {shown.map((row) => (
                  <li key={row.code} className="border-t border-canvas first:border-t-0">
                    <CourseRow row={row} active={row.code === selected?.code} onSelect={() => pick(row)} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
        detail={(
          <div ref={detailRef} className="scroll-mt-4">
            {selected ? (
              <CourseEditor key={selected.code} course={selected} courses={rows} nextTerm={nextTerm}
                onSaved={(row) => changed(row, `${row.code} saved as a draft.`)} />
            ) : <Card><DetailEmpty>Select a course to edit it.</DetailEmpty></Card>}
          </div>
        )} />
    </div>
  )
}

function CourseRow({ row, active, onSelect }) {
  return (
    <button type="button" aria-pressed={active} onClick={onSelect}
      className={`grid w-full cursor-pointer grid-cols-[72px_minmax(0,1fr)] items-center gap-x-3 gap-y-1.5 rounded-xl border-0 px-3 py-3 text-left text-navy sm:grid-cols-[80px_minmax(0,1fr)_auto_auto] ${
        active ? 'bg-surface-sunk shadow-[inset_4px_0_0_var(--color-accent)]' : 'bg-transparent hover:bg-surface-sunk'}`}>
      <span className="flex items-center gap-1.5 font-display text-sm font-bold">
        {row.code}
        {row.draft && (
          <span className="size-2 shrink-0 rounded-full bg-amber" title="Draft"><span className="sr-only">Draft</span></span>
        )}
      </span>
      <span className="truncate text-sm">{row.name}</span>
      <span className="col-start-2 flex gap-1.5 sm:contents">
        <Pill tone={COURSE_TYPE_TONE[row.type]}>{row.type}</Pill>
        <Pill tone={row.offered ? 'gray' : 'pink'}>{row.offerLabel}</Pill>
      </span>
    </button>
  )
}

function AddCoursePanel({ onAdded, onCancel }) {
  const id = useId()
  const [form, setForm] = useState({ code: '', name: '', credits: '3', type: 'Elective' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState(null)
  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    const code = normalizeCode(form.code)
    const credits = Number(form.credits)
    const found = {}
    if (!CODE.test(code)) found.code = 'Use a code like "CS 612".'
    if (!form.name.trim()) found.name = 'Enter the course name.'
    if (!Number.isInteger(credits) || credits < 1 || credits > 6) found.credits = 'Credits must be between 1 and 6.'
    setErrors(found)
    setFailure(null)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      onAdded(await api('/admin/catalog/courses', { method: 'POST', body: { code, name: form.name.trim(), credits, type: form.type } }))
    } catch (err) {
      if (err.status === 409) setErrors({ code: err.message })
      else if (err.status === 422 && err.details?.length) setErrors(fieldErrors(err))
      else setFailure(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" aria-label="Add a course" className="gap-4">
      <CardHeader title="Add a course" subtitle="It stays a draft until you publish the catalog." />
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[140px_minmax(0,1fr)_110px_160px]">
          <Field id={`${id}-code`} label="Code" error={errors.code}>
            <TextInput id={`${id}-code`} value={form.code} onChange={set('code')} placeholder="CS 612" autoComplete="off" />
          </Field>
          <Field id={`${id}-name`} label="Course name" error={errors.name}>
            <TextInput id={`${id}-name`} value={form.name} onChange={set('name')} maxLength={200} autoComplete="off" />
          </Field>
          <Field id={`${id}-credits`} label="Credits" error={errors.credits}>
            <TextInput id={`${id}-credits`} type="number" inputMode="numeric" min={1} max={6} value={form.credits}
              onChange={set('credits')} />
          </Field>
          <Field id={`${id}-type`} label="Counts toward" error={errors.type}>
            <Select id={`${id}-type`} value={form.type} onChange={set('type')}>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </Select>
          </Field>
        </div>
        {failure && <Notice tone="pink" role="status">{failure}</Notice>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>{busy ? 'Adding…' : 'Add course'}</Button>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}

function CourseEditor({ course, courses, nextTerm, onSaved }) {
  const id = useId()
  const [form, setForm] = useState({
    name: course.name, type: course.type, offered: course.offered, credits: String(course.credits),
    prerequisites: course.prerequisites, description: course.description ?? '',
  })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState(null)
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))
  const togglePrereq = (code) => set('prerequisites', form.prerequisites.includes(code)
    ? form.prerequisites.filter((c) => c !== code) : [...form.prerequisites, code].sort())

  const save = async (event) => {
    event.preventDefault()
    const credits = Number(form.credits)
    const found = {}
    if (!form.name.trim()) found.name = 'Enter the course name.'
    if (!Number.isInteger(credits) || credits < 1 || credits > 6) found.credits = 'Credits must be between 1 and 6.'
    setErrors(found)
    setFailure(null)
    if (Object.keys(found).length) return
    const body = { name: form.name.trim(), type: form.type, credits, prerequisites: form.prerequisites, description: form.description }
    if (nextTerm) Object.assign(body, { offered: form.offered, termId: nextTerm.id })
    setBusy(true)
    try {
      onSaved(await api(`/admin/catalog/courses/${encodeURIComponent(course.code)}`, { method: 'PUT', body }))
    } catch (err) {
      if (err.status === 400) setErrors({ prerequisites: err.message })
      else if (err.status === 422 && err.details?.length) setErrors(fieldErrors(err))
      else setFailure(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const others = courses.filter((c) => c.code !== course.code)

  return (
    <Card as="aside" aria-label="Edit course" className="gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="m-0 text-xl font-bold">Edit {course.code}</h2>
        {course.draft && <Pill tone="amber">Draft</Pill>}
      </div>
      <form onSubmit={save} noValidate className="flex flex-col gap-4">
        <Field id={`${id}-name`} label="Course name" error={errors.name}>
          <TextInput id={`${id}-name`} value={form.name} onChange={(e) => set('name', e.target.value)} maxLength={200} />
        </Field>

        <div className="flex flex-col gap-2">
          <span id={`${id}-type`} className="text-sm font-bold">Counts toward</span>
          <div role="group" aria-labelledby={`${id}-type`} className="flex flex-wrap gap-2">
            {TYPES.map((t) => (
              <button key={t} type="button" aria-pressed={form.type === t} onClick={() => set('type', t)}
                className={`cursor-pointer rounded-full border px-3.5 py-2 text-[13px] font-bold ${
                  form.type === t ? 'border-navy bg-navy text-white' : 'border-line bg-surface text-slate hover:bg-surface-sunk'}`}>
                {t}
              </button>
            ))}
          </div>
          {errors.type && <span className="text-[13px] text-pink-ink">{errors.type}</span>}
        </div>

        {nextTerm && (
          <SwitchRow id={`${id}-offered`} label={`Offered in ${nextTerm.name}`}
            description="Acadmate only suggests offered courses." checked={form.offered} onChange={(on) => set('offered', on)} />
        )}

        <Field id={`${id}-credits`} label="Credits" error={errors.credits}>
          <TextInput id={`${id}-credits`} type="number" inputMode="numeric" min={1} max={6} className="max-w-[120px]"
            value={form.credits} onChange={(e) => set('credits', e.target.value)} />
        </Field>

        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0" aria-describedby={errors.prerequisites ? `${id}-pre-error` : undefined}>
          <legend className="mb-2 p-0 text-sm font-bold">Prerequisites</legend>
          <div className="grid max-h-48 grid-cols-2 gap-x-3 gap-y-2 overflow-y-auto rounded-xl border border-line p-3 sm:grid-cols-3">
            {others.map((c) => (
              <label key={c.code} className="flex cursor-pointer items-center gap-2 text-[13px]" title={c.name}>
                <input type="checkbox" className="size-4 cursor-pointer accent-accent" checked={form.prerequisites.includes(c.code)}
                  onChange={() => togglePrereq(c.code)} />
                <span className="font-display font-bold">{c.code}</span>
              </label>
            ))}
          </div>
          {errors.prerequisites && <span id={`${id}-pre-error`} className="text-[13px] text-pink-ink">{errors.prerequisites}</span>}
        </fieldset>

        <Field id={`${id}-desc`} label="Description" error={errors.description}>
          <Textarea id={`${id}-desc`} rows={3} maxLength={2000} value={form.description}
            onChange={(e) => set('description', e.target.value)} />
        </Field>

        {failure && <Notice tone="pink" role="status">{failure}</Notice>}
        <div>
          <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save course'}</Button>
        </div>
      </form>
    </Card>
  )
}

// --- degree requirements -----------------------------------------------------------------------------------------

function RequirementsTab({ programId, onProgram, onSaved }) {
  const { data, error, reload } = useApi(`/admin/catalog/requirements${programId ? `?program=${programId}` : ''}`)
  const all = useApi('/admin/catalog/courses')
  const [groups, setGroups] = useState(null)
  const [open, setOpen] = useState(null)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState(null)
  const id = useId()

  useEffect(() => { if (data) setGroups(data.groups) }, [data])

  if (error && !data) return <ErrorState message={error.message} onRetry={reload} />
  if (!data || !groups) return <Loading label="Loading requirements…" />

  const total = groups.reduce((sum, g) => sum + g.courses * g.creditsPerCourse, 0)
  const update = (groupId, patch) => setGroups((gs) => gs.map((g) => (g.id === groupId ? { ...g, ...patch } : g)))
  const toggle = (group, code) => update(group.id, {
    eligible: group.eligible.includes(code) ? group.eligible.filter((c) => c !== code) : [...group.eligible, code].sort(),
  })

  const save = async () => {
    setBusy(true)
    setFailure(null)
    try {
      const result = await api('/admin/catalog/requirements', {
        method: 'PUT',
        body: { programId: data.program.id, groups: groups.map((g) => ({ id: g.id, courses: g.courses, eligible: g.eligible })) },
      })
      setGroups(result.groups)
      onSaved(`Requirements saved as a draft (${result.totalCredits} credits).`)
    } catch (err) {
      setFailure(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" aria-labelledby={`${id}-title`} className="gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${id}-title`} className="m-0 text-xl font-bold">{data.program.name} · catalog {data.catalogYear}</h2>
        {data.programs.length > 1 && (
          <Select aria-label="Program" className="w-auto" value={data.program.id} onChange={(e) => onProgram(e.target.value)}>
            {data.programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        )}
      </div>
      <p className="m-0 text-sm text-slate">Total: <strong className="text-navy">{total} credits</strong></p>

      <ul className="m-0 flex list-none flex-col p-0">
        {groups.map((g) => {
          const short = g.label.replace(/ courses$/i, '')
          return (
            <li key={g.id} className="flex flex-col gap-3 border-t border-canvas py-4 first:border-t-0">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-bold">{g.label}</span>
                  <span className="text-[13px] text-muted">{g.courses * g.creditsPerCourse} credits · {g.creditsPerCourse} per course</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" aria-label={`Fewer ${short} courses`} disabled={g.courses <= 0}
                    onClick={() => update(g.id, { courses: g.courses - 1 })}>−</Button>
                  <span className="min-w-[88px] text-center text-sm font-semibold" aria-live="polite">{plural(g.courses, 'course')}</span>
                  <Button variant="secondary" size="sm" aria-label={`More ${short} courses`} disabled={g.courses >= MAX_GROUP_COURSES}
                    onClick={() => update(g.id, { courses: g.courses + 1 })}>+</Button>
                </div>
              </div>
              <div>
                <button type="button" aria-expanded={open === g.id} onClick={() => setOpen(open === g.id ? null : g.id)}
                  className="cursor-pointer border-0 bg-transparent p-0 text-[13px] font-bold text-accent">
                  Eligible courses ({g.eligible.length})
                </button>
              </div>
              {open === g.id && (
                <fieldset className="m-0 grid grid-cols-2 gap-x-3 gap-y-2 rounded-xl border border-line p-3 sm:grid-cols-4">
                  <legend className="sr-only">Courses that count toward {g.label}</legend>
                  {(all.data?.courses ?? []).map((c) => (
                    <label key={c.code} className="flex cursor-pointer items-center gap-2 text-[13px]" title={c.name}>
                      <input type="checkbox" className="size-4 cursor-pointer accent-accent" checked={g.eligible.includes(c.code)}
                        onChange={() => toggle(g, c.code)} />
                      <span className="font-display font-bold">{c.code}</span>
                    </label>
                  ))}
                </fieldset>
              )}
            </li>
          )
        })}
      </ul>

      {failure && <Notice tone="pink" role="status">{failure}</Notice>}
      <div>
        <Button onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save requirements'}</Button>
      </div>
    </Card>
  )
}

// --- terms -------------------------------------------------------------------------------------------------------

const DATE_FIELDS = [
  { key: 'registrationOpens', label: 'Registration opens' },
  { key: 'startDate', label: 'Classes begin' },
  { key: 'lastAdd', label: 'Last day to add' },
  { key: 'lastDrop', label: 'Last day to drop' },
  { key: 'endDate', label: 'Classes end' },
]

// Same rules and messages as services/admin_catalog._check_dates (YYYY-MM-DD strings compare as dates).
function checkDates(d) {
  const found = {}
  if (!d.startDate) found.startDate = 'Enter the first day of classes.'
  if (!d.endDate) found.endDate = 'Enter the last day of classes.'
  if (d.startDate && d.endDate && d.endDate <= d.startDate) found.endDate = 'Classes end must be after classes begin.'
  if (d.lastAdd && d.startDate && d.lastAdd < d.startDate) found.lastAdd = "The last day to add can't be before classes begin."
  if (d.lastDrop && d.lastAdd && d.lastDrop < d.lastAdd) found.lastDrop = "The last day to drop can't be before the last day to add."
  return found
}

function TermsTab({ onSaved }) {
  const { data, error, reload } = useApi('/admin/catalog/terms')
  const [termId, setTermId] = useState(null)
  const [adding, setAdding] = useState(false)

  if (error && !data) return <ErrorState message={error.message} onRetry={reload} />
  if (!data) return <Loading label="Loading terms…" />

  const term = data.terms.find((t) => t.id === (termId ?? data.nextTermId)) ?? data.terms.at(-1)

  return (
    <div className="flex flex-col gap-4">
      {adding && (
        <AddTermPanel onCancel={() => setAdding(false)}
          onAdded={(row) => { setAdding(false); setTermId(row.id); onSaved(`${row.name} added.`); reload() }} />
      )}
      {term ? (
        <TermEditor key={term.id} term={term} terms={data.terms} onTerm={setTermId}
          onAdd={() => setAdding((on) => !on)} adding={adding}
          onSaved={() => { onSaved('Dates saved as a draft.'); reload() }} />
      ) : <Card><Empty>No terms yet.</Empty></Card>}
    </div>
  )
}

function TermEditor({ term, terms, onTerm, onAdd, adding, onSaved }) {
  const id = useId()
  const [dates, setDates] = useState(() => Object.fromEntries(DATE_FIELDS.map(({ key }) => [key, term[key] ?? ''])))
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState(null)

  const save = async (event) => {
    event.preventDefault()
    const found = checkDates(dates)
    setErrors(found)
    setFailure(null)
    if (Object.keys(found).length) return
    const body = Object.fromEntries(DATE_FIELDS.filter(({ key }) => dates[key]).map(({ key }) => [key, dates[key]]))
    setBusy(true)
    try {
      await api(`/admin/catalog/terms/${term.id}`, { method: 'PUT', body })
      onSaved()
    } catch (err) {
      if (err.status === 422 && err.details?.length) setErrors(fieldErrors(err))
      else setFailure(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" aria-labelledby={`${id}-title`} className="gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Field id={`${id}-term`} label="Term">
          <Select id={`${id}-term`} className="w-auto min-w-[200px]" value={term.id} onChange={(e) => onTerm(Number(e.target.value))}>
            {terms.map((t) => (
              <option key={t.id} value={t.id}>{t.name}{t.isCurrent ? ' (current)' : ''}{t.draft ? ' · draft' : ''}</option>
            ))}
          </Select>
        </Field>
        <Button variant="secondary" size="sm" onClick={onAdd} aria-expanded={adding}>Add term</Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <h2 id={`${id}-title`} className="m-0 text-xl font-bold">{term.name} key dates</h2>
        {term.draft && <Pill tone="amber">Draft</Pill>}
      </div>
      <form onSubmit={save} noValidate className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DATE_FIELDS.map(({ key, label }) => (
            <Field key={key} id={`${id}-${key}`} label={label} error={errors[key]}>
              <TextInput id={`${id}-${key}`} type="date" value={dates[key]}
                onChange={(e) => setDates((d) => ({ ...d, [key]: e.target.value }))} />
            </Field>
          ))}
        </div>
        {failure && <Notice tone="pink" role="status">{failure}</Notice>}
        <div>
          <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save dates'}</Button>
        </div>
      </form>
    </Card>
  )
}

function AddTermPanel({ onAdded, onCancel }) {
  const id = useId()
  const [form, setForm] = useState({ name: '', startDate: '', endDate: '' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState(null)
  const set = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    const found = {}
    if (!/^(Spring|Summer|Fall) \d{4}$/i.test(form.name.trim())) found.name = 'Use a name like "Spring 2028".'
    Object.assign(found, checkDates(form))
    setErrors(found)
    setFailure(null)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      onAdded(await api('/admin/catalog/terms', { method: 'POST', body: { ...form, name: form.name.trim() } }))
    } catch (err) {
      if (err.status === 409) setErrors({ name: err.message })
      else if (err.status === 422 && err.details?.length) setErrors(fieldErrors(err))
      else setFailure(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" aria-label="Add a term" className="gap-4">
      <CardHeader title="Add a term" subtitle="New terms are available right away; offer courses in them to use them." />
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field id={`${id}-name`} label="Name" error={errors.name}>
            <TextInput id={`${id}-name`} value={form.name} onChange={set('name')} placeholder="Spring 2028" autoComplete="off" />
          </Field>
          <Field id={`${id}-start`} label="Classes begin" error={errors.startDate}>
            <TextInput id={`${id}-start`} type="date" value={form.startDate} onChange={set('startDate')} />
          </Field>
          <Field id={`${id}-end`} label="Classes end" error={errors.endDate}>
            <TextInput id={`${id}-end`} type="date" value={form.endDate} onChange={set('endDate')} />
          </Field>
        </div>
        {failure && <Notice tone="pink" role="status">{failure}</Notice>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={busy}>{busy ? 'Adding…' : 'Add term'}</Button>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}
