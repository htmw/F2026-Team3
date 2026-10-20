import { useState } from 'react'
import PageHeader from '../../components/layout/PageHeader.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import ColorSwatches from '../../components/ui/ColorSwatches.jsx'
import ConfirmInline from '../../components/ui/ConfirmInline.jsx'
import { Field, TextInput } from '../../components/ui/Field.jsx'
import Notice from '../../components/ui/Notice.jsx'
import { SwitchRow } from '../../components/ui/Switch.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { ACCENTS, applyAccent } from '../../lib/theme.js'
import { useApi } from '../../lib/useApi.js'
import { useSaveState } from '../../lib/useSaveState.js'

const SECTIONS = ['institution', 'security', 'retention', 'branding']
const ZONES = ['Eastern', 'Central', 'Pacific']
const TIMEOUTS = ['30 min', '2 hours', '8 hours']
const AI_RETENTION = ['30 days', '1 year', 'Until graduation']
const AUDIT_RETENTION = ['90 days', '1 year', '2 years']
const DOMAIN = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/i
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const TEXT_FIELDS = ['name', 'domain', 'supportEmail']

// Editable values only: the term list and demo mode come from the server.
const pick = (data) => {
  const { terms, ...institution } = data.institution // eslint-disable-line no-unused-vars
  return { ...Object.fromEntries(SECTIONS.map((key) => [key, data[key]])), institution }
}

function validate(institution) {
  const errors = {}
  if (!institution.name.trim() || institution.name.trim().length > 120) errors.name = 'Enter a name of 1 to 120 characters.'
  if (!DOMAIN.test(institution.domain.trim())) errors.domain = 'Enter a domain like pac.edu.'
  if (!EMAIL.test(institution.supportEmail.trim())) errors.supportEmail = 'Enter a valid email address.'
  return errors
}

// Only the fields that changed, grouped by section, so a save never rewrites what another admin just changed.
function changedFields(form, baseline) {
  const patch = {}
  for (const key of SECTIONS) {
    for (const [field, value] of Object.entries(form[key])) {
      const next = typeof value === 'string' && TEXT_FIELDS.includes(field) ? value.trim() : value
      if (next !== baseline[key][field]) patch[key] = { ...patch[key], [field]: next }
    }
  }
  return patch
}

