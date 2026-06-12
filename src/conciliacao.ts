import fs from 'node:fs';
import path from 'node:path';
import pkg from 'xlsx';
const { readFile, read, utils } = pkg;
import chardet from 'chardet';
import iconv from 'iconv-lite';

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTES — Mapeamento Semântico de Colunas
// ═══════════════════════════════════════════════════════════════════════════════

export const VARIACOES_DATA_PRIMARIA = new Set([
  "data da transação", "data da transacao", "data transação", "data transacao",
  "data de venda", "data venda", "data da venda", "dt_venda", "dt_transacao",
  "dt venda", "dt transacao", "date", "transaction_date", "timestamp", "data",
  "data_criacao", "date_created", "data da criação", "data_transacao",
  "data do abastecimento", "data abastecimento", "dt_abastecimento", "dt abastecimento", "abastecimento",
  "data/hora da venda", "data/hora venda", "data/hora", "data hora", "data e hora", "data e hora da venda",
  "data/hora da transação", "data/hora da transacao", "data_venda",
  "data da venda/transação", "data da venda/transacao",
  "dia", "dataehora", "data e hora", "dataehora",
  "dh abast", "dh abast.", "dh_abast", "dh abast/leitura", "dh leitura", "dh_leitura", "dh",
  "created_at", "data_criacao",
  "order_created_at", "data da compra (date_created)", "date_created", "dt_trans",
  "date e hora da venda", "date e hora", "date/hora da venda", "date/hora"
]);

export const VARIACOES_DATA_SECUNDARIA = new Set([
  "data lançamento", "data lancamento", "dt lançamento", "dt lancamento", "lançamento", "data lancamento/venda",
  "data/hora faturamento", "data de faturamento", "data faturamento", "data_faturamento", "dt_faturamento", "dt faturamento",
  "data da operacao", "data_operacao", "data operacao", "dt_operacao", "dt operacao",
  "data do depósito", "data do deposito", "data depósito", "data deposito", "dt_deposito", "dt deposito", "depósito", "deposito",
  "data de lançamento", "data de lancamento", "data_lancamento", "data do lançamento", "data do lancamento",
  "data de faturamento", "data de autorização", "data de autorizacao",
  "data da autorização da venda", "data da autorizacao da venda", "data de autoriza o", "data da autoriza o da venda",
  "data de pagamento", "data pagamento", "data do pagamento", "dt_pagamento", "dt pagamento", "payment_date", "order_payment_date", "data_pagamento",
  "data prevista de pagamento da venda", "data efetiva do pagamento da venda"
]);

export const VARIACOES_DATA = new Set([...VARIACOES_DATA_PRIMARIA, ...VARIACOES_DATA_SECUNDARIA]);

export const VARIACOES_HORA = new Set([
  "hora", "horário", "horario", "hora da transação", "hora da transacao",
  "hora da venda", "horário da transação", "horario da transacao",
  "horário da venda", "horario da venda", "hora do depósito", "hora do deposito",
  "hora depósito", "hora deposito", "dt_hora", "horário de faturamento", "horario de faturamento",
  "horário da transação", "hr_trans"
]);

export const VARIACOES_BRUTO = new Set([
  "valor bruto", "valor parcela bruto", "valor bruto da venda", "valor da transação",
  "valor da transacao", "valor", "valor total", "montante", "valor_bruto", "valor_total",
  "vl_bruto", "vl_total", "vl. bruto", "amount", "total", "valor da venda original",
  "bruto", "vlr bruto", "valor original", "valor_total_liquidado_recebível", 
  "valor_total_liquidado", "valor total original(r$)", "preço original(r$)", "valor total original",
  "valor do depósito", "valor do deposito", "valor depósito", "valor deposito", 
  "vl_deposito", "vl deposito", "valor_deposito",
  "val total (r$)", "val total", "valor total", "val total original",
  "valor_trans", "valor trans", "vl_trans", "vl trans", "volume",
  "valor bruto da transação", "valor bruto da transacao", "valor bruto da parcela", "valor bruto total",
  "total_order", "quantia", "quantia da retirada",
  "valor venda", "valor a receber", "valor do produto (transaction_amount)", "transaction_amount",
  "r$ valor", "valor nf.", "valor nf", "valor_nf",
  "valor (r$)", "valor r", "valor total (r$)", "vlr. declarado", "vlr declarado", "declarado",
  "valor declarado", "vlr. validado", "vlr validado", "validado", "valor validado",
  "valor em r$", "valor em r", "valor r$"
]);

