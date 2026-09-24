import type {
  Client,
  ClientInput,
  Page,
  Product,
  ProductInput,
  Specification,
  SpecificationItem,
  TestDefinition,
  TestDefinitionInput,
} from '../types/api'
import { http } from './client'

export interface MasterDataFilters {
  q?: string
  is_active?: boolean
  page?: number
  size?: number
  sort?: string
}

export const clientsApi = {
  search: (filters: MasterDataFilters) => http.get<Page<Client>>('/clients', { ...filters }),
  create: (data: ClientInput) => http.post<Client>('/clients', data),
  update: (id: number, data: ClientInput) => http.patch<Client>(`/clients/${id}`, data),
}

export const productsApi = {
  search: (filters: MasterDataFilters) => http.get<Page<Product>>('/products', { ...filters }),
  create: (data: ProductInput) => http.post<Product>('/products', data),
  update: (id: number, data: ProductInput) => http.patch<Product>(`/products/${id}`, data),
  specifications: (id: number) => http.get<Specification[]>(`/products/${id}/specifications`),
  replaceSpecifications: (id: number, items: SpecificationItem[]) =>
    http.put<Specification[]>(`/products/${id}/specifications`, items),
}

export const testDefinitionsApi = {
  search: (filters: MasterDataFilters) =>
    http.get<Page<TestDefinition>>('/test-definitions', { ...filters }),
  create: (data: TestDefinitionInput) => http.post<TestDefinition>('/test-definitions', data),
  update: (id: number, data: TestDefinitionInput) =>
    http.patch<TestDefinition>(`/test-definitions/${id}`, data),
}
