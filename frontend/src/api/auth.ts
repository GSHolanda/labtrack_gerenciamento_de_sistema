import type { CurrentUser, TokenResponse } from '../types/api'
import { http } from './client'

export const authApi = {
  login: (username: string, password: string) =>
    http.postForm<TokenResponse>('/auth/login', { username, password }),
  me: () => http.get<CurrentUser>('/auth/me'),
}
