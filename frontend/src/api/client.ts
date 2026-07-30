import type { ErrorEnvelope, RequestOtpResponse, VerifyOtpResponse } from '../types/auth'
import { normalizeEmail } from '../utils/email'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export class ApiError extends Error {
  readonly status: number
  readonly envelope: ErrorEnvelope

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.message)
    this.name = 'ApiError'
    this.status = status
    this.envelope = envelope
  }
}

async function parseErrorResponse(response: Response): Promise<ApiError> {
  try {
    const envelope = (await response.json()) as ErrorEnvelope
    return new ApiError(response.status, envelope)
  } catch {
    return new ApiError(response.status, {
      code: 'INTERNAL_ERROR',
      message: 'Request failed.',
    })
  }
}

export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = sessionStorage.getItem('access_token')
  const headers = new Headers(init.headers)
  if (token !== null) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (response.status === 401) {
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('user_email')
  }

  return response
}

export async function requestOtp(email: string): Promise<RequestOtpResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/otp/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })

  if (!response.ok) {
    throw await parseErrorResponse(response)
  }

  return response.json() as Promise<RequestOtpResponse>
}

export async function verifyOtp(
  email: string,
  otp: string,
): Promise<VerifyOtpResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/otp/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp }),
  })

  if (!response.ok) {
    throw await parseErrorResponse(response)
  }

  const result = (await response.json()) as VerifyOtpResponse
  sessionStorage.setItem('access_token', result.access_token)
  const normalizedEmail = normalizeEmail(email)
  if (normalizedEmail !== undefined) {
    sessionStorage.setItem('user_email', normalizedEmail)
  }
  return result
}

export async function checkAuthenticated(): Promise<{ status: string }> {
  const response = await authenticatedFetch('/health/authenticated')

  if (!response.ok) {
    throw await parseErrorResponse(response)
  }

  return response.json() as Promise<{ status: string }>
}

export async function logout(): Promise<void> {
  const response = await authenticatedFetch('/auth/logout', {
    method: 'POST',
  })

  if (response.status === 204) {
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('user_email')
    return
  }

  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
}
