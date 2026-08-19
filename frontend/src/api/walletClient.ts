import { ApiError, authenticatedFetch } from './client'
import { parseSubmissionAccepted, type SubmissionAccepted } from './submission'
import type {
  BalanceList,
  CurrencyItem,
  DataList,
  ExchangeRequest,
  TransactionList,
  TransferRequest,
  UserReferenceItem,
  WithdrawRequest,
} from '../types/wallet'

export type { SubmissionAccepted }

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

export async function getUserBalances(): Promise<BalanceList> {
  const response = await authenticatedFetch('/me/balances')
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<BalanceList>
}

export async function listUserTransactions(
  pageNumber = 0,
  pageSize = 20,
): Promise<TransactionList> {
  const params = new URLSearchParams({
    page_number: String(pageNumber),
    page_size: String(pageSize),
  })
  const response = await authenticatedFetch(
    `/me/transactions?${params.toString()}`,
  )
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<TransactionList>
}

export async function listReferenceCurrencies(): Promise<DataList<CurrencyItem>> {
  const response = await authenticatedFetch('/reference/currencies')
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<DataList<CurrencyItem>>
}

export async function listReferenceUsers(): Promise<DataList<UserReferenceItem>> {
  const response = await authenticatedFetch('/reference/users')
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<DataList<UserReferenceItem>>
}

export async function submitAuthenticatedMutation(
  path: string,
  body: unknown,
): Promise<SubmissionAccepted> {
  const response = await authenticatedFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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

export async function createExchange(
  body: ExchangeRequest,
): Promise<SubmissionAccepted> {
  return submitAuthenticatedMutation('/me/exchanges', body)
}

export async function createWithdrawal(
  body: WithdrawRequest,
): Promise<SubmissionAccepted> {
  return submitAuthenticatedMutation('/me/withdrawals', body)
}

export async function createTransfer(
  body: TransferRequest,
): Promise<SubmissionAccepted> {
  return submitAuthenticatedMutation('/me/transfers', body)
}
