export function normalizeEmail(
  value: string | null | undefined,
): string | undefined {
  if (value === null || value === undefined) {
    return undefined
  }
  const normalized = value.trim().toLowerCase()
  return normalized === '' ? undefined : normalized
}
