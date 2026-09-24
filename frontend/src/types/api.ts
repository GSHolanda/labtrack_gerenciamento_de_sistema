// Tipos do domínio, espelhando os contratos da API (backend/app/schemas).
// Valores analíticos trafegam como texto decimal ("7.2100") para não perder precisão.

export type Decimal = string
export type IsoDateTime = string
export type IsoDate = string

export type RoleCode = 'ADMIN' | 'ANALYST' | 'REVIEWER' | 'MANAGER'

export type Permission =
  | 'USER_MANAGE'
  | 'MASTER_DATA_MANAGE'
  | 'TEST_DEFINITION_MANAGE'
  | 'INSTRUMENT_MANAGE'
  | 'SAMPLE_READ'
  | 'SAMPLE_CREATE'
  | 'SAMPLE_ASSIGN_TESTS'
  | 'SAMPLE_ANALYZE'
  | 'RESULT_ENTER'
  | 'SAMPLE_REVIEW'
  | 'SAMPLE_CANCEL'
  | 'AUDIT_READ'
  | 'REPORT_EXPORT'
  | 'DASHBOARD_VIEW'

export type SampleStatus =
  | 'RECEIVED'
  | 'IN_ANALYSIS'
  | 'AWAITING_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'CANCELLED'
export type SamplePriority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT'
export type SampleOrigin =
  | 'PRODUCTION'
  | 'RAW_MATERIAL'
  | 'STABILITY'
  | 'CUSTOMER'
  | 'ENVIRONMENTAL'
export type SampleTestStatus = 'PENDING' | 'COMPLETED' | 'CANCELLED'
export type SpecStatus = 'IN_SPEC' | 'OOS'
export type ResultSource = 'MANUAL' | 'INSTRUMENT'
export type SampleAction =
  | 'start_analysis'
  | 'submit_for_review'
  | 'approve'
  | 'reject'
  | 'return_to_analysis'
  | 'cancel'

export type InstrumentType =
  | 'PH_METER'
  | 'HPLC'
  | 'BALANCE'
  | 'DENSITY_METER'
  | 'MOISTURE_ANALYZER'
  | 'VISCOMETER'
  | 'THERMOMETER'
  | 'CONDUCTIVITY_METER'
export type InstrumentStatus = 'ACTIVE' | 'MAINTENANCE' | 'INACTIVE'
export type InstrumentMessageStatus = 'ACCEPTED' | 'REJECTED'
export type ActorType = 'USER' | 'INSTRUMENT' | 'SYSTEM'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ErrorEnvelope {
  error: {
    code: string
    message: string
    details: unknown
    request_id: string | null
  }
}

// --- Autenticação e usuários ------------------------------------------------------

export interface CurrentUser {
  id: number
  username: string
  email: string
  full_name: string
  role: RoleCode
  permissions: Permission[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_at: IsoDateTime
  user: CurrentUser
}

export interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: RoleCode
  is_active: boolean
  last_login_at: IsoDateTime | null
  created_at: IsoDateTime
}

export interface UserCreate {
  username: string
  email: string
  full_name: string
  password: string
  role: RoleCode
}

export type UserUpdate = Partial<Omit<UserCreate, 'username'>> & { is_active?: boolean }

export interface Role {
  code: RoleCode
  name: string
  description: string | null
  permissions: Permission[]
}

// --- Cadastros ----------------------------------------------------------------------

export interface Client {
  id: number
  code: string
  name: string
  tax_id: string | null
  contact_email: string | null
  is_active: boolean
  created_at: IsoDateTime
}

export interface ClientInput {
  code?: string
  name?: string
  tax_id?: string | null
  contact_email?: string | null
  is_active?: boolean
}

export interface Product {
  id: number
  code: string
  name: string
  category: string | null
  description: string | null
  is_active: boolean
  created_at: IsoDateTime
}

export interface ProductInput {
  code?: string
  name?: string
  category?: string | null
  description?: string | null
  is_active?: boolean
}

export interface TestDefinition {
  id: number
  code: string
  name: string
  unit: string
  spec_min: Decimal | null
  spec_max: Decimal | null
  method: string
  instrument_type: InstrumentType | null
  decimal_places: number
  description: string | null
  is_active: boolean
}

export interface TestDefinitionInput {
  code?: string
  name?: string
  unit?: string
  spec_min?: Decimal | null
  spec_max?: Decimal | null
  method?: string
  instrument_type?: InstrumentType | null
  decimal_places?: number
  description?: string | null
  is_active?: boolean
}

