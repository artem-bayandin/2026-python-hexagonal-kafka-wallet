import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import {
  adminDeposit,
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
  TransactionStatus,
  UserReferenceItem,
} from '../types/admin'
import { formatTransactionAsset } from '../utils/transaction'
import { acceptanceToastMessage, statusToastMessage } from '../utils/toast'
import { spendableOf } from '../utils/transaction_status'

type AdminPageProps = {
  onBack: () => void
}

const TRANSACTIONS_POLL_LIMIT = 100
const INITIAL_RETRY_MS = 1000
const MAX_RETRY_MS = 8000

const parsedToastMs = Number.parseInt(
  import.meta.env.VITE_STATUS_TOAST_MS ?? '5000',
  10,
)
const STATUS_TOAST_MS =
  Number.isFinite(parsedToastMs) && parsedToastMs > 0 ? parsedToastMs : 5000

const STATUS_RANK: Record<TransactionStatus, number> = {
  submitted: 0,
  pending: 1,
  in_progress: 2,
  succeeded: 3,
  failed: 3,
}

const TOAST_STATUSES = new Set<TransactionStatus>([
  'pending',
  'in_progress',
  'succeeded',
  'failed',
])

function isTerminalStatus(status: TransactionStatus): boolean {
  return status === 'succeeded' || status === 'failed'
}

type StatusToast = {
  id: string
  message: string
  variant?: 'status' | 'accepted'
}

type TimestampKey = {
  epochSecond: number
  fraction: string
}

function timestampKey(value: string): TimestampKey | null {
  const match =
    /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$/.exec(
      value,
    )
  if (match === null) {
    return null
  }
  const epochSecond = Date.parse(`${match[1]}${match[3]}`)
  if (Number.isNaN(epochSecond)) {
    return null
  }
  return { epochSecond, fraction: match[2] ?? '' }
}

function compareTimestamps(left: string, right: string): number {
  const leftKey = timestampKey(left)
  const rightKey = timestampKey(right)
  if (leftKey === null || rightKey === null) {
    return left.localeCompare(right)
  }
  if (leftKey.epochSecond !== rightKey.epochSecond) {
    return leftKey.epochSecond - rightKey.epochSecond
  }
  const precision = Math.max(leftKey.fraction.length, rightKey.fraction.length)
  return leftKey.fraction
    .padEnd(precision, '0')
    .localeCompare(rightKey.fraction.padEnd(precision, '0'))
}

function newestFirst(
  left: TransactionItem,
  right: TransactionItem,
): number {
  const timestampOrder = compareTimestamps(right.updated_at, left.updated_at)
  return timestampOrder === 0 ? right.id.localeCompare(left.id) : timestampOrder
}

function upsertTransaction(
  current: TransactionItem[],
  incoming: TransactionItem,
): { accepted: boolean; items: TransactionItem[] } {
  const matching = current.filter(
    (item) =>
      item.id === incoming.id || item.request_id === incoming.request_id,
  )
  if (matching.length === 0) {
    return {
      accepted: true,
      items: [...current, incoming].sort(newestFirst),
    }
  }

  const existing = matching.reduce((latest, item) =>
    compareTimestamps(item.updated_at, latest.updated_at) > 0 ? item : latest,
  )
  if (
    compareTimestamps(incoming.updated_at, existing.updated_at) <= 0 ||
    STATUS_RANK[incoming.status] < STATUS_RANK[existing.status] ||
    (isTerminalStatus(existing.status) &&
      incoming.status !== existing.status)
  ) {
    return { accepted: false, items: current }
  }

  return {
    accepted: true,
    items: [
      ...current.filter(
        (item) =>
          item.id !== incoming.id &&
          item.request_id !== incoming.request_id,
      ),
      incoming,
    ].sort(newestFirst),
  }
}

