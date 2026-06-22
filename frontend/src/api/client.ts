import axios, { AxiosError } from "axios"

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export const TOKEN_STORAGE_KEY = "access_token"

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const onLoginPage = window.location.pathname === "/login"
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      if (!onLoginPage) {
        window.location.assign("/login")
      }
    }
    return Promise.reject(error)
  }
)

interface ApiErrorBody {
  detail?: string | { msg?: string }[]
}

export function extractErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again."
): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiErrorBody | undefined
    const detail = data?.detail
    if (typeof detail === "string") {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (first && typeof first.msg === "string") {
        return first.msg
      }
    }
    if (error.message) {
      return error.message
    }
  }
  if (error instanceof Error) {
    return error.message
  }
  return fallback
}