// Admin settings (spec 37): institution, security, data retention, branding and the demo reset.
export default function AdminSettings() {
  const { user, refresh, refreshBadges } = useAuth()
  const toast = useToast()
  const { data, error, reload, setData } = useApi('/admin/settings')
  const [form, setForm] = useState(null)
  const [errors, setErrors] = useState({})
  const [saveError, setSaveError] = useState(null)
  const { label: saveLabel, saving, run } = useSaveState()

  if (error && !data) {
    return (
      <>
        <PageHeader title="Settings" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading settings…" />

  const baseline = pick(data)
  const current = form ?? baseline
  const patch = changedFields(current, baseline)
  const dirty = Object.keys(patch).length > 0
  const set = (section, values) => setForm({ ...current, [section]: { ...current[section], ...values } })

  const save = () => {
    const found = validate(current.institution)
    setErrors(found)
    setSaveError(null)
    if (Object.keys(found).length) return
    run(async () => {
      const saved = await api('/admin/settings', { method: 'PATCH', body: patch })
      setData(saved)
      setForm(null)
      applyAccent(saved.branding.accent)
      toast.show({ message: 'Settings saved' })
    }).catch((err) => {
      const fieldErrors = Object.fromEntries((err.details ?? []).filter((d) => d.field).map((d) => [d.field, d.message]))
      setErrors(fieldErrors)
      setSaveError(Object.keys(fieldErrors).length ? err.message : errorText(err))
    })
  }

  const afterReset = () => {
    setForm(null)
    setErrors({})
    reload()
    refresh()
    refreshBadges()
    applyAccent(ACCENTS[0].value)
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="Institution, security, data retention and branding" initials={user?.initials}
        actions={<Button onClick={save} disabled={saving || !dirty} aria-live="polite">{saveLabel}</Button>} />
      {saveError && <Notice tone="pink">{saveError}</Notice>}
      {dirty && <Notice tone="indigo">You have unsaved changes.</Notice>}

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <Institution value={current.institution} terms={data.institution.terms} errors={errors}
          onChange={(values) => set('institution', values)} />
        <div className="flex flex-col gap-4">
          <Security value={current.security} onChange={(values) => set('security', values)} />
          <Retention value={current.retention} onChange={(values) => set('retention', values)} />
          <Card as="section" className="gap-3">
            <CardHeader title="Branding" subtitle="Applies to everyone after saving" />
            <span className="text-sm font-semibold">Accent color</span>
            <ColorSwatches label="Accent color" options={ACCENTS} value={current.branding.accent}
              onChange={(accent) => set('branding', { accent })} />
          </Card>
        </div>
      </div>

      {data.demoMode && <DangerZone onReset={afterReset} />}
    </>
  )
}

function Choice({ label, children, note }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-semibold">{label}</span>
      {children}
      {note && <span className="text-[13px] text-muted">{note}</span>}
    </div>
  )
}

function Institution({ value, terms, errors, onChange }) {
  return (
    <Card as="section" className="gap-4">
      <CardHeader title="Institution" />
      <Field id="set-name" label="Institution name" error={errors.name}>
        <TextInput id="set-name" value={value.name} maxLength={120} onChange={(e) => onChange({ name: e.target.value })} />
      </Field>
      <Field id="set-domain" label="Email domain" hint="Student sign-up emails must use this domain." error={errors.domain}>
        <TextInput id="set-domain" value={value.domain} maxLength={100} autoComplete="off"
          onChange={(e) => onChange({ domain: e.target.value })} />
      </Field>
      <Field id="set-support" label="Support email" error={errors.supportEmail}>
        <TextInput id="set-support" type="email" value={value.supportEmail} maxLength={254}
          onChange={(e) => onChange({ supportEmail: e.target.value })} />
      </Field>
      {terms.length > 0 && (
        <Choice label="Current term" note={errors.currentTermId}>
          <SegmentedTabs label="Current term" value={value.currentTermId} onChange={(currentTermId) => onChange({ currentTermId })}
            options={terms.map((term) => ({ value: term.id, label: term.name }))} />
        </Choice>
      )}
      <Choice label="Time zone">
        <SegmentedTabs label="Time zone" value={value.timeZone} onChange={(timeZone) => onChange({ timeZone })} options={ZONES} />
      </Choice>
      <SwitchRow id="set-signup" label="Students can create their own accounts"
        description={`Sign-up is open to ${value.domain || 'school'} email addresses.`} checked={value.selfSignup}
        onChange={(selfSignup) => onChange({ selfSignup })} />
    </Card>
  )
}

function Security({ value, onChange }) {
  const { config } = useAuth()
  return (
    <Card as="section" className="gap-3">
      <CardHeader title="Security" />
      <div className="flex flex-col">
        <SwitchRow id="set-google" label="Allow Sign in with Google" checked={value.google}
          description={`Students and staff can sign in with a Google account instead of a password.${
            value.google && config?.googleEnabled === false ? ' Google isn’t configured on the server yet.' : ''}`}
          onChange={(google) => onChange({ google })} />
        <SwitchRow id="set-mfa" label="Two-step sign-in for staff" checked={value.mfa}
          description="Advisors and admins confirm sign-in on their phone. Takes effect when two-step sign-in is available."
          onChange={(mfa) => onChange({ mfa })} />
        <SwitchRow id="set-ip" label="Log IP addresses" description="Shown in the audit log." checked={value.ipLog}
          onChange={(ipLog) => onChange({ ipLog })} />
      </div>
      <Choice label="Sign people out after" note="“Keep me signed in” sessions still last 30 days.">
        <SegmentedTabs label="Sign people out after" value={value.timeout} onChange={(timeout) => onChange({ timeout })} options={TIMEOUTS} />
      </Choice>
    </Card>
  )
}

function Retention({ value, onChange }) {
  return (
    <Card as="section" className="gap-4">
      <CardHeader title="Data retention" />
      <Choice label="Keep AI conversations for">
        <SegmentedTabs label="Keep AI conversations for" value={value.ai} onChange={(ai) => onChange({ ai })} options={AI_RETENTION} />
      </Choice>
      <Choice label="Keep the audit log for">
        <SegmentedTabs label="Keep the audit log for" value={value.audit} onChange={(audit) => onChange({ audit })} options={AUDIT_RETENTION} />
      </Choice>
      <span className="text-[13px] text-muted">Degree plans and approvals are kept as academic records.</span>
    </Card>
  )
}

function DangerZone({ onReset }) {
  const [status, setStatus] = useState('')

  const reset = async () => {
    setStatus('')
    try {
      const result = await api('/admin/demo/reset', { method: 'POST' })
      setStatus(result.message)
      onReset()
    } catch (err) {
      setStatus(errorText(err))
      return false
    }
  }

  return (
    <Card as="section" aria-labelledby="danger-zone" className="mt-4 gap-3 border-2 border-pink-ink">
      <h2 id="danger-zone" className="m-0 text-xl font-bold">Danger zone</h2>
      <p className="m-0 text-sm text-slate">
        Reset demo data removes all sample students, plans and messages. Real accounts are not affected.
      </p>
      <div>
        <ConfirmInline label="Reset demo data" warning="Are you sure?" confirmLabel="Yes, reset" busyLabel="Resetting…"
          onConfirm={reset} />
      </div>
      <p className="m-0 text-sm font-semibold" role="status" aria-live="polite">{status}</p>
    </Card>
  )
}
