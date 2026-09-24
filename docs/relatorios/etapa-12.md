# Relatório da ETAPA 12: Testes

**Status:** concluída · **Branch:** `claude/festive-bell-x898pg`

## Resumo

A suíte de testes foi consolidada em torno das 28 regras de negócio. Cada regra
tem teste declarado e verificado automaticamente, um cenário ponta a ponta
atravessa o sistema inteiro, a suíte de API roda também no PostgreSQL, há
cobertura mínima no backend e no frontend, e um pipeline de CI no GitHub
Actions executa tudo a cada push.

## Entregas

| Item | Resultado |
| ---- | --------- |
| Rastreabilidade regra → teste | `@pytest.mark.rules("RN-xx")` em 90 testes; matriz gerada em [`docs/testing.md`](../testing.md); `test_traceability.py` falha se uma regra ficar sem teste ou a matriz desatualizar |
| Fluxo ponta a ponta | `tests/api/test_end_to_end.py`: equipamento → registro → worklist → OOS do instrumento → aprovação barrada → devolução → correção → assinatura → relatório → timeline completa → cadeia íntegra → dashboard |
| Cenários negativos novos | cliente inativo (RN-02), tolerância de relógio (RN-03), teste inativo ou inexistente (RN-05), teste concluído (RN-07), amostra finalizada imutável em 7 operações × 3 status finais (RN-14), numeração concorrente no PostgreSQL (RN-01) |
| Suíte no PostgreSQL | `pytest --postgres`: schema recriado pelas migrações a cada teste |
| Cobertura | backend 96,9% com ramos (piso 95%); frontend de 51% para 79% das linhas (piso 75%) |
| Frontend | 20 testes novos: audit trail, resultados, catálogo de testes, equipamentos, administração, reprovação e cancelamento com justificativa |
| CI | `.github/workflows/ci.yml`: backend, backend no PostgreSQL 16, simulador e frontend em paralelo |

## Números

| Parte | Antes | Depois |
| ----- | ----- | ------ |
| Backend (SQLite) | 455 | 467 (+6 só no PostgreSQL) |
| Backend no PostgreSQL | 5 testes específicos | 473 (suíte inteira) |
| Frontend (Vitest) | 74 | 94 |
| Simulador | 41 | 41 |

## O que a etapa revelou

Rodar a suíte inteira no PostgreSQL mostrou uma única diferença: os testes que
simulavam adulteração do audit trail com `UPDATE` eram barrados pelo trigger
*append-only* do banco (a proteção funcionando). Os testes agora confirmam o
bloqueio e, em seguida, desligam o trigger como faria alguém com acesso de dono
da tabela, provando que a verificação da cadeia de hashes ainda detecta a
alteração. São duas defesas independentes, ambas testadas.

Nenhum defeito de produto apareceu: os cenários negativos novos passaram na
primeira execução, o que confirma que as regras já estavam implementadas; o que
faltava era a prova explícita e rastreável.

## Decisões

- A rastreabilidade fica no próprio código de teste (marcador), não numa
  planilha: a matriz é gerada e conferida pela suíte, então não desatualiza.
- A suíte padrão continua em SQLite (rápida e sem infraestrutura); o
  PostgreSQL entra por opção local e sempre no CI.
- Os pisos de cobertura são um pouco abaixo do medido, para impedir regressão
  sem travar o trabalho.

## Validação

Todos os jobs do CI foram ensaiados localmente em ambiente limpo: virtualenv
novo para backend e simulador e `npm ci` para o frontend.

## Próxima etapa

ETAPA 13: Docker, com imagens *multi-stage* e `docker compose up` subindo banco,
migrações, dados de demonstração, API, frontend e simulador.
