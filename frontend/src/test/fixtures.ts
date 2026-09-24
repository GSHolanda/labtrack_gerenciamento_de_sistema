import type {
  CurrentUser,
  Permission,
  RoleCode,
  SampleDetail,
  SampleTest,
  TimelineEvent,
} from '../types/api'

// Espelho da matriz de permissões do backend (app/domain/permissions.py).
const PERMISSIONS: Record<RoleCode, Permission[]> = {
  ADMIN: [
    'USER_MANAGE',
    'MASTER_DATA_MANAGE',
    'TEST_DEFINITION_MANAGE',
    'INSTRUMENT_MANAGE',
    'SAMPLE_READ',
    'AUDIT_READ',
    'DASHBOARD_VIEW',
  ],
  ANALYST: [
    'SAMPLE_READ',
    'SAMPLE_CREATE',
    'SAMPLE_ASSIGN_TESTS',
    'SAMPLE_ANALYZE',
    'RESULT_ENTER',
    'REPORT_EXPORT',
    'DASHBOARD_VIEW',
  ],
  REVIEWER: ['SAMPLE_READ', 'SAMPLE_REVIEW', 'AUDIT_READ', 'REPORT_EXPORT', 'DASHBOARD_VIEW'],
  MANAGER: ['SAMPLE_READ', 'SAMPLE_CANCEL', 'AUDIT_READ', 'REPORT_EXPORT', 'DASHBOARD_VIEW'],
}

const NAMES: Record<RoleCode, [string, string]> = {
  ADMIN: ['admin', 'Administrador do Sistema'],
  ANALYST: ['carlos.silva', 'Carlos Silva'],
  REVIEWER: ['ana.souza', 'Ana Souza'],
  MANAGER: ['marcos.lima', 'Marcos Lima'],
}

export function userWith(role: RoleCode): CurrentUser {
  const [username, full_name] = NAMES[role]
  const ids: Record<RoleCode, number> = { ADMIN: 1, ANALYST: 2, REVIEWER: 3, MANAGER: 4 }
  return {
    id: ids[role],
    username,
    email: `${username}@labtrack.dev`,
    full_name,
    role,
    permissions: PERMISSIONS[role],
  }
}

export function sampleTest(overrides: Partial<SampleTest> = {}): SampleTest {
  return {
    id: 11,
    test_definition_id: 1,
    test_code: 'PH',
    test_name: 'pH',
    method: 'Potenciometria',
    unit: 'pH',
    decimal_places: 2,
    spec_min: '5.5000',
    spec_max: '7.0000',
    status: 'PENDING',
    assigned_at: '2026-09-20T11:20:00Z',
    current_result: null,
    result_versions: 0,
    had_oos: false,
    ...overrides,
  }
}

export function sampleDetail(overrides: Partial<SampleDetail> = {}): SampleDetail {
  return {
    id: 7,
    sample_code: 'SMP-2026-0007',
    product: { id: 1, code: 'PRD-SHAMPOO', name: 'Xampu Neutro 500 mL' },
    client: { id: 1, code: 'CLI-BELLA', name: 'Bella Pele Cosméticos' },
    lot_number: 'XN-2609-01',
    origin: 'PRODUCTION',
    received_at: '2026-09-20T11:00:00Z',
    priority: 'NORMAL',
    status: 'IN_ANALYSIS',
    responsible: { id: 2, full_name: 'Carlos Silva' },
    version: 2,
    created_at: '2026-09-20T11:20:00Z',
    tests_total: 1,
    tests_completed: 0,
    has_oos: false,
    notes: null,
    created_by: { id: 2, full_name: 'Carlos Silva' },
    submitted_at: null,
    reviewed_by: null,
    reviewed_at: null,
    review_comment: null,
    completed_at: null,
    tests: [sampleTest()],
    oos_tests: [],
    allowed_actions: ['submit_for_review', 'cancel'],
    ...overrides,
  }
}

export function timelineEvent(overrides: Partial<TimelineEvent> = {}): TimelineEvent {
  return {
    id: 1,
    occurred_at: '2026-09-20T12:30:00Z',
    actor_type: 'USER',
    actor_name: 'Carlos Silva',
    user_id: 2,
    instrument_id: null,
    action: 'RESULT_ENTERED',
    entity_type: 'test_result',
    entity_id: '31',
    entity_label: 'SMP-2026-0007 / PH',
    sample_id: 7,
    old_value: null,
    new_value: { value: '7.21', unit: 'pH', spec_status: 'IN_SPEC', source: 'MANUAL' },
    reason: null,
    is_correction: false,
    has_oos: false,
    ...overrides,
  }
}
