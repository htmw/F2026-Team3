// On/off toggle. `label` is the accessible name; use SwitchRow for the settings-list layout.
export default function Switch({ checked, onChange, label, disabled = false, id }) {
  return (
    <button id={id} type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full border-0 p-0 transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? 'bg-accent' : 'bg-line-strong'}`}>
      <span className={`absolute left-1 size-5 rounded-full bg-white shadow-sm transition-transform ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
    </button>
  )
}

export function SwitchRow({ id, label, description, checked, onChange, disabled }) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-canvas py-3.5 first:border-t-0">
      <div className="flex min-w-0 flex-col gap-[3px]">
        <label htmlFor={id} className="text-sm font-semibold">{label}</label>
        {description && <span className="text-[13px] text-muted">{description}</span>}
      </div>
      <Switch id={id} checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  )
}
