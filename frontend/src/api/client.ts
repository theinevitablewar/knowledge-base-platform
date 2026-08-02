import axios from 'axios'
import { useAuth } from '../stores/auth'

export const api = axios.create({ baseURL: '/api/v1', timeout: 30_000 })
api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(undefined, async (error: unknown) => {
  if (axios.isAxiosError(error) && error.response?.status === 403) {
    useAuth.getState().logout()
  }
  return Promise.reject(error)
})

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) return error.response?.data?.error?.message ?? error.message
  return error instanceof Error ? error.message : '未知错误'
}
