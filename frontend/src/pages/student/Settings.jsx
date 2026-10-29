import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import SaveBar from '../../components/settings/SaveBar.jsx'
import SectionNav from '../../components/settings/SectionNav.jsx'
import Avatar from '../../components/ui/Avatar.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import ConfirmInline from '../../components/ui/ConfirmInline.jsx'
import { Field, Select, TextInput } from '../../components/ui/Field.jsx'
import { SwitchRow } from '../../components/ui/Switch.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useSaveState } from '../../lib/useSaveState.js'

const SECTIONS = [
  { id: 'set-profile', label: 'Profile' },
  { id: 'set-notify', label: 'Notifications' },
  { id: 'set-ai', label: 'AI advisor' },
  { id: 'set-signin', label: 'Sign-in' },
  { id: 'set-privacy', label: 'Privacy and account' },
]

const NOTIFY_TOGGLES = [
  ['deadlines', 'Deadline reminders', 'Assignments, forms and registration dates.'],
  ['messages', 'Advisor and faculty messages', 'Alert me when my advisor or a professor writes.'],
  ['suggestions', 'Acadmate suggestions', 'Study blocks, course ideas and plan changes.'],
  ['weeklySummary', 'Weekly summary email', 'Every Sunday evening: the week ahead.'],
  ['sms', 'Text message alerts', 'Only for deadlines due within 24 hours.'],
]

const AI_TOGGLES = [
  ['useGrades', 'Use my grades', 'Lets Acadmate answer questions about your GPA and course grades.'],
  ['useSchedule', 'Use my schedule', 'Lets Acadmate read your classes, events and meetings.'],
  ['dashboardSuggestions', 'Dashboard suggestions', 'Show Acadmate’s next-term recommendation on your dashboard.'],
  ['shareWithAdvisor', 'Share AI conversations with my advisor', 'Your advisor can read your AI advisor conversations.'],
]

const REMINDER_OPTIONS = ['1 day before', '2 days before', '1 week before']
const SCHOOL_MANAGED = 'Managed by your school.'

const SECTION = 'scroll-mt-6 gap-3'

