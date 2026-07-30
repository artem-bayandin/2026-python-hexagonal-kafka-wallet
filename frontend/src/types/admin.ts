export type DataList<T> = {
  items: T[]
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

export type AdminDepositRequest = {
  email: string
  asset: string
  amount: string
}

export type AdminDepositResponse = {
  id: string
  type: string
  status: string
}

export type BalanceItem = {
  asset: string
  available: string
}

export type BalanceList = {
  items: BalanceItem[]
}

export type TransactionItem = {
  id: string
  type: string
  status: string
  source_asset: string | null
  dest_asset: string | null
  amount: string
  created_at: string
}

export type TransactionList = {
  total_items: number
  items: TransactionItem[]
}
