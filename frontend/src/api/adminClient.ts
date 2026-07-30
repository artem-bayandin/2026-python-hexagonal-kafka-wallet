import { ApiError } from './client'
import type {
  AdminDepositRequest,
  AdminDepositResponse,
  BalanceList,
  CurrencyItem,
  DataList,
  TransactionList,
  UserReferenceItem,
} from '../types/admin'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const ADMIN_KEY_STORAGE = 'admin_api_key'

export function getAdminKey(): string | null {
  return sessionStorage.getItem(ADMIN_KEY_STORAGE)
}

export function setAdminKey(key: string): void {
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

export async function AdminDeposit(
  body: AdminDepositRequest,
): Promise<AdminDepositResponse> {
  const response = await adminFetch('/admin/deposits', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<AdminDepositResponse>
}

export async function getAdminBalances(): Promise<BalanceList> {
  const response = await adminFetch('/admin/balances')
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<BalanceList>
}

export async function listAdminTransactions(
  pageNumber = 0,
  pageSize = 20,
): Promise<TransactionList> {
  const params = new URLSearchParams({
    page_number: String(pageNumber),
    page_size: String(pageSize),
  })
  const response = await adminFetch(`/admin/transactions?${params.toString()}`)
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<TransactionList>
}
