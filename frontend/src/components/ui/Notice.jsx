import Icon from './Icon.jsx'

const TONES = {
  amber: { box: 'bg-amber-soft', text: 'text-amber-deep', icon: 'var(--color-amber-ink)' },
  teal: { box: 'bg-teal-soft', text: 'text-teal-ink', icon: 'var(--color-teal-ink)' },
  pink: { box: 'bg-pink-soft', text: 'text-pink-ink', icon: 'var(--color-pink-ink)' },
  indigo: { box: 'bg-indigo-soft', text: 'text-indigo-ink', icon: 'var(--color-indigo-ink)' },
}
const DEFAULT_ICON = { amber: 'alert', pink: 'alert', teal: 'check', indigo: 'info' }

// Inline banner for warnings, approval pre-check results, import results and form-level errors.
export default function Notice({ tone = 'amber', icon, className = '', children, ...rest }) {
  const style = TONES[tone]
  return (
    <div className={`flex items-start gap-2.5 rounded-xl px-3.5 py-3 ${style.box} ${className}`} {...rest}>
      <Icon name={icon ?? DEFAULT_ICON[tone]} size={18} color={style.icon} strokeWidth={2.2} className="mt-px shrink-0" />
      <div className={`text-[13px] leading-normal ${style.text}`}>{children}</div>
    </div>
  )
}
