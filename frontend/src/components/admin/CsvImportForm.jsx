import { useId, useState } from 'react'
import Button from '../ui/Button.jsx'
import { Field, Select } from '../ui/Field.jsx'
import Notice from '../ui/Notice.jsx'
import { api, errorText } from '../../lib/api.js'

// Header row each import type expects (services/imports.HEADERS).
const TYPES = {
  courses: { label: 'Courses', header: 'code,name,credits,type,description' },
  enrollments: { label: 'Enrollments', header: 'student_email,course_code,term,status' },
  grades: {
    label: 'Grades',
    header: 'student_email,course_code,term,grade,grade_points — or …,component,weight,score',
  },
}
const MAX_BYTES = 1024 * 1024
const SHOWN_SKIPS = 5

// CSV data import (spec 35): type, file, Upload. Reports the import and the skipped lines, then calls onDone().
export default function CsvImportForm({ onDone }) {
  const id = useId()
  const [type, setType] = useState('grades')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const upload = async (event) => {
    event.preventDefault()
    setError(null)
    setResult(null)
    if (!file) return setError('Choose a CSV file.')
    if (file.size > MAX_BYTES) return setError('The file is larger than 1 MB.')
    setBusy(true)
    try {
      setResult(await api(`/admin/imports?type=${type}`, { method: 'POST', body: await file.text(), contentType: 'text/csv' }))
      onDone?.()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const skipped = result?.skipped ?? []
  return (
    <form onSubmit={upload} noValidate className="flex flex-col gap-3">
      <Field id={`${id}-type`} label="File type" hint={`Header: ${TYPES[type].header}`}>
        <Select id={`${id}-type`} value={type} onChange={(e) => setType(e.target.value)}>
          {Object.entries(TYPES).map(([value, t]) => <option key={value} value={value}>{t.label}</option>)}
        </Select>
      </Field>
      <Field id={`${id}-file`} label="CSV file">
        <input id={`${id}-file`} type="file" accept=".csv,text/csv"
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setError(null) }}
          className="text-sm file:mr-3 file:cursor-pointer file:rounded-lg file:border file:border-line file:bg-surface file:px-3 file:py-2 file:text-sm file:font-semibold file:text-navy" />
      </Field>
      {error && <Notice tone="pink" role="status">{error}</Notice>}
      {result && (
        <Notice tone={skipped.length ? 'amber' : 'teal'} role="status">
          <span className="flex flex-col gap-1">
            <span>{result.message}{skipped.length ? ` · ${skipped.length} row${skipped.length === 1 ? '' : 's'} skipped` : ''}</span>
            {skipped.slice(0, SHOWN_SKIPS).map((s) => <span key={s.line} className="text-[13px]">Line {s.line}: {s.reason}</span>)}
            {skipped.length > SHOWN_SKIPS && <span className="text-[13px]">…and {skipped.length - SHOWN_SKIPS} more</span>}
          </span>
        </Notice>
      )}
      <div><Button type="submit" disabled={busy}>{busy ? 'Uploading…' : 'Upload'}</Button></div>
    </form>
  )
}
