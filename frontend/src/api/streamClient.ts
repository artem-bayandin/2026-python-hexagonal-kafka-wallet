import type { TransactionStatusEvent } from '../types/wallet'
import { authenticatedFetch } from './client'

const MIN_RETRY_MS = 3000
const MAX_RETRY_MS = 30000

export type StatusStreamHandlers = {
  onEvent: (event: TransactionStatusEvent, lastEventId: string | null) => void
  onConnectionChange: (connected: boolean) => void
}

function parseRetryMs(value: string | undefined, fallback: number): number {
  if (value === undefined) {
    return fallback
  }
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed < MIN_RETRY_MS) {
    return Math.max(fallback, MIN_RETRY_MS)
  }
  return Math.min(parsed, MAX_RETRY_MS)
}

function parseSseBlock(
  block: string,
): { event: TransactionStatusEvent; lastEventId: string | null } | null {
  let eventName = 'message'
  let data = ''
  let lastEventId: string | null = null
  for (const rawLine of block.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    if (line.startsWith(':') || line === '') {
      continue
    }
    const splitAt = line.indexOf(':')
    const field = splitAt === -1 ? line : line.slice(0, splitAt)
    const value = splitAt === -1 ? '' : line.slice(splitAt + 1).replace(/^ /, '')
    if (field === 'event') {
      eventName = value
    } else if (field === 'data') {
      data = data === '' ? value : `${data}\n${value}`
    } else if (field === 'id') {
      lastEventId = value
    }
  }
  if (eventName !== 'transaction_status' || data === '') {
    return null
  }
  const parsed = JSON.parse(data) as TransactionStatusEvent
  return { event: parsed, lastEventId }
}

export async function connectTransactionStatusStream(
  signal: AbortSignal,
  handlers: StatusStreamHandlers,
): Promise<void> {
  let lastEventId: string | null = null
  let retryMs = MIN_RETRY_MS
  let attempt = 0

  while (!signal.aborted) {
    try {
      const headers: Record<string, string> = {}
      if (lastEventId !== null) {
        headers['Last-Event-ID'] = lastEventId
      }
      const response = await authenticatedFetch('/me/stream', { headers, signal })
      if (response.status === 401) {
        handlers.onConnectionChange(false)
        return
      }
      if (!response.ok || response.body === null) {
        handlers.onConnectionChange(false)
        throw new Error(`stream failed: ${response.status}`)
      }
      handlers.onConnectionChange(true)
      attempt = 0
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (!signal.aborted) {
        const { done, value } = await reader.read()
        if (done) {
          break
        }
        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r\n/g, '\n')
        let separator = buffer.indexOf('\n\n')
        while (separator !== -1) {
          const block = buffer.slice(0, separator)
          buffer = buffer.slice(separator + 2)
          for (const line of block.split('\n')) {
            if (line.startsWith('retry:')) {
              retryMs = parseRetryMs(line.slice('retry:'.length).trim(), retryMs)
            }
          }
          const parsed = parseSseBlock(block)
          if (parsed !== null) {
            if (parsed.lastEventId !== null) {
              lastEventId = parsed.lastEventId
            }
            handlers.onEvent(parsed.event, lastEventId)
          }
          separator = buffer.indexOf('\n\n')
        }
      }
      handlers.onConnectionChange(false)
    } catch (error) {
      handlers.onConnectionChange(false)
      if (signal.aborted) {
        return
      }
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
    }
    attempt += 1
    const delay = Math.min(MAX_RETRY_MS, retryMs * 2 ** Math.max(0, attempt - 1))
    await new Promise((resolve) => {
      const timer = window.setTimeout(resolve, delay)
      const onAbort = () => {
        window.clearTimeout(timer)
        resolve(undefined)
      }
      signal.addEventListener('abort', onAbort, { once: true })
    })
  }
}
