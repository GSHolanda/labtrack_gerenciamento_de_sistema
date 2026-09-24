# Testes

O LabTrack é testado em camadas. Cada etapa entregou os testes do que
implementou; a ETAPA 12 consolidou a suíte: fluxo ponta a ponta, cenários
negativos de todas as regras de negócio, execução completa no PostgreSQL,
rastreabilidade regra → teste, cobertura mínima e integração contínua.

## O que cada camada verifica

| Camada | Onde | O que garante |
| ------ | ---- | ------------- |
| Domínio | `backend/tests/unit/` | Regras puras sem banco nem HTTP: máquina de estados, avaliação OOS com `Decimal`, permissões, calibração, hash do audit trail, janelas do dashboard, impressão digital do relatório. Inclui o **teste de arquitetura** (regra de dependência entre camadas) e o de **rastreabilidade**. |
| API | `backend/tests/api/` | O contrato HTTP como o cliente usa: autenticação e perfis, status e códigos de erro, efeitos no banco e no audit trail. Um laboratório de teste é montado pela própria API (`tests/api/conftest.py`). |
| Ponta a ponta | `backend/tests/api/test_end_to_end.py` | Um único cenário do cadastro do equipamento ao relatório: worklist, resultado do instrumento fora da especificação, aprovação barrada, devolução, correção justificada, assinatura com senha, amostra bloqueada, relatório, timeline completa (ordem e ator de cada evento), cadeia de hashes íntegra e dashboard. |
| Banco | `backend/tests/db/` | Constraints (atribuição do resultado, versão vigente única, revisor em amostra final) e, no PostgreSQL: trigger *append-only* do audit trail, migrações iguais aos modelos e concorrência (numeração da amostra e resultados simultâneos de instrumentos). |
| Simulador | `instrument-simulator/tests/` | Protocolo do simulador e, com o backend instalado, execução contra a API real em processo. |
| Interface | `frontend/src/**/*.test.tsx` | A aplicação real (rotas, autenticação, providers) com o `fetch` simulado: permissões por perfil em cada tela, formulários e erros da API, decimais sem arredondar, fuso, filtros na URL, gráficos com tabela equivalente, emissão do PDF. |

## Como rodar

```bash
cd backend
pytest                                   # SQLite em memória (padrão, rápido)
pytest --cov                             # com cobertura (mínimo de 95%, com ramos)
export LABTRACK_TEST_DATABASE_URL=postgresql+psycopg://labtrack:labtrack@localhost:5432/labtrack_test
pytest                                   # + testes exclusivos do PostgreSQL (tests/db)
pytest --postgres                        # suíte inteira no PostgreSQL
python -m tests.traceability --write     # atualiza a matriz abaixo

cd ../instrument-simulator && pytest     # com o backend instalado no mesmo ambiente
cd ../frontend && npm test               # ou npm run test:coverage
```

Com `--postgres`, cada teste de API recebe um schema recriado pelas migrações
(`DROP SCHEMA` + `alembic upgrade head`): trigger do audit trail e perfis da
migração 0002 incluídos, como numa instalação nova. Foi assim que apareceu a
única diferença entre os bancos: os testes que simulam adulteração do audit
trail com `UPDATE` eram barrados pelo trigger. Agora eles confirmam o bloqueio
e depois desligam o trigger (o dono da tabela pode), mostrando que a cadeia de
hashes ainda detecta a alteração: são duas defesas independentes.

## Números da ETAPA 12

| Parte | Testes | Cobertura |
| ----- | ------ | --------- |
| Backend (SQLite) | 467 (+6 exclusivos do PostgreSQL) | 96,9% com ramos (mínimo 95%) |
| Backend no PostgreSQL 16 | 473, suíte inteira | — |
| Simulador | 41 (4 contra a API real) | — |
| Frontend | 94 (Vitest) | 79% das linhas (mínimos: 75% linhas e instruções, 65% funções e ramos) |

A cobertura do frontend era de 51% antes desta etapa: audit trail, resultados,
catálogo de testes, equipamentos, administração e as ações com justificativa
não tinham teste.

## Integração contínua

`.github/workflows/ci.yml` roda a cada push e pull request, com quatro jobs em
paralelo:

| Job | Etapas |
| --- | ------ |
| Backend | Ruff (lint e formatação) e pytest com cobertura mínima |
| Backend no PostgreSQL 16 | Serviço `postgres:16` e `pytest --postgres` (inclui trigger, migrações e concorrência) |
| Simulador | Ruff e pytest, com o backend instalado para os testes ponta a ponta |
| Frontend | `npm ci`, `tsc`, oxlint, Vitest com cobertura mínima e `vite build` |

