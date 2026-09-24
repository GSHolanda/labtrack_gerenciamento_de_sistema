// Rótulos exibidos na interface para os códigos da API (docs/sample-lifecycle.md).

import type {
  ActorType,
  InstrumentMessageStatus,
  InstrumentStatus,
  InstrumentType,
  RoleCode,
  SampleAction,
  SampleOrigin,
  SamplePriority,
  SampleStatus,
  SampleTestStatus,
  SpecStatus,
} from '../types/api'

export type Tone = 'neutral' | 'info' | 'progress' | 'warning' | 'success' | 'danger' | 'muted'

export const SAMPLE_STATUS: Record<SampleStatus, { label: string; tone: Tone }> = {
  RECEIVED: { label: 'Recebida', tone: 'info' },
  IN_ANALYSIS: { label: 'Em análise', tone: 'progress' },
  AWAITING_REVIEW: { label: 'Aguardando revisão', tone: 'warning' },
  APPROVED: { label: 'Aprovada', tone: 'success' },
  REJECTED: { label: 'Reprovada', tone: 'danger' },
  CANCELLED: { label: 'Cancelada', tone: 'muted' },
}

export const SAMPLE_STATUSES = Object.keys(SAMPLE_STATUS) as SampleStatus[]

export const PRIORITY: Record<SamplePriority, { label: string; tone: Tone }> = {
  URGENT: { label: 'Urgente', tone: 'danger' },
  HIGH: { label: 'Alta', tone: 'warning' },
  NORMAL: { label: 'Normal', tone: 'neutral' },
  LOW: { label: 'Baixa', tone: 'muted' },
}

export const PRIORITIES = Object.keys(PRIORITY) as SamplePriority[]

export const ORIGIN: Record<SampleOrigin, string> = {
  PRODUCTION: 'Produção',
  RAW_MATERIAL: 'Matéria-prima',
  STABILITY: 'Estabilidade',
  CUSTOMER: 'Cliente',
  ENVIRONMENTAL: 'Monitoramento ambiental',
}

export const ORIGINS = Object.keys(ORIGIN) as SampleOrigin[]

export const TEST_STATUS: Record<SampleTestStatus, { label: string; tone: Tone }> = {
  PENDING: { label: 'Pendente', tone: 'info' },
  COMPLETED: { label: 'Concluído', tone: 'success' },
  CANCELLED: { label: 'Cancelado', tone: 'muted' },
}

export const SPEC_STATUS: Record<SpecStatus, { label: string; tone: Tone }> = {
  IN_SPEC: { label: 'Dentro da especificação', tone: 'success' },
  OOS: { label: 'Fora da especificação', tone: 'danger' },
}

export const SAMPLE_ACTION: Record<SampleAction, string> = {
  start_analysis: 'Iniciar análise',
  submit_for_review: 'Enviar para revisão',
  approve: 'Aprovar',
  reject: 'Reprovar',
  return_to_analysis: 'Devolver para análise',
  cancel: 'Cancelar amostra',
}

export const INSTRUMENT_TYPE: Record<InstrumentType, string> = {
  PH_METER: 'pHmetro',
  HPLC: 'Cromatógrafo (HPLC)',
  BALANCE: 'Balança',
  DENSITY_METER: 'Densímetro',
  MOISTURE_ANALYZER: 'Analisador de umidade',
  VISCOMETER: 'Viscosímetro',
  THERMOMETER: 'Termômetro',
  CONDUCTIVITY_METER: 'Condutivímetro',
}

export const INSTRUMENT_TYPES = Object.keys(INSTRUMENT_TYPE) as InstrumentType[]

export const INSTRUMENT_STATUS: Record<InstrumentStatus, { label: string; tone: Tone }> = {
  ACTIVE: { label: 'Ativo', tone: 'success' },
  MAINTENANCE: { label: 'Em manutenção', tone: 'warning' },
  INACTIVE: { label: 'Inativo', tone: 'muted' },
}

export const INSTRUMENT_STATUSES = Object.keys(INSTRUMENT_STATUS) as InstrumentStatus[]

export const MESSAGE_STATUS: Record<InstrumentMessageStatus, { label: string; tone: Tone }> = {
  ACCEPTED: { label: 'Aceita', tone: 'success' },
  REJECTED: { label: 'Recusada', tone: 'danger' },
}

export const ROLE: Record<RoleCode, string> = {
  ADMIN: 'Administrador',
  ANALYST: 'Analista',
  REVIEWER: 'Revisor',
  MANAGER: 'Gestor',
}

export const ROLES = Object.keys(ROLE) as RoleCode[]

export const ACTOR_TYPE: Record<ActorType, string> = {
  USER: 'Usuário',
  INSTRUMENT: 'Equipamento',
  SYSTEM: 'Sistema',
}

export const AUDIT_ACTION: Record<string, string> = {
  LOGIN_SUCCEEDED: 'Login realizado',
  LOGIN_FAILED: 'Falha de login',
  USER_CREATED: 'Usuário criado',
  USER_UPDATED: 'Usuário alterado',
  CLIENT_CREATED: 'Cliente criado',
  CLIENT_UPDATED: 'Cliente alterado',
  PRODUCT_CREATED: 'Produto criado',
  PRODUCT_UPDATED: 'Produto alterado',
  SPECIFICATION_UPDATED: 'Plano analítico alterado',
  TEST_DEFINITION_CREATED: 'Tipo de teste criado',
  TEST_DEFINITION_UPDATED: 'Tipo de teste alterado',
  INSTRUMENT_CREATED: 'Equipamento cadastrado',
  INSTRUMENT_UPDATED: 'Equipamento alterado',
  INSTRUMENT_KEY_ROTATED: 'Chave de integração rotacionada',
  SAMPLE_CREATED: 'Amostra registrada',
  SAMPLE_UPDATED: 'Dados da amostra alterados',
  SAMPLE_STATUS_CHANGED: 'Status alterado',
  TESTS_ASSIGNED: 'Testes atribuídos',
  TEST_CANCELLED: 'Teste cancelado',
  RESULT_ENTERED: 'Resultado registrado',
  RESULT_AMENDED: 'Resultado corrigido',
  INSTRUMENT_MESSAGE_REJECTED: 'Mensagem de equipamento recusada',
  REPORT_GENERATED: 'Relatório gerado',
}

export const AUDIT_ACTIONS = Object.keys(AUDIT_ACTION)

export function auditActionLabel(action: string): string {
  return AUDIT_ACTION[action] ?? action
}

export function sampleStatusLabel(status: string): string {
  return SAMPLE_STATUS[status as SampleStatus]?.label ?? status
}
