import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import SaveBar from '../../components/settings/SaveBar.jsx'
import SectionNav from '../../components/settings/SectionNav.jsx'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import { Field, TextInput } from '../../components/ui/Field.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import { SwitchRow } from '../../components/ui/Switch.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useSaveState } from '../../lib/useSaveState.js'

const SECTIONS = [
  { id: 'profile', label: 'Profile' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'booking', label: 'Booking' },
]

const NOTIFY_TOGGLES = [
  ['newApproval', 'New approval requests', 'When an advisee submits a plan, form or request.'],
  ['booking', 'Booking requests', 'When an advisee asks for a meeting.'],
  ['messages', 'Advisee messages', 'Direct messages from advisees.'],
  ['weeklyDigest', 'Weekly digest', 'Monday morning summary of your caseload.'],
]

const APPROVAL_TOGGLES = [
  ['precheck', 'Run Acadmate pre-checks', 'Check plans against degree requirements before you review them.'],
  ['remindAfter3Days', 'Remind me about requests older than 3 days', 'Keeps response times down before registration.'],
]

const LENGTHS = [{ value: 15, label: '15 min' }, { value: 30, label: '30 min' }, { value: 45, label: '45 min' }]
const WINDOWS = ['1 week ahead', '2 weeks ahead', '4 weeks ahead']
const SECTION = 'scroll-mt-6 gap-3'

const toDraft = (data) => ({
  profile: { fullName: data.profile.fullName, email: data.profile.email },
  advisor: {
    title: data.advisor.title ?? '', office: data.advisor.office ?? '', meetingLength: data.advisor.meetingLength,
    bookingWindow: data.advisor.bookingWindow, autoConfirm: data.advisor.autoConfirm,
  },
  notify: data.notify,
  approvals: data.approvals,
})

const changed = (draft, base) => Object.fromEntries(Object.entries(draft)
  .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value])
  .filter(([key, value]) => value !== (typeof base[key] === 'string' ? base[key].trim() : base[key])))