function isAdminWalletTransaction(item: TransactionItem): boolean {
  return item.type === 'deposit' || item.type === 'withdrawal'
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function isAuthorizationError(error: unknown): error is ApiError {
  return (
    error instanceof ApiError && (error.status === 401 || error.status === 403)
  )
}

function isTransientTransportError(error: unknown): boolean {
  return (
    error instanceof TypeError ||
    (error instanceof ApiError &&
      (error.status === 408 || error.status === 429 || error.status >= 500))
  )
}

function waitForRetry(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve()
      return
    }
    const timeoutId = window.setTimeout(finish, milliseconds)
    signal.addEventListener('abort', finish, { once: true })

    function finish() {
      window.clearTimeout(timeoutId)
      signal.removeEventListener('abort', finish)
      resolve()
    }
  })
}

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
  const [selectedCurrencyLabel, setSelectedCurrencyLabel] = useState('')
  const [selectedUserEmail, setSelectedUserEmail] = useState('')
  const [amount, setAmount] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [pollErrorMessage, setPollErrorMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmittingDeposit, setIsSubmittingDeposit] = useState(false)
  const [dataLoaded, setDataLoaded] = useState(false)
  const [pollSessionId, setPollSessionId] = useState<number | null>(null)
  const [statusToasts, setStatusToasts] = useState<StatusToast[]>([])
  const pollControllerRef = useRef<AbortController | null>(null)
  const loadGenerationRef = useRef(0)
  const transactionsRef = useRef<TransactionItem[]>([])
  const succeededAdminTransactionsRef = useRef(new Set<string>())
  const toastTimersRef = useRef(new Map<string, number>())

  const pushToast = useCallback(
    (message: string, variant: 'status' | 'accepted' = 'status') => {
      const id = crypto.randomUUID()
      setStatusToasts((current) => [{ id, message, variant }, ...current])
      const timeoutId = window.setTimeout(() => {
        toastTimersRef.current.delete(id)
        setStatusToasts((current) =>
          current.filter((toast) => toast.id !== id),
        )
      }, STATUS_TOAST_MS)
      toastTimersRef.current.set(id, timeoutId)
    },
    [],
  )

  const selectedCurrency = currencies.find(
    (currency) => currency.label === selectedCurrencyLabel,
  )

  const isBusy = isLoading || isSubmittingDeposit

  useEffect(() => {
    const toastTimers = toastTimersRef.current
    return () => {
      for (const timeoutId of toastTimers.values()) {
        window.clearTimeout(timeoutId)
      }
      toastTimers.clear()
    }
  }, [])

  useEffect(() => {
    if (pollSessionId === null) {
      return
    }

    const controller = new AbortController()
    const { signal } = controller
    pollControllerRef.current = controller

    function clearToastTimers() {
      for (const timeoutId of toastTimersRef.current.values()) {
        window.clearTimeout(timeoutId)
      }
      toastTimersRef.current.clear()
    }

    function loseAdminAccess(message: string) {
      if (signal.aborted) {
        return
      }
      loadGenerationRef.current += 1
      controller.abort()
      setAdminKey('')
      setAdminKeyInput('')
      setPollSessionId(null)
      setCurrencies([])
      setUsers([])
      setBalances([])
      setSelectedCurrencyLabel('')
      setSelectedUserEmail('')
      setAmount('')
      transactionsRef.current = []
      setTransactions([])
      succeededAdminTransactionsRef.current.clear()
      clearToastTimers()
      setStatusToasts([])
      setDataLoaded(false)
      setPollErrorMessage(null)
      setErrorMessage(null)
      setErrorMessage(message)
    }

    function pushStatusToast(message: string) {
      pushToast(message)
    }

    async function refreshBalances() {
      try {
        const result = await getAdminBalances(signal)
        if (!signal.aborted) {
          setBalances(result.items)
        }
      } catch (error) {
        if (signal.aborted || isAbortError(error)) {
          return
        }
        if (isAuthorizationError(error)) {
          loseAdminAccess(error.envelope.message)
        } else if (error instanceof ApiError) {
          setErrorMessage(error.envelope.message)
        } else {
          setErrorMessage('Unable to refresh admin balances.')
        }
      }
    }

    async function processItems(items: TransactionItem[], live: boolean) {
      let current = transactionsRef.current
      let shouldRefreshBalances = false

      for (const item of items) {
        const result = upsertTransaction(current, item)
        if (!result.accepted) {
          continue
        }
        current = result.items

        if (
          isAdminWalletTransaction(item) &&
          item.status === 'succeeded' &&
          !succeededAdminTransactionsRef.current.has(item.request_id)
        ) {
          succeededAdminTransactionsRef.current.add(item.request_id)
          shouldRefreshBalances = live
        }

        if (
          live &&
          isAdminWalletTransaction(item) &&
          TOAST_STATUSES.has(item.status)
        ) {
          pushStatusToast(
            statusToastMessage(item.type, item.request_id, item.status),
          )
        }
      }

      if (current !== transactionsRef.current) {
        transactionsRef.current = current
        setTransactions(current)
      }
      if (shouldRefreshBalances) {
        await refreshBalances()
      }
    }

    async function pollTransactions() {
      let cursor: string | undefined
      let catchingUp = true
      let retryCount = 0

      while (!signal.aborted) {
        try {
          const result = await listAdminTransactions({
            ...(cursor === undefined ? {} : { cursor }),
            limit: TRANSACTIONS_POLL_LIMIT,
            ...(catchingUp ? { timeoutSeconds: 0 } : {}),
            signal,
          })
          if (signal.aborted) {
            return
          }

          retryCount = 0
          setPollErrorMessage(null)
          await processItems(result.items, !catchingUp)
          if (signal.aborted) {
            return
          }

          const nextCursor = result.next_cursor ?? undefined
          if (result.items.length > 0 && nextCursor === undefined) {
            setPollErrorMessage(
              'Live transaction updates returned an invalid cursor.',
            )
            return
          }
          cursor = nextCursor

          if (catchingUp) {
            if (result.items.length === 0) {
              catchingUp = false
              await refreshBalances()
              if (signal.aborted) {
                return
              }
            }
            continue
          }

          if (cursor === undefined && result.items.length === 0) {
            await waitForRetry(INITIAL_RETRY_MS, signal)
          }
        } catch (error) {
          if (signal.aborted || isAbortError(error)) {
            return
          }
          if (isAuthorizationError(error)) {
            loseAdminAccess(error.envelope.message)
            return
          }
          if (!isTransientTransportError(error)) {
            setPollErrorMessage(
              error instanceof ApiError
                ? error.envelope.message
                : 'Live transaction updates stopped.',
            )
            return
          }

          retryCount = Math.min(retryCount + 1, 4)
          setPollErrorMessage(
            'Live transaction updates unavailable. Retrying…',
          )
          const retryMilliseconds = Math.min(
            INITIAL_RETRY_MS * 2 ** (retryCount - 1),
            MAX_RETRY_MS,
          )
          await waitForRetry(retryMilliseconds, signal)
        }
      }
    }

    void pollTransactions()

    return () => {
      controller.abort()
      if (pollControllerRef.current === controller) {
        pollControllerRef.current = null
      }
    }
  }, [pollSessionId, pushToast])

  async function handleSaveKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const key = adminKeyInput.trim()
    const generation = loadGenerationRef.current + 1
    loadGenerationRef.current = generation
    pollControllerRef.current?.abort()
    setPollSessionId(null)
    setAdminKey(key)
    setIsLoading(true)
    setErrorMessage(null)
    setPollErrorMessage(null)
    setDataLoaded(false)
    setCurrencies([])
    setUsers([])
    setBalances([])
    setSelectedCurrencyLabel('')
    setSelectedUserEmail('')
    setAmount('')
    transactionsRef.current = []
    setTransactions([])
    succeededAdminTransactionsRef.current.clear()
    for (const timeoutId of toastTimersRef.current.values()) {
      window.clearTimeout(timeoutId)
    }
    toastTimersRef.current.clear()
    setStatusToasts([])

    try {
      const [currencyResult, userResult, balanceResult] = await Promise.all([
        listReferenceCurrencies(),
        listReferenceUsers(),
        getAdminBalances(),
      ])
      if (loadGenerationRef.current !== generation) {
        return
      }
      setCurrencies(currencyResult.items)
      setUsers(userResult.items)
      setBalances(balanceResult.items)
      setSelectedCurrencyLabel(
        currencyResult.items.length > 0 ? currencyResult.items[0].label : '',
      )
      setSelectedUserEmail(
        userResult.items.length > 0 ? userResult.items[0].email : '',
      )
      setDataLoaded(true)
      setPollSessionId(generation)
    } catch (error) {
      if (loadGenerationRef.current !== generation) {
        return
      }
      if (isAuthorizationError(error)) {
        setAdminKey('')
        setAdminKeyInput('')
        setSelectedCurrencyLabel('')
        setSelectedUserEmail('')
        setAmount('')
        setPollErrorMessage(null)
        setErrorMessage(null)
        setErrorMessage(error.envelope.message)
      } else if (error instanceof ApiError) {
        setErrorMessage(error.envelope.message)
      } else if (error instanceof Error) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('Unable to load reference data.')
      }
      setDataLoaded(false)
    } finally {
      if (loadGenerationRef.current === generation) {
        setIsLoading(false)
      }
    }
  }

  async function handleDepositSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (selectedUserEmail === '' || selectedCurrencyLabel === '') {
      return
    }

    const generation = loadGenerationRef.current
    setIsSubmittingDeposit(true)
    setErrorMessage(null)

    try {
      const result = await adminDeposit({
        email: selectedUserEmail,
        asset: selectedCurrencyLabel,
        amount,
      })
      if (loadGenerationRef.current !== generation) {
        return
      }
      pushToast(
        acceptanceToastMessage('deposit', result.request_id),
        'accepted',
      )
      setAmount('')
    } catch (error) {
      if (loadGenerationRef.current !== generation) {
        return
      }
      if (isAuthorizationError(error)) {
        loadGenerationRef.current += 1
        pollControllerRef.current?.abort()
        setAdminKey('')
        setAdminKeyInput('')
        setPollSessionId(null)
        setCurrencies([])
        setUsers([])
        setBalances([])
        setSelectedCurrencyLabel('')
        setSelectedUserEmail('')
        setAmount('')
        transactionsRef.current = []
        setTransactions([])
        succeededAdminTransactionsRef.current.clear()
        for (const timeoutId of toastTimersRef.current.values()) {
          window.clearTimeout(timeoutId)
        }
        toastTimersRef.current.clear()
        setStatusToasts([])
        setDataLoaded(false)
        setPollErrorMessage(null)
        setErrorMessage(null)
        setErrorMessage(error.envelope.message)
      } else if (error instanceof ApiError) {
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

  function handleDismissToast(id: string) {
    const timeoutId = toastTimersRef.current.get(id)
    if (timeoutId !== undefined) {
      window.clearTimeout(timeoutId)
      toastTimersRef.current.delete(id)
    }
    setStatusToasts((current) => current.filter((toast) => toast.id !== id))
  }

  function handleBack() {
    loadGenerationRef.current += 1
    pollControllerRef.current?.abort()
    setPollSessionId(null)
    transactionsRef.current = []
    succeededAdminTransactionsRef.current.clear()
    for (const timeoutId of toastTimersRef.current.values()) {
      window.clearTimeout(timeoutId)
    }
    toastTimersRef.current.clear()
    onBack()
  }

  return (
    <main className="wallet-page">
      <h1>Admin</h1>
      <p className="auth-detail">Development-only admin operator page.</p>
      <div className="status-toast-stack" aria-live="polite">
        {statusToasts.map((toast) => (
          <div
            className={
              toast.variant === 'accepted'
                ? 'status-toast status-toast--accepted'
                : 'status-toast'
            }
            key={toast.id}
            role="status"
          >
            <span>{toast.message}</span>
            <button
              className="status-toast-dismiss"
              type="button"
              aria-label="Dismiss notification"
              onClick={() => handleDismissToast(toast.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>

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
          disabled={isBusy}
        />
        <button className="auth-button" type="submit" disabled={isBusy}>
          {isLoading ? 'Loading…' : 'Save key and load data'}
        </button>
      </form>

      {errorMessage !== null && (
        <p className="auth-error" role="alert">
          {errorMessage}
        </p>
      )}

      {pollErrorMessage !== null && (
        <p className="auth-detail" role="status">
          {pollErrorMessage}
        </p>
      )}

      {dataLoaded && (
        <>
          <section className="wallet-section">
            <h2 className="auth-label">Balances</h2>
            {isLoading ? (
              <p className="auth-detail">Loading balances…</p>
            ) : balances.length === 0 ? (
              <p className="auth-detail">No balances yet.</p>
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
                      <td>{spendableOf(balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <form className="wallet-operation-card" onSubmit={handleDepositSubmit}>
            <h2>Deposit</h2>
            <label className="auth-label" htmlFor="currency-select">
              Currency
            </label>
            {currencies.length === 0 ? (
              <p className="auth-detail">No currencies available.</p>
            ) : (
              <div className="auth-select-wrap">
                <select
                  id="currency-select"
                  className="auth-input"
                  value={selectedCurrencyLabel}
                  onChange={(event) =>
                    setSelectedCurrencyLabel(event.target.value)
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
            <label className="auth-label" htmlFor="user-select">
              Recipient user
            </label>
            {users.length === 0 ? (
              <p className="auth-detail">No users available.</p>
            ) : (
              <div className="auth-select-wrap">
                <select
                  id="user-select"
                  className="auth-input"
                  value={selectedUserEmail}
                  onChange={(event) => setSelectedUserEmail(event.target.value)}
                  disabled={isBusy}
                >
                  {users.map((user) => (
                    <option key={user.user_id} value={user.email}>
                      {user.email}
                    </option>
                  ))}
                </select>
              </div>
            )}
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
                isBusy || users.length === 0 || currencies.length === 0
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
                isBusy ||
                users.length === 0 ||
                currencies.length === 0 ||
                amount.trim() === ''
              }
            >
              {isSubmittingDeposit ? 'Submitting…' : 'Submit deposit'}
            </button>
          </form>

          <section className="wallet-section">
            <h2 className="auth-label">Transaction history</h2>
            {isLoading ? (
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
                      <td>{transaction.type}</td>
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
          </section>
        </>
      )}

      <div className="wallet-actions">
        <button
          className="auth-button"
          type="button"
          onClick={handleBack}
          disabled={isBusy}
        >
          Back to app
        </button>
      </div>
    </main>
  )
}
