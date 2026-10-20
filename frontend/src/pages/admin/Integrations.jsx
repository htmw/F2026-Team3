import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader.jsx'
import ApiKeyDialog from '../../components/admin/ApiKeyDialog.jsx'
import CsvImportForm from '../../components/admin/CsvImportForm.jsx'
import SmtpForm from '../../components/admin/SmtpForm.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import ConfirmInline from '../../components/ui/ConfirmInline.jsx'
import Notice from '../../components/ui/Notice.jsx'
import Pill from '../../components/ui/Pill.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api, errorText } from '../../lib/api.js'
import { relativeDate } from '../../lib/dates.js'
import { useApi } from '../../lib/useApi.js'
import { INTEGRATION_TONE } from '../../lib/status.js'

const IDS = ['csv', 'mail', 'gcal', 'outlook']
const CALENDARS = ['gcal', 'outlook']
// "created today", "created Aug 12".
const createdLabel = (value) => {
  const label = relativeDate(value)
  return label === 'Today' || label === 'Yesterday' ? label.toLowerCase() : label
}

// Admin integrations (spec 35): CSV import, email, calendars and API keys.
export default function AdminIntegrations() {
  const { user: me } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const { data, error, reload, setData } = useApi('/admin/integrations')
  const keys = useApi('/admin/api-keys')
  const [smtpOpen, setSmtpOpen] = useState(false)
  const selectedId = IDS.includes(params.get('id')) ? params.get('id') : 'csv'

  const select = (id) => setParams(id === 'csv' ? {} : { id }, { replace: true })
  const replaceRow = (row) => setData((current) => current && {
    ...current, integrations: current.integrations.map((r) => (r.id === row.id ? row : r)),
  })

  const connect = async (row) => {
    select(row.id)
    if (row.id === 'mail') {
      setSmtpOpen(true)
      return
    }
    try {
      const result = await api(`/admin/integrations/${row.id}/connect`, { method: 'POST' })
      if (result.url) window.location.assign(result.url) // calendar: continue at Google / Microsoft
      else {
        replaceRow(result)
        toast.show({ message: `${row.name} connected` })
      }
    } catch (err) {
      toast.show({ message: errorText(err) })
    }
  }

  const disconnect = async (row) => {
    try {
      replaceRow(await api(`/admin/integrations/${row.id}/disconnect`, { method: 'POST' }))
      if (row.id === 'mail') setSmtpOpen(false)
      toast.show({ message: `${row.name} disconnected` })
    } catch (err) {
      toast.show({ message: errorText(err) })
      return false
    }
  }

  if (error && !data) {
    return (
      <>
        <PageHeader title="Integrations" />
        <ErrorState message={error.message} onRetry={reload} />
      </>
    )
  }
  if (!data) return <Loading label="Loading integrations…" />

  const selected = data.integrations.find((r) => r.id === selectedId) ?? data.integrations[0]

  return (
    <>
      <PageHeader title="Integrations" subtitle="Data imports, email, calendars and API keys" initials={me?.initials} />
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]">
        <section aria-label="Integrations" className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {data.integrations.map((row) => (
            <IntegrationCard key={row.id} row={row} selected={row.id === selected.id}
              onDetails={() => { select(row.id); setSmtpOpen(false) }}
              onConnect={() => connect(row)} onDisconnect={() => disconnect(row)} />
          ))}
        </section>
        <div className="flex flex-col gap-4">
          <IntegrationDetails key={selected.id} row={selected} smtpOpen={smtpOpen && selected.id === 'mail'}
            onSmtp={setSmtpOpen} onChanged={(row) => { replaceRow(row); setSmtpOpen(false) }} onReload={reload} />
          <ApiKeys keys={keys} />
        </div>
      </div>
    </>
  )
}

