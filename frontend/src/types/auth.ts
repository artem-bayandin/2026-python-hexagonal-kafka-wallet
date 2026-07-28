export type RequestOtpResponse = {
  expires_at: string
  otp?: string
}

export type ErrorEnvelope = {
  code: string
  message: string
  details?: Record<string, unknown>
}
