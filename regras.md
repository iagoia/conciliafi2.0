## Preamble

Estas regras **não podem** ser violadas dentro de seus respectivos tiers de aplicação.

### Precedência

Em caso de conflito entre regras:

**Segurança > Privacidade > Resiliência > Observabilidade > Build > SOLID > KISS/DRY**

Complexidade adicional é aceita e documentada quando mitiga riscos críticos. KISS não justifica omitir Secrets Manager, observabilidade ou mecanismos de rollback.

### Proporcionalidade

| Tier | Classe | Regras obrigatórias |
|------|--------|---------------------|
| 1 | Produção | Todas as 20 regras |
| 2 | MVP / pré-produção | 1–10, 17–18 + roadmap mínimo + CI básico |
| 3 | Protótipo / spike | 1–3, 6 (sem mocks em prod), 8 (secrets básicos) |
| 4 | Script pontual | 1, 2, 8 (sem hardcoded secrets) |

---

## Bloco I — Fundamentos de Engenharia

### 1. DRY — Don't Repeat Yourself

- Deve existir uma **única fonte de verdade**
- É proibida duplicação de lógica, regras de negócio ou configurações
- Constantes e configurações devem ser centralizadas

### 2. KISS — Keep It Simple

- Priorizar soluções **simples, diretas e legíveis**
- Evitar abstrações, camadas ou padrões sem necessidade real
- Over-engineering é considerado erro
- KISS não anula regras de maior precedência — ver preamble

### 3. SOLID

Aplicar SOLID com foco em **manutenibilidade**, não complexidade.

- **SRP**: uma responsabilidade por módulo/classe
- **OCP**: extensão sem modificar código existente sempre que possível
- **LSP**: substituições não exigem lógica defensiva
- **ISP**: evitar interfaces grandes ou genéricas
- **DIP**: depender de abstrações, não de implementações concretas

### 4. Arquitetura

- Definir arquitetura antes de iniciar a implementação
- Documentar: componentes, integrações, responsabilidades e fluxos de dados
- Monólito é permitido; microserviços exigem justificativa objetiva documentada
- Decisões arquiteturais registradas em ADR (Architecture Decision Record) ou equivalente
- APIs têm contratos documentados: OpenAPI, GraphQL schema, gRPC proto, etc.
- Versionamento semântico de APIs; breaking changes exigem novo major version
- Backward compatibility mantida por N versões antes de deprecar — N definido por projeto

---

## Bloco II — Integridade & Qualidade

### 5. Validação de Build

- Sempre validar a build ao final das alterações
- A build **não pode** conter erros ou warnings críticos
- Validar em Debug e Release

### 6. Dados em Produção

- É proibido usar dados fictícios, mocks ou sintéticos em produção
- Estratégia de ambientes **explicitamente definida** e documentada:
  - **dev**: dados sintéticos e mocks são permitidos
  - **staging**: dados de produção anonimizados; staging espelha prod em configuração
  - **prod**: dados reais exclusivamente
- Diferenças entre staging e prod são documentadas e justificadas

### 7. Dependências

- Minimizar dependências externas — cada dependência é um risco
- Antes de adicionar: avaliar manutenção ativa, atividade do projeto, licença e risco de abandono
- Dependabot, Renovate ou equivalente configurado para monitoramento contínuo de vulnerabilidades
- Remover dependências obsoletas periodicamente

---

## Bloco III — Segurança & Privacidade

### 8. Segurança

- Segurança é **requisito funcional**, não adicional
- **Obrigatório**: secrets manager, TLS, análise de vulnerabilidades (OWASP, CVEs), princípio do menor privilégio
- **Proibido**: credenciais hardcoded, tokens em logs, dados sensíveis em repositórios
- Toda dependência nova passa por avaliação de segurança
- **Human-in-the-loop obrigatório**: IA e agentes são estritamente proibidos de executar comandos destrutivos (`DROP`, `DELETE` em massa, `rm -rf`, truncate) ou realizar deploys em produção sem aprovação humana explícita

### 9. Privacidade & Compliance

- Segurança ≠ Privacidade — ambas são obrigatórias e independentes
- **PII não aparece em logs** — anonimizar ou omitir antes de registrar
- Conformidade com **LGPD** (Brasil) e regulações aplicáveis ao mercado do produto
- Política de retenção de dados definida, documentada e auditável
- Consentimento documentado onde aplicável pela legislação
- Distinção explícita entre: dados pessoais / dados sensíveis / dados anonimizados / dados agregados

---

## Bloco IV — Testes & Verificação

### 10. Estratégia de Testes