export const VARIACOES_LIQUIDO = new Set([
  "valor líquido", "valor liquido", "valor parcela liquido", "valor parcela líquido",
  "valor_liquido", "valor_líquido", "vlr liquido", "valor recebido", "valor creditado",
  "vl_liquido", "liquido", "net_amount",
  "valor líquido da parcela/transação", "valor liquido da parcela/transacao", "valor líquido da parcela transação", "valor liquido da parcela transacao",
  "valor líquido da parcela", "valor liquido da parcela",
  "valor líquido da transação", "valor liquido da transacao",
  "valor_recebido", "valor recebido", "valor creditado",
  "paid_amount", "paid_value", "order_balance",
  "valor a receber", "valor do produto (transaction_amount)", "transaction_amount",
  "r$ valor", "valor nf.", "valor nf", "valor_nf",
  "liquido (r$)", "liquido r", "valor liquido (r$)", "valor liquido r", "recebido (r$)", "recebido r",
  "saldo total", "saldo"
]);

export const VARIACOES_REPASSE = new Set([
  "valor do repasse", "valor repasse", "valor pago", "valor pago repasse",
  "repasse", "pago", "valor net", "valor_repasse", "valor_pago", "dt_repasse",
  "valor pago(r$)"
]);

export const VARIACOES_TAXA = new Set([
  "desconto", "taxa", "tarifa", "valor taxa", "valor desconto", "desconto parcela",
  "valor_taxa", "valor_desconto", "comissão", "comissao", "fee", "mdr",
  "valor mdr", "vlr mdr", "vl mdr",
  "valor taxa adm", "taxa adm", "taxa administração", "taxa administracao", "taxa_adm",
  "mdr_venda_taxa", "desconto total(r$)", "valor descontado",
  "valor da taxa (mdr)", "valor da taxa mdr", "taxa (mdr)", "taxa mdr", "taxas"
]);

export const VARIACOES_PRODUTO = new Set([
  "produto", "tipo de produto", "tipo produto", "tipo de transação", "tipo transacao", 
  "tipo", "operacao", "tipo operacao", "meio de pagamento", "bandeira", "modalidade", 
  "captura", "transacao", "payment_method", "method", "type", "product", "tipo_produto",
  "tipo_transacao", "descrição", "descricao", "descrição do serviço", "serviço", "plano", "bandeira/produto"
]);

export const VARIACOES_TERMINAL = new Set([
  "pos", "terminal", "equipamento", "logica", "lógica", "nº pos", "numero pos",
  "id_terminal", "id terminal", "nº terminal", "nro terminal", "nro_terminal", "serial", "serial number",
  "código da maquininha", "codigo da maquininha", "nº da maquininha", "numero da maquininha",
  "maquininha", "numero_serie", "num_serie", "nº série", "numero de série", "no_serie",
  "terminal_id", "codigo_terminal", "código_terminal", "numero_terminal", "número_terminal",
  "nsu_terminal", "store_pos_name", "numero do caixa (pos_id)", "numero do caixa", "pos_id",
  "pdv", "loja", "posto", "ponto de venda", "ponto venda",
  "terminal lógico", "terminal logico", "código loja", "codigo loja",
  "descrição loja", "descricao loja", "código do terminal", "codigo do terminal",
  "número do terminal", "numero do terminal", "número terminal", "numero terminal",
  "cód. do posto", "cod. do posto", "código do posto", "codigo do posto",
  "n de serie", "n° de série", "n. de serie", "numero de serie", "stonecode", "stone id",
  "placa",
  "estabelecimento", "pdv granito",
  "identificador", "id_loja", "id loja", "numero do caixa"
]);

export const VARIACOES_STATUS = new Set([
  "status da venda", "status venda", "status da transação", "status da transacao",
  "status", "situação", "situacao", "status da operacao", "status da operação",
  "state", "status_transacao", "status_venda", "status da venda/ajuste"
]);

// ═══════════════════════════════════════════════════════════════════════════════
// AUXILIARES DE NORMALIZAÇÃO
// ═══════════════════════════════════════════════════════════════════════════════

export function removerAcentos(texto: string): string {
  if (texto === null || texto === undefined) return "";
  return String(texto)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, "");
}

