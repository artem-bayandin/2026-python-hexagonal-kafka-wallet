import { type FormEvent, useEffect, useState } from 'react'
import { ApiError, checkAuthenticated, logout, requestOtp, verifyOtp } from './api/client'
import { AdminPage } from './pages/AdminPage'
import './App.css'

type OtpStepState = {
  email: string
  expiresAt: string
  demoOtp?: string
}

type AuthStatus = 'checking' | 'authorized' | 'unauthenticated' | 'check-error'
type AppView = 'auth' | 'admin'

function formatExpiry(iso: string): string {
  return new Date(iso).toLocaleString()
}

function App() {
  const [view, setView] = useState<AppView>('auth')
  const [email, setEmail] = useState('')
  const [otpStep, setOtpStep] = useState<OtpStepState | null>(null)
  const [otp, setOtp] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [authStatus, setAuthStatus] = useState<AuthStatus>(() =>
    sessionStorage.getItem('access_token') ? 'checking' : 'unauthenticated',
  )

  useEffect(() => {
    if (authStatus !== 'checking') {
      return
    }

    let cancelled = false

    async function validateSession() {
      try {
        await checkAuthenticated()
        if (!cancelled) {
          setAuthStatus('authorized')
        }
      } catch (error) {
        if (cancelled) {
          return
        }
        if (error instanceof ApiError && error.status === 401) {
          setAuthStatus('unauthenticated')
        } else {
          setAuthStatus('check-error')
        }
      }
    }

    void validateSession()

    return () => {
      cancelled = true
    }
  }, [authStatus])

  if (import.meta.env.DEV && view === 'admin') {
    return <AdminPage onBack={() => setView('auth')} />
  }

  async function handleEmailSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setIsSubmitting(true)

    try {
      const result = await requestOtp(email)
      setOtp('')
      setOtpStep({
        email,
        expiresAt: result.expires_at,
        demoOtp: result.otp,
      })
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else {
        setErrorMessage('Unable to request an OTP. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleOtpSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (otpStep === null) {
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)

    try {
      await verifyOtp(otpStep.email, otp)
      setOtpStep(null)
      setOtp('')
      setAuthStatus('authorized')
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else {
        setErrorMessage('Unable to verify the OTP. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleRetryAuthCheck() {
    if (sessionStorage.getItem('access_token')) {
      setAuthStatus('checking')
    } else {
      setAuthStatus('unauthenticated')
    }
  }

  async function handleLogout() {
    setErrorMessage(null)
    setIsSubmitting(true)

    try {
      await logout()
      setEmail('')
      setOtpStep(null)
      setOtp('')
      setAuthStatus('unauthenticated')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setEmail('')
        setOtpStep(null)
        setOtp('')
        setAuthStatus('unauthenticated')
      } else if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else {
        setErrorMessage('Unable to log out. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (authStatus === 'checking') {
    return (
      <main className="auth">
        <h1>Checking session…</h1>
        <p className="auth-detail">Verifying your sign-in status.</p>
      </main>
    )
  }

  if (authStatus === 'check-error') {
    return (
      <main className="auth">
        <h1>Session check failed</h1>
        <p className="auth-detail">
          We could not verify your session. Your sign-in token was kept so you can
          try again.
        </p>
        <button className="auth-button" type="button" onClick={handleRetryAuthCheck}>
          Retry
        </button>
      </main>
    )
  }

  if (authStatus === 'authorized') {
    return (
      <main className="auth">
        <h1>Authorized</h1>
        <p className="auth-detail">You are signed in.</p>
        {errorMessage !== null && (
          <p className="auth-error" role="alert">
            {errorMessage}
          </p>
        )}
        {import.meta.env.DEV && (
          <button
            className="auth-button"
            type="button"
            onClick={() => setView('admin')}
            disabled={isSubmitting}
          >
            Open admin page
          </button>
        )}
        <button
          className="auth-button"
          type="button"
          onClick={handleLogout}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Logging out…' : 'Logout'}
        </button>
      </main>
    )
  }

  if (otpStep !== null) {
    return (
      <main className="auth">
        <h1>Enter verification code</h1>
        <p className="auth-detail">
          Code sent to <strong>{otpStep.email}</strong>
        </p>
        <p className="auth-detail">Expires at {formatExpiry(otpStep.expiresAt)}</p>
        {otpStep.demoOtp !== undefined && (
          <p className="auth-demo">
            Demo OTP: <code>{otpStep.demoOtp}</code>
          </p>
        )}
        <form className="auth-form otp-shell" onSubmit={handleOtpSubmit}>
          <label className="auth-label" htmlFor="otp">
            6-digit code
          </label>
          <input
            id="otp"
            className="auth-input otp-input"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            required
            value={otp}
            onChange={(event) => setOtp(event.target.value.replace(/\D/g, ''))}
            disabled={isSubmitting}
          />
          {errorMessage !== null && (
            <p className="auth-error" role="alert">
              {errorMessage}
            </p>
          )}
          <button className="auth-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Verifying…' : 'Verify code'}
          </button>
        </form>
      </main>
    )
  }

  return (
    <main className="auth">
      <h1>Sign in</h1>
      <p className="auth-detail">Enter your email to receive a one-time code.</p>
      {import.meta.env.DEV && (
        <button
          className="auth-button"
          type="button"
          onClick={() => setView('admin')}
          disabled={isSubmitting}
        >
          Open admin page
        </button>
      )}
      <form className="auth-form" onSubmit={handleEmailSubmit}>
        <label className="auth-label" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          className="auth-input"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={isSubmitting}
        />
        {errorMessage !== null && (
          <p className="auth-error" role="alert">
            {errorMessage}
          </p>
        )}
        <button className="auth-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Sending…' : 'Request code'}
        </button>
      </form>
    </main>
  )
}

export default App
