import type { Page, Role, RoleCode, User, UserCreate, UserUpdate } from '../types/api'
import { http } from './client'

export interface UserFilters {
  q?: string
  role?: RoleCode
  is_active?: boolean
  page?: number
  size?: number
  sort?: string
}

export const usersApi = {
  search: (filters: UserFilters) => http.get<Page<User>>('/users', { ...filters }),
  create: (data: UserCreate) => http.post<User>('/users', data),
  update: (id: number, data: UserUpdate) => http.patch<User>(`/users/${id}`, data),
  roles: () => http.get<Role[]>('/roles'),
}
