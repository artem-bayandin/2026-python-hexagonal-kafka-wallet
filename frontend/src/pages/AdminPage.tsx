import { type FormEvent, useState } from 'react'
import { ApiError } from '../api/client'
import {
  AdminDeposit,
  getAdminKey,
  listReferenceCurrencies,
  listReferenceUsers,
  setAdminKey,
} from '../api/adminClient'
import type { CurrencyItem, UserReferenceItem } from '../types/admin'

type AdminPageProps = {
  onBack: () => void
}

function amountStepForPrecision(precision: number): string {
  if (precision <= 0) {
    return '1'
  }
  return `0.${'0'.repeat(precision - 1)}1`
}

export function AdminPage({ onBack }: AdminPageProps) {
  const [adminKeyInput, setAdminKeyInput] = useState(getAdminKey() ?? '')
  const [currencies, setCurrencies] = useState<CurrencyItem[]>([])
  const [users, setUsers] = useState<UserReferenceItem[]>([])
  const [selectedCurrencyLabel, setSelectedCurrencyLabel] = useState('')
  const [selectedUserEmail, setSelectedUserEmail] = useState('')
  const [amount, setAmount] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmittingDeposit, setIsSubmittingDeposit] = useState(false)
  const [dataLoaded, setDataLoaded] = useState(false)

  const selectedCurrency = currencies.find(
    (currency) => currency.label === selectedCurrencyLabel,
  )

  async function loadReferenceData() {
    setIsLoading(true)
    setErrorMessage(null)
    setSuccessMessage(null)

    try {
      const [currencyResult, userResult] = await Promise.all([
        listReferenceCurrencies(),
        listReferenceUsers(),
      ])
      setCurrencies(currencyResult.items)
      setUsers(userResult.items)
      setSelectedCurrencyLabel(
        currencyResult.items.length > 0 ? currencyResult.items[0].label : '',
      )
      setSelectedUserEmail(
        userResult.items.length > 0 ? userResult.items[0].email : '',
      )
      setDataLoaded(true)
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Unable to load reference data.')
      }
      setDataLoaded(false)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleSaveKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAdminKey(adminKeyInput.trim())
    await loadReferenceData()
  }

  async function handleDepositSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (selectedUserEmail === '' || selectedCurrencyLabel === '') {
      return
    }

    setIsSubmittingDeposit(true)
    setErrorMessage(null)
    setSuccessMessage(null)

    try {
      const result = await AdminDeposit({
        email: selectedUserEmail,
        asset: selectedCurrencyLabel,
        amount,
      })
      setSuccessMessage(
        `Deposit completed. Transaction ${result.id} (${result.type} / ${result.status}).`,
      )
      setAmount('')
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Unable to submit deposit.')
      }
    } finally {
      setIsSubmittingDeposit(false)
    }
  }

  return (
    <main className="auth">
      <h1>Admin</h1>
      <p className="auth-detail">Development-only admin operator page.</p>

      <form className="auth-form" onSubmit={handleSaveKey}>
        <label className="auth-label" htmlFor="admin-key">
          Admin API key
        </label>
        <input
          id="admin-key"
          className="auth-input"
          type="password"
          autoComplete="off"
          required
          value={adminKeyInput}
          onChange={(event) => setAdminKeyInput(event.target.value)}
          disabled={isLoading || isSubmittingDeposit}
        />
        <button
          className="auth-button"
          type="submit"
          disabled={isLoading || isSubmittingDeposit}
        >
          {isLoading ? 'Loading…' : 'Save key and load data'}
        </button>
      </form>

      {errorMessage !== null && (
        <p className="auth-error" role="alert">
          {errorMessage}
        </p>
      )}

      {successMessage !== null && (
        <p className="auth-detail" role="status">
          {successMessage}
        </p>
      )}

      {dataLoaded && (
        <>
          <section className="auth-form">
            <label className="auth-label" htmlFor="currency-select">
              Currency
            </label>
            {currencies.length === 0 ? (
              <p className="auth-detail">Currencies: no data</p>
            ) : (
              <div className="auth-select-wrap">
                <select
                  id="currency-select"
                  className="auth-input"
                  value={selectedCurrencyLabel}
                  onChange={(event) => setSelectedCurrencyLabel(event.target.value)}
                  disabled={isLoading || isSubmittingDeposit}
                >
                  {currencies.map((currency) => (
                    <option key={currency.label} value={currency.label}>
                      {currency.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </section>

          <section className="auth-form">
            <label className="auth-label" htmlFor="user-select">
              Recipient user
            </label>
            {users.length === 0 ? (
              <p className="auth-detail">Users: no data</p>
            ) : (
              <div className="auth-select-wrap">
                <select
                  id="user-select"
                  className="auth-input"
                  value={selectedUserEmail}
                  onChange={(event) => setSelectedUserEmail(event.target.value)}
                  disabled={isLoading || isSubmittingDeposit}
                >
                  {users.map((user) => (
                    <option key={user.user_id} value={user.email}>
                      {user.email}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </section>

          <form className="auth-form" onSubmit={handleDepositSubmit}>
            <label className="auth-label" htmlFor="deposit-amount">
              Amount
            </label>
            <input
              id="deposit-amount"
              className="auth-input"
              type="text"
              inputMode="decimal"
              required
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              disabled={
                isLoading ||
                isSubmittingDeposit ||
                users.length === 0 ||
                currencies.length === 0
              }
              step={
                selectedCurrency !== undefined
                  ? amountStepForPrecision(selectedCurrency.precision)
                  : undefined
              }
            />
            <button
              className="auth-button"
              type="submit"
              disabled={
                isLoading ||
                isSubmittingDeposit ||
                users.length === 0 ||
                currencies.length === 0 ||
                amount.trim() === ''
              }
            >
              {isSubmittingDeposit ? 'Submitting…' : 'Submit deposit'}
            </button>
          </form>
        </>
      )}

      <button className="auth-button" type="button" onClick={onBack}>
        Back to app
      </button>
    </main>
  )
}
