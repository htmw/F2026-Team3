import { useState } from 'react'
import PageHeader from '../../components/layout/PageHeader.jsx'
import MasterDetail, { DetailEmpty, ListRow } from '../../components/layout/MasterDetail.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import Button from '../../components/ui/Button.jsx'
import Pill, { Chip, PILL_TONES } from '../../components/ui/Pill.jsx'
import Icon from '../../components/ui/Icon.jsx'
import ProgressBar from '../../components/ui/ProgressBar.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import Switch, { SwitchRow } from '../../components/ui/Switch.jsx'
import Avatar from '../../components/ui/Avatar.jsx'
import Notice from '../../components/ui/Notice.jsx'
import BarChart from '../../components/ui/BarChart.jsx'
import Dialog from '../../components/ui/Dialog.jsx'
import SearchInput from '../../components/ui/SearchInput.jsx'
import { Field, Select, TextInput, Textarea } from '../../components/ui/Field.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import StatTile from '../../components/ui/StatTile.jsx'
import ExportButton from '../../components/ui/ExportButton.jsx'
import ConfirmInline from '../../components/ui/ConfirmInline.jsx'
import { useSaveState } from '../../lib/useSaveState.js'
import { ACCENTS, applyAccent } from '../../lib/theme.js'

// Dev-only visual reference for the shared components (registered only when import.meta.env.DEV).
// Fixture data is allowed here because this page never ships to production.
const ICONS = ['cap', 'bell', 'sparkle', 'send', 'check', 'user', 'eye', 'mail', 'alert', 'info', 'calendar', 'clock', 'search',
  'settings', 'download', 'upload', 'trash', 'chat', 'plus', 'x', 'chevronLeft', 'chevronRight', 'chevronDown', 'edit', 'users',
  'book', 'filter', 'lock', 'refresh', 'undo', 'external', 'flag', 'thumbUp', 'thumbDown', 'pin']
const PEOPLE = [
  { id: 1, name: 'Sample Student One', status: 'On track' },
  { id: 2, name: 'Sample Student Two', status: 'Needs attention' },
  { id: 3, name: 'Sample Student Three', status: 'Graduating' },
]

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// Save changes → Saving… → Saved (2 s), driven by a fake request.
function SaveDemo() {
  const [dirty, setDirty] = useState(true)
  const { label, saving, run } = useSaveState()
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button onClick={() => run(() => wait(800)).then(() => setDirty(false))} disabled={saving || !dirty} aria-live="polite">{label}</Button>
      <Button variant="secondary" onClick={() => setDirty(true)}>Make a change</Button>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <Card className="gap-4">
      <CardHeader title={title} />
      {children}
    </Card>
  )
}

