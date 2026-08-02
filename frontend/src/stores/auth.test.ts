import { beforeEach, describe, expect, it } from 'vitest'
import { useAuth } from './auth'

describe('auth store', () => {
  beforeEach(() => { localStorage.clear(); useAuth.getState().logout() })
  it('persists and clears tokens', () => {
    useAuth.getState().setTokens('access', 'refresh')
    expect(localStorage.getItem('access_token')).toBe('access')
    useAuth.getState().logout()
    expect(useAuth.getState().accessToken).toBeNull()
  })
})
