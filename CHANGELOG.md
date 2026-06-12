# Changelog - Conciliador Financeiro

Histórico de alterações e lançamentos do Conciliador Financeiro local. Segue as diretrizes de [regras.md](file:///C:/Users/supor/OneDrive/Imagens/Nova%20pasta/regras.md).

---

## [1.2.0] — 2026-06-12
### Adicionado
- **Filtro de Status Malsucedidos:** Agora o sistema lê a coluna de status (`status da venda` ou similar) e descarta automaticamente registros marcados com status falhos (ex: `negada`, `expirado`, `cancelado`). Isso impede que tentativas falhas inflem o faturamento bruto ou distorçam os custos de taxas.
- **Gráfico de Linha por Hora:** Se o período selecionado ou a planilha contiver apenas 1 único dia de transações, o gráfico de tendência diária de volume passa a agrupar e plotar o volume **hora a hora (das 00h às 23h)** em vez de exibir um gráfico em branco com um único ponto diário.
- **Tratamento de Hífen no Pix:** Modificação em `limparValorMonetario` para converter hífen (`-`) para `NaN` (não-número) ao invés de `0`. Isso permite que a dedução de valores herde o valor bruto para o valor líquido em transações Pix com status `pago`.

### Corrigido
- **Fuso Horário (Timezone Shift):** Correção crítica na conversão e normalização de datas. Trocados todos os métodos de leitura de data UTC (`getUTCHours()`, `getUTCFullYear()`, etc.) por métodos de timezone local. As datas e horas das transações agora coincidem exatamente com o visualizado nas planilhas originais.
- **Enquadramento de Período Padrão:** O período sugerido de análise nos seletores agora força o horário de início para `00:00` (meia-noite) e término para `23:59` de forma robusta, impedindo perda de transações nos primeiros ou últimos minutos do dia.
- **Corte de Exibição:** Remoção do limite oculto de `.slice(0, 500)` no retorno do backend, permitindo a exibição de todas as transações da planilha.

### Otimizado
- **Modularização do Bundle:** Configurados os módulos `express` e `open` como externos no script de build do `esbuild`. Isso reduziu o tamanho do arquivo compilado intermediário `dist/bundle.cjs` de **672 KB (15.000+ linhas) para apenas 65,7 KB (1.850 linhas)** de código-fonte puro e limpo, enquanto o `@yao-pkg/pkg` continua gerando o executável final de forma 100% autônoma a partir do `node_modules`.

---

## [1.1.0] — 2026-06-11
### Adicionado
- **Busca Dinâmica de Pastas:** Adicionado o escaneamento de arquivos em subdiretórios comuns do usuário (`Downloads`, `Documentos`, `OneDrive`, etc.) de forma dinâmica, em vez de usar caminhos fixados.

### Removido
- **Tracer do Agente:** Removida a seção visual de logs de execução do agente IA e do JSON de payload da tela do Dashboard para simplificar o visual.

---

## [1.0.0] — 2026-06-10
### Adicionado
- **Lançamento Inicial:** Servidor local Node.js com TypeScript de conciliação de relatórios de adquirentes e dashboard web interativo.