export default function UiKit() {
  const [tab, setTab] = useState('all')
  const [switches, setSwitches] = useState({ a: true, b: false })
  const [selected, setSelected] = useState(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [query, setQuery] = useState('')
  const toast = useToast()
  const person = PEOPLE.find((item) => item.id === selected)

  return (
    <div className="box-border min-h-screen bg-canvas p-5 font-sans text-navy">
      <div className="mx-auto flex max-w-[1100px] flex-col gap-5">
        <PageHeader title="UI kit" subtitle="Dev-only reference for frontend/src/components"
          search={{ label: 'Search', placeholder: 'Controlled search…', value: query, onChange: setQuery }}
          actions={<ExportButton href="#" />} />

        <Section title="Buttons">
          <div className="flex flex-wrap gap-2">
            {['primary', 'secondary', 'google', 'disabled', 'sun', 'mint', 'danger'].map((variant) => (
              <Button key={variant} variant={variant}>{variant}</Button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2 rounded-xl bg-navy p-4"><Button variant="ghostDark">ghostDark</Button></div>
        </Section>

        <Section title="Accent (Admin → Settings → Branding)">
          <div role="group" aria-label="Accent colour" className="flex flex-wrap gap-2">
            {ACCENTS.map((accent) => (
              <Button key={accent.value} variant="secondary" onClick={() => applyAccent(accent.value)}>
                <span aria-hidden="true" className="size-4 rounded-full" style={{ background: accent.value }} />{accent.label}
              </Button>
            ))}
          </div>
          <span className="text-[13px] text-muted">Links, primary buttons, progress bars and charts follow the accent.</span>
        </Section>

        <section aria-label="Stat tiles" className="flex flex-wrap gap-4">
          <StatTile label="Credits completed" value="78 / 120" pill={{ tone: 'teal', text: 'On track' }} pct={65} note="42 credits to go" />
          <StatTile label="Major requirements" value="9 / 14" pct={64} warn note="1 at risk this term" />
          <StatTile label="Open items" value="5" note="2 due this week" />
        </section>

        <Section title="Save, export, confirm">
          <SaveDemo />
          <div><ExportButton href="#" /></div>
          <ConfirmInline label="Reset demo data" confirmLabel="Yes, reset" busyLabel="Resetting…"
            warning="Are you sure? This replaces all demo records. Real accounts are not affected."
            onConfirm={async () => { await wait(800); toast.show({ message: 'Demo data reset' }) }} />
        </Section>

        <Section title="Pills, chips, avatars">
          <div className="flex flex-wrap items-center gap-2">
            {Object.keys(PILL_TONES).map((tone) => <Pill key={tone} tone={tone}>{tone}</Pill>)}
            {Object.keys(PILL_TONES).map((tone) => <Chip key={tone} tone={tone}>CS 101</Chip>)}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {Object.keys(PILL_TONES).map((tone) => <Avatar key={tone} name={`Tone ${tone}`} tone={tone} />)}
            {PEOPLE.map((item) => <Avatar key={item.id} name={item.name} size="sm" />)}
            <Avatar name="Large Avatar" size="lg" />
          </div>
        </Section>

        <Section title="Icons">
          <div className="flex flex-wrap gap-4">
            {ICONS.map((name) => (
              <div key={name} className="flex w-20 flex-col items-center gap-1 text-[11px] text-muted">
                <Icon name={name} color="var(--color-navy)" />{name}
              </div>
            ))}
          </div>
        </Section>

        <Section title="Segmented tabs, search, switches">
          <SegmentedTabs label="Filter" value={tab} onChange={setTab}
            options={[{ value: 'all', label: 'All', count: 12 }, { value: 'open', label: 'Open', count: 4 }, { value: 'done', label: 'Done', count: 8 }]} />
          <SearchInput label="In-card search" placeholder="Search courses…" value={query} onChange={setQuery} />
          <div className="flex items-center gap-3"><Switch label="Standalone" checked={switches.a} onChange={(a) => setSwitches({ ...switches, a })} /> standalone</div>
          <div>
            <SwitchRow id="sw-b" label="Email reminders" description="Send a reminder 24 h before deadlines"
              checked={switches.b} onChange={(b) => setSwitches({ ...switches, b })} />
            <SwitchRow id="sw-c" label="Disabled setting" description="Turned off by your administrator" checked={false} onChange={() => {}} disabled />
          </div>
        </Section>

        <Section title="Form fields">
          <Field id="kit-name" label="Name" hint="As it appears on your transcript"><TextInput id="kit-name" /></Field>
          <Field id="kit-email" label="Email" error="Use your school email address."><TextInput id="kit-email" type="email" defaultValue="someone@example.com" /></Field>
          <Field id="kit-role" label="Role"><Select id="kit-role"><option>Student</option><option>Advisor</option></Select></Field>
          <Field id="kit-note" label="Note"><Textarea id="kit-note" /></Field>
        </Section>

        <Section title="Notices, progress, chart">
          {['amber', 'teal', 'pink', 'indigo'].map((tone) => <Notice key={tone} tone={tone}>A {tone} notice.</Notice>)}
          <ProgressBar value={64} label="Progress" />
          <BarChart unit="h" label="Example" data={[
            { label: 'Mon', value: 2 }, { label: 'Tue', value: 4 }, { label: 'Wed', value: 1 }, { label: 'Thu', value: 3, highlight: true },
          ]} />
        </Section>

        <Section title="Dialog and toast">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setDialogOpen(true)}>Open dialog</Button>
            <Button variant="secondary" onClick={() => toast.show({ message: 'Approved', actionLabel: 'Undo', onAction: () => toast.show({ message: 'Reopened' }) })}>
              Show toast
            </Button>
          </div>
          <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} title="Invite users"
            actions={<><Button variant="secondary" onClick={() => setDialogOpen(false)}>Cancel</Button><Button onClick={() => setDialogOpen(false)}>Send invites</Button></>}>
            <Field id="kit-invite" label="Emails"><TextInput id="kit-invite" placeholder="a@school.edu, b@school.edu" /></Field>
          </Dialog>
        </Section>

        <MasterDetail
          list={(
            <Card className="gap-1 p-3">
              {PEOPLE.map((item) => (
                <ListRow key={item.id} selected={item.id === selected} onSelect={() => setSelected(item.id)}>
                  <Avatar name={item.name} size="sm" />
                  <span className="flex-1 text-sm font-semibold">{item.name}</span>
                  <Pill tone={item.status === 'On track' ? 'teal' : item.status === 'Graduating' ? 'indigo' : 'amber'}>{item.status}</Pill>
                </ListRow>
              ))}
            </Card>
          )}
          detail={<Card>{person ? <CardHeader title={person.name} subtitle={person.status} /> : <DetailEmpty />}</Card>} />

        <Section title="Status states">
          <Loading label="Loading example…" />
          <Empty>Nothing here right now.</Empty>
        </Section>
        <ErrorState message="Example error message from the API." onRetry={() => {}} />
      </div>
    </div>
  )
}
