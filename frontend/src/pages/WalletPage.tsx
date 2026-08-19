import { type FormEvent, useEffect, useState } from 'react'
import { ApiError, logout } from '../api/client'
import {
  createExchange,
  createTransfer,
  createWithdrawal,
  getUserBalances,
  listReferenceCurrencies,
  listReferenceUsers,
  listUserTransactions,
} from '../api/walletClient'
import type {
  BalanceItem,
  CurrencyItem,
  TransactionItem,
  UserReferenceItem,
} from '../types/wallet'
import { normalizeEmail } from '../utils/email'
import { reconcileTransactionsByRequestId, spendableOf } from '../utils/transaction_status'
import { formatTransactionAsset, formatTransactionType } from '../utils/transaction'

type WalletPageProps = {
  onOpenAdmin?: () => void
  onLoggedOut: () => void
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

export function WalletPage({ onOpenAdmin, onLoggedOut }: WalletPageProps) {
  const [currencies, setCurrencies] = useState<CurrencyItem[]>([])
  const [users, setUsers] = useState<UserReferenceItem[]>([])
  const [balances, setBalances] = useState<BalanceItem[]>([])
  const [transactions, setTransactions] = useState<TransactionItem[]>([])
  const [transactionsTotalItems, setTransactionsTotalItems] = useState(0)
  const [transactionsPageNumber, setTransactionsPageNumber] = useState(0)
  const [exchangeSourceAsset, setExchangeSourceAsset] = useState('')
  const [exchangeDestAsset, setExchangeDestAsset] = useState('')
  const [exchangeAmount, setExchangeAmount] = useState('')
  const [withdrawAsset, setWithdrawAsset] = useState('')
  const [withdrawAmount, setWithdrawAmount] = useState('')
  const [transferRecipientEmail, setTransferRecipientEmail] = useState('')
  const [transferAsset, setTransferAsset] = useState('')
  const [transferAmount, setTransferAmount] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [acceptanceMessage, setAcceptanceMessage] = useState<string | null>(null)
  const [isLoadingWallet, setIsLoadingWallet] = useState(true)
  const [isLoadingReference, setIsLoadingReference] = useState(true)
  const [isSubmittingExchange, setIsSubmittingExchange] = useState(false)
  const [isSubmittingWithdrawal, setIsSubmittingWithdrawal] = useState(false)
  const [isSubmittingTransfer, setIsSubmittingTransfer] = useState(false)
  const [isLoadingMoreTransactions, setIsLoadingMoreTransactions] =
    useState(false)
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  const currentUserEmail = normalizeEmail(sessionStorage.getItem('user_email'))

  const transferRecipients = users.filter(
    (user) =>
      currentUserEmail === undefined ||
      normalizeEmail(user.email) !== currentUserEmail,
  )

  const exchangeSourceCurrency = currencies.find(
    (currency) => currency.label === exchangeSourceAsset,
  )
  const withdrawCurrency = currencies.find(
    (currency) => currency.label === withdrawAsset,
  )
  const transferCurrency = currencies.find(
    (currency) => currency.label === transferAsset,
  )

  function applyCurrencyDefaults(items: CurrencyItem[]) {
    if (items.length === 0) {
      return
    }
    const firstLabel = items[0].label
    setExchangeSourceAsset(firstLabel)
    setExchangeDestAsset(items.length > 1 ? items[1].label : firstLabel)
    setWithdrawAsset(firstLabel)
    setTransferAsset(firstLabel)
  }

  async function loadWalletData() {
    const [balanceResult, transactionResult] = await Promise.all([
      getUserBalances(),
      listUserTransactions(0, TRANSACTIONS_PAGE_SIZE),
    ])
    setBalances(balanceResult.items)
    setTransactions(transactionResult.items)
    setTransactionsTotalItems(transactionResult.total_items)
    setTransactionsPageNumber(0)
  }

  useEffect(() => {
    let cancelled = false

    async function loadWallet() {
      setIsLoadingWallet(true)
      setErrorMessage(null)

      try {
        await loadWalletData()
      } catch (error) {
        if (cancelled) {
          return
        }
        if (error instanceof ApiError) {
          setErrorMessage(error.envelope.message)
        } else if (error instanceof Error) {
          setErrorMessage(error.message)
        } else {
          setErrorMessage('Unable to load wallet data.')
        }
      } finally {
        if (!cancelled) {
          setIsLoadingWallet(false)
        }
      }
    }

    void loadWallet()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadReference() {
      setIsLoadingReference(true)

      try {
        const [currencyResult, userResult] = await Promise.all([
          listReferenceCurrencies(),
          listReferenceUsers(),
        ])
        if (cancelled) {
          return
        }
        setCurrencies(currencyResult.items)
        setUsers(userResult.items)
        applyCurrencyDefaults(currencyResult.items)
        const recipients =
          currentUserEmail === undefined
            ? userResult.items
            : userResult.items.filter(
                (user) => normalizeEmail(user.email) !== currentUserEmail,
              )
        if (recipients.length > 0) {
          setTransferRecipientEmail(recipients[0].email)
        }
      } catch (error) {
        if (cancelled) {
          return
        }
        if (error instanceof ApiError) {
          setErrorMessage(error.envelope.message)
        } else if (error instanceof Error) {
          setErrorMessage(error.message)
        } else {
          setErrorMessage('Unable to load reference data.')
        }
      } finally {
        if (!cancelled) {
          setIsLoadingReference(false)
        }
      }
    }

    void loadReference()

    return () => {
      cancelled = true
    }
  }, [currentUserEmail])

  async function handleLoadMoreTransactions() {
    if (transactions.length >= transactionsTotalItems) {
      return
    }

    const nextPageNumber = transactionsPageNumber + 1
    setIsLoadingMoreTransactions(true)
    setErrorMessage(null)

    try {
      const result = await listUserTransactions(
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

  async function handleExchangeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (exchangeSourceAsset === exchangeDestAsset) {
      setErrorMessage('Source and destination assets must differ.')
      return
    }
    setIsSubmittingExchange(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    setAcceptanceMessage(null)

    try {
      const result = await createExchange({
        source_asset: exchangeSourceAsset,
        destination_asset: exchangeDestAsset,
        amount: exchangeAmount,
      })
      setAcceptanceMessage(
        `Exchange accepted for processing (request ${result.request_id}).`,
      )
      setExchangeAmount('')
      const [balanceResult, transactionResult] = await Promise.all([
        getUserBalances(),
        listUserTransactions(0, TRANSACTIONS_PAGE_SIZE),
      ])
      setBalances(balanceResult.items)
      setTransactions((current) =>
        reconcileTransactionsByRequestId(current, transactionResult.items),
      )
      setTransactionsTotalItems(transactionResult.total_items)
      setTransactionsPageNumber(0)
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Unable to submit exchange.')
      }
    } finally {
      setIsSubmittingExchange(false)
    }
  }

  async function handleWithdrawSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmittingWithdrawal(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    setAcceptanceMessage(null)

    try {
      const result = await createWithdrawal({
        asset: withdrawAsset,
        amount: withdrawAmount,
      })
      setAcceptanceMessage(
        `Withdrawal accepted for processing (request ${result.request_id}).`,
      )
      setWithdrawAmount('')
      const [balanceResult, transactionResult] = await Promise.all([
        getUserBalances(),
        listUserTransactions(0, TRANSACTIONS_PAGE_SIZE),
      ])
      setBalances(balanceResult.items)
      setTransactions((current) =>
        reconcileTransactionsByRequestId(current, transactionResult.items),
      )
      setTransactionsTotalItems(transactionResult.total_items)
      setTransactionsPageNumber(0)
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Unable to submit withdrawal.')
      }
    } finally {
      setIsSubmittingWithdrawal(false)
    }
  }

  async function handleTransferSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmittingTransfer(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    setAcceptanceMessage(null)

    try {
      const result = await createTransfer({
        email: transferRecipientEmail,
        asset: transferAsset,
        amount: transferAmount,
      })
      setAcceptanceMessage(
        `Transfer accepted for processing (request ${result.request_id}).`,
      )
      setTransferAmount('')
      const [balanceResult, transactionResult] = await Promise.all([
        getUserBalances(),
        listUserTransactions(0, TRANSACTIONS_PAGE_SIZE),
      ])
      setBalances(balanceResult.items)
      setTransactions((current) =>
        reconcileTransactionsByRequestId(current, transactionResult.items),
      )
      setTransactionsTotalItems(transactionResult.total_items)
      setTransactionsPageNumber(0)
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Unable to submit transfer.')
      }
    } finally {
      setIsSubmittingTransfer(false)
    }
  }

  async function handleLogout() {
    setIsLoggingOut(true)
    setErrorMessage(null)

    try {
      await logout()
      onLoggedOut()
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        onLoggedOut()
      } else if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else {
        setErrorMessage('Unable to log out. Please try again.')
      }
    } finally {
      setIsLoggingOut(false)
    }
  }

  const isBusy =
    isLoadingWallet ||
    isLoadingReference ||
    isSubmittingExchange ||
    isSubmittingWithdrawal ||
    isSubmittingTransfer ||
    isLoadingMoreTransactions ||
    isLoggingOut

  return (
    <main className="wallet-page">
      <h1>Wallet</h1>
      <p className="auth-detail">Your balances and wallet operations.</p>

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

      {acceptanceMessage !== null && (
        <p className="auth-detail" role="status">
          {acceptanceMessage}
        </p>
      )}

      <section className="wallet-section">
        <h2 className="auth-label">Balances</h2>
        {isLoadingWallet ? (
          <p className="auth-detail">Loading balances…</p>
        ) : balances.length === 0 ? (
          <p className="auth-detail">No balances yet.</p>
        ) : (
          <table className="auth-table">
            <thead>
              <tr>
                <th>Asset</th>
                <th>Total</th>
                <th>Locked</th>
                <th>Spendable</th>
              </tr>
            </thead>
            <tbody>
              {balances.map((balance) => (
                <tr key={balance.asset}>
                  <td>{balance.asset}</td>
                  <td>{balance.amount}</td>
                  <td>{balance.locked}</td>
                  <td>{spendableOf(balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="wallet-operations">
        <form
          className="wallet-operation-card"
          onSubmit={handleExchangeSubmit}
        >
          <h2>Exchange</h2>
          <label className="auth-label" htmlFor="exchange-source">
            Source asset
          </label>
          {isLoadingReference || currencies.length === 0 ? (
            <p className="auth-detail">
              {isLoadingReference ? 'Loading currencies…' : 'No currencies available.'}
            </p>
          ) : (
            <div className="auth-select-wrap">
              <select
                id="exchange-source"
                className="auth-input"
                value={exchangeSourceAsset}
                onChange={(event) =>
                  setExchangeSourceAsset(event.target.value)
                }
                disabled={isBusy}
              >
                {currencies.map((currency) => (
                  <option key={currency.label} value={currency.label}>
                    {currency.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <label className="auth-label" htmlFor="exchange-dest">
            Destination asset
          </label>
          {isLoadingReference || currencies.length === 0 ? (
            <p className="auth-detail">
              {isLoadingReference ? 'Loading currencies…' : 'No currencies available.'}
            </p>
          ) : (
            <div className="auth-select-wrap">
              <select
                id="exchange-dest"
                className="auth-input"
                value={exchangeDestAsset}
                onChange={(event) => setExchangeDestAsset(event.target.value)}
                disabled={isBusy}
              >
                {currencies.map((currency) => (
                  <option key={currency.label} value={currency.label}>
                    {currency.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <label className="auth-label" htmlFor="exchange-amount">
            Amount
          </label>
          <input
            id="exchange-amount"
            className="auth-input"
            type="text"
            inputMode="decimal"
            required
            value={exchangeAmount}
            onChange={(event) => setExchangeAmount(event.target.value)}
            disabled={isBusy || currencies.length === 0}
            step={
              exchangeSourceCurrency !== undefined
                ? amountStepForPrecision(exchangeSourceCurrency.precision)
                : undefined
            }
          />
          <button
            className="auth-button"
            type="submit"
            disabled={
              isBusy ||
              currencies.length === 0 ||
              exchangeAmount.trim() === '' ||
              exchangeSourceAsset === exchangeDestAsset
            }
          >
            {isSubmittingExchange ? 'Submitting…' : 'Submit exchange'}
          </button>
        </form>

        <form
          className="wallet-operation-card"
          onSubmit={handleWithdrawSubmit}
        >
          <h2>Withdraw</h2>
          <label className="auth-label" htmlFor="withdraw-asset">
            Asset
          </label>
          {isLoadingReference || currencies.length === 0 ? (
            <p className="auth-detail">
              {isLoadingReference ? 'Loading currencies…' : 'No currencies available.'}
            </p>
          ) : (
            <div className="auth-select-wrap">
              <select
                id="withdraw-asset"
                className="auth-input"
                value={withdrawAsset}
                onChange={(event) => setWithdrawAsset(event.target.value)}
                disabled={isBusy}
              >
                {currencies.map((currency) => (
                  <option key={currency.label} value={currency.label}>
                    {currency.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <label className="auth-label" htmlFor="withdraw-amount">
            Amount
          </label>
          <input
            id="withdraw-amount"
            className="auth-input"
            type="text"
            inputMode="decimal"
            required
            value={withdrawAmount}
            onChange={(event) => setWithdrawAmount(event.target.value)}
            disabled={isBusy || currencies.length === 0}
            step={
              withdrawCurrency !== undefined
                ? amountStepForPrecision(withdrawCurrency.precision)
                : undefined
            }
          />
          <button
            className="auth-button"
            type="submit"
            disabled={
              isBusy || currencies.length === 0 || withdrawAmount.trim() === ''
            }
          >
            {isSubmittingWithdrawal ? 'Submitting…' : 'Submit withdrawal'}
          </button>
        </form>

        <form
          className="wallet-operation-card"
          onSubmit={handleTransferSubmit}
        >
          <h2>Transfer</h2>
          <label className="auth-label" htmlFor="transfer-recipient">
            Recipient
          </label>
          {isLoadingReference ? (
            <p className="auth-detail">Loading users…</p>
          ) : transferRecipients.length === 0 ? (
            <p className="auth-detail">No recipients available.</p>
          ) : (
            <div className="auth-select-wrap">
              <select
                id="transfer-recipient"
                className="auth-input"
                value={transferRecipientEmail}
                onChange={(event) =>
                  setTransferRecipientEmail(event.target.value)
                }
                disabled={isBusy}
              >
                {transferRecipients.map((user) => (
                  <option key={user.user_id} value={user.email}>
                    {user.email}
                  </option>
                ))}
              </select>
            </div>
          )}
          <label className="auth-label" htmlFor="transfer-asset">
            Asset
          </label>
          {isLoadingReference || currencies.length === 0 ? (
            <p className="auth-detail">
              {isLoadingReference ? 'Loading currencies…' : 'No currencies available.'}
            </p>
          ) : (
            <div className="auth-select-wrap">
              <select
                id="transfer-asset"
                className="auth-input"
                value={transferAsset}
                onChange={(event) => setTransferAsset(event.target.value)}
                disabled={isBusy}
              >
                {currencies.map((currency) => (
                  <option key={currency.label} value={currency.label}>
                    {currency.label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <label className="auth-label" htmlFor="transfer-amount">
            Amount
          </label>
          <input
            id="transfer-amount"
            className="auth-input"
            type="text"
            inputMode="decimal"
            required
            value={transferAmount}
            onChange={(event) => setTransferAmount(event.target.value)}
            disabled={
              isBusy ||
              currencies.length === 0 ||
              transferRecipients.length === 0
            }
            step={
              transferCurrency !== undefined
                ? amountStepForPrecision(transferCurrency.precision)
                : undefined
            }
          />
          <button
            className="auth-button"
            type="submit"
            disabled={
              isBusy ||
              currencies.length === 0 ||
              transferRecipients.length === 0 ||
              transferAmount.trim() === ''
            }
          >
            {isSubmittingTransfer ? 'Submitting…' : 'Submit transfer'}
          </button>
        </form>
      </div>

      <section className="wallet-section">
        <h2 className="auth-label">Transaction history</h2>
        {isLoadingWallet ? (
          <p className="auth-detail">Loading transactions…</p>
        ) : transactions.length === 0 ? (
          <p className="auth-detail">No transactions yet.</p>
        ) : (
          <table className="auth-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Asset</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((transaction) => (
                <tr key={transaction.id}>
                  <td>{formatTransactionType(transaction.type, transaction.direction)}</td>
                  <td>
                    {formatTransactionAsset(
                      transaction.type,
                      transaction.source_asset,
                      transaction.dest_asset,
                    )}
                  </td>
                  <td>{transaction.amount}</td>
                  <td>{transaction.status}</td>
                  <td>{formatTimestamp(transaction.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!isLoadingWallet && transactions.length < transactionsTotalItems && (
          <button
            className="auth-button"
            type="button"
            onClick={handleLoadMoreTransactions}
            disabled={isBusy}
          >
            {isLoadingMoreTransactions ? 'Loading…' : 'Load more'}
          </button>
        )}
      </section>

      <div className="wallet-actions">
        {import.meta.env.DEV && onOpenAdmin !== undefined && (
          <button
            className="auth-button"
            type="button"
            onClick={onOpenAdmin}
            disabled={isBusy}
          >
            Open admin page
          </button>
        )}

        <button
          className="auth-button"
          type="button"
          onClick={handleLogout}
          disabled={isBusy}
        >
          {isLoggingOut ? 'Logging out…' : 'Logout'}
        </button>
      </div>
    </main>
  )
}
