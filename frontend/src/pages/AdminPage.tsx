import { type FormEvent, useState } from 'react'
import { ApiError } from '../api/client'
import {
  getAdminKey,
  listReferenceCurrencies,
  listReferenceUsers,
  setAdminKey,
} from '../api/adminClient'
import type { CurrencyItem, UserReferenceItem } from '../types/admin'

type AdminPageProps = {
  onBack: () => void
}

export function AdminPage({ onBack }: AdminPageProps) {
  const [adminKeyInput, setAdminKeyInput] = useState(getAdminKey() ?? '')
  const [currencies, setCurrencies] = useState<CurrencyItem[]>([])
  const [users, setUsers] = useState<UserReferenceItem[]>([])
  const [selectedCurrencyLabel, setSelectedCurrencyLabel] = useState('')
  const [selectedUserEmail, setSelectedUserEmail] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [dataLoaded, setDataLoaded] = useState(false)

  async function loadReferenceData() {
    setIsLoading(true)
    setErrorMessage(null)

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
          disabled={isLoading}
        />
        <button className="auth-button" type="submit" disabled={isLoading}>
          {isLoading ? 'Loading…' : 'Save key and load data'}
        </button>
      </form>

      {errorMessage !== null && (
        <p className="auth-error" role="alert">
          {errorMessage}
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
                  disabled={isLoading}
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
                  disabled={isLoading}
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
        </>
      )}

      <button className="auth-button" type="button" onClick={onBack}>
        Back to app
      </button>
    </main>
  )
}
