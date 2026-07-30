import { type FormEvent, useState } from 'react'
import { ApiError } from '../api/client'
import {
  AdminDeposit,
  getAdminBalances,
  getAdminKey,
  listAdminTransactions,
  listReferenceCurrencies,
  listReferenceUsers,
  setAdminKey,
} from '../api/adminClient'
import type {
  BalanceItem,
  CurrencyItem,
  TransactionItem,
  UserReferenceItem,
} from '../types/admin'

type AdminPageProps = {
  onBack: () => void
}

const TRANSACTIONS_PAGE_SIZE = 20

function amountStepForPrecision(precision: number): string {
  if (precision <= 0) {
    return '1'
  }
  return `0.${'0'.repeat(precision - 1)}1`
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString()
}

export function AdminPage({ onBack }: AdminPageProps) {
  const [adminKeyInput, setAdminKeyInput] = useState(getAdminKey() ?? '')
  const [currencies, setCurrencies] = useState<CurrencyItem[]>([])
  const [users, setUsers] = useState<UserReferenceItem[]>([])
  const [balances, setBalances] = useState<BalanceItem[]>([])
  const [transactions, setTransactions] = useState<TransactionItem[]>([])
  const [transactionsTotalItems, setTransactionsTotalItems] = useState(0)
  const [transactionsPageNumber, setTransactionsPageNumber] = useState(0)
  const [selectedCurrencyLabel, setSelectedCurrencyLabel] = useState('')
  const [selectedUserEmail, setSelectedUserEmail] = useState('')
  const [amount, setAmount] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmittingDeposit, setIsSubmittingDeposit] = useState(false)
  const [isLoadingMoreTransactions, setIsLoadingMoreTransactions] =
    useState(false)
  const [dataLoaded, setDataLoaded] = useState(false)

  const selectedCurrency = currencies.find(
    (currency) => currency.label === selectedCurrencyLabel,
  )

  async function loadWalletData() {
    const [balanceResult, transactionResult] = await Promise.all([
      getAdminBalances(),
      listAdminTransactions(0, TRANSACTIONS_PAGE_SIZE),
    ])
    setBalances(balanceResult.items)
    setTransactions(transactionResult.items)
    setTransactionsTotalItems(transactionResult.total_items)
    setTransactionsPageNumber(0)
  }

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
      await loadWalletData()
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
      await loadWalletData()
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

  async function handleLoadMoreTransactions() {
    if (transactions.length >= transactionsTotalItems) {
      return
    }

    const nextPageNumber = transactionsPageNumber + 1
    setIsLoadingMoreTransactions(true)
    setErrorMessage(null)

    try {
      const result = await listAdminTransactions(
        nextPageNumber,
        TRANSACTIONS_PAGE_SIZE,
      )
      setTransactions((current) => [...current, ...result.items])
      setTransactionsTotalItems(result.total_items)
      setTransactionsPageNumber(nextPageNumber)
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Unable to load more transactions.')
      }
    } finally {
      setIsLoadingMoreTransactions(false)
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
          disabled={isLoading || isSubmittingDeposit || isLoadingMoreTransactions}
        />
        <button
          className="auth-button"
          type="submit"
          disabled={isLoading || isSubmittingDeposit || isLoadingMoreTransactions}
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
            <h2 className="auth-label">Admin balances</h2>
            {balances.length === 0 ? (
              <p className="auth-detail">Balances: no data</p>
            ) : (
              <table className="auth-table">
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Available</th>
                  </tr>
                </thead>
                <tbody>
                  {balances.map((balance) => (
                    <tr key={balance.asset}>
                      <td>{balance.asset}</td>
                      <td>{balance.available}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="auth-form">
            <h2 className="auth-label">Transaction history</h2>
            {transactions.length === 0 ? (
              <p className="auth-detail">Transactions: no data</p>
            ) : (
              <table className="auth-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr key={transaction.id}>
                      <td>{transaction.type}</td>
                      <td>{transaction.status}</td>
                      <td>{formatTimestamp(transaction.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {transactions.length < transactionsTotalItems && (
              <button
                className="auth-button"
                type="button"
                onClick={handleLoadMoreTransactions}
                disabled={
                  isLoading ||
                  isSubmittingDeposit ||
                  isLoadingMoreTransactions
                }
              >
                {isLoadingMoreTransactions ? 'Loading…' : 'Load more'}
              </button>
            )}
          </section>

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
