export type RequestOtpResponse = {
  expires_at: string
  otp?: string
}

export type VerifyOtpResponse = {
  access_token: string
  token_type: 'bearer'
  expires_at: string
}

export type ErrorEnvelope = {
  code: string
  message: string
  details?: Record<string, unknown>
}
