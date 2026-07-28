import type { ErrorEnvelope, RequestOtpResponse } from '../types/auth'

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