// One label/description/control row inside the Sign-in and Privacy cards.
function ActionRow({ title, description, children }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-canvas py-3.5 first:border-t-0">
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-[3px]">
        <span className="text-sm font-semibold">{title}</span>
        {description && <span className="text-[13px] text-muted">{description}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

function ProfileSection({ profile, form, setField, nameError, prefs, setPrefs, graduationOptions }) {
  const managed = [
    ['studentNumber', 'Student ID'],
    ['program', 'Program'],
    ['advisor', 'Advisor'],
    ['expectedGraduation', 'Expected graduation'],
  ].filter(([key]) => profile[key])
  return (
    <Card as="section" id="set-profile" aria-labelledby="set-profile-title" className={SECTION}>
      <h2 id="set-profile-title" className="m-0 text-lg font-bold">Profile</h2>
      <div className="flex items-center gap-3">
        <Avatar initials={profile.initials} tone="teal" size="lg" />
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-[15px] font-bold">{profile.fullName}</span>
          <span className="truncate text-[13px] text-muted">{profile.email}</span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field id="set-fullName" label="Full name" error={nameError}>
          <TextInput id="set-fullName" autoComplete="name" maxLength={120} value={form.fullName} onChange={(e) => setField('fullName', e.target.value)} />
        </Field>
        <Field id="set-preferred" label="Preferred name" hint="Used in greetings.">
          <TextInput id="set-preferred" autoComplete="nickname" maxLength={60} value={form.preferredName} onChange={(e) => setField('preferredName', e.target.value)} />
        </Field>
        <Field id="set-email" label="School email">
          <TextInput id="set-email" type="email" autoComplete="email" maxLength={254} value={form.email} onChange={(e) => setField('email', e.target.value)} />
        </Field>
        {managed.map(([key, label]) => (
          <Field key={key} id={`set-${key}`} label={label} hint={SCHOOL_MANAGED}>
            <TextInput id={`set-${key}`} value={profile[key]} disabled className="bg-surface-sunk text-muted" />
          </Field>
        ))}
        {profile.role === 'student' && graduationOptions.length > 0 && (
          <Field id="set-targetGraduation" label="Target graduation" hint="Acadmate plans your courses around this date.">
            <Select id="set-targetGraduation" value={prefs.targetGraduation ?? ''}
              onChange={(e) => setPrefs((p) => ({ ...p, targetGraduation: e.target.value || null }))}>
              {!prefs.targetGraduation && <option value="">Choose a date</option>}
              {prefs.targetGraduation && !graduationOptions.includes(prefs.targetGraduation) && (
                <option value={prefs.targetGraduation}>{prefs.targetGraduation}</option>
              )}
              {graduationOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
          </Field>
        )}
      </div>
    </Card>
  )
}

function NotificationsSection({ prefs, setPrefs }) {
  return (
    <Card as="section" id="set-notify" aria-labelledby="set-notify-title" className={SECTION}>
      <h2 id="set-notify-title" className="m-0 text-lg font-bold">Notifications</h2>
      <div className="flex flex-col">
        {NOTIFY_TOGGLES.map(([key, label, description]) => (
          <SwitchRow key={key} id={`notify-${key}`} label={label} description={description} checked={prefs.notify[key]}
            onChange={(next) => setPrefs((p) => ({ ...p, notify: { ...p.notify, [key]: next } }))} />
        ))}
      </div>
      <div className="flex flex-col gap-2 border-t border-canvas pt-3.5">
        <span className="text-sm font-semibold">Remind me about deadlines</span>
        <SegmentedTabs label="Reminder timing" options={REMINDER_OPTIONS} value={prefs.reminderTiming}
          onChange={(reminderTiming) => setPrefs((p) => ({ ...p, reminderTiming }))} />
      </div>
    </Card>
  )
}

function AiSection({ prefs, setPrefs }) {
  return (
    <Card as="section" id="set-ai" aria-labelledby="set-ai-title" className={SECTION}>
      <div className="flex flex-col gap-1">
        <h2 id="set-ai-title" className="m-0 text-lg font-bold">AI advisor</h2>
        <span className="text-sm text-muted">Choose what Acadmate may use when it answers you.</span>
      </div>
      <div className="flex flex-col">
        {AI_TOGGLES.map(([key, label, description]) => (
          <SwitchRow key={key} id={`ai-${key}`} label={label} description={description} checked={prefs.ai[key]}
            onChange={(next) => setPrefs((p) => ({ ...p, ai: { ...p.ai, [key]: next } }))} />
        ))}
      </div>
      <div className="flex flex-col gap-2 border-t border-canvas pt-3.5">
        <span className="text-sm font-semibold">Answer style</span>
        <SegmentedTabs label="Answer style" options={['Concise', 'Detailed']} value={prefs.aiStyle}
          onChange={(aiStyle) => setPrefs((p) => ({ ...p, aiStyle }))} />
      </div>
      <Notice tone="teal" icon="shield">
        Acadmate never registers you for or drops you from a course. It suggests plans; you and your advisor decide.
      </Notice>
    </Card>
  )
}

function SignInSection({ profile, google, onGoogleChanged }) {
  const toast = useToast()
  const [busy, setBusy] = useState(null) // 'google' | 'password'
  const [error, setError] = useState(null)
  const [resetSent, setResetSent] = useState(false)

  const connect = async () => {
    setBusy('google')
    setError(null)
    try {
      const { url } = await api('/users/me/google/connect', { method: 'POST' })
      window.location.assign(url)
    } catch (err) {
      setError(errorText(err))
      setBusy(null)
    }
  }

  const disconnect = async () => {
    setBusy('google')
    setError(null)
    try {
      await api('/users/me/google', { method: 'DELETE' })
      toast.show({ message: 'Google account disconnected' })
      onGoogleChanged()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const sendReset = async () => {
    setBusy('password')
    setError(null)
    try {
      await api('/auth/password-reset', { method: 'POST', body: { email: profile.email } })
      setResetSent(true)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card as="section" id="set-signin" aria-labelledby="set-signin-title" className={SECTION}>
      <h2 id="set-signin-title" className="m-0 text-lg font-bold">Sign-in</h2>
      <div className="flex flex-col">
        <ActionRow title="Sign in with Google"
          description={!google.available ? 'Google sign-in isn’t turned on for your school.'
            : google.connected ? `Signed in as ${google.email}` : 'Use your Google account instead of a password.'}>
          {google.available && google.connected && <Pill tone="teal">Connected</Pill>}
          {google.available && (google.connected
            ? <Button variant="secondary" size="sm" onClick={disconnect} disabled={busy != null}>{busy === 'google' ? 'Disconnecting…' : 'Disconnect'}</Button>
            : <Button variant="secondary" size="sm" onClick={connect} disabled={busy != null}>{busy === 'google' ? 'Opening Google…' : 'Connect'}</Button>)}
        </ActionRow>
        <ActionRow title="Password"
          description={profile.hasPassword ? 'We’ll email you a link to choose a new one.' : 'You sign in with Google only. Add a password as a backup.'}>
          <Button variant="secondary" size="sm" onClick={sendReset} disabled={busy != null || resetSent}>
            {busy === 'password' ? 'Sending…' : profile.hasPassword ? 'Change password' : 'Set a password'}
          </Button>
        </ActionRow>
      </div>
      {resetSent && <Notice tone="teal" role="status">Check your email — we sent a link to {profile.email}.</Notice>}
      {error && <Notice tone="pink" role="alert">{error}</Notice>}
    </Card>
  )
}

function PrivacySection({ profile, retention }) {
  const toast = useToast()
  const navigate = useNavigate()
  const { setUser } = useAuth()
  const [busy, setBusy] = useState(null) // 'export' | 'history' | 'calendar' | 'delete'
  const [password, setPassword] = useState('')
  const [deleteError, setDeleteError] = useState(null)

  // Each action resolves to true when it succeeded, so ConfirmInline can disarm itself.
  const run = async (key, action) => {
    setBusy(key)
    try {
      await action()
      return true
    } catch (err) {
      toast.show({ message: errorText(err) })
      return false
    } finally {
      setBusy(null)
    }
  }

  const download = () => run('export', async () => {
    const data = await api('/users/me/export', { method: 'POST' })
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const link = Object.assign(document.createElement('a'), { href: url, download: 'acadmate-export.json' })
    document.body.append(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    toast.show({ message: 'Your data was downloaded' })
  })

  const clearHistory = () => run('history', async () => {
    await api('/students/me/ai/threads', { method: 'DELETE' })
    toast.show({ message: 'Your AI chat history was cleared' })
  })

  const rotateCalendar = () => run('calendar', async () => {
    await api('/students/me/calendar/rotate', { method: 'POST' })
    toast.show({ message: 'New calendar link created — copy it from Schedule.' })
  })

  const deleteAccount = async () => {
    setBusy('delete')
    setDeleteError(null)
    try {
      await api('/users/me', { method: 'DELETE', body: profile.hasPassword ? { password } : {} })
      setUser(null)
      navigate('/login', { replace: true })
      return true
    } catch (err) {
      setDeleteError(errorText(err))
      setBusy(null)
      return false
    }
  }

  return (
    <Card as="section" id="set-privacy" aria-labelledby="set-privacy-title" className={SECTION}>
      <h2 id="set-privacy-title" className="m-0 text-lg font-bold">Privacy and account</h2>
      <div className="flex flex-col">
        <ActionRow title="Download my data" description="Your profile, courses, plans, messages and activity as one file.">
          <Button variant="secondary" size="sm" onClick={download} disabled={busy === 'export'}>
            <Icon name="download" size={16} />{busy === 'export' ? 'Preparing…' : 'Download'}
          </Button>
        </ActionRow>
        <ActionRow title="Clear AI conversation history"
          description={`Removes past chats. Saved degree plans stay. Your school keeps AI advisor conversations for ${retention.toLowerCase()}.`}>
          <ConfirmInline triggerVariant="secondary" label="Clear history" confirmLabel="Yes, clear history" busyLabel="Clearing…" busy={busy === 'history'}
            warning="Delete every AI advisor conversation? This can’t be undone." onConfirm={clearHistory} />
        </ActionRow>
        <ActionRow title="Reset calendar link" description="Makes a new private feed link for Google Calendar or Outlook.">
          <ConfirmInline triggerVariant="secondary" label="Reset link" confirmLabel="Yes, reset link" busyLabel="Resetting…" busy={busy === 'calendar'}
            warning="Calendar apps subscribed to the old link will stop updating. You’ll need to subscribe again from Schedule." onConfirm={rotateCalendar} />
        </ActionRow>
        <ActionRow title="Delete account" description="Permanently deletes your Acadmate account. Your school records are not affected.">
          <ConfirmInline triggerVariant="secondary" label="Delete account" confirmLabel="Delete my account" busyLabel="Deleting…" busy={busy === 'delete'}
            disabled={profile.hasPassword && !password}
            warning="This permanently deletes your Acadmate account, plans, messages and AI conversations. It can’t be undone."
            onConfirm={deleteAccount}>
            {profile.hasPassword && (
              <Field id="delete-password" label="Enter your password to confirm">
                <TextInput id="delete-password" type="password" autoComplete="current-password" maxLength={128} value={password}
                  onChange={(e) => { setPassword(e.target.value); setDeleteError(null) }} />
              </Field>
            )}
            {deleteError && <Notice tone="pink" role="alert">{deleteError}</Notice>}
          </ConfirmInline>
        </ActionRow>
      </div>
    </Card>
  )
}

const profileForm = (profile) => ({ fullName: profile.fullName, preferredName: profile.preferredName ?? '', email: profile.email })
// graduationOptions comes with the preferences but isn't one; keep it out of the draft.
const prefsForm = ({ graduationOptions, ...prefs }) => prefs

// Profile, notification and AI preferences share one draft and one Save; Sign-in and Privacy act immediately.
function SettingsForm({ me, retention, reloadMe }) {
  const { refresh } = useAuth()
  const graduationOptions = me.preferences.graduationOptions ?? []
  const [baseline, setBaseline] = useState(() => ({ profile: profileForm(me.profile), prefs: prefsForm(me.preferences) }))
  const [draft, setDraft] = useState(baseline)
  const { label: saveLabel, saving, run } = useSaveState()
  const [saveError, setSaveError] = useState(null)
  const [nameError, setNameError] = useState(null)

  const edited = () => setSaveError(null)
  const setField = (key, value) => {
    edited()
    if (key === 'fullName') setNameError(null)
    setDraft((d) => ({ ...d, profile: { ...d.profile, [key]: value } }))
  }
  const setPrefs = (change) => { edited(); setDraft((d) => ({ ...d, prefs: change(d.prefs) })) }

  const profileChanges = Object.fromEntries(Object.entries(draft.profile)
    .map(([key, value]) => [key, value.trim()])
    .filter(([key, value]) => value !== baseline.profile[key]))
  const prefsDirty = JSON.stringify(draft.prefs) !== JSON.stringify(baseline.prefs)
  const dirty = Object.keys(profileChanges).length > 0 || prefsDirty

  const save = async () => {
    if (!draft.profile.fullName.trim()) {
      setNameError('Enter your full name.')
      document.getElementById('set-fullName')?.focus()
      return
    }
    setSaveError(null)
    await run(async () => {
      if (Object.keys(profileChanges).length) {
        const body = { ...profileChanges }
        if ('preferredName' in body) body.preferredName = body.preferredName || null
        const { user } = await api('/users/me', { method: 'PATCH', body })
        const next = profileForm(user)
        setBaseline((b) => ({ ...b, profile: next }))
        setDraft((d) => ({ ...d, profile: next }))
        refresh()
        reloadMe()
      }
      if (prefsDirty) {
        const { preferences } = await api('/users/me/preferences', { method: 'PATCH', body: draft.prefs })
        const next = prefsForm(preferences)
        setBaseline((b) => ({ ...b, prefs: next }))
        setDraft((d) => ({ ...d, prefs: next }))
        // Target graduation also changes the read-only Expected graduation field.
        if (next.targetGraduation !== baseline.prefs.targetGraduation) reloadMe()
      }
    }).catch((err) => setSaveError(errorText(err)))
  }

  const discard = () => { setDraft(baseline); setNameError(null); setSaveError(null) }

  return (
    <>
      <ProfileSection profile={me.profile} form={draft.profile} setField={setField} nameError={nameError}
        prefs={draft.prefs} setPrefs={setPrefs} graduationOptions={graduationOptions} />
      <NotificationsSection prefs={draft.prefs} setPrefs={setPrefs} />
      <AiSection prefs={draft.prefs} setPrefs={setPrefs} />

      <SaveBar dirty={dirty} saving={saving} label={saveLabel} error={saveError} onSave={save} onDiscard={discard} />

      <SignInSection profile={me.profile} google={me.google} onGoogleChanged={reloadMe} />
      <PrivacySection profile={me.profile} retention={retention} />
    </>
  )
}

export default function StudentSettings() {
  const { user } = useAuth()
  const toast = useToast()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const me = useApi('/users/me')
  const context = useApi('/students/me/ai/context')
  const ready = Boolean(me.data && context.data)

  // Back from Google's account linking (?google=connected|taken).
  const google = searchParams.get('google')
  useEffect(() => {
    if (!google) return
    toast.show({ message: google === 'connected' ? 'Google account connected' : 'That Google account is already linked to another user' })
    setSearchParams({}, { replace: true })
  }, [google, setSearchParams, toast])

  // The router doesn't scroll to #hash links (e.g. from Schedule); do it once the sections exist.
  useEffect(() => {
    if (ready && location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView()
  }, [ready, location.hash])

  const error = me.error ?? context.error
  if (error && !ready) {
    return (
      <>
        <PageHeader title="Settings" />
        <ErrorState message={error.message} onRetry={() => { me.reload(); context.reload() }} />
      </>
    )
  }
  if (!ready) return <Loading label="Loading your settings…" />

  return (
    <>
      <PageHeader title="Settings" subtitle="Your profile, notifications, AI advisor and account" initials={user?.initials} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[200px_minmax(0,1fr)]">
        <SectionNav sections={SECTIONS} />
        <div className="flex min-w-0 flex-col gap-4">
          <SettingsForm me={me.data} retention={context.data.retention} reloadMe={me.reload} />
        </div>
      </div>
    </>
  )
}
