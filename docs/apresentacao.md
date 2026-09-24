# Apresentação do LabTrack

Material para apresentar o projeto em entrevistas: um resumo de 30 segundos, um
roteiro de 5 minutos com demonstração, as decisões técnicas e as perguntas mais
prováveis, com respostas.

## Em 30 segundos

> O LabTrack é um Mini-LIMS: controla a amostra de laboratório do recebimento à
> aprovação. O foco é integridade de dados: workflow com máquina de estados,
> classificação automática fora da especificação, resultados que nunca são
> sobrescritos, audit trail com cadeia de hashes, aprovação com senha e
> segregação de funções, integração com equipamentos por API e relatório em PDF
> com impressão digital. Backend FastAPI em camadas, React no frontend,
> PostgreSQL, tudo em Docker, com as 28 regras de negócio ligadas a testes e CI.

## Roteiro de 5 minutos

Prepare antes: `docker compose up --build` e o navegador em http://localhost:8080.
As amostras citadas são as da demonstração; o simulador pode acrescentar
resultados às amostras em análise enquanto a stack roda.

| Tempo | Assunto | O que mostrar e dizer |
| ----- | ------- | --------------------- |
| 0:00 | Problema | Planilhas não respondem "quem mudou este resultado e por quê?" nem "alguém aprovou com resultado fora da especificação?". O LabTrack responde as duas. |
| 0:30 | Dashboard (`marcos.lima`) | Carga atual, amostras em aberto com OOS vigente (bloqueiam a aprovação), indicadores do período comparados ao anterior, gráficos com tabela equivalente. |
| 1:10 | Amostra aguardando revisão com OOS (`ana.souza`) | SMP-2026-0015: o botão **Aprovar** está bloqueado e explica o motivo (teor do ativo fora da especificação). A revisora só pode reprovar ou devolver, sempre com justificativa. |
| 1:40 | Aprovação com assinatura | SMP-2026-0016: aprovar pede a senha; senha errada não registra nada. A aprovação só é possível porque a revisora não lançou resultados da amostra (quatro olhos). |
| 2:10 | Correção rastreável (SMP-2026-0005) | O teor veio do HPLC como OOS e foi corrigido com justificativa. A tela mostra "Houve OOS"; a Sample Timeline mostra o valor original, o novo e o motivo. |
| 2:50 | Audit trail | Filtrar pela amostra; **Verificar integridade** percorre a cadeia de hashes. Contar que o banco bloqueia UPDATE e DELETE por trigger e que um teste prova que, mesmo burlando o trigger, a cadeia detecta a adulteração. |
| 3:20 | Relatório | Prévia e **Emitir PDF**: o rodapé traz a impressão digital SHA-256, a mesma registrada no audit trail a cada emissão. |
| 3:50 | Equipamentos | Status, calibração e comunicação ao vivo; o simulador é um processo separado que só usa a API, com chave própria por equipamento. Mostrar uma mensagem recusada (calibração vencida) com o payload original. |
| 4:20 | Engenharia | Camadas com regra de dependência testada; 28 regras de negócio, cada uma com teste marcado (a suíte falha se alguma ficar sem teste); suíte inteira também no PostgreSQL; CI com a stack Docker e smoke test. |
| 4:50 | Fechamento | O que faria em seguida: SSO, bloqueio por tentativas de login, notificações e relatórios por período. |

## Decisões técnicas

| Decisão | Alternativa considerada | Por quê |
| ------- | ----------------------- | ------- |
| Monólito modular em camadas | Microsserviços | Um caso de uso e o seu registro de auditoria precisam estar na mesma transação; a equipe (uma pessoa) e o domínio não pedem distribuição. As camadas deixam a divisão possível depois. |
| Camada `domain` pura | Regras dentro dos serviços | Workflow, OOS, permissões e calibração são testados sem banco nem HTTP, e ficam legíveis para quem conhece o negócio. |
| Audit trail gravado pelos serviços | Trigger que copia linhas | O serviço conhece a semântica (ação, justificativa, valor anterior e novo); o trigger só vê colunas. O banco entra como segunda defesa, bloqueando alterações. |
| Hash encadeado | Só permissões | Permissões impedem a aplicação de alterar; a cadeia detecta alteração feita por fora, inclusive por quem tem acesso ao banco. |
| Resultados versionados | UPDATE do valor | A correção vira nova versão com justificativa; o valor original, inclusive um OOS, nunca some. |
| `Decimal` do banco à tela | `float` | `7.2150` com duas casas continua `7,215`; nenhum dígito registrado é arredondado. O frontend compara com `BigInt` na prévia OOS. |
| Limites copiados na atribuição | Consultar o limite atual | Mudar a especificação amanhã não pode mudar o veredito de uma amostra de ontem. |
| Chave por instrumento guardada como hash | Token de usuário de serviço | Cada equipamento é identificável no audit trail, a chave pode ser revogada sozinha e o vazamento do banco não expõe chaves. |
| Numeração com advisory lock | Sequência do banco por ano | O código `SMP-AAAA-NNNN` reinicia por ano sem lacunas nem colisões; um teste com seis registros simultâneos no PostgreSQL prova isso. |
| Relatório com impressão digital | PDF simples | Quem recebe o documento pode conferir no audit trail que ele corresponde ao que está no sistema. |
| Rastreabilidade por marcador de teste | Planilha de requisitos | A matriz regra → teste é gerada da própria suíte e conferida por ela; não desatualiza. |