## Rastreabilidade das regras de negócio

As regras RN-01 a RN-28 estão em [`sample-lifecycle.md`](sample-lifecycle.md).
Cada teste declara as regras que verifica com `@pytest.mark.rules("RN-12")`.
O teste `tests/unit/test_traceability.py` falha se uma regra documentada ficar
sem teste, se um teste citar uma regra que não existe ou se a matriz abaixo
estiver desatualizada (ela é gerada por `python -m tests.traceability --write`).

<!-- rule-matrix:start -->
| Regra | Testes |
| ----- | ------ |
| RN-01 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_samples.py`: `test_register_generates_sequential_code_per_year`, `test_code_sequence_restarts_each_year`<br>`db/test_constraints.py`: `test_sample_code_is_unique`<br>`db/test_postgres.py`: `test_concurrent_registrations_get_distinct_sequential_codes`<br>`unit/test_specification.py`: `test_sample_code_format_and_parse` |
| RN-02 | `api/test_samples.py`: `test_registration_rules`, `test_inactive_product_cannot_receive_samples`, `test_inactive_client_cannot_send_samples` |
| RN-03 | `api/test_samples.py`: `test_registration_rules`, `test_received_at_tolerates_small_clock_skew_only` |
| RN-04 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_master_data.py`: `test_inactive_test_cannot_enter_a_plan`<br>`api/test_samples.py`: `test_product_plan_is_assigned_with_limit_snapshot` |
| RN-05 | `api/test_samples.py`: `test_assign_additional_test`, `test_same_test_cannot_be_assigned_twice`, `test_sample_is_locked_while_awaiting_review`, `test_only_existing_active_tests_can_be_assigned`<br>`unit/test_workflow.py`: `test_sample_is_locked_outside_editable_statuses` |
| RN-06 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_results.py`: `test_result_uses_product_limits_and_is_audited`<br>`api/test_samples.py`: `test_product_plan_is_assigned_with_limit_snapshot`, `test_later_limit_change_does_not_affect_existing_sample`<br>`unit/test_specification.py`: `test_default_limits_apply_without_override`, `test_product_override_replaces_both_limits`, `test_product_can_override_a_single_side` |
| RN-07 | `api/test_samples.py`: `test_cancel_pending_test_requires_reason`, `test_completed_test_cannot_be_cancelled` |
| RN-08 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_samples.py`: `test_analysis_requires_assigned_tests`<br>`unit/test_workflow.py`: `test_forbidden_shortcuts` |
| RN-09 | `api/test_results.py`: `test_received_sample_does_not_accept_results`, `test_cancelled_test_does_not_accept_results` |
| RN-10 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_samples.py`: `test_full_flow_until_review_with_history` |
| RN-11 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_results.py`: `test_results_are_locked_after_submission`<br>`api/test_samples.py`: `test_sample_is_locked_while_awaiting_review` |
| RN-12 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_results.py`: `test_approval_records_reviewer_timestamps_history_and_audit`, `test_failed_approval_does_not_change_sample_or_audit`, `test_result_author_cannot_review_after_role_change`<br>`db/test_constraints.py`: `test_final_sample_requires_reviewer`<br>`unit/test_workflow.py`: `test_forbidden_shortcuts` |
| RN-13 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_results.py`: `test_review_actions_require_reason`, `test_rejection_records_reason_and_reviewer`, `test_return_to_analysis_allows_correction_and_resubmission`<br>`api/test_samples.py`: `test_cancellation_is_managerial_and_requires_reason`<br>`unit/test_workflow.py`: `test_reason_required_for_negative_actions` |
| RN-14 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_samples.py`: `test_final_sample_accepts_no_change`<br>`unit/test_workflow.py`: `test_final_statuses_allow_no_action`, `test_sample_is_locked_outside_editable_statuses` |
| RN-15 | `api/test_audit.py`: `test_verify_complete_chain_after_full_workflow_is_read_only`, `test_timeline_retains_oos_correction_and_workflow`<br>`api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_results.py`: `test_approval_records_reviewer_timestamps_history_and_audit`<br>`api/test_samples.py`: `test_full_flow_until_review_with_history`, `test_invalid_transition_is_rejected`<br>`db/test_postgres.py`: `test_audit_logs_are_append_only`<br>`unit/test_workflow.py`: `test_documented_transitions`, `test_every_other_combination_is_rejected` |
| RN-16 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_results.py`: `test_result_uses_product_limits_and_is_audited`<br>`unit/test_specification.py`: `test_evaluate`, `test_evaluate_is_exact_where_float_would_fail` |
| RN-17 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_instruments.py`: `test_correction_of_instrument_result_is_manual_and_justified`<br>`api/test_results.py`: `test_amendment_requires_meaningful_reason`, `test_correction_preserves_oos_history_and_audits_both_values`, `test_return_to_analysis_allows_correction_and_resubmission`<br>`db/test_constraints.py`: `test_amended_result_requires_reason`, `test_only_one_current_result_per_test`, `test_result_version_history_is_kept` |
| RN-18 | `api/test_audit.py`: `test_timeline_retains_oos_correction_and_workflow`<br>`api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_reports.py`: `test_report_content_of_an_approved_sample`<br>`api/test_results.py`: `test_correction_preserves_oos_history_and_audits_both_values`, `test_search_oos_defaults_to_current_results_and_can_include_history`<br>`api/test_samples.py`: `test_search_reports_progress_and_current_oos` |
| RN-19 | `api/test_instruments.py`: `test_create_shows_key_once_and_stores_only_its_hash`, `test_rotation_invalidates_the_previous_key`, `test_integration_requires_a_valid_key`, `test_user_token_does_not_authenticate_an_instrument`, `test_heartbeat_body_is_optional_but_must_match_the_key`, `test_rejected_message_is_logged_and_audited_without_result` |
| RN-20 | `api/test_instruments.py`: `test_worklist_refused_when_instrument_cannot_measure`, `test_calibration_is_valid_until_the_due_date`, `test_rejected_message_is_logged_and_audited_without_result`<br>`unit/test_instruments_domain.py`: `test_calibration_is_valid_until_due_date_inclusive`, `test_missing_calibration_is_not_valid`, `test_only_active_and_calibrated_instruments_measure`, `test_expired_or_missing_calibration_blocks_measurement` |
| RN-21 | `api/test_instruments.py`: `test_worklist_lists_pending_compatible_tests_by_priority`, `test_rejected_message_is_logged_and_audited_without_result`<br>`unit/test_instruments_domain.py`: `test_instrument_type_must_match_the_test` |
| RN-22 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_instruments.py`: `test_worklist_lists_pending_compatible_tests_by_priority`, `test_duplicate_submission_never_overwrites_the_result`, `test_correction_of_instrument_result_is_manual_and_justified`, `test_rejected_message_is_logged_and_audited_without_result`<br>`db/test_postgres.py`: `test_concurrent_instrument_results_never_overwrite` |
| RN-23 | `api/test_instruments.py`: `test_rejected_message_is_logged_and_audited_without_result`<br>`unit/test_instruments_domain.py`: `test_unit_must_match_exactly` |
| RN-24 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_instruments.py`: `test_accepted_result_is_recorded_logged_and_audited`, `test_rejected_message_is_logged_and_audited_without_result`, `test_malformed_message_is_logged`, `test_rejection_appears_in_sample_timeline` |
| RN-25 | `api/test_auth.py`: `test_inactive_user_cannot_log_in`, `test_deactivation_revokes_existing_token_immediately`<br>`api/test_users.py`: `test_deactivated_user_cannot_log_in`, `test_admin_cannot_lock_themselves_out`, `test_users_cannot_be_deleted` |
| RN-26 | `api/test_auth.py`: `test_successful_login_is_audited`, `test_wrong_password_and_unknown_user_get_identical_response`, `test_failed_logins_are_audited_with_reason` |
| RN-27 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_reports.py`: `test_samples_not_yet_reviewed_have_no_report`<br>`unit/test_report_domain.py`: `test_reviewed_samples_are_reportable`, `test_other_statuses_have_no_report` |
| RN-28 | `api/test_end_to_end.py`: `test_sample_lifecycle_from_registration_to_report`<br>`api/test_reports.py`: `test_reading_the_report_is_not_audited_and_fingerprint_is_stable`, `test_pdf_emission_is_audited_with_the_fingerprint`, `test_every_emission_is_recorded_with_the_same_fingerprint`<br>`unit/test_report_domain.py`: `test_fingerprint_ignores_representation_but_not_content` |
<!-- rule-matrix:end -->