// Advisor settings (spec 27): profile, notifications, approvals and booking rules behind one Save.
export default function AdvisorSettings() {
  const { user } = useAuth()
  const location = useLocation()
  const settings = useApi('/advisor/settings')
  const ready = Boolean(settings.data)

  // The router doesn't scroll to #hash links (e.g. Approval settings on Approvals); do it once the sections exist.
  useEffect(() => {
    if (ready && location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView()
  }, [ready, location.hash])

  if (settings.error && !ready) {
    return (
      <>
        <PageHeader title="Settings" />
        <ErrorState message={settings.error.message} onRetry={settings.reload} />
      </>
    )
  }
  if (!ready) return <Loading label="Loading your settings…" />

  return (
    <>
      <PageHeader title="Settings" subtitle="Your profile, notifications, approvals and booking rules" initials={user?.initials} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[200px_minmax(0,1fr)]">
        <SectionNav sections={SECTIONS} />
        <div className="flex min-w-0 flex-col gap-4">
          <SettingsForm data={settings.data} />
        </div>
      </div>
    </>
  )
}

function SettingsForm({ data }) {
  const { refresh } = useAuth()
  const [baseline, setBaseline] = useState(() => toDraft(data))
  const [draft, setDraft] = useState(baseline)
  const { label: saveLabel, saving, run } = useSaveState()
  const [saveError, setSaveError] = useState(null)
  const [nameError, setNameError] = useState(null)

  const set = (group, key, value) => {
    setSaveError(null)
    if (key === 'fullName') setNameError(null)
    setDraft((d) => ({ ...d, [group]: { ...d[group], [key]: value } }))
  }

  const profileChanges = changed(draft.profile, baseline.profile)
  const advisorChanges = changed(draft.advisor, baseline.advisor)
  const notifyChanges = changed(draft.notify, baseline.notify)
  const approvalChanges = changed(draft.approvals, baseline.approvals)
  const settingsBody = {
    ...advisorChanges,
    ...(Object.keys(notifyChanges).length ? { notify: notifyChanges } : {}),
    ...(Object.keys(approvalChanges).length ? { approvals: approvalChanges } : {}),
  }
  const dirty = Object.keys(profileChanges).length > 0 || Object.keys(settingsBody).length > 0

  const save = async () => {
    if (!draft.profile.fullName.trim()) {
      setNameError('Enter your full name.')
      document.getElementById('adv-fullName')?.focus()
      return
    }
    setSaveError(null)
    await run(async () => {
      if (Object.keys(profileChanges).length) {
        const { user } = await api('/users/me', { method: 'PATCH', body: profileChanges })
        const next = { fullName: user.fullName, email: user.email }
        setBaseline((b) => ({ ...b, profile: next }))
        setDraft((d) => ({ ...d, profile: next }))
        refresh()
      }
      if (Object.keys(settingsBody).length) {
        const saved = await api('/advisor/settings', { method: 'PATCH', body: settingsBody })
        const next = toDraft(saved)
        setBaseline((b) => ({ ...next, profile: b.profile }))
        setDraft((d) => ({ ...next, profile: d.profile }))
      }
    }).catch((err) => setSaveError(errorText(err)))
  }

  const discard = () => { setDraft(baseline); setNameError(null); setSaveError(null) }

  return (
    <>
      <Card as="section" id="profile" aria-labelledby="profile-title" className={SECTION}>
        <h2 id="profile-title" className="m-0 text-lg font-bold">Profile</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="adv-fullName" label="Full name" error={nameError}>
            <TextInput id="adv-fullName" autoComplete="name" maxLength={120} value={draft.profile.fullName}
              onChange={(e) => set('profile', 'fullName', e.target.value)} />
          </Field>
          <Field id="adv-title" label="Title">
            <TextInput id="adv-title" maxLength={100} value={draft.advisor.title}
              onChange={(e) => set('advisor', 'title', e.target.value)} />
          </Field>
          <Field id="adv-office" label="Office">
            <TextInput id="adv-office" maxLength={120} value={draft.advisor.office}
              onChange={(e) => set('advisor', 'office', e.target.value)} />
          </Field>
          <Field id="adv-email" label="Email">
            <TextInput id="adv-email" type="email" autoComplete="email" maxLength={254} value={draft.profile.email}
              onChange={(e) => set('profile', 'email', e.target.value)} />
          </Field>
          {data.advisor.department && (
            <Field id="adv-department" label="Department" hint="Managed by your school.">
              <TextInput id="adv-department" value={data.advisor.department} disabled className="bg-surface-sunk text-muted" />
            </Field>
          )}
        </div>
      </Card>

      <Card as="section" id="notifications" aria-labelledby="notifications-title" className={SECTION}>
        <h2 id="notifications-title" className="m-0 text-lg font-bold">Notifications</h2>
        <div className="flex flex-col">
          {NOTIFY_TOGGLES.map(([key, label, description]) => (
            <SwitchRow key={key} id={`notify-${key}`} label={label} description={description} checked={draft.notify[key]}
              onChange={(next) => set('notify', key, next)} />
          ))}
        </div>
      </Card>

      <Card as="section" id="approvals" aria-labelledby="approvals-title" className={SECTION}>
        <h2 id="approvals-title" className="m-0 text-lg font-bold">Approvals</h2>
        <div className="flex flex-col">
          {APPROVAL_TOGGLES.map(([key, label, description]) => (
            <SwitchRow key={key} id={`approvals-${key}`} label={label} description={description} checked={draft.approvals[key]}
              onChange={(next) => set('approvals', key, next)} />
          ))}
        </div>
        <Notice tone="teal" icon="shield">Acadmate never approves anything on its own. Pre-checks only flag issues for you.</Notice>
      </Card>

      <Card as="section" id="booking" aria-labelledby="booking-title" className={SECTION}>
        <h2 id="booking-title" className="m-0 text-lg font-bold">Booking</h2>
        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold">Default meeting length</span>
          <SegmentedTabs label="Default meeting length" options={LENGTHS} value={draft.advisor.meetingLength}
            onChange={(value) => set('advisor', 'meetingLength', value)} />
        </div>
        <div className="flex flex-col gap-2 border-t border-canvas pt-3.5">
          <span className="text-sm font-semibold">Students can book up to</span>
          <SegmentedTabs label="Students can book up to" options={WINDOWS} value={draft.advisor.bookingWindow}
            onChange={(value) => set('advisor', 'bookingWindow', value)} />
        </div>
        <div className="flex flex-col border-t border-canvas pt-1">
          <SwitchRow id="booking-autoConfirm" label="Confirm bookings automatically"
            description="New bookings are confirmed right away instead of waiting for you to accept them."
            checked={draft.advisor.autoConfirm} onChange={(next) => set('advisor', 'autoConfirm', next)} />
        </div>
        <div>
          <Button variant="secondary" size="sm" to="/advisor/meetings#office-hours"><Icon name="clock" size={16} />Edit office hours</Button>
        </div>
      </Card>

      <SaveBar dirty={dirty} saving={saving} label={saveLabel} error={saveError} onSave={save} onDiscard={discard} />
    </>
  )
}
