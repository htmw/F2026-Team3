import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Logo from '../../components/ui/Logo.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Button from '../../components/ui/Button.jsx'
import { HOME } from '../../config/nav.js'

const POINTS = [
  { title: 'See your whole degree at once', text: 'Requirements, credits and your graduation date in one place.' },
  { title: 'Ask the AI advisor anything', text: 'Course plans and answers based on your own degree audit.' },
  { title: 'Your advisor stays in charge', text: 'Every AI plan goes to your faculty advisor for approval.' },
]
const ROLES = ['Student', 'Advisor', 'Admin']
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const INPUT = 'box-border h-12 w-full rounded-xl border border-line bg-surface px-3.5 text-[15px] text-navy'
const LINK_BTN = 'min-h-8 cursor-pointer border-0 bg-transparent p-0 font-bold text-accent'

function Field({ id, label, children, aside }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-[13px] font-bold">{label}</label>
        {aside}
      </div>
      {children}
    </div>
  )
}

function Divider({ children }) {
  return (
    <div className="flex items-center gap-3 text-[13px] text-muted">
      <span className="h-px flex-1 bg-line-soft" />{children}<span className="h-px flex-1 bg-line-soft" />
    </div>
  )
}

function Heading({ title, text }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h2 className="m-0 font-display text-[28px] font-bold tracking-[-0.01em]">{title}</h2>
      <span className="text-sm leading-normal text-muted">{text}</span>
    </div>
  )
}

function Hint({ children }) {
  return <span role="status" className="min-h-[18px] text-[13px] font-semibold text-warn">{children}</span>
}