## Perguntas prováveis

**Por que FastAPI e não Django?**
O projeto é uma API com contrato forte (Pydantic gera validação e OpenAPI) e um
frontend separado. Django traria ORM, admin e templates que não seriam usados;
com FastAPI + SQLAlchemy a arquitetura em camadas fica explícita e testável.

**Como você garante que ninguém altera um resultado sem deixar rastro?**
Três camadas: a aplicação não tem rota de alteração do audit trail e toda
correção cria nova versão com justificativa; o PostgreSQL bloqueia UPDATE,
DELETE e TRUNCATE na tabela de auditoria por trigger; e cada registro guarda o
hash do anterior, então qualquer alteração por fora quebra a cadeia, o que a
tela de audit trail verifica.

**E se duas pessoas registrarem amostras ao mesmo tempo?**
O sequencial do ano é calculado sob um advisory lock do PostgreSQL, que
serializa só essa parte. Para edições concorrentes da mesma amostra há
*optimistic locking* (coluna `version`), e resultados simultâneos de
instrumentos são barrados por um índice único parcial (uma versão vigente por
teste). Os três casos têm testes no PostgreSQL real.

**Como funciona a "assinatura eletrônica"?**
É um conceito simplificado: a aprovação exige a senha do revisor no ato, o
revisor não pode ter lançado resultados da amostra e não pode haver resultado
vigente fora da especificação. O projeto não alega conformidade com nenhuma
norma; demonstra os princípios.

**Por que o simulador é um processo separado?**
Porque um equipamento real também é. Ele só conhece a API REST, autentica com a
própria chave e recebe as mesmas recusas de um instrumento real (calibração
vencida, unidade errada, amostra fora de análise). Trocar o simulador por um
driver de verdade não muda nada no backend.

**Como você testou?**
Pirâmide: domínio puro, contrato HTTP com um laboratório montado pela própria
API, constraints e concorrência no banco, um fluxo ponta a ponta, e a interface
com a aplicação real e `fetch` simulado. A suíte de API roda em SQLite (rápida)
e inteira no PostgreSQL no CI. As 28 regras têm testes marcados e a suíte falha
se alguma ficar sem teste. Cobertura: 96,9% no backend (com ramos) e 79% no
frontend.

**O que o PostgreSQL revelou que o SQLite escondia?**
Os testes que simulavam adulteração do audit trail com UPDATE passavam no
SQLite e eram barrados pelo trigger no PostgreSQL. Não era defeito: era a
proteção funcionando. Os testes passaram a provar as duas defesas.

**Como o dashboard lida com fuso horário?**
Tudo é gravado em UTC; os intervalos do dashboard e as datas do relatório usam o
fuso do laboratório (configurável). Uma decisão às 23h30 de 30/09 em São Paulo
conta em setembro, embora já seja 01/10 em UTC, e há teste para isso.

**Como os gráficos ficaram acessíveis?**
Nenhum eixo duplo, legenda só com mais de uma série, tooltip também por
teclado, tabela equivalente para cada gráfico e cores conferidas com um
validador de paleta (verde contra vermelho foi reprovado para daltonismo; a
dupla azul e laranja passou). Variações usam seta e texto, não só cor.

**Como você colocaria em produção?**
As imagens já rodam sem root e com healthchecks; a API recusa a chave JWT de
desenvolvimento em produção. Faltaria TLS num proxy à frente, segredos num cofre,
backup do volume do banco, coleta dos logs JSON (já com `request_id`) e,
conforme a escala, réplicas da API (as migrações rodam num serviço separado,
então réplicas não competem por elas).

**Quais são as limitações conhecidas?**
Não há SSO nem bloqueio por tentativas de login (as tentativas são auditadas);
o PDF usa a fonte padrão dos leitores (símbolos fora do Latin-1 são trocados no
documento, não no dado); há um único laboratório por instalação; e a
"assinatura" é um conceito, não uma implementação validada para uso regulado.

**O que você faria diferente?**
Começaria a execução no PostgreSQL mais cedo no CI e padronizaria antes a
formatação do frontend. A rastreabilidade por marcador de teste também valeria
desde a primeira regra, e não consolidada no fim.

## Números do projeto

| | |
| --- | --- |
| Regras de negócio | 28, cada uma com teste |
| API | 55 operações REST documentadas no OpenAPI |
| Banco | 13 tabelas, 3 migrações, trigger de imutabilidade do audit trail |
| Testes | backend 469 (475 no PostgreSQL), simulador 41, frontend 94 |
| Cobertura | backend 96,9% com ramos, frontend 79% das linhas |
| Entrega | 14 etapas, CI com 5 jobs, stack completa em Docker |
