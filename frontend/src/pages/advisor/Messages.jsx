import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import MessagesPage from '../../components/messages/MessagesPage.jsx'
import QuickReplies from '../../components/messages/QuickReplies.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { api, errorText } from '../../lib/api.js'

const QUICK_REPLIES = ["Let's discuss this at our next meeting.", 'Please book a time on Acadmate.', 'Approved. Thanks!']

// Advisor messages (spec 25): the shared MessagesPage with the advising team, record / booking links and quick replies.
// `?to={userId}` opens (or creates) the direct conversation with that person.
export default function AdvisorMessages() {
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [select, setSelect] = useState(null)
  const [opening, setOpening] = useState(false)
  const to = Number(params.get('to')) || null
  const handled = useRef(null)

  useEffect(() => {
    if (!to || handled.current === to) return
    handled.current = to
    api('/conversations', { method: 'POST', body: { recipientIds: [to] } })
      .then(({ id }) => setSelect({ id }))
      .catch((err) => toast.show({ message: errorText(err) }))
      .finally(() => setParams((current) => { const next = new URLSearchParams(current); next.delete('to'); return next },
        { replace: true }))
  }, [to, setParams, toast])

  const openTeam = async () => {
    setOpening(true)
    try {
      const { id } = await api('/conversations/team', { method: 'POST' })
      setSelect({ id })
    } catch (err) {
      toast.show({ message: errorText(err) })
    } finally {
      setOpening(false)
    }
  }

  return (
    <MessagesPage select={select} searchLabel="Search conversations" searchPlaceholder="Search conversations…"
      subtitle={(unread) => `Advisees, the advising team and Acadmate notifications${unread ? ` · ${unread} unread` : ''}`}
      actions={({ openNew }) => (
        <>
          <Button variant="secondary" onClick={openTeam} disabled={opening}><Icon name="users" size={18} />Message advising team</Button>
          <Button onClick={openNew}><Icon name="plus" size={18} />New message</Button>
        </>
      )}
      headerActionFor={(conversation) => {
        if (conversation.studentId) {
          return (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" to={`/advisor/advisees/${conversation.studentId}`}>Open record</Button>
              <Button variant="secondary" size="sm" to={`/advisor/meetings?book=${conversation.studentId}`}>
                <Icon name="calendar" size={16} />Book meeting
              </Button>
            </div>
          )
        }
        if (conversation.kind === 'system') return <Button variant="secondary" size="sm" to="/advisor/approvals">Open approvals</Button>
        if (conversation.team) return <Button variant="secondary" size="sm" to="/advisor/reports">Open reports</Button>
        return null
      }}
      readOnlyActionFor={() => <Button variant="secondary" size="sm" to="/advisor/approvals">Open approvals</Button>}
      aboveComposerFor={(conversation, send) => <QuickReplies replies={QUICK_REPLIES} onPick={send} />} />
  )
}
