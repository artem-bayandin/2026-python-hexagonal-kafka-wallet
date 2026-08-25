import { ApiError } from './client'
import { parseSubmissionAccepted, type SubmissionAccepted } from './submission'
import type {
  AdminDepositRequest,
  AdminTransactionPollResponse,
  BalanceList,
  CurrencyItem,
  DataList,
  UserReferenceItem,
} from '../types/admin'

export type { SubmissionAccepted }

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const ADMIN_KEY_STORAGE = 'admin_api_key'

export function getAdminKey(): string | null {
  return sessionStorage.getItem(ADMIN_KEY_STORAGE)
}

export function setAdminKey(key: string): void {
  if (key === '') {
    sessionStorage.removeItem(ADMIN_KEY_STORAGE)
    return
  }
  sessionStorage.setItem(ADMIN_KEY_STORAGE, key)
}

async function parseErrorResponse(response: Response): Promise<ApiError> {
  try {
    const envelope = (await response.json()) as {
      code: string
      message: string
    }
    return new ApiError(response.status, envelope)
  } catch {
    return new ApiError(response.status, {
      code: 'INTERNAL_ERROR',
      message: 'Request failed.',
    })
  }
}

export async function adminFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const key = getAdminKey()
  if (!key) {
    throw new Error('Admin key is not set.')
  }
  const headers = new Headers(init.headers)
  headers.set('X-Admin-Key', key)
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers })
}

export async function submitAdminMutation(
  path: string,
  body: unknown,
): Promise<SubmissionAccepted> {
  const response = await adminFetch(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  if (response.status === 202) {
    return parseSubmissionAccepted(response)
  }
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  throw await parseErrorResponse(response)
}

export async function listReferenceCurrencies(): Promise<DataList<CurrencyItem>> {
  const response = await adminFetch('/reference/currencies')
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<DataList<CurrencyItem>>
}

export async function listReferenceUsers(): Promise<DataList<UserReferenceItem>> {
  const response = await adminFetch('/reference/users')
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<DataList<UserReferenceItem>>
}

export async function adminDeposit(
  body: AdminDepositRequest,
): Promise<SubmissionAccepted> {
  return submitAdminMutation('/admin/deposits', body)
}

export async function getAdminBalances(
  signal?: AbortSignal,
): Promise<BalanceList> {
  const response = await adminFetch(
    '/admin/balances',
    signal === undefined ? {} : { signal },
  )
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<BalanceList>
}

export async function listAdminTransactions(
  {
    cursor,
    limit,
    timeoutSeconds,
    signal,
  }: {
    cursor?: string
    limit?: number
    timeoutSeconds?: number
    signal?: AbortSignal
  } = {},
): Promise<AdminTransactionPollResponse> {
  const params = new URLSearchParams()
  if (cursor !== undefined) {
    params.set('cursor', cursor)
  }
  if (limit !== undefined) {
    params.set('limit', String(limit))
  }
  if (timeoutSeconds !== undefined) {
    params.set('timeout_seconds', String(timeoutSeconds))
  }
  const query = params.toString()
  const path = query === '' ? '/admin/transactions' : `/admin/transactions?${query}`
  const response = await adminFetch(path, signal === undefined ? {} : { signal })
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<AdminTransactionPollResponse>
}