export default function Login() {
  const navigate = useNavigate()
  const [step, setStep] = useState('login')
  const [role, setRole] = useState('Student')
  const [form, setForm] = useState({ email: '', pw: '', name: '', code: '' })
  const [showPw, setShowPw] = useState(false)
  const [remember, setRemember] = useState(true)
  const [hint, setHint] = useState('')

  const dest = HOME[role.toLowerCase()]
  const validEmail = EMAIL_RE.test(form.email)
  const filled = validEmail && form.pw.length > 0
  const signupOk = form.name.trim() && validEmail && form.pw.length >= 8

  const set = (key) => (e) => {
    const value = key === 'code' ? e.target.value.replace(/\D/g, '').slice(0, 6) : e.target.value
    setForm((current) => ({ ...current, [key]: value }))
    setHint('')
  }
  const go = (nextStep) => () => { setStep(nextStep); setHint(''); setForm((current) => ({ ...current, code: '' })) }

  const signInWithGoogle = () => navigate(dest)

  const submitLogin = () => {
    if (!filled) return setHint(validEmail ? 'Enter your password.' : 'Enter a valid email address.')
    role === 'Student' ? navigate(dest) : go('code')()
  }

  return (
    <div className="box-border flex min-h-screen items-stretch justify-center bg-canvas p-5 font-sans text-navy">
      <div className="flex w-full max-w-[1200px] flex-wrap items-stretch gap-5">
        <section aria-label="About Acadmate"
          className="box-border flex min-h-[560px] flex-[1_1_380px] flex-col gap-7 rounded-3xl bg-navy px-10 py-12 text-frost">
          <Logo size="lg" />
          <h1 className="m-0 font-display text-[40px] font-bold leading-[1.15] tracking-[-0.02em] text-white">
            Plan your degree with an advisor in your pocket.
          </h1>
          <div className="flex flex-col gap-[18px]">
            {POINTS.map((point) => (
              <div key={point.title} className="flex items-start gap-3.5">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-navy-raised">
                  <Icon name="check" size={16} color="#5EEAD4" strokeWidth={2.8} />
                </span>
                <div className="flex flex-col gap-[3px]">
                  <span className="text-base font-bold text-white">{point.title}</span>
                  <span className="text-sm leading-normal text-mist">{point.text}</span>
                </div>
              </div>
            ))}
          </div>
          <span className="mt-auto text-[13px] text-haze">For students, faculty advisors and administrators.</span>
        </section>

        <section aria-label="Sign in"
          className="box-border flex flex-[1_1_400px] flex-col justify-center rounded-3xl bg-surface px-10 py-12">
          <div className="mx-auto flex w-full max-w-[400px] flex-col gap-[18px]">
            {step === 'login' && (
              <>
                <Heading title="Welcome back" text="Sign in to continue to Acadmate." />
                <div className="flex flex-col gap-2">
                  <span id="role-label" className="text-[13px] font-bold">Prototype: sign in as</span>
                  <div role="group" aria-labelledby="role-label" className="flex gap-1.5 rounded-xl bg-surface-sunk p-1">
                    {ROLES.map((item) => (
                      <button key={item} type="button" aria-pressed={role === item} onClick={() => { setRole(item); setHint('') }}
                        className={`min-h-10 flex-1 cursor-pointer rounded-[9px] border-0 text-sm font-bold text-navy ${
                          role === item ? 'bg-surface shadow-[0_1px_3px_rgba(19,33,46,0.15)]' : 'bg-transparent'}`}>
                        {item}
                      </button>
                    ))}
                  </div>
                </div>
                <Button variant="google" size="lg" onClick={signInWithGoogle}>
                  <Icon name="user" color="#13212E" /> Sign in with Google
                </Button>
                <Divider>or use your email</Divider>
                <Field id="login-email" label="Email">
                  <input id="login-email" type="email" autoComplete="email" value={form.email} onChange={set('email')}
                    placeholder="you@school.edu" className={INPUT} />
                </Field>
                <Field id="login-pw" label="Password"
                  aside={<button type="button" onClick={go('forgot')} className={`${LINK_BTN} text-[13px]`}>Forgot password?</button>}>
                  <div className="flex gap-2">
                    <input id="login-pw" type={showPw ? 'text' : 'password'} autoComplete="current-password" value={form.pw}
                      onChange={set('pw')} placeholder="Your password" className={`${INPUT} min-w-0 flex-1`} />
                    <button type="button" onClick={() => setShowPw((value) => !value)} aria-label={showPw ? 'Hide password' : 'Show password'}
                      className="flex size-12 shrink-0 cursor-pointer items-center justify-center rounded-xl border border-line bg-surface">
                      <Icon name="eye" color="#13212E" />
                    </button>
                  </div>
                </Field>
                <div className="flex min-h-8 items-center gap-2.5">
                  <input type="checkbox" id="login-remember" checked={remember} onChange={() => setRemember((value) => !value)}
                    className="size-[18px] accent-accent" />
                  <label htmlFor="login-remember" className="text-sm">Keep me signed in on this device</label>
                </div>
                <Button variant={filled ? 'primary' : 'disabled'} size="lg" onClick={submitLogin}>Sign in</Button>
                <Hint>{hint}</Hint>
                <span className="text-center text-sm text-muted">
                  New to Acadmate?{' '}
                  <button type="button" onClick={go('signup')} className={`${LINK_BTN} px-0.5 text-sm`}>Create an account</button>
                </span>
              </>
            )}

            {step === 'code' && (
              <>
                <Heading title="Two-step sign-in" text="Staff accounts need a second step. Enter the 6-digit code from your authenticator app." />
                <Field id="login-code" label="Verification code">
                  <input id="login-code" type="text" inputMode="numeric" autoComplete="one-time-code"
                    value={form.code} onChange={set('code')} placeholder="123456"
                    className={`${INPUT} text-center font-display text-[22px] tracking-[0.3em]`} />
                </Field>
                <Button variant={form.code.length === 6 ? 'primary' : 'disabled'} size="lg"
                  onClick={() => (form.code.length === 6 ? navigate(dest) : setHint('Enter all 6 digits.'))}>
                  Verify and continue
                </Button>
                <Hint>{hint}</Hint>
                <Button variant="secondary" size="lg" onClick={go('login')}>Back to sign in</Button>
              </>
            )}

            {step === 'forgot' && (
              <>
                <Heading title="Reset your password"
                  text="We'll email you a link to choose a new one. If you use Google to sign in, you don't need a password." />
                <Field id="reset-email" label="Email">
                  <input id="reset-email" type="email" autoComplete="email" value={form.email} onChange={set('email')}
                    placeholder="you@school.edu" className={INPUT} />
                </Field>
                <Button size="lg" onClick={() => (validEmail ? go('sent')() : setHint('Enter a valid email address.'))}>
                  Send reset link
                </Button>
                <Hint>{hint}</Hint>
                <Button variant="secondary" size="lg" onClick={go('login')}>Back to sign in</Button>
              </>
            )}

            {step === 'sent' && (
              <div role="status" className="flex flex-col gap-[18px]">
                <div className="flex size-[52px] items-center justify-center rounded-full bg-teal-soft">
                  <Icon name="mail" size={24} color="#115E59" strokeWidth={2.4} />
                </div>
                <h2 className="m-0 font-display text-[28px] font-bold">Check your email</h2>
                <span className="text-sm leading-normal text-muted">
                  If an account exists for {form.email}, a reset link is on its way. It expires in 30 minutes.
                </span>
                <Button size="lg" onClick={go('login')}>Back to sign in</Button>
              </div>
            )}

            {step === 'signup' && (
              <>
                <Heading title="Create your account" text="Students can sign up here. Advisors and admins are invited by an administrator." />
                <Button variant="google" size="lg" onClick={() => navigate(HOME.student)}>
                  <Icon name="user" color="#13212E" /> Sign up with Google
                </Button>
                <Divider>or</Divider>
                <Field id="su-name" label="Full name">
                  <input id="su-name" type="text" autoComplete="name" value={form.name} onChange={set('name')} placeholder="Your name" className={INPUT} />
                </Field>
                <Field id="su-email" label="School email">
                  <input id="su-email" type="email" autoComplete="email" value={form.email} onChange={set('email')} placeholder="you@school.edu" className={INPUT} />
                </Field>
                <Field id="su-pw" label="Password (8 characters or more)">
                  <input id="su-pw" type="password" autoComplete="new-password" value={form.pw} onChange={set('pw')} placeholder="Choose a password" className={INPUT} />
                </Field>
                <Button variant={signupOk ? 'primary' : 'disabled'} size="lg"
                  onClick={() => signupOk ? navigate(HOME.student)
                    : setHint(!form.name.trim() ? 'Enter your name.' : !validEmail ? 'Enter a valid email address.' : 'Use at least 8 characters for your password.')}>
                  Create account
                </Button>
                <Hint>{hint}</Hint>
                <span className="text-center text-sm text-muted">
                  Already have an account?{' '}
                  <button type="button" onClick={go('login')} className={`${LINK_BTN} px-0.5 text-sm`}>Sign in</button>
                </span>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
