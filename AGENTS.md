# AGENTS.md — Instruções Canônicas para Agentes

Este arquivo é a **fonte principal e canônica de instruções** para todos os agentes que atuam neste repositório (`conciliafi2.0`).

## Diretrizes Gerais do Projeto

1. **Leitura e Preservação Obrigatória de `regras.md`:**
   - Antes de planejar ou executar qualquer alteração, leia integralmente e siga o arquivo [`regras.md`](./regras.md) na raiz do repositório.
   - Preserve integralmente o conteúdo de `regras.md` e respeite sua hierarquia de precedência (**Segurança > Privacidade > Resiliência > Observabilidade > Build > SOLID > KISS/DRY**).
2. **Proteção de Dados Financeiros e Segredos:**
   - Nunca exponha, versione ou registre em logs/PRs credenciais, tokens, variáveis `.env` ou dados financeiros/PII contidos em planilhas (`.xlsx`, `.xls`, `.csv`, `.rar`, `.zip`).
   - Não execute comandos destrutivos sem aprovação humana explícita.
3. **Rastreabilidade e Qualidade:**
   - Atualize o [`CHANGELOG.md`](./CHANGELOG.md) proporcionalmente às mudanças realizadas, conforme a Regra 18 de `regras.md`.

<!-- shared-agent-pr-policy:v1 -->
## Política Compartilhada de Branches, Revisão e Pull Requests

- **Escopo de Aplicação:** Aplica-se a Hermes, Codex, OpenCode, Antigravity e demais agentes do projeto; preserve instruções existentes de segurança, permissões e custo.
- **Branch por Tarefa e Unicidade de PR:** Toda tarefa que altera arquivos deve usar uma branch específica da tarefa, nunca editar ou fazer push direto na branch padrão (`main`/`master`). Mantenha apenas **um PR por objetivo**; descubra e atualize o PR existente quando continuar o mesmo trabalho.
- **Revisão Pré-PR e Verificações Obrigatórias:** Antes de abrir **ou** atualizar um PR, revise o diff completo em relação à branch base atualizada (incluindo arquivos *staged*, *unstaged* e *untracked* quando relevante), procure regressões, mudanças fora do escopo e segredos; rode `git diff --check` e as verificações/testes relevantes do projeto; corrija os problemas encontrados e reporte bloqueios reais.
- **Segunda Revisão no Orca (Somente Leitura e Gratuita):** Se houver outro agente gratuito disponível no Orca, solicite segunda revisão do diff em modo somente leitura, sem escritores concorrentes; não use fallback pago; registre no PR o agente/modelo utilizado e o resultado da revisão, ou a indisponibilidade/motivo. Não invente revisões nem execuções de testes.
- **Conteúdo do PR e Merge Exclusivo Humano:** Todo PR deve conter resumo claro, comandos executados e resultados reais de testes/verificações, estado da segunda revisão e eventuais pendências. O merge é **exclusivo do usuário**; agentes nunca devem fazer merge nem ativar *auto-merge*.
- **Isolamento de Workspace e Preservação Local:** Preserve alterações locais preexistentes; use `worktree` isolado por repositório e clone separado para repositórios ainda não abertos no Orca.
<!-- /shared-agent-pr-policy:v1 -->
