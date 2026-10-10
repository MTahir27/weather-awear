export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string'
        ? body.detail
        : `Request failed with status ${response.status}`
    throw new ApiError(response.status, detail)
  }
  return body as T
}

export interface HealthResponse {
  status: 'ok'
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}