export function normalizarParaBusca(texto: string): string {
  if (!texto) return "";
  let s = removerAcentos(String(texto)).trim().toLowerCase();
  if (s.endsWith(':')) s = s.slice(0, -1).trim();
  s = s.replace(/[^a-z0-9\s]/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

// ═══════════════════════════════════════════════════════════════════════════════
// FUNÇÕES DE INGESTÃO
// ═══════════════════════════════════════════════════════════════════════════════

export function detectarEncoding(buffer: Buffer): string {
  try {
    const result = chardet.detect(buffer);
    const encoding = result ? String(result) : "utf-8";
    console.log(`  [OK] Encoding detectado: ${encoding}`);
    return encoding;
  } catch (err) {
    console.log(`  [!] Falha ao detectar encoding. Usando UTF-8.`);
    return "utf-8";
  }
}

export function detectarLinhasIgnorar(buffer: Buffer, encoding: string): number {
  const separadores = [";", ",", "\t"];
  try {
    // Decode only the first 20KB of the buffer to detect header lines quickly
    const headBuffer = buffer.subarray(0, 20480);
    const content = iconv.decode(headBuffer, encoding);
    const linhas = content.split(/\r?\n/);
    
    for (let i = 0; i < Math.min(40, linhas.length); i++) {
      const linha = linhas[i];
      if (!linha) continue;
      
      for (const sep of separadores) {
        const partes = linha.split(sep).map(p => p.trim().toLowerCase());
        const temData = partes.some(p => VARIACOES_DATA.has(p));
        const temValor = partes.some(p => {
          const normP = normalizarParaBusca(p);
          const variacoesValor = new Set([
            ...VARIACOES_BRUTO, ...VARIACOES_LIQUIDO, ...VARIACOES_REPASSE, ...VARIACOES_TAXA
          ]);
          return variacoesValor.has(p) || [...variacoesValor].some(cv => p.includes(cv));
        });
        
        if (temData && temValor) {
          if (i > 0) {
            console.log(`  [!] Detectadas ${i} linha(s) de metadados a serem ignoradas no cabeçalho.`);
          }
          return i;
        }
      }
    }
  } catch (e: any) {
    console.log(`  [!] Erro ao detectar linhas a ignorar: ${e.message}`);
  }
  return 0;
}

export function promoverCabecalhoExcel(grid: any[][]): { grid: any[][], offset: number } {
  const chavesData = new Set([...VARIACOES_DATA].map(v => normalizarParaBusca(v)));
  const chavesValor = new Set([
    ...VARIACOES_BRUTO, ...VARIACOES_LIQUIDO, ...VARIACOES_REPASSE, ...VARIACOES_TAXA
  ].map(v => normalizarParaBusca(v)));

  if (grid.length === 0) return { grid, offset: 0 };

  const firstRowCols = grid[0].map(c => normalizarParaBusca(String(c)));
  const temData = firstRowCols.some(c => chavesData.has(c));
  const temValor = firstRowCols.some(c => chavesValor.has(c) || [...chavesValor].some(cv => c.includes(cv)));

  if (temData && temValor) {
    return { grid, offset: 2 };
  }

  for (let i = 0; i < Math.min(40, grid.length); i++) {
    const linha = grid[i].map(val => normalizarParaBusca(String(val)));
    const temDataLinha = linha.some(p => chavesData.has(p));
    const temValorLinha = linha.some(p => chavesValor.has(p) || [...chavesValor].some(cv => p.includes(cv)));
    
    if (temDataLinha && temValorLinha) {
      console.log(`  [!] Detectadas ${i + 1} linha(s) de metadados ignoradas no Excel.`);
      const novasColunas = grid[i].map((c, idx) => {
        const strC = String(c).trim();
        return (strC !== null && strC !== undefined && strC !== "") ? strC : `Unnamed_${idx}`;
      });
      const sliceGrid = grid.slice(i + 1);
      // Colocar o cabeçalho novo como primeira linha
      sliceGrid.unshift(novasColunas);
      return { grid: sliceGrid, offset: i + 2 };
    }
  }
  return { grid, offset: 2 };
}

export function obterMelhorSheet(sheetNames: string[]): string {
  const keywords = ["recebimentos", "recebidos", "recebido", "pagamentos", "pagamento", "vendas", "transacoes", "transações", "movimentacao", "movimentação", 
                    "lancamentos", "lançamentos", "extrato", "relatorio", "relatório", "venda", "recebimento", "detalhes"];
  for (const sheet of sheetNames) {
    const sLow = sheet.toLowerCase();
    if (keywords.some(kw => sLow.includes(kw))) {
      if (!sLow.includes("instru") && !sLow.includes("como usar") && !sLow.includes("help") && sLow !== "capa" && !sLow.includes("capa")) {
        return sheet;
      }
    }
  }
  for (const sheet of sheetNames) {
    const sLow = sheet.toLowerCase();
    if (!sLow.includes("instru") && !sLow.includes("como usar") && !sLow.includes("help") && sLow !== "capa" && !sLow.includes("capa")) {
      return sheet;
    }
  }
  return sheetNames[0];
}

export function inlineQuotesWrapped(line: string): boolean {
  const lineStrip = line.trim();
  return lineStrip.startsWith('"') && lineStrip.endsWith('"') && lineStrip.includes(',"');
}

export function removerLinhasVaziasFinais(grid: any[][]): any[][] {
  let lastNonEmptyIndex = grid.length - 1;
  while (lastNonEmptyIndex >= 0) {
    const row = grid[lastNonEmptyIndex];
    if (row && Array.isArray(row)) {
      const isEmpty = row.every(cell => cell === null || cell === undefined || String(cell).trim() === "");
      if (!isEmpty) {
        break;
      }
    }
    lastNonEmptyIndex--;
  }
  return grid.slice(0, lastNonEmptyIndex + 1);
}

export function carregarArquivo(caminhoArquivo: string): { columns: string[], rows: any[] } {
  const caminho = path.resolve(caminhoArquivo);
  if (!fs.existsSync(caminho)) {
    throw new Error(`Arquivo não encontrado: ${caminhoArquivo}`);
  }

  const buffer = fs.readFileSync(caminho); // Read file once here
  const filename = path.basename(caminho);
  const extensao = path.extname(filename).toLowerCase();
  const isVspague = filename.toLowerCase().includes("vspague_");

  // ── Assinatura Especial: Brinks headerless Excel
  if (filename.toLowerCase().includes("brinks") || path.dirname(caminho).toLowerCase().includes("brinks")) {
    console.log("  [OK] Brinks headerless Excel detectado.");
    try {
      const workbook = read(buffer); // Use read(buffer) instead of readFile
      const sheetName = workbook.SheetNames[0];
      const sheet = workbook.Sheets[sheetName];
      const allRows = utils.sheet_to_json<any[]>(sheet, { header: 1, defval: "" });
      const rows = removerLinhasVaziasFinais(allRows);
      
      const parsedRows = rows.map((row, idx) => {
        return {
          "data_transacao": row[2] ? String(row[2]) : "",
          "hora": row[5] ? String(row[5]) : "",
          "valor_bruto": row[4] ? String(row[4]) : "",
          "terminal_original": row[1] ? String(row[1]) : "",
          "linha_arquivo": idx + 1
        };
      });
      return {
        columns: ["data_transacao", "hora", "valor_bruto", "terminal_original", "linha_arquivo"],
        rows: parsedRows
      };
    } catch (e: any) {
      console.log(`  [!] Falha na assinatura especial Brinks: ${e.message}`);
    }
  }

  // ── Assinatura Especial: Destaxa VSPague (CSV sem cabeçalho)
  if (isVspague && !filename.toLowerCase().endsWith(".zip")) {
    try {
      const isZip = buffer.slice(0, 4).toString('hex') === '504b0304';
      if (!isZip) {
        console.log("  [OK] Destaxa VSPague headerless CSV detectado.");
        const encoding = detectarEncoding(buffer);
        const content = iconv.decode(buffer, encoding);
        const lines = content.split(/\r?\n/).filter(l => l.trim() !== "");
        const parsedRows = lines.map((line, idx) => {
          const parts = line.split(';');
          return {
            "data_transacao": parts[1] || "",
            "valor_bruto": parts[19] || "",
            "valor_taxa": parts[24] || "",
            "valor_liquido": parts[26] || "",
            "linha_arquivo": idx + 1
          };
        });
        return {
          columns: ["data_transacao", "valor_bruto", "valor_taxa", "valor_liquido", "linha_arquivo"],
          rows: parsedRows
        };
      }
    } catch (e: any) {
      console.log(`  [!] Falha na assinatura especial Destaxa VSPague: ${e.message}`);
    }
  }

  // Slice head buffer from the already loaded buffer
  const headBuffer = buffer.subarray(0, 200);
  const isZip = headBuffer.slice(0, 4).toString('hex') === '504b0304';
  const headStr = headBuffer.toString('utf-8');
  const isXml = (headStr.includes("<?xml") || headStr.includes("<Workbook")) && !isZip;
  const isHtml = (headStr.includes("<html") || headStr.toLowerCase().includes("<table") || headStr.toLowerCase().includes("<body")) && !isZip;

  if (extensao === ".xlsx" || extensao === ".xls" || isZip || isXml || isHtml) {
    try {
      const workbook = read(buffer, { cellDates: true, raw: false }); // Use read(buffer)
      const sheetName = obterMelhorSheet(workbook.SheetNames);
      console.log(`  [OK] Aba selecionada: '${sheetName}' de [${workbook.SheetNames.join(', ')}]`);
      const sheet = workbook.Sheets[sheetName];
      let allGrid = utils.sheet_to_json<any[]>(sheet, { header: 1, defval: "" });
      let grid = removerLinhasVaziasFinais(allGrid);
      
      const headerVal = isVspague ? 0 : 1;
      let offset = 1;
      if (headerVal !== 0) {
        const res = promoverCabecalhoExcel(grid);
        grid = res.grid;
        offset = res.offset;
      }
      
      if (grid.length === 0) {
        throw new Error("Planilha vazia após processamento do cabeçalho.");
      }

      const columns = grid[0].map(c => String(c).trim());
      const rows: any[] = [];
      for (let i = 1; i < grid.length; i++) {
        const rowObj: any = {};
        for (let j = 0; j < columns.length; j++) {
          const col = columns[j];
          if (col === '__proto__' || col === 'constructor' || col === 'prototype') continue;
          rowObj[col] = grid[i][j];
        }
        rowObj["linha_arquivo"] = i + offset - 1;
        rows.push(rowObj);
      }
      return { columns, rows };
    } catch (err: any) {
      throw new Error(`Não foi possível ler o arquivo Excel: ${err.message}`);
    }
  } else {
    // Carregar CSV/TXT
    const encoding = detectarEncoding(buffer); // Use buffer instead of path
    const encodingsTentar = [encoding, "cp1252", "latin1", "utf-8"];
    let erroFinal: any = null;

    for (const enc of encodingsTentar) {
      try {
        let content = iconv.decode(buffer, enc); // Use buffer already read once
        const skiprows = detectarLinhasIgnorar(buffer, enc); // Use buffer instead of path
        
        let lines = content.split(/\r?\n/);
        
        // Tratar caso o arquivo CSV esteja malformado com aspas ao redor da linha inteira
        if (lines.length > 0) {
          const firstLine = lines[0].trim();
          if (firstLine.startsWith('"') && firstLine.endsWith('"') && firstLine.includes(',"')) {
            console.log("  [!] Detectado CSV malformado com aspas externas. Sanitizando...");
            content = lines.map(line => {
              let lineStrip = line.trim();
              if (lineStrip.startsWith('"') && lineStrip.endsWith('"')) {
                lineStrip = lineStrip.slice(1, -1).replace(/""/g, '"');
              }
              return lineStrip;
            }).join('\n');
            lines = content.split('\n');
          }
        }

        const linesToParse = lines.slice(skiprows).filter(l => l.trim() !== "");
        if (linesToParse.length === 0) continue;

        // Tentar separadores
        const separadores = [";", ",", "\t"];
        let bestSep = ",";
        let maxCols = 0;

        for (const sep of separadores) {
          const cols = linesToParse[0].split(sep).length;
          if (cols > maxCols) {
            maxCols = cols;
            bestSep = sep;
          }
        }

        const grid = linesToParse.map(l => {
          // Parse simples do CSV respeitando aspas
          const result: string[] = [];
          let current = "";
          let inQuotes = false;
          for (let i = 0; i < l.length; i++) {
            const char = l[i];
            if (char === '"') {
              inQuotes = !inQuotes;
            } else if (char === bestSep && !inQuotes) {
              result.push(current.trim());
              current = "";
            } else {
              current += char;
            }
          }
          result.push(current.trim());
          return result;
        });

        if (grid.length === 0 || grid[0].length <= 1) {
          continue;
        }

        const columns = grid[0].map(c => String(c).replace(/^"|"$/g, '').trim());
        const rows: any[] = [];
        for (let i = 1; i < grid.length; i++) {
          const rowObj: any = {};
          for (let j = 0; j < columns.length; j++) {
            rowObj[columns[j]] = grid[i][j] !== undefined ? String(grid[i][j]).replace(/^"|"$/g, '') : "";
          }
          rowObj["linha_arquivo"] = i + skiprows + 2;
          rows.push(rowObj);
        }

        return { columns, rows };
      } catch (e: any) {
        erroFinal = e;
      }
    }
    throw new Error(`Não foi possível carregar o arquivo CSV/TXT: ${erroFinal ? erroFinal.message : "Erro desconhecido"}`);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// FUNÇÕES DE TRANSFORMAÇÃO E MAPEAMENTO
// ═══════════════════════════════════════════════════════════════════════════════

export function mapearColunas(columns: string[], rows: any[]): { columns: string[], rows: any[] } {
  // Achatar colunas do tipo MultiIndex/tuplas para strings simples (se houver)
  const columnsClean = columns.map(c => String(c).trim());

  // Detectar VSPague
  let isVspague = false;
  if (columnsClean.length >= 28) {
    const firstCol = columnsClean[0];
    const isAllDigits = /^\d+$/.test(firstCol);
    if (isAllDigits && firstCol.length >= 10) {
      isVspague = true;
    } else if (columnsClean.slice(0, 10).every(c => /^\d+$/.test(c.trim()))) {
      isVspague = true;
    }
  }

  if (isVspague) {
    console.log("  [OK] Renomeando colunas do formato VSPague...");
    const mappedRows = rows.map(row => {
      const keys = Object.keys(row);
      const newRow: any = { ...row };
      newRow["data_transacao"] = row[keys[1]];
      newRow["valor_bruto"] = row[keys[19]];
      newRow["valor_taxa"] = row[keys[24]];
      newRow["valor_liquido"] = row[keys[26]];
      return newRow;
    });
    
    if (mappedRows.length > 0 && !mappedRows[0]["data_transacao"]) {
      throw new Error("Coluna de data ('data_transacao') nao encontrada após o mapeamento.");
    }
    return {
      columns: ["data_transacao", "valor_bruto", "valor_taxa", "valor_liquido", "linha_arquivo"],
      rows: mappedRows
    };
  }

  const colunasOriginaisNormalized: Record<string, string> = {};
  for (const col of columnsClean) {
    colunasOriginaisNormalized[normalizarParaBusca(col)] = col;
  }

  const renomeacao: Record<string, string> = {};
  function buscarCandidato(variacoes: Set<string>, target: string): string | null {
    const sortedVars = Array.from(variacoes).sort((a, b) => b.length - a.length);
    for (const varName of sortedVars) {
      const normVar = normalizarParaBusca(varName);
      if (colunasOriginaisNormalized[normVar] !== undefined) {
        const colOrig = colunasOriginaisNormalized[normVar];
        if (renomeacao[colOrig] === undefined) {
          renomeacao[colOrig] = target;
          return colOrig;
        }
      }
    }
    return null;
  }

  let colData = buscarCandidato(VARIACOES_DATA_PRIMARIA, "data_transacao");
  if (colData === null) {
    colData = buscarCandidato(VARIACOES_DATA_SECUNDARIA, "data_transacao");
  }
  buscarCandidato(VARIACOES_BRUTO, "valor_bruto");
  buscarCandidato(VARIACOES_LIQUIDO, "valor_liquido");
  buscarCandidato(VARIACOES_REPASSE, "valor_repasse");
  buscarCandidato(VARIACOES_TAXA, "valor_taxa");
  buscarCandidato(VARIACOES_PRODUTO, "produto_original");
  buscarCandidato(VARIACOES_TERMINAL, "terminal_original");
  buscarCandidato(VARIACOES_STATUS, "status_original");

  let colHora: string | null = null;
  const sortedHoras = Array.from(VARIACOES_HORA).sort((a, b) => b.length - a.length);
  for (const varName of sortedHoras) {
    const normVar = normalizarParaBusca(varName);
    if (colunasOriginaisNormalized[normVar] !== undefined) {
      const colOrig = colunasOriginaisNormalized[normVar];
      if (colOrig !== colData) {
        colHora = colOrig;
        break;
      }
    }
  }

  const mappedRows = rows.map(row => {
    const newRow: any = {};
    for (const key of Object.keys(row)) {
      const mappedKey = renomeacao[key] || key;
      newRow[mappedKey] = row[key];
    }
    // Copiar linha_arquivo
    newRow["linha_arquivo"] = row["linha_arquivo"];
    return newRow;
  });

  if (renomeacao) {
    const mapeados = Object.entries(renomeacao).map(([k, v]) => `'${k}' → '${v}'`).join(", ");
    console.log(`  [OK] Colunas mapeadas: ${mapeados}`);
  }

  // Detecção de serial Excel para datas (números no range de data válidas de Excel)
  const amostraDt = mappedRows.slice(0, 30).map(r => r["data_transacao"]).filter(v => v !== null && v !== undefined && v !== "");
  const numericos = amostraDt.map(v => Number(v)).filter(n => !isNaN(n));
  const seriaisOk = numericos.filter(n => n >= 1 && n <= 2958465);

  if (numericos.length > 0 && seriaisOk.length >= numericos.length * 0.8) {
    console.log(`  [FIX] Seriais Excel detectados na coluna de data (${seriaisOk.length} valores). Convertendo...`);
    const EXCEL_EPOCH = new Date(1899, 11, 30); // 1899-12-30
    mappedRows.forEach(row => {
      const v = row["data_transacao"];
      if (v !== null && v !== undefined && v !== "") {
        const n = Number(v);
        if (!isNaN(n) && n >= 1 && n <= 2958465) {
          const dias = Math.floor(n);
          const ms = Math.round((n - dias) * 86400 * 1000);
          const dt = new Date(EXCEL_EPOCH.getTime() + (dias * 24 * 60 * 60 * 1000) + ms);
          row["data_transacao"] = dt;
        }
      }
    });
  }

  // Validar se coluna de hora é de fato hora (padrão HH:MM ou Date)
  if (colHora !== null) {
    const horaAmostra = mappedRows.slice(0, 50).map(r => r[colHora!]).filter(v => v !== null && v !== undefined && v !== "");
    if (horaAmostra.length > 0) {
      const tempoValidos = horaAmostra.filter(v => {
        if (v instanceof Date) return true;
        return /^\s*\d{1,2}:\d{2}/.test(String(v));
      }).length;
      if (tempoValidos / horaAmostra.length < 0.25) {
        console.log(`  [!] Coluna hora '${colHora}' descartada (apenas ${tempoValidos}/${horaAmostra.length} valores com padrão HH:MM).`);
        colHora = null;
      }
    }
  }

  if (colHora !== null) {
    const extrairApenasHora = (valStr: any) => {
      if (valStr instanceof Date) {
        const h = String(valStr.getHours()).padStart(2, '0');
        const m = String(valStr.getMinutes()).padStart(2, '0');
        const s = String(valStr.getSeconds()).padStart(2, '0');
        return `${h}:${m}:${s}`;
      }
      const s = String(valStr).trim();
      if (!s || ["nan", "nat", "<na>"].includes(s.toLowerCase())) return "00:00:00";
      let parts = s;
      if (s.includes(" ")) {
        parts = s.split(" ").pop() || "";
      }
      const match = /(\d{2}:\d{2}(:\d{2})?)/.exec(parts);
      if (match) return match[1];
      return "00:00:00";
    };

    const extrairApenasData = (valStr: string) => {
      const s = String(valStr).trim();
      if (!s || ["nan", "nat", "<na>"].includes(s.toLowerCase())) return "";
      if (s.includes(" ")) {
        return s.split(" ")[0];
      }
      return s;
    };

    mappedRows.forEach(row => {
      const dtVal = row["data_transacao"] instanceof Date ? row["data_transacao"] : String(row["data_transacao"] || "");
      const hrVal = row[colHora!];
      
      if (dtVal instanceof Date) {
        // Se já é Date, apenas aplica a hora se hrVal for válido
        const horaStr = extrairApenasHora(hrVal);
        const [h, m, sSec] = horaStr.split(":").map(Number);
        dtVal.setHours(h || 0, m || 0, sSec || 0);
        row["data_transacao"] = dtVal;
      } else {
        const dataStr = extrairApenasData(dtVal);
        const horaStr = extrairApenasHora(hrVal);
        if (dataStr) {
          row["data_transacao"] = `${dataStr} ${horaStr}`;
        } else {
          row["data_transacao"] = "";
        }
      }
    });
  }

  if (mappedRows.length > 0 && mappedRows[0]["data_transacao"] === undefined) {
    throw new Error("Coluna de data ('data_transacao') nao encontrada após o mapeamento.");
  }

  const newColumns = Object.keys(mappedRows[0] || {});
  return { columns: newColumns, rows: mappedRows };
}

export function limparValorMonetario(val: any): number {
  if (val === null || val === undefined) return NaN;
  if (typeof val === 'number') return val;
  
  let s = String(val).trim();
  if (s === "" || s === "-" || s === "—") return NaN;
  s = s.replace("R$", "");
  s = s.replace(/\s+/g, "");

  // Corrigir trailing minus (ex: "100.00-")
  s = s.replace(/^(.*?)\s*-\s*$/, '-$1');

  if (s.includes(',')) {
    s = s.replace(/\./g, '').replace(',', '.');
  }

  const num = parseFloat(s);
  return num;
}

export function extrairAnoDoArquivo(caminhoArquivo: string | null, rows?: any[]): number {
  if (!caminhoArquivo) return new Date().getFullYear();
  
  const absPath = path.resolve(caminhoArquivo);
  const baseName = path.basename(absPath);
  const years = baseName.match(/\b(20\d{2})\b/);
  if (years) return parseInt(years[1]);

  if (rows && rows.length > 0) {
    const testFields = ["idOperacao", "txId", "id_operacao", "tx_id"];
    for (const col of testFields) {
      if (rows[0][col]) {
        const val = String(rows[0][col]);
        const m = val.match(/\b(20\d{2})\b/);
        if (m) return parseInt(m[1]);
        
        const mLong = val.match(/(20\d{2})\d{4}/);
        if (mLong) return parseInt(mLong[1]);
      }
    }
  }

  try {
    const stats = fs.statSync(absPath);
    return stats.mtime.getFullYear();
  } catch (err) {
    return new Date().getFullYear();
  }
}

export function limparDataCustomizada(val: string, ano: number): string {
  if (typeof val !== 'string') return val;
  
  let valClean = val.trim();
  // Strip invisible/zero-width Unicode chars
  valClean = valClean.replace(/[\u200b\u200c\u200d\u200e\u200f\ufeff\xa0\u00ad\u2028\u2029]+/g, '').trim();
  valClean = valClean.replace(/\s+às\s+/gi, ' ').replace(/\s+as\s+/gi, ' ');
  
  const meses: Record<string, string> = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
    "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"
  };

  const hasLetterMonth = /[a-zA-Z]{3}/.test(valClean);
  if (valClean.includes("•") || hasLetterMonth) {
    valClean = valClean.replace("•", " ").replace(/\s+/g, " ");
    valClean = valClean.replace(/(\d{1,2})h(\d{1,2})m(\d{1,2})s/i, "$1:$2:$3");
    valClean = valClean.replace(/(\d{1,2})h(\d{1,2})m/i, "$1:$2:00");
    valClean = valClean.replace(/(\d{1,2})h/i, "$1:00:00");

    const has4DigitYear = /\b(20\d{2})\b/.test(valClean);
    for (const [ptM, num] of Object.entries(meses)) {
      valClean = valClean.replace(new RegExp(ptM, 'gi'), num);
    }

    if (has4DigitYear) return valClean;

    const m = /(\d{1,2})\s*[-/]?\s*(\d{2})/.exec(valClean);
    if (m) {
      const dia = m[1].padStart(2, '0');
      const mes = m[2];
      let timePart = "";
      const timeMatch = /(\d{1,2}:\d{1,2}(:\d{1,2})?)/.exec(valClean);
      if (timeMatch) {
        timePart = " " + timeMatch[1];
      }
      return `${dia}/${mes}/${ano}${timePart}`;
    }
  }
  return valClean;
}

const INVALID_DATE_STRINGS = new Set(["nan", "nat", "<na>", "none", "n/a", "nd", "-", "", "null"]);

const RODAPE_RE = /^(total|filtro|valor\s*total|subtotal|m[eé]dia|observa|legenda|nota|relat[oó]|emiss[aã]o|nome\b|cpf\b|tipo\b|forma\b|rede\b|status\b|n[uú]mero\b|descri|dep[oó]sito|depos|c[eé]dula|envelope|recibo|lan[cç]amento\b)/i;

export function parseDateManual(s: string, dayFirst: boolean): Date | null {
  if (!s) return null;
  
  // Tentar padrões comuns
  // ISO: YYYY-MM-DD HH:mm:ss
  const isoMatch = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/.exec(s);
  if (isoMatch) {
    const y = parseInt(isoMatch[1]);
    const m = parseInt(isoMatch[2]) - 1;
    const d = parseInt(isoMatch[3]);
    const hr = parseInt(isoMatch[4] || "0");
    const min = parseInt(isoMatch[5] || "0");
    const sec = parseInt(isoMatch[6] || "0");
    const dt = new Date(y, m, d, hr, min, sec);
    return isNaN(dt.getTime()) ? null : dt;
  }

  // BR: DD/MM/YYYY HH:mm:ss ou DD/MM/YY
  const brMatch = /^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/.exec(s);
  if (brMatch) {
    let day = parseInt(brMatch[1]);
    let month = parseInt(brMatch[2]);
    let year = parseInt(brMatch[3]);
    
    if (year < 100) {
      year += year < 50 ? 2000 : 1900;
    }

    if (!dayFirst) {
      // Formato americano MM/DD/YYYY
      const temp = day;
      day = month;
      month = temp;
    }

    const hr = parseInt(brMatch[4] || "0");
    const min = parseInt(brMatch[5] || "0");
    const sec = parseInt(brMatch[6] || "0");
    const dt = new Date(year, month - 1, day, hr, min, sec);
    return isNaN(dt.getTime()) ? null : dt;
  }

  // VSPague / Custom YYYYMMDD HHMMSS or YYYYMMDD
  const yyyymmddMatch = /^(\d{4})(\d{2})(\d{2})(?:\s+(\d{2})(\d{2})(\d{2}))?/.exec(s);
  if (yyyymmddMatch) {
    const y = parseInt(yyyymmddMatch[1]);
    const m = parseInt(yyyymmddMatch[2]) - 1;
    const d = parseInt(yyyymmddMatch[3]);
    const hr = parseInt(yyyymmddMatch[4] || "0");
    const min = parseInt(yyyymmddMatch[5] || "0");
    const sec = parseInt(yyyymmddMatch[6] || "0");
    const dt = new Date(y, m, d, hr, min, sec);
    return isNaN(dt.getTime()) ? null : dt;
  }

  // Fallback para native Date.parse
  const parseVal = Date.parse(s);
  if (!isNaN(parseVal)) return new Date(parseVal);

  return null;
}

export function normalizarDatas(rows: any[], caminhoArquivo: string | null): (Date | null)[] {
  const ano = extrairAnoDoArquivo(caminhoArquivo, rows);
  
  // Primeiro passo: Limpeza inicial e classificação
  const cleanedStrs = rows.map(row => {
    let s = String(row["data_transacao"] || "").trim();
    if (row["data_transacao"] instanceof Date) {
      const d = row["data_transacao"];
      return new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes(), d.getSeconds());
    }
    s = s.replace(/[\u200b\u200c\u200d\u200e\u200f\ufeff\xa0\u00ad]+/g, '').trim();
    const isInvalid = INVALID_DATE_STRINGS.has(s.toLowerCase());
    const isRodape = RODAPE_RE.test(s);
    if (isInvalid || isRodape) return null;
    return limparDataCustomizada(s, ano);
  });

  const validStrs = cleanedStrs.filter(s => s !== null && !(s instanceof Date)) as string[];
  const padraoIsoCount = validStrs.filter(s => /^\d{4}[-/]\d{1,2}[-/]\d{1,2}/.test(s)).length;
  const proporcaoIso = padraoIsoCount / Math.max(validStrs.length, 1);
  const dayFirst = proporcaoIso <= 0.5;

  let nulosConvert = 0;
  const result = cleanedStrs.map((val) => {
    if (val === null) return null;
    if (val instanceof Date) return val;
    
    const parsed = parseDateManual(val, dayFirst);
    if (parsed === null) {
      nulosConvert++;
    }
    return parsed;
  });

  if (nulosConvert > 0) {
    console.log(`  [!] ${nulosConvert} data(s) nao puderam ser convertidas (NaT)`);
  }
  return result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// FORMATADOR
// ═══════════════════════════════════════════════════════════════════════════════

export function formatarMoedaBr(valor: any): string {
  try {
    let num = typeof valor === 'number' ? valor : parseFloat(String(valor));
    if (isNaN(num)) return "R$ 0,00";
    
    const negativo = num < 0;
    const valAbs = Math.abs(num);
    const parteInteira = Math.floor(valAbs);
    const parteDecimal = Math.round((valAbs - parteInteira) * 100);
    
    // Formatar inteira com pontos como separadores de milhar
    const inteiraStr = parteInteira.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    const decimalStr = parteDecimal.toString().padStart(2, '0');
    
    let res = `R$ ${inteiraStr},${decimalStr}`;
    if (negativo) {
      res = `-${res}`;
    }
    return res;
  } catch {
    return "R$ 0,00";
  }
}
