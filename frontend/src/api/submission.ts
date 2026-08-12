import type { SubmissionAccepted } from '../types/submission'

export type { SubmissionAccepted }

export async function parseSubmissionAccepted(
  response: Response,
): Promise<SubmissionAccepted> {
  return response.json() as Promise<SubmissionAccepted>
}
