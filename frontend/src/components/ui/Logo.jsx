import Icon from './Icon.jsx'

export default function Logo({ size = 'md' }) {
  const box = size === 'lg' ? 'size-11 rounded-xl' : 'size-[38px] rounded-[11px]'
  const text = size === 'lg' ? 'text-[26px]' : 'text-[22px]'
  return (
    <div className="flex items-center gap-2.5">
      <div className={`${box} flex items-center justify-center bg-teal`}>
        <Icon name="cap" size={size === 'lg' ? 24 : 22} color="var(--color-navy)" strokeWidth={2.2} />
      </div>
      <span className={`font-display font-bold tracking-[-0.02em] text-white ${text}`}>Acadmate</span>
    </div>
  )
}
