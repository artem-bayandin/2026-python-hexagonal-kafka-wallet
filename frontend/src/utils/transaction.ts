/** Asset column label for transaction history (deposit/withdraw/transfer vs exchange). */
export function formatTransactionAsset(
  type: string,
  sourceAsset: string | null | undefined,
  destAsset: string | null | undefined,
): string {
  const source = sourceAsset ?? ''
  const dest = destAsset ?? ''
  const normalizedType = type.toUpperCase()

  if (normalizedType === 'EXCHANGE' && source !== '' && dest !== '') {
    return `${source}/${dest}`
  }
  if (normalizedType === 'DEPOSIT') {
    return dest
  }
  return source || dest
}
