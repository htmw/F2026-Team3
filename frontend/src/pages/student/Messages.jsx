import MessagesPage from '../../components/messages/MessagesPage.jsx'
import Button from '../../components/ui/Button.jsx'
import Icon from '../../components/ui/Icon.jsx'

// Student messages (spec 16); the screen itself is the shared MessagesPage.
export default function StudentMessages() {
  return (
    <MessagesPage
      actions={({ openNew }) => (
        <>
          <Button variant="secondary" to="/student/book-meeting"><Icon name="calendar" size={18} />Book a meeting</Button>
          <Button onClick={openNew}><Icon name="plus" size={18} />New message</Button>
        </>
      )}
      headerActionFor={(conversation) => conversation.bookable && (
        <Button variant="secondary" size="sm" to={`/student/book-meeting?with=${conversation.otherUserId}`}>
          <Icon name="calendar" size={16} />Schedule meeting
        </Button>
      )}
      readOnlyActionFor={() => <Button variant="secondary" size="sm" to="/student/ai-advisor">Ask Acadmate</Button>} />
  )
}
