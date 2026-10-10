import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getHealth } from './client'

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

describe('api client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns the parsed body on success', async () => {
    const fetchSpy = mockFetch(200, { status: 'ok' })

    await expect(getHealth()).resolves.toEqual({ status: 'ok' })
    expect(fetchSpy).toHaveBeenCalledWith('/api/health', expect.anything())
  })

  it('throws ApiError carrying the server detail message', async () => {
    mockFetch(502, { detail: 'Routing provider unavailable' })

    const error = await getHealth().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 502, message: 'Routing provider unavailable' })
  })

  it('falls back to a generic message when the body has no detail', async () => {
    mockFetch(500, {})

    await expect(getHealth()).rejects.toThrow('Request failed with status 500')
  })
})
