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