export interface Specification {
  test_definition_id: number
  test_code: string
  test_name: string
  unit: string
  spec_min: Decimal | null
  spec_max: Decimal | null
  overrides_default: boolean
  product_spec_min: Decimal | null
  product_spec_max: Decimal | null
}

export interface SpecificationItem {
  test_definition_id: number
  spec_min: Decimal | null
  spec_max: Decimal | null
}

// --- Amostras e resultados -------------------------------------------------------------

export interface UserReference {
  id: number
  full_name: string
}

export interface Reference {
  id: number
  code: string
  name: string
}

export interface SampleSummary {
  id: number
  sample_code: string
  product: Reference
  client: Reference
  lot_number: string
  origin: SampleOrigin
  received_at: IsoDateTime
  priority: SamplePriority
  status: SampleStatus
  responsible: UserReference | null
  version: number
  created_at: IsoDateTime
  tests_total: number
  tests_completed: number
  has_oos: boolean
}

export interface ResultRead {
  id: number
  sample_test_id: number
  value: Decimal
  unit: string
  spec_status: SpecStatus
  source: ResultSource
  version: number
  is_current: boolean
  entered_by: UserReference | null
  instrument_code: string | null
  entered_at: IsoDateTime
  change_reason: string | null
  comment: string | null
}

export interface SampleTest {
  id: number
  test_definition_id: number
  test_code: string
  test_name: string
  method: string
  unit: string
  decimal_places: number
  spec_min: Decimal | null
  spec_max: Decimal | null
  status: SampleTestStatus
  assigned_at: IsoDateTime
  current_result: ResultRead | null
  result_versions: number
  had_oos: boolean
}

export interface SampleDetail extends SampleSummary {
  notes: string | null
  created_by: UserReference
  submitted_at: IsoDateTime | null
  reviewed_by: UserReference | null
  reviewed_at: IsoDateTime | null
  review_comment: string | null
  completed_at: IsoDateTime | null
  tests: SampleTest[]
  oos_tests: string[]
  allowed_actions: SampleAction[]
}

export interface SampleCreate {
  product_id: number
  client_id: number
  lot_number: string
  origin: SampleOrigin
  received_at: IsoDateTime
  priority: SamplePriority
  responsible_id: number | null
  notes: string | null
}

export interface SampleUpdate {
  version: number
  lot_number?: string
  origin?: SampleOrigin
  priority?: SamplePriority
  notes?: string | null
}

export interface ResultEntry {
  value: Decimal
  comment?: string | null
  change_reason?: string | null
}

export interface ResultListItem extends ResultRead {
  sample_id: number
  sample_code: string
  test_code: string
  test_name: string
  decimal_places: number
  spec_min: Decimal | null
  spec_max: Decimal | null
}

// --- Audit trail -----------------------------------------------------------------------

export interface AuditEvent {
  id: number
  occurred_at: IsoDateTime
  actor_type: ActorType
  actor_name: string
  user_id: number | null
  instrument_id: number | null
  action: string
  entity_type: string
  entity_id: string
  entity_label: string | null
  sample_id: number | null
  old_value: unknown
  new_value: unknown
  reason: string | null
}

export interface AuditRecord extends AuditEvent {
  request_id: string | null
  ip_address: string | null
  previous_hash: string | null
  record_hash: string
}

export interface TimelineEvent extends AuditEvent {
  is_correction: boolean
  has_oos: boolean
}

export interface AuditVerification {
  valid: boolean
  checked_records: number
  first_invalid_id: number | null
  error_code: string | null
}

// --- Instrumentos ------------------------------------------------------------------------

export interface Instrument {
  id: number
  code: string
  name: string
  instrument_type: InstrumentType
  manufacturer: string | null
  model: string | null
  serial_number: string | null
  location: string | null
  status: InstrumentStatus
  calibration_due_date: IsoDate | null
  calibration_valid: boolean
  last_communication_at: IsoDateTime | null
  online: boolean
  created_at: IsoDateTime
}

export interface InstrumentWithKey extends Instrument {
  api_key: string
}

export interface InstrumentInput {
  code?: string
  name?: string
  instrument_type?: InstrumentType
  manufacturer?: string | null
  model?: string | null
  serial_number?: string | null
  location?: string | null
  status?: InstrumentStatus
  calibration_due_date?: IsoDate
}

export interface InstrumentMessage {
  id: number
  received_at: IsoDateTime
  status: InstrumentMessageStatus
  sample_code: string | null
  test_code: string | null
  value: Decimal | null
  unit: string | null
  error_code: string | null
  error_message: string | null
  test_result_id: number | null
  payload: unknown
}
