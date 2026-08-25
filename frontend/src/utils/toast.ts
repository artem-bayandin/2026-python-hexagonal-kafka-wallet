export type TransactionToastType =
  | 'deposit'
  | 'withdrawal'
  | 'exchange'
  | 'transfer'

export function toastTypeLabel(type: TransactionToastType): string {
  return type === 'withdrawal' ? 'withdraw' : type
}

export function statusToastMessage(
  type: TransactionToastType,
  requestId: string,
  status: string,
): string {
  return `${toastTypeLabel(type)} (ID: ${requestId.slice(0, 4)}) moved to ${status}`
}

export function acceptanceToastMessage(
  type: TransactionToastType,
  requestId: string,
): string {
  return `${toastTypeLabel(type)} (ID: ${requestId.slice(0, 4)}) accepted`
}
