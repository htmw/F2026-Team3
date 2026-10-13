import { Link } from 'react-router-dom'

const BASE = 'inline-flex items-center justify-center gap-2.5 rounded-xl font-bold no-underline cursor-pointer box-border transition-colors'
const VARIANTS = {
  primary: 'bg-accent text-white border-0 hover:brightness-110 hover:text-white',
  secondary: 'bg-surface text-navy border border-line font-semibold hover:bg-surface-sunk hover:text-navy',
  google: 'bg-surface text-navy border border-line-strong hover:bg-surface-sunk hover:text-navy',
  disabled: 'bg-line-strong text-slate border-0',
  sun: 'bg-sun text-navy border-0 hover:brightness-105 hover:text-navy',
  mint: 'bg-teal text-navy border-0 hover:brightness-105 hover:text-navy',
  ghostDark: 'bg-transparent text-frost border border-navy-line font-semibold hover:bg-navy-raised hover:text-frost',
  danger: 'bg-pink-soft text-pink-ink border-0 hover:brightness-95 hover:text-pink-ink',
}
const SIZES = { lg: 'min-h-[52px] text-[15px] w-full', md: 'min-h-11 px-4 text-sm', sm: 'min-h-10 px-3.5 text-[13px]' }

// `to` renders a router Link; `href` renders a plain <a> (e.g. CSV downloads via apiUrl()).
export default function Button({ to, href, variant = 'primary', size = 'md', className = '', children, ...rest }) {
  const cls = `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`
  if (to) return <Link to={to} className={cls} {...rest}>{children}</Link>
  if (href) return <a href={href} className={cls} {...rest}>{children}</a>
  return <button type="button" className={cls} {...rest}>{children}</button>
}
