export type TransactionStatus =
  | 'submitted'
  | 'pending'
  | 'in_progress'
  | 'succeeded'
  | 'failed'

export type TransactionType = 'deposit' | 'withdrawal' | 'exchange' | 'transfer'

export interface TransactionStatusEvent {
  request_id: string
  status: TransactionStatus
  type: TransactionType
  error: string | null
}

export interface BalanceItem {
  asset: string
  amount: string
  locked: string
}

export type BalanceList = {
  items: BalanceItem[]
}

export interface TransactionItem {
  id: string
  request_id: string
  type: TransactionType
  status: TransactionStatus
  source_asset: string | null
  dest_asset: string | null
  amount: string
  error: string | null
  created_at: string
  updated_at: string
  direction?: 'in' | 'out'
}

export type TransactionList = {
  total_items: number
  items: TransactionItem[]
}

export type CurrencyItem = {
  label: string
  name: string
  type: string
  precision: number
}

export type UserReferenceItem = {
  user_id: string
  email: string
}

export type DataList<T> = {
  items: T[]
}

export type WalletMutationResponse = {
  id: string
  type: string
  status: string
}

export type ExchangeRequest = {
  source_asset: string
  destination_asset: string
  amount: string
}

export type WithdrawRequest = {
  asset: string
  amount: string
}

export type TransferRequest = {
  email: string
  asset: string
  amount: string
}
