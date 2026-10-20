import Button from './Button.jsx'
import Icon from './Icon.jsx'
import { useFlash } from '../../lib/useSaveState.js'

// CSV download link whose label reads "Exported" for 2 s after a click. Pass `href={apiUrl('/…csv?…')}`.
export default function ExportButton({ href, label = 'Export CSV', doneLabel = 'Exported', variant = 'secondary', size = 'md' }) {
  const [done, flash] = useFlash()
  return (
    <Button href={href} download variant={variant} size={size} onClick={flash} aria-live="polite">
      <Icon name={done ? 'check' : 'download'} size={18} />{done ? doneLabel : label}
    </Button>
  )
}
