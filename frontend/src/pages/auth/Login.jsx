import { useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import Logo from '../../components/ui/Logo.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Button from '../../components/ui/Button.jsx'
import { Field, INPUT } from '../../components/ui/Field.jsx'
import { HOME } from '../../config/nav.js'
import { useAuth } from '../../auth/AuthContext.jsx'
import { API_URL, api } from '../../lib/api.js'

const POINTS = [
  { title: 'See your whole degree at once', text: 'Requirements, credits and your graduation date in one place.' },
  { title: 'Ask the AI advisor anything', text: 'Course plans and answers based on your own degree audit.' },
  { title: 'Your advisor stays in charge', text: 'Every AI plan goes to your faculty advisor for approval.' },
]
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const LINK_BTN = 'hit-44 min-h-8 cursor-pointer border-0 bg-transparent p-0 font-bold text-accent'
// Messages for ?error= codes the API's Google callback redirects back with.
const REDIRECT_ERRORS = {
  google_state: 'Google sign-in was interrupted. Try again.',
  google_failed: "Google sign-in didn't complete. Try again.",
  google_domain: 'Use your school Google account.',
  google_session: 'Sign in first, then connect Google from Settings.',
  deactivated: 'This account is deactivated. Contact your administrator.',
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
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const { user, loading, setUser, config } = useAuth()
  const resetToken = location.pathname === '/reset-password' ? params.get('token') : null

  const [step, setStep] = useState(resetToken ? 'reset' : 'login')
  const [form, setForm] = useState({ email: '', pw: '', name: '', code: '' })
  const [showPw, setShowPw] = useState(false)
  const [remember, setRemember] = useState(true)
  const [hint, setHint] = useState(REDIRECT_ERRORS[params.get('error')] ?? '')
  const [pending, setPending] = useState(false)
  const [challenge, setChallenge] = useState(null)
  const [linkInfo, setLinkInfo] = useState(null)

  const googleEnabled = Boolean(config.googleEnabled)
  const validEmail = EMAIL_RE.test(form.email)
  const filled = validEmail && form.pw.length > 0
  const signupOk = form.name.trim() && validEmail && form.pw.length >= 8

  // Resume a two-step sign-in that started with Google (the API redirects back with ?mfa=).
  useEffect(() => {
    const mfa = params.get('mfa')
    if (!mfa) return
    setParams({}, { replace: true })
    api(`/auth/2fa/challenge/${encodeURIComponent(mfa)}`)
      .then((data) => { setChallenge(data); setStep('code') })
      .catch((err) => setHint(err.message))
  }, [params, setParams])

  // Check a reset / invite link before asking for a new password.
  useEffect(() => {
    if (!resetToken) return
    api(`/auth/password-reset/${encodeURIComponent(resetToken)}`)
      .then(setLinkInfo)
      .catch((err) => { setHint(err.message); setStep('resetInvalid') })
  }, [resetToken])

  if (!loading && user && !resetToken) return <Navigate to={location.state?.from?.startsWith(HOME[user.role]) ? location.state.from : HOME[user.role]} replace />

  const set = (key) => (e) => {
    const value = key === 'code' ? e.target.value.replace(/\D/g, '').slice(0, 6) : e.target.value
    setForm((current) => ({ ...current, [key]: value }))
    setHint('')
  }
  const go = (nextStep) => () => {
    setStep(nextStep)
    setHint('')
    setForm((current) => ({ ...current, code: '', pw: '' }))
    if (location.pathname !== '/login') navigate('/login', { replace: true })
  }

  // Runs an API call with a pending state; errors land in the hint line.
  const submit = async (fn) => {
    if (pending) return
    setPending(true)
    setHint('')
    try {
      await fn()
    } catch (err) {
      setHint(err.message)
    } finally {
      setPending(false)
    }
  }

  const finish = (data) => {
    setUser(data.user)
    navigate(data.home, { replace: true })
  }

  const signInWithGoogle = () => {
    if (!googleEnabled) return setHint("Google sign-in isn't set up on this server yet. Use your email and password.")
    window.location.assign(`${API_URL}/auth/google?remember=${remember}`)
  }

  const submitLogin = () => {
    if (!filled) return setHint(validEmail ? 'Enter your password.' : 'Enter a valid email address.')
    submit(async () => {
      const data = await api('/auth/login', { method: 'POST', body: { email: form.email, password: form.pw, remember } })
      if (data.mfaRequired) {
        setChallenge(data)
        setForm((current) => ({ ...current, code: '', pw: '' }))
        setStep('code')
      } else finish(data)
    })
  }

  const submitCode = () => {
    if (form.code.length !== 6) return setHint('Enter all 6 digits.')
    submit(async () => finish(await api('/auth/2fa/verify', { method: 'POST', body: { challenge: challenge.challenge, code: form.code } })))
  }

  const submitForgot = () => {
    if (!validEmail) return setHint('Enter a valid email address.')
    submit(async () => {
      await api('/auth/password-reset', { method: 'POST', body: { email: form.email } })
      setStep('sent')
    })
  }

  const submitSignup = () => {
    if (!signupOk) return setHint(!form.name.trim() ? 'Enter your name.' : !validEmail ? 'Enter a valid email address.' : 'Use at least 8 characters for your password.')
    submit(async () => finish(await api('/auth/signup', { method: 'POST', body: { name: form.name.trim(), email: form.email, password: form.pw } })))
  }

  const submitReset = () => {
    if (form.pw.length < 8) return setHint('Use at least 8 characters for your password.')
    submit(async () => {
      await api('/auth/password-reset/confirm', { method: 'POST', body: { token: resetToken, password: form.pw } })
      setForm((current) => ({ ...current, email: linkInfo?.email ?? current.email, pw: '' }))
      setStep('resetDone')
    })
  }

  const busy = (label, idle) => (pending ? label : idle)

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
                  <Icon name="check" size={16} color="var(--color-teal-bright)" strokeWidth={2.8} />
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
          <form className="mx-auto flex w-full max-w-[400px] flex-col gap-[18px]" noValidate onSubmit={(e) => e.preventDefault()}>
            {step === 'login' && (
              <>
                <Heading title="Welcome back" text="Sign in to continue to Acadmate." />
                <Button variant="google" size="lg" onClick={signInWithGoogle}>
                  <Icon name="user" color="var(--color-navy)" /> Sign in with Google
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
                      <Icon name="eye" color="var(--color-navy)" />
                    </button>
                  </div>
                </Field>
                <div className="flex min-h-8 items-center gap-2.5">
                  <input type="checkbox" id="login-remember" checked={remember} onChange={() => setRemember((value) => !value)}
                    className="size-[18px] accent-accent" />
                  <label htmlFor="login-remember" className="text-sm">Keep me signed in on this device</label>
                </div>
                <Button type="submit" variant={filled && !pending ? 'primary' : 'disabled'} size="lg" onClick={submitLogin} aria-busy={pending}>
                  {busy('Signing in…', 'Sign in')}
                </Button>
                <Hint>{hint}</Hint>
                <span className="text-center text-sm text-muted">
                  New to Acadmate?{' '}
                  <button type="button" onClick={go('signup')} className={`${LINK_BTN} px-0.5 text-sm`}>Create an account</button>
                </span>
              </>
            )}

            {step === 'code' && (
              <>
                <Heading title="Two-step sign-in" text={challenge?.setup
                  ? 'Staff accounts need a second step. Add Acadmate to your authenticator app with the key below, then enter the 6-digit code it shows.'
                  : 'Staff accounts need a second step. Enter the 6-digit code from your authenticator app.'} />
                {challenge?.setup && (
                  <div className="flex flex-col gap-1.5 rounded-xl bg-surface-sunk px-3.5 py-3">
                    <span className="text-[13px] font-bold">Setup key</span>
                    <code className="break-all font-display text-[15px] tracking-[0.08em]">{challenge.setup.secret.match(/.{1,4}/g).join(' ')}</code>
                    <a href={challenge.setup.otpauthUrl} className="text-[13px] font-semibold">Open in authenticator app</a>
                  </div>
                )}
                <Field id="login-code" label="Verification code">
                  <input id="login-code" type="text" inputMode="numeric" autoComplete="one-time-code"
                    value={form.code} onChange={set('code')} placeholder="123456"
                    className={`${INPUT} text-center font-display text-[22px] tracking-[0.3em]`} />
                </Field>
                <Button type="submit" variant={form.code.length === 6 && !pending ? 'primary' : 'disabled'} size="lg" onClick={submitCode}>
                  {busy('Checking…', 'Verify and continue')}
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
                <Button type="submit" size="lg" variant={pending ? 'disabled' : 'primary'} onClick={submitForgot}>
                  {busy('Sending…', 'Send reset link')}
                </Button>
                <Hint>{hint}</Hint>
                <Button variant="secondary" size="lg" onClick={go('login')}>Back to sign in</Button>
              </>
            )}

            {step === 'sent' && (
              <div role="status" className="flex flex-col gap-[18px]">
                <div className="flex size-[52px] items-center justify-center rounded-full bg-teal-soft">
                  <Icon name="mail" size={24} color="var(--color-teal-ink)" strokeWidth={2.4} />
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
                <Button variant="google" size="lg" onClick={signInWithGoogle}>
                  <Icon name="user" color="var(--color-navy)" /> Sign up with Google
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
                <Button type="submit" variant={signupOk && !pending ? 'primary' : 'disabled'} size="lg" onClick={submitSignup}>
                  {busy('Creating account…', 'Create account')}
                </Button>
                <Hint>{hint}</Hint>
                <span className="text-center text-sm text-muted">
                  Already have an account?{' '}
                  <button type="button" onClick={go('login')} className={`${LINK_BTN} px-0.5 text-sm`}>Sign in</button>
                </span>
              </>
            )}

            {step === 'reset' && (
              <>
                <Heading title={linkInfo?.purpose === 'invite' ? 'Set up your account' : 'Choose a new password'}
                  text={linkInfo ? `For ${linkInfo.email}. Use 8 characters or more.` : 'Checking your link…'} />
                <Field id="new-pw" label="New password">
                  <input id="new-pw" type="password" autoComplete="new-password" value={form.pw} onChange={set('pw')}
                    placeholder="Choose a password" className={INPUT} disabled={!linkInfo} />
                </Field>
                <Button type="submit" variant={linkInfo && form.pw.length >= 8 && !pending ? 'primary' : 'disabled'} size="lg" onClick={submitReset}>
                  {busy('Saving…', linkInfo?.purpose === 'invite' ? 'Activate account' : 'Save new password')}
                </Button>
                <Hint>{hint}</Hint>
              </>
            )}

            {step === 'resetDone' && (
              <div role="status" className="flex flex-col gap-[18px]">
                <div className="flex size-[52px] items-center justify-center rounded-full bg-teal-soft">
                  <Icon name="check" size={24} color="var(--color-teal-ink)" strokeWidth={2.6} />
                </div>
                <h2 className="m-0 font-display text-[28px] font-bold">Password saved</h2>
                <span className="text-sm leading-normal text-muted">Sign in with your new password to continue.</span>
                <Button size="lg" onClick={go('login')}>Go to sign in</Button>
              </div>
            )}

            {step === 'resetInvalid' && (
              <>
                <Heading title="Link expired" text={hint || 'This link is invalid or has expired.'} />
                <Button size="lg" onClick={go('forgot')}>Request a new link</Button>
                <Button variant="secondary" size="lg" onClick={go('login')}>Back to sign in</Button>
              </>
            )}
          </form>
        </section>
      </div>
    </div>
  )
}
