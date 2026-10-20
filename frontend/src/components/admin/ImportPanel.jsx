import { useRef, useState } from 'react'
import Button from '../ui/Button.jsx'
import Card, { CardHeader } from '../ui/Card.jsx'
import Icon from '../ui/Icon.jsx'
import Notice from '../ui/Notice.jsx'
import { api, errorText } from '../../lib/api.js'

const MAX_BYTES = 1024 * 1024 // matches services/admin_users.MAX_IMPORT_BYTES
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

// Admin users: upsert users from a CSV (spec 31). `onDone()` reloads the list after an import.
export default function ImportPanel({ onDone, onCancel }) {
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  const pick = (event) => {
    const chosen = event.target.files?.[0] ?? null
    event.target.value = '' // picking the same file again still fires onChange
    setResult(null)
    if (!chosen) return
    if (!chosen.name.toLowerCase().endsWith('.csv')) {
      setFile(null)
      setResult({ tone: 'pink', text: 'Choose a .csv file.' })
    } else if (chosen.size > MAX_BYTES) {
      setFile(null)
      setResult({ tone: 'pink', text: 'The file is larger than 1 MB.' })
    } else {
      setFile(chosen)
    }
  }

  const upload = async () => {
    setBusy(true)
    setResult(null)
    try {
      const data = await api('/admin/users/import', { method: 'POST', body: await file.text(), contentType: 'text/csv' })
      const imported = data.created + data.updated
      setResult({
        tone: imported ? (data.skipped.length ? 'amber' : 'teal') : 'pink',
        text: `Imported ${plural(imported, 'user')} from ${file.name}.`
          + (data.created ? ` ${data.created} new ${data.created === 1 ? 'person was' : 'people were'} invited.` : ''),
        skipped: data.skipped,
      })
      if (imported) onDone()
    } catch (err) {
      setResult({ tone: 'pink', text: errorText(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" aria-label="Import users" className="gap-4">
      <CardHeader title="Import users from a CSV file"
        subtitle="Columns: name, email, role, program. Existing emails are updated, not duplicated." />
      <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" tabIndex={-1} aria-hidden="true" onChange={pick} />
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={() => input.current?.click()}>
          <Icon name="upload" size={18} />{file ? file.name : 'Choose CSV file'}
        </Button>
        <Button onClick={upload} disabled={!file || busy}>{busy ? 'Importing…' : 'Import'}</Button>
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
      </div>
      {result && (
        <Notice tone={result.tone} role="status">
          {result.text}
          {result.skipped?.length > 0 && (
            <>
              <span className="mt-1.5 block font-bold">Skipped {plural(result.skipped.length, 'row')}:</span>
              <ul className="m-0 pl-4">
                {result.skipped.map((s) => <li key={s.line}>Line {s.line}: {s.reason}</li>)}
              </ul>
            </>
          )}
        </Notice>
      )}
    </Card>
  )
}
