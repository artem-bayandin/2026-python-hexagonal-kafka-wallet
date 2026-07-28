import { type FormEvent, useState } from 'react'
import { ApiError, requestOtp } from './api/client'
import './App.css'

type OtpStepState = {
  email: string
  expiresAt: string
  demoOtp?: string
}

function formatExpiry(iso: string): string {
  return new Date(iso).toLocaleString()
}

function App() {
  const [email, setEmail] = useState('')
  const [otpStep, setOtpStep] = useState<OtpStepState | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleEmailSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setIsSubmitting(true)

    try {
      const result = await requestOtp(email)
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
        <section className="otp-shell" aria-label="OTP entry" />
      </main>
    )
  }

  return (
    <main className="auth">
      <h1>Sign in</h1>
      <p className="auth-detail">Enter your email to receive a one-time code.</p>
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