- Testes **não podem** estar embutidos no código de produção
- Testes devem residir em projetos/módulos separados
- Testes não devem impactar fluxo, performance ou UX
- Camadas obrigatórias: **unit → integration → E2E**
  - **Unit**: mocks e stubs são obrigatórios para isolamento e velocidade — sem infraestrutura real
  - **Integration / E2E**: verificação live, endpoints reais em execução, sem mocks de infraestrutura, estado real de banco de dados
- Automatizar fluxo de teste via harness/agents sempre que possível
- Cobertura é **métrica**, não objetivo — priorizar testes de alto valor

### 11. Continual Harness

- Testes são **contínuos**: não apenas no commit
- Hooks obrigatórios: pre-commit, pre-push e post-deploy
- Harness verifica: build + testes + health de endpoints + checks de produção
- **Nenhum deploy sem harness verde**
- Execuções periódicas agendadas para monitoramento de produção em tempo real

---

## Bloco V — Observabilidade

### 12. Observabilidade

- Todo projeto em produção deve possuir: logs estruturados, métricas, health checks e alertas para falhas críticas
- **SLOs definidos** para: disponibilidade, latência (p50 / p95 / p99) e taxa de erros — alertas baseados em SLOs, não thresholds arbitrários
- Monitorar obrigatoriamente: disponibilidade, erros, latência, consumo de recursos e custo de infra (FinOps básico)
- Falhas críticas geram **notificação automática**
- Deploy sem observabilidade configurada **não é considerado completo**

---

## Bloco VI — Processo & Automação

### 13. Code Review & Pull Requests

- Todo código — humano ou gerado por IA — **passa por revisão antes do merge**
- PRs são atômicos: uma responsabilidade, um objetivo
- IA gera código; humano aprova o merge — agente não faz merge direto sem revisão humana
- Estratégia de branch documentada (trunk-based, gitflow, etc.) e consistente no projeto

### 14. CI/CD

- Todo projeto tem **pipeline desde o dia zero**
- Etapas mínimas: lint → build → test → deploy
- Deploys são automatizados — **proibido deploy manual via copy-paste**
- Falha no pipeline bloqueia deploy sem exceção

### 15. Deploy & Integrações

- Infrastructure-as-code sobre configuração manual sempre que possível
- Credenciais e segredos via variáveis de ambiente ou secrets manager — **nunca hardcoded**
- Automatizar tudo que pode ser automatizado; deprecar tooling legado proativamente
- Integração com serviços externos documentada e versionada

### 16. Resiliência

- Todo deploy deve ter: rollback documentado, backup validado e recuperação testada
- **Migrations de banco têm rollback documentado e testado antes de aplicar em produção** — rollback de código sem rollback de schema é falsa segurança
- Deploy só é considerado seguro quando o rollback também funciona
- Testar processo de recovery periodicamente — não apenas no incidente
- Falhas em produção têm **runbook de resposta** documentado

---

## Bloco VII — Planejamento & Rastreamento

### 17. Roadmap

- Todo projeto tem roadmap **antes** da implementação começar
- Define: objetivos, milestones, prioridades e dependências
- Roadmap é um **documento vivo** — atualizar conforme requisitos evoluem
- Nenhuma feature começa sem estar posicionada no contexto do roadmap

### 18. Changelog

- O CHANGELOG deve ser **atualizado a cada alteração**
- Seguir semver; breaking changes explicitamente sinalizados
- Incluir: status da build, resultados dos testes, cobertura quando aplicável
- Vincular a milestones do roadmap quando aplicável
- O próprio documento de Regras Absolutas segue este processo

---

## Bloco VIII — Desenvolvimento AI-Native

### 19. Skillset

- Antes de criar novo agente ou automação: **buscar skills existentes**
- Criar skills reutilizáveis para tarefas recorrentes: deploy, review, test, format, generate-rules, etc.
- Skills são **artefatos de código de primeira classe** — sujeitos a DRY, KISS e SOLID
- Preferir compor skills existentes a construir agentes monolíticos
- Skills documentadas e compartilháveis entre projetos e contextos de LLM

### 20. Escolha Tecnológica

- Favorecer a tecnologia que **maximize valor de longo prazo** — não pela novidade
- Avaliar por critérios mensuráveis: manutenção ativa, adoção de mercado, estabilidade, documentação, ecossistema, produtividade e integração com IA
- A tecnologia escolhida deve superar alternativas nesses critérios
- Não restringir por familiaridade; não adotar apenas por ser recente
- Migrar proativamente de tech que não passa nos critérios acima
- Exemplos de escolhas corretas independente de "idade": PostgreSQL, Linux, Git