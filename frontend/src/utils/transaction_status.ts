import type { BalanceItem, TransactionItem, TransactionStatus } from '../types/wallet'

const STATUS_RANK: Record<TransactionStatus, number> = {
  submitted: 0,
  pending: 1,
  in_progress: 2,
  succeeded: 3,
  failed: 3,
}

const TERMINAL_STATUSES = new Set<TransactionStatus>(['succeeded', 'failed'])

export function statusRank(status: TransactionStatus): number {
  return STATUS_RANK[status]
}

export function isTerminal(status: TransactionStatus): boolean {
  return TERMINAL_STATUSES.has(status)
}

export function mergeStatus(
  current: TransactionItem | undefined,
  incoming: TransactionItem,
): TransactionItem {
  if (current === undefined) {
    return incoming
  }

  const incomingUpdatedAt = Date.parse(incoming.updated_at)
  const currentUpdatedAt = Date.parse(current.updated_at)

  if (Number.isNaN(incomingUpdatedAt) || Number.isNaN(currentUpdatedAt)) {
    return incoming
  }

  if (incomingUpdatedAt < currentUpdatedAt) {
    return current
  }

  if (incomingUpdatedAt > currentUpdatedAt) {
    if (statusRank(incoming.status) < statusRank(current.status)) {
      return {
        ...incoming,
        status: current.status,
        error: current.error ?? incoming.error,
      }
    }
    return incoming
  }

  if (statusRank(incoming.status) >= statusRank(current.status)) {
    return incoming
  }

  return current
}

type DecimalParts = {
  sign: bigint
  scale: number
}

function parseDecimalParts(value: string): DecimalParts {
  const trimmed = value.trim()
  if (!/^-?\d+(\.\d+)?$/.test(trimmed)) {
    throw new Error(`Invalid decimal string: ${value}`)
  }

  const negative = trimmed.startsWith('-')
  const unsigned = negative ? trimmed.slice(1) : trimmed
  const [integerPart, fractionalPart = ''] = unsigned.split('.')
  const digits = BigInt(integerPart + fractionalPart)

  return {
    sign: negative ? -digits : digits,
    scale: fractionalPart.length,
  }
}

function scaleDecimal(parts: DecimalParts, targetScale: number): bigint {
  if (parts.scale > targetScale) {
    throw new Error(`Cannot scale ${parts.scale} down to ${targetScale}`)
  }
  const factor = 10n ** BigInt(targetScale - parts.scale)
  return parts.sign * factor
}

function formatDecimal(value: bigint, scale: number): string {
  const negative = value < 0n
  const absolute = negative ? -value : value
  const raw = absolute.toString().padStart(scale + 1, '0')

  if (scale === 0) {
    return `${negative ? '-' : ''}${raw}`
  }

  const integerPart = raw.slice(0, -scale) || '0'
  const fractionalPart = raw.slice(-scale)
  return `${negative ? '-' : ''}${integerPart}.${fractionalPart}`
}

export function spendableOf(balance: Pick<BalanceItem, 'amount' | 'locked'>): string {
  const amount = parseDecimalParts(balance.amount)
  const locked = parseDecimalParts(balance.locked)
  const scale = Math.max(amount.scale, locked.scale)
  const spendable = scaleDecimal(amount, scale) - scaleDecimal(locked, scale)
  return formatDecimal(spendable, scale)
}

export function reconcileTransactionsByRequestId(
  existing: TransactionItem[],
  refreshed: TransactionItem[],
): TransactionItem[] {
  const byRequestId = new Map(existing.map((item) => [item.request_id, item]))
  for (const incoming of refreshed) {
    const current = byRequestId.get(incoming.request_id)
    byRequestId.set(incoming.request_id, mergeStatus(current, incoming))
  }

  const seen = new Set<string>()
  const merged: TransactionItem[] = []
  for (const item of existing) {
    const next = byRequestId.get(item.request_id) ?? item
    if (!seen.has(next.request_id)) {
      merged.push(next)
      seen.add(next.request_id)
    }
  }
  for (const incoming of refreshed) {
    if (!seen.has(incoming.request_id)) {
      merged.push(byRequestId.get(incoming.request_id) ?? incoming)
      seen.add(incoming.request_id)
    }
  }
  return merged
}