function IntegrationCard({ row, selected, onDetails, onConnect, onDisconnect }) {
  return (
    <Card as="article" aria-label={row.name}
      className={`gap-3 ${selected ? 'border-2 border-accent' : 'border-2 border-transparent'}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="m-0 text-base font-bold">{row.name}</h2>
        <Pill tone={INTEGRATION_TONE[row.status]}>{row.status}</Pill>
      </div>
      <p className="m-0 text-[13px] text-slate">{row.desc}</p>
      <span className="text-xs text-muted">{row.sync}</span>
      <div className="mt-auto flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={onDetails} aria-pressed={selected}>Details</Button>
        {row.connected ? (
          <ConfirmInline label="Disconnect" triggerVariant="secondary" confirmLabel="Disconnect" busyLabel="Disconnecting…"
            warning={`Disconnect ${row.name}?${row.id === 'mail' ? ' Emails will only be written to the server log.' : ''}`}
            onConfirm={onDisconnect} />
        ) : <Button size="sm" onClick={onConnect}>Connect</Button>}
      </div>
    </Card>
  )
}

function IntegrationDetails({ row, smtpOpen, onSmtp, onChanged, onReload }) {
  const toast = useToast()
  const [syncing, setSyncing] = useState(false)

  const sync = async () => {
    setSyncing(true)
    try {
      onChanged(await api(`/admin/integrations/${row.id}/sync`, { method: 'POST' }))
      toast.show({ message: row.id === 'mail' ? 'Test email sent' : 'Sync completed' })
    } catch (err) {
      toast.show({ message: errorText(err) })
      onReload()
    } finally {
      setSyncing(false)
    }
  }

  return (
    <Card as="section" aria-labelledby={`int-${row.id}`} className="gap-4">
      <div className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id={`int-${row.id}`} className="m-0 text-xl font-bold">{row.name}</h2>
          <Pill tone={INTEGRATION_TONE[row.status]}>{row.status}</Pill>
        </div>
        <p className="m-0 text-[13px] text-slate">{row.desc}</p>
      </div>

      {row.status === 'Error' && <Notice tone="pink">The last connection attempt failed. Try Connect again.</Notice>}

      {row.id === 'csv' && row.connected && <CsvImportForm onDone={onReload} />}
      {row.id === 'mail' && (smtpOpen ? (
        <SmtpForm config={row.config} onConnected={onChanged} onCancel={() => onSmtp(false)} />
      ) : row.connected && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={sync} disabled={syncing}>{syncing ? 'Sending…' : 'Send test email'}</Button>
          <Button size="sm" variant="secondary" onClick={() => onSmtp(true)}>Change settings</Button>
        </div>
      ))}
      {CALENDARS.includes(row.id) && row.connected && (
        <div><Button size="sm" onClick={sync} disabled={syncing}>{syncing ? 'Syncing…' : 'Sync now'}</Button></div>
      )}

      <section aria-labelledby={`int-${row.id}-log`} className="flex flex-col gap-1 border-t border-canvas pt-3">
        <h3 id={`int-${row.id}-log`} className="m-0 mb-1 text-base font-bold">Recent activity</h3>
        <ul className="m-0 flex list-none flex-col p-0">
          {row.log.map((entry, i) => (
            <li key={`${entry.a}-${i}`} className="flex items-center justify-between gap-3 border-t border-canvas py-2 text-[13px] first:border-t-0">
              <span className="text-slate">{entry.a}</span>
              <span className="shrink-0 text-muted">{entry.b}</span>
            </li>
          ))}
        </ul>
      </section>
    </Card>
  )
}

function ApiKeys({ keys }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const rows = keys.data?.keys ?? []

  const revoke = async (key) => {
    try {
      await api(`/admin/api-keys/${key.id}`, { method: 'DELETE' })
      toast.show({ message: `${key.name} revoked` })
      keys.reload()
    } catch (err) {
      toast.show({ message: errorText(err) })
      return false
    }
  }

  return (
    <Card as="section" className="gap-3">
      <CardHeader title="API keys" subtitle="For reporting tools: Authorization: Bearer acm_…"
        action={<Button size="sm" onClick={() => setOpen(true)}>Generate key</Button>} />
      {keys.error && !keys.data && <ErrorState message={keys.error.message} onRetry={keys.reload} />}
      {!keys.data && !keys.error && <Loading label="Loading API keys…" />}
      {keys.data && rows.length === 0 && <Empty>No active keys.</Empty>}
      {rows.length > 0 && (
        <ul className="m-0 flex list-none flex-col p-0">
          {rows.map((key) => (
            <li key={key.id} className="flex flex-col gap-2 border-t border-canvas py-3 first:border-t-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-semibold">{key.name} · created {createdLabel(key.createdAt)}</span>
                  <code className="font-mono text-[13px] text-muted">{key.mask}</code>
                </div>
                <ConfirmInline label="Revoke" confirmLabel="Revoke" busyLabel="Revoking…"
                  warning={`Revoke ${key.name}? Tools using it stop working right away.`} onConfirm={() => revoke(key)} />
              </div>
            </li>
          ))}
        </ul>
      )}
      <ApiKeyDialog open={open} onClose={() => setOpen(false)} onCreated={keys.reload} />
    </Card>
  )
}
