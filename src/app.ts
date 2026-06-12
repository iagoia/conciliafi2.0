import express from 'express';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import net from 'node:net';
import { fileURLToPath } from 'node:url';
import { exec } from 'node:child_process';

import {
  carregarArquivo,
  mapearColunas,
  limparValorMonetario,
  normalizarDatas,
  formatarMoedaBr
} from './conciliacao.js';

// @ts-ignore
const _filename = typeof __filename !== 'undefined' ? __filename : fileURLToPath(import.meta.url);
// @ts-ignore
const _dirname = typeof __dirname !== 'undefined' ? __dirname : path.dirname(_filename);
const BASE_DIR = path.resolve(_dirname, '..');
const LOG_FILE = typeof (process as any).pkg !== 'undefined' 
  ? path.join(path.dirname(process.execPath), "conciliacao.log") 
  : path.join(BASE_DIR, "conciliacao.log");

const DEFAULT_PORT = 8000;

// Configurar logging
function logInfo(message: string) {
  const time = new Date().toISOString().replace('T', ' ').substring(0, 19);
  const logLine = `${time} [INFO] 127.0.0.1 - ${message}\n`;
  fs.appendFileSync(LOG_FILE, logLine, 'utf-8');
  console.log(logLine.trim());
}

function logError(message: string, error?: any) {
  const time = new Date().toISOString().replace('T', ' ').substring(0, 19);
  let logLine = `${time} [ERROR] ${message}\n`;
  if (error && error.stack) {
    logLine += `Traceback:\n${error.stack}\n`;
  }
  fs.appendFileSync(LOG_FILE, logLine, 'utf-8');
  console.error(logLine.trim());
}

// ═══════════════════════════════════════════════════════════════════════════════
// CLASSIFICADORES E AUXILIARES
// ═══════════════════════════════════════════════════════════════════════════════

function triagemMain(payload: any): any {
  const caminhoLocal = payload.caminho_local || "";
  const filename = payload.filename || "";
  const fileData = payload.file_data || "";

  let nomeArquivo = "";
  if (caminhoLocal) {
    nomeArquivo = path.basename(caminhoLocal);
  } else if (filename) {
    nomeArquivo = filename;
  }

  const arquivoRecebido = !!(caminhoLocal || (filename && fileData));

  // Detecção de adquirente por nome do arquivo
  const nomeMin = nomeArquivo.toLowerCase();
  let adquirente = "desconhecida";
  if (nomeMin.includes("cielo")) {
    adquirente = "cielo";
  } else if (nomeMin.includes("stone")) {
    adquirente = "stone";
  } else if (nomeMin.includes("rede")) {
    adquirente = "rede";
  } else if (nomeMin.includes("pagseguro") || nomeMin.includes("pagbank")) {
    adquirente = "pagseguro";
  } else if (nomeMin.includes("getnet")) {
    adquirente = "getnet";
  } else if (nomeMin.includes("safrapay")) {
    adquirente = "safrapay";
  } else if (nomeMin.includes("mercado")) {
    adquirente = "mercadopago";
  }

  if (arquivoRecebido) {
    return {
      acao: "delegar",
      alvo: "Especialista_CONCILIADOR",
      contexto: {
        tipo_operacao: "conciliacao_financeira",
        arquivo_recebido: true,
        nome_arquivo: nomeArquivo,
        adquirente_detectada: adquirente
      }
    };
  }
  return {
    acao: "negar",
    motivo: "operacao_nao_suportada"
  };
}

function sanitizarDadosAntiPromptInjection(rows: any[]): any[] {
  const padroesSuspeitos = [
    /ignore/gi, /override/gi, /instrução/gi, /instruction/gi,
    /sistema/gi, /system/gi, /command/gi, /update/gi, /delete/gi,
    /selecione/gi, /output/gi, /saída/gi, /retorne/gi
  ];

  return rows.map(row => {
    const newRow: any = {};
    for (const key of Object.keys(row)) {
      if (key === '__proto__' || key === 'constructor' || key === 'prototype') continue;
      let val = row[key];
      if (typeof val === 'string') {
        for (const padrao of padroesSuspeitos) {
          val = val.replace(padrao, "[REDACTED]");
        }
      }
      newRow[key] = val;
    }
    return newRow;
  });
}

function classificarMeio(row: any): string {
  let valLiquido = 0;
  try {
    valLiquido = parseFloat(row["valor_liquido"]);
    if (isNaN(valLiquido)) valLiquido = 0;
  } catch {
    valLiquido = 0;
  }

  let prodVal = "";
  if (row["produto_original"]) {
    prodVal = String(row["produto_original"]).trim();
  }
  const bandeira = prodVal.toUpperCase();

  let tipoCompra = "";
  const colsTipo = ["Tipo de compra", "tipo_compra", "tipo de compra", "modalidade", "tipo", "bandeira"];
  for (const col of colsTipo) {
    if (row[col] !== undefined && row[col] !== null) {
      tipoCompra = String(row[col]).trim().toUpperCase();
      break;
    }
  }

  // Concatenar todos os valores para busca
  const rowValuesUpper = Object.values(row).map(val => String(val).toUpperCase());
  const rowTextJoined = rowValuesUpper.join(" | ");

  // Estorno
  if (rowTextJoined.includes("ESTORNO") || rowTextJoined.includes("REVERSAO") || rowTextJoined.includes("REVERSÃO") || valLiquido < 0) {
    return "Estorno";
  }

  // Pix
  const pixKeywords = ["PIX", "PIX QR", "PIX DINAMICO", "PIX DINÂMICO", "PIX ESTATICO", "PIX ESTÁTICO"];
  if (pixKeywords.some(kw => bandeira.includes(kw) || tipoCompra.includes(kw) || rowValuesUpper.some(v => v.includes(kw)))) {
    return "Pix";
  }

  // Débito
  const debitoKeywords = ["DEB", "DEBIT", "DEBITO", "DÉBITO"];
  if (debitoKeywords.some(kw => bandeira.includes(kw) || tipoCompra.includes(kw) || rowValuesUpper.some(v => v.includes(kw)))) {
    return "Débito";
  }

  return "Crédito";
}

function formatBrDate(dt: Date): string {
  const d = String(dt.getDate()).padStart(2, '0');
  const m = String(dt.getMonth() + 1).padStart(2, '0');
  const y = dt.getFullYear();
  const h = String(dt.getHours()).padStart(2, '0');
  const min = String(dt.getMinutes()).padStart(2, '0');
  const sec = String(dt.getSeconds()).padStart(2, '0');
  return `${d}/${m}/${y} ${h}:${min}:${sec}`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// PIPELINE ESPECIALISTA LUKOS
// ═══════════════════════════════════════════════════════════════════════════════

function executarEspecialistaLukos(delegation: any, payload: any, apenasAnalise: boolean = false): any {
  const contexto = delegation.contexto || {};
  const nomeArquivo = contexto.nome_arquivo || "";
  const caminhoLocal = payload.caminho_local || "";
  const fileDataB64 = payload.file_data || "";
  const dataInicioStr = payload.data_inicio || "";
  const dataFimStr = payload.data_fim || "";

  let dtInicio: Date | null = null;
  let dtFim: Date | null = null;

  if (!apenasAnalise) {
    // Parse de datas início e fim
    const parseFormDate = (dateStr: string, defaultHours: number, defaultMinutes: number, defaultSeconds: number): Date => {
      const s = dateStr.trim();
      
      // Tentar formato BR/PT: DD/MM/YYYY ou DD-MM-YYYY (com ou sem hora)
      const brMatch = /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/.exec(s);
      if (brMatch) {
        const day = parseInt(brMatch[1]);
        const month = parseInt(brMatch[2]) - 1;
        const year = parseInt(brMatch[3]);
        const hr = brMatch[4] !== undefined ? parseInt(brMatch[4]) : defaultHours;
        const min = brMatch[5] !== undefined ? parseInt(brMatch[5]) : defaultMinutes;
        const sec = brMatch[6] !== undefined ? parseInt(brMatch[6]) : defaultSeconds;
        const dt = new Date(year, month, day, hr, min, sec);
        if (!isNaN(dt.getTime())) return dt;
      }

      // Tentar formato ISO/US: YYYY-MM-DD ou YYYY/MM/DD (com ou sem hora/T)
      const isoMatch = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[\sT]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/.exec(s);
      if (isoMatch) {
        const year = parseInt(isoMatch[1]);
        const month = parseInt(isoMatch[2]) - 1;
        const day = parseInt(isoMatch[3]);
        const hr = isoMatch[4] !== undefined ? parseInt(isoMatch[4]) : defaultHours;
        const min = isoMatch[5] !== undefined ? parseInt(isoMatch[5]) : defaultMinutes;
        const sec = isoMatch[6] !== undefined ? parseInt(isoMatch[6]) : defaultSeconds;
        const dt = new Date(year, month, day, hr, min, sec);
        if (!isNaN(dt.getTime())) return dt;
      }

      // Fallback para native Date.parse
      const parseVal = Date.parse(s);
      if (!isNaN(parseVal)) return new Date(parseVal);

      return new Date(NaN);
    };

    dtInicio = parseFormDate(dataInicioStr, 0, 0, 0);
    dtFim = parseFormDate(dataFimStr, 23, 59, 59);
    
    if (isNaN(dtInicio.getTime()) || isNaN(dtFim.getTime())) {
      throw new Error(`Datas inválidas: ${dataInicioStr} a ${dataFimStr}`);
    }
  }

  let usandoTemp = false;
  let tempPath = "";

  if (caminhoLocal) {
    tempPath = caminhoLocal;
  } else {
    const fileBytes = Buffer.from(fileDataB64, 'base64');
    const sufixo = path.extname(nomeArquivo).toLowerCase();
    tempPath = path.join(os.tmpdir(), `concilia_temp_${Date.now()}${sufixo}`);
    usandoTemp = true;
    fs.writeFileSync(tempPath, fileBytes);
  }

  try {
    let loadResult;
    try {
      loadResult = carregarArquivo(tempPath);
    } catch (readErr: any) {
      return {
        "status": "ERRO_LEITURA_ARQUIVO",
        "motivo": "encoding_nao_suportado",
        "message": `Falha ao ler arquivo: ${readErr.message}`
      };
    }

    const { columns, rows } = loadResult;
    const totalBruto = rows.length;

    // Anti Prompt Injection
    let sanitizedRows = sanitizarDadosAntiPromptInjection(rows);

    // Mapeamento
    const mappedResult = mapearColunas(columns, sanitizedRows);
    let mappedRows = mappedResult.rows;

    // Normalização de Datas
    const datasNormalizadas = normalizarDatas(mappedRows, tempPath);
    mappedRows.forEach((row, idx) => {
      row["data_transacao"] = datasNormalizadas[idx];
    });

    if (apenasAnalise) {
      const datasValidas = datasNormalizadas.filter((d): d is Date => d instanceof Date);
      if (datasValidas.length === 0) {
        throw new Error("Nenhuma data válida encontrada no arquivo.");
      }

      const minDate = new Date(Math.min(...datasValidas.map(d => d.getTime())));
      const maxDate = new Date(Math.max(...datasValidas.map(d => d.getTime())));

      // Formatar no formato ISO simplificado local YYYY-MM-DDTHH:mm
      const toISOLocal = (dt: Date) => {
        const offset = dt.getTimezoneOffset();
        const local = new Date(dt.getTime() - (offset * 60 * 1000));
        return local.toISOString().slice(0, 16);
      };

      return {
        "status": "success",
        "delegacao_trace": delegation,
        "min_date": toISOLocal(minDate),
        "max_date": toISOLocal(maxDate),
        "min_date_formatted": formatBrDate(minDate),
        "max_date_formatted": formatBrDate(maxDate),
        "total_registros": totalBruto
      };
    }

    const colunasMapeadas = new Set(mappedResult.columns);

    // Limpeza de Valores Monetários
    mappedRows.forEach(row => {
      for (const col of ["valor_bruto", "valor_liquido", "valor_repasse", "valor_taxa"]) {
        if (row[col] !== undefined && row[col] !== null) {
          row[col] = limparValorMonetario(row[col]);
        } else {
          row[col] = NaN;
        }
      }
    });

    // Dedução inteligente
    mappedRows.forEach(row => {
      if (isNaN(row["valor_bruto"])) {
        row["valor_bruto"] = row["valor_liquido"];
      }
      if (isNaN(row["valor_liquido"])) {
        row["valor_liquido"] = row["valor_bruto"];
      }
      if (isNaN(row["valor_bruto"]) && isNaN(row["valor_liquido"])) {
        const baseCol = colunasMapeadas.has("valor_repasse") ? "valor_repasse" : "valor_taxa";
        if (colunasMapeadas.has(baseCol)) {
          row["valor_bruto"] = row[baseCol];
          row["valor_liquido"] = row[baseCol];
        }
      }
      if (isNaN(row["valor_repasse"])) {
        row["valor_repasse"] = row["valor_liquido"];
      }
    });

    // Taxas inconsistentes
    if (colunasMapeadas.has("valor_taxa") && colunasMapeadas.has("valor_bruto") && colunasMapeadas.has("valor_liquido")) {
      let inconsistentes = 0;
      mappedRows.forEach(row => {
        const difReal = row["valor_bruto"] - row["valor_liquido"];
        const tx = isNaN(row["valor_taxa"]) ? 0 : row["valor_taxa"];
        if (Math.abs(tx - difReal) > 1.0) {
          inconsistentes++;
        }
      });
      const proporcaoInconsistente = inconsistentes / Math.max(mappedRows.length, 1);
      if (proporcaoInconsistente > 0.5) {
        mappedRows.forEach(row => {
          row["valor_taxa"] = row["valor_bruto"] - row["valor_liquido"];
        });
      }
    }

    mappedRows.forEach(row => {
      if (isNaN(row["valor_taxa"])) {
        row["valor_taxa"] = row["valor_bruto"] - row["valor_liquido"];
      }
      row["valor_transacao"] = row["valor_liquido"];
    });

    // Filtros por datas e validade
    const validRows = mappedRows.filter(row => {
      if (row["valor_transacao"] === null || isNaN(row["valor_transacao"]) || !(row["data_transacao"] instanceof Date)) {
        return false;
      }
      
      // Filtrar fora status malsucedidos
      if (row["status_original"]) {
        const statusMin = String(row["status_original"]).trim().toLowerCase();
        const STATUS_FALHADOS = new Set([
          "negada", "negado", "expirado", "expirada", "cancelada", "cancelado",
          "rejeitada", "rejeitado", "falhou", "erro", "failed", "denied", "expired",
          "cancel", "canceled", "declined"
        ]);
        if (STATUS_FALHADOS.has(statusMin)) {
          return false;
        }
      }
      return true;
    });
    
    const filteredRows = validRows.filter(row => {
      const dt = row["data_transacao"] as Date;
      return dt >= dtInicio! && dt <= dtFim!;
    });

    const totalNoPeriodo = filteredRows.length;
    const volumeBruto = filteredRows.reduce((acc, row) => acc + (isNaN(row["valor_bruto"]) ? 0 : row["valor_bruto"]), 0);
    const volumeLiquido = filteredRows.reduce((acc, row) => acc + (isNaN(row["valor_liquido"]) ? 0 : row["valor_liquido"]), 0);
    const volumeRepasse = filteredRows.reduce((acc, row) => acc + (isNaN(row["valor_repasse"]) ? 0 : row["valor_repasse"]), 0);
    const volumeTaxa = filteredRows.reduce((acc, row) => acc + (isNaN(row["valor_taxa"]) ? 0 : row["valor_taxa"]), 0);

    // Classificação de Meio de Pagamento
    filteredRows.forEach(row => {
      row["meio_pagamento"] = classificarMeio(row);
    });

    const creditos = filteredRows.filter(r => r["meio_pagamento"] === "Crédito");
    const valorCreditos = creditos.reduce((acc, r) => acc + r["valor_transacao"], 0);
    
    const debitos = filteredRows.filter(r => r["meio_pagamento"] === "Débito");
    const valorDebitos = debitos.reduce((acc, r) => acc + r["valor_transacao"], 0);

    const pixList = filteredRows.filter(r => r["meio_pagamento"] === "Pix");
    const valorPix = pixList.reduce((acc, r) => acc + r["valor_transacao"], 0);

    const estornosList = filteredRows.filter(r => r["meio_pagamento"] === "Estorno");
    const valorEstornos = estornosList.reduce((acc, r) => acc + r["valor_transacao"], 0);

    const descartados = totalBruto - validRows.length;

    // Detalhar registros descartados
    const descartadosRows = mappedRows.filter(row => row["valor_transacao"] === null || isNaN(row["valor_transacao"]) || !(row["data_transacao"] instanceof Date));
    const descartadosDetalhes = descartadosRows.map(row => {
      const linha = row["linha_arquivo"];
      const conteudo: Record<string, string> = {};
      for (const k of Object.keys(row)) {
        if (!["valor_transacao", "data_transacao", "linha_arquivo", "diferenca_validacao"].includes(k) && row[k] !== undefined && String(row[k]).trim() !== "") {
          conteudo[k] = String(row[k]);
        }
      }
      return { linha, conteudo };
    });

    // Auditoria matemática
    let excedeuTolerancia = false;
    filteredRows.forEach(row => {
      row["diferenca_validacao"] = Math.abs((row["valor_bruto"] - row["valor_taxa"]) - row["valor_liquido"]);
      if (row["diferenca_validacao"] > 0.02) {
        excedeuTolerancia = true;
      }
    });

    const statusReconciliacao = excedeuTolerancia ? "DISCREPANCIA_FINANCEIRA" : "success";

    // Ordenar por data decrescente e limitar top 500
    const sortedFiltered = [...filteredRows].sort((a, b) => (b["data_transacao"] as Date).getTime() - (a["data_transacao"] as Date).getTime());
    const transacoesList = sortedFiltered.map(row => {
      const dt = row["data_transacao"] as Date;
      const meio = row["meio_pagamento"];
      return {
        "data": formatBrDate(dt),
        "valor_bruto": row["valor_bruto"],
        "valor_liquido": row["valor_liquido"],
        "valor_repasse": row["valor_repasse"],
        "valor_taxa": row["valor_taxa"],
        "valor": row["valor_liquido"],
        "valor_formatado": formatarMoedaBr(row["valor_liquido"]),
        "valor_bruto_formatado": formatarMoedaBr(row["valor_bruto"]),
        "valor_liquido_formatado": formatarMoedaBr(row["valor_liquido"]),
        "valor_repasse_formatado": formatarMoedaBr(row["valor_repasse"]),
        "valor_taxa_formatado": formatarMoedaBr(row["valor_taxa"]),
        "tipo": meio,
        "produto": row["produto_original"] ? String(row["produto_original"]).trim() : "",
        "terminal": row["terminal_original"] ? String(row["terminal_original"]).trim() : "",
        "meio_pagamento": meio
      };
    });

    // Dados para o Gráfico
    // Agrupar por data (DD/MM/YYYY)
    const agrupado: Record<string, number> = {};
    filteredRows.forEach(row => {
      const dt = row["data_transacao"] as Date;
      const key = `${String(dt.getDate()).padStart(2, '0')}/${String(dt.getMonth() + 1).padStart(2, '0')}/${dt.getFullYear()}`;
      agrupado[key] = (agrupado[key] || 0) + row["valor_transacao"];
    });

    const labels = Object.keys(agrupado).sort((a, b) => {
      const [dA, mA, yA] = a.split("/").map(Number);
      const [dB, mB, yB] = b.split("/").map(Number);
      return new Date(yA, mA - 1, dA).getTime() - new Date(yB, mB - 1, dB).getTime();
    });
    const valores = labels.map(l => agrupado[l]);

    const chartData = { labels, valores };

    return {
      "status": statusReconciliacao,
      "delegacao_trace": delegation,
      "resumo": {
        "arquivo": nomeArquivo,
        "periodo": `${dataInicioStr} a ${dataFimStr}`,
        "total_registros": totalBruto,
        "no_periodo": totalNoPeriodo,
        "volume_bruto": volumeBruto,
        "taxas": volumeTaxa,
        "liquido": volumeLiquido,
        "repasse": volumeRepasse,
        "credito": {
          "valor": valorCreditos,
          "qtd": creditos.length,
          "valor_formatado": formatarMoedaBr(valorCreditos)
        },
        "debito": {
          "valor": valorDebitos,
          "qtd": debitos.length,
          "valor_formatado": formatarMoedaBr(valorDebitos)
        },
        "pix": {
          "valor": valorPix,
          "qtd": pixList.length,
          "valor_formatado": formatarMoedaBr(valorPix)
        },
        "estorno": {
          "valor": valorEstornos,
          "qtd": estornosList.length,
          "valor_formatado": formatarMoedaBr(valorEstornos)
        },
        // Chaves antigas para compatibilidade
        "creditos_qtd": creditos.length,
        "creditos_valor": valorCreditos,
        "creditos_formatado": formatarMoedaBr(valorCreditos),
        "debitos_qtd": debitos.length,
        "debitos_valor": valorDebitos,
        "debitos_formatado": formatarMoedaBr(valorDebitos),
        "pix_qtd": pixList.length,
        "pix_valor": valorPix,
        "pix_formatado": formatarMoedaBr(valorPix),
        "estornos_qtd": estornosList.length,
        "estornos_valor": valorEstornos,
        "estornos_formatado": formatarMoedaBr(valorEstornos),
        "descartados": descartados,
        "valor_bruto_total": volumeBruto,
        "valor_liquido_total": volumeLiquido,
        "valor_repasse_total": volumeRepasse,
        "valor_taxa_total": volumeTaxa,
        "volume_total": volumeLiquido,
        "volume_total_formatado": formatarMoedaBr(volumeLiquido),
        "volume_bruto_formatado": formatarMoedaBr(volumeBruto),
        "volume_liquido_formatado": formatarMoedaBr(volumeLiquido),
        "volume_repasse_formatado": formatarMoedaBr(volumeRepasse),
        "volume_taxa_formatado": formatarMoedaBr(volumeTaxa)
      },
      "transacoes": transacoesList,
      "chart_data": chartData,
      "descartados_detalhes": descartadosDetalhes
    };

  } finally {
    if (usandoTemp && tempPath && fs.existsSync(tempPath)) {
      try {
        fs.unlinkSync(tempPath);
      } catch {}
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// DETECTOR DE ARQUIVOS LOCAIS E ATUALIZAÇÕES
// ═══════════════════════════════════════════════════════════════════════════════

function obterPastasPermitidas(): Set<string> {
  const home = os.homedir();
  const pastas = new Set<string>([
    path.resolve(BASE_DIR),
    path.resolve(BASE_DIR, "Importar_Conciliacao"),
    home,
  ]);

  try {
    if (fs.existsSync(home)) {
      const items = fs.readdirSync(home);
      for (const item of items) {
        if (item.startsWith(".") || item.toLowerCase() === "appdata") continue;
        const fullPath = path.resolve(home, item);
        try {
          const stats = fs.statSync(fullPath);
          if (stats.isDirectory()) {
            pastas.add(fullPath);

            if (item.toLowerCase() === "onedrive") {
              try {
                const subItems = fs.readdirSync(fullPath);
                for (const subItem of subItems) {
                  if (subItem.startsWith(".")) continue;
                  const subPath = path.resolve(fullPath, subItem);
                  if (fs.statSync(subPath).isDirectory()) {
                    pastas.add(subPath);
                  }
                }
              } catch {}
            }
          }
        } catch {}
      }
    }
  } catch {}

  return pastas;
}

function escaneiaPastasComuns(): any[] {
  const pastas = obterPastasPermitidas();
  const arquivosEncontrados: any[] = [];
  const formatos = new Set([".csv", ".xlsx", ".xls", ".txt", ".tsv"]);
  const palavrasChave = new Set(["venda", "transac", "relatorio", "cielo", "stone", "pagseguro", "concilia", "extrato", "financeiro", "rede", "getnet", "safrapay", "mercado"]);

  const arquivosAdicionados = new Set<string>();

  for (const pasta of pastas) {
    if (!fs.existsSync(pasta)) continue;
    try {
      const items = fs.readdirSync(pasta);
      for (const item of items) {
        const itemPath = path.join(pasta, item);
        try {
          const stats = fs.statSync(itemPath);
          if (stats.isFile() && formatos.has(path.extname(item).toLowerCase())) {
            const nomeMin = item.toLowerCase();
            const contemPalavraChave = Array.from(palavrasChave).some(pw => nomeMin.includes(pw));
            if (contemPalavraChave) {
              const caminhoStr = path.resolve(itemPath);
              if (!arquivosAdicionados.has(caminhoStr)) {
                arquivosAdicionados.add(caminhoStr);
                arquivosEncontrados.push({
                  nome: item,
                  caminho: caminhoStr,
                  tamanho: stats.size,
                  pasta_origem: path.basename(pasta) || pasta
                });
              }
            }
          }
        } catch {}
      }
    } catch (e: any) {
      logError(`Erro ao escanear pasta ${pasta}: ${e.message}`);
    }
  }

  arquivosEncontrados.sort((a, b) => a.nome.localeCompare(b.nome));
  return arquivosEncontrados;
}

function validarCaminhoLocal(caminhoStr: string): boolean {
  if (!caminhoStr) return false;
  const pastasPermitidas = obterPastasPermitidas();

  try {
    const caminho = path.resolve(caminhoStr);
    if (!fs.existsSync(caminho)) return false;
    for (const pasta of pastasPermitidas) {
      if (fs.existsSync(pasta)) {
        if (caminho === pasta || caminho.startsWith(pasta + path.sep)) {
          return true;
        }
      }
    }
  } catch {}
  return false;
}

async function verificarAtualizacao(): Promise<any> {
  const version = "1.0.0";
  const updateUrl = "https://raw.githubusercontent.com/iagoia/concilia-fi-update/main/update.json";
  try {
    const response = await fetch(updateUrl, { signal: AbortSignal.timeout(2000) });
    const data: any = await response.json();
    
    const latestVersion = data.versao_mais_recente || "1.0.0";
    const urlDownload = data.url_download || "";
    const novidades = data.novidades || "";

    const vLocal = version.split(".").map(Number);
    const vOnline = latestVersion.split(".").map(Number);

    let updateAvailable = false;
    for (let i = 0; i < Math.max(vLocal.length, vOnline.length); i++) {
      const l = vLocal[i] || 0;
      const o = vOnline[i] || 0;
      if (o > l) {
        updateAvailable = true;
        break;
      } else if (l > o) {
        break;
      }
    }

    return {
      update_available: updateAvailable,
      latest_version: latestVersion,
      current_version: version,
      url_download: urlDownload,
      novidades
    };
  } catch (err: any) {
    return {
      update_available: false,
      error: err.message,
      current_version: version
    };
  }
}

function obterIpLocal(): string {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    const activeNet = interfaces[name];
    if (activeNet) {
      for (const netInfo of activeNet) {
        if (netInfo.family === 'IPv4' && !netInfo.internal) {
          return netInfo.address;
        }
      }
    }
  }
  return "127.0.0.1";
}

function abrirComoApp(url: string): boolean {
  if (process.platform !== 'win32') return false;

  const caminhosChrome = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    path.join(os.homedir(), "AppData\\Local\\Google\\Chrome\\Application\\chrome.exe")
  ];

  const caminhosEdge = [
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
  ];

  for (const caminho of caminhosChrome) {
    const resolvedPath = caminho.replace(/%([^%]+)%/g, (_: string, n: string) => process.env[n] || "");
    if (fs.existsSync(resolvedPath)) {
      try {
        exec(`"${resolvedPath}" --app=${url}`);
        logInfo("Google Chrome aberto em modo aplicativo.");
        return true;
      } catch {}
    }
  }

  for (const caminho of caminhosEdge) {
    const resolvedPath = caminho.replace(/%([^%]+)%/g, (_: string, n: string) => process.env[n] || "");
    if (fs.existsSync(resolvedPath)) {
      try {
        exec(`"${resolvedPath}" --app=${url}`);
        logInfo("Microsoft Edge aberto em modo aplicativo.");
        return true;
      } catch {}
    }
  }
  return false;
}

function encontrarPortaLivre(portaInicial: number): Promise<number> {
  return new Promise((resolve) => {
    let porta = portaInicial;
    const probe = () => {
      const server = net.createServer();
      server.unref();
      server.on('error', () => {
        porta++;
        if (porta < 9000) {
          probe();
        } else {
          resolve(portaInicial);
        }
      });
      server.listen(porta, '0.0.0.0', () => {
        server.close(() => {
          resolve(porta);
        });
      });
    };
    probe();
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SERVIDOR WEB EXPRESS
// ═══════════════════════════════════════════════════════════════════════════════

const app = express();
app.use(express.json({ limit: '100mb' }));

// CORS
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === 'OPTIONS') {
    res.sendStatus(200);
  } else {
    next();
  }
});

// Middleware de Log
app.use((req, res, next) => {
  logInfo(`"${req.method} ${req.path} HTTP/${req.httpVersion}"`);
  next();
});

// Rotas da API
app.get('/api/listar_arquivos_locais', (req, res) => {
  try {
    const arquivos = escaneiaPastasComuns();
    res.json({
      status: "success",
      arquivos
    });
  } catch (err: any) {
    logError("Erro ao listar arquivos locais", err);
    res.status(500).json({ status: "error", message: err.message });
  }
});

app.get('/api/checar_atualizacao', async (req, res) => {
  try {
    const data = await verificarAtualizacao();
    res.json(data);
  } catch (err: any) {
    logError("Erro ao checar atualizacao", err);
    res.status(500).json({ status: "error", message: err.message });
  }
});

app.post('/api/conciliar', (req, res) => {
  try {
    const payload = req.body;
    if (!payload || Object.keys(payload).length === 0) {
      return res.status(400).json({ status: "error", message: "Corpo da requisição está vazio." });
    }

    const delegation = triagemMain(payload);
    if (delegation.acao === "negar") {
      return res.status(400).json({ status: "error", message: `Triagem recusou a operacao: ${delegation.motivo}` });
    }

    // Human-in-the-Loop check
    for (const key of Object.keys(payload)) {
      if (key === '__proto__' || key === 'constructor' || key === 'prototype') continue;
      const v = payload[key];
      if (typeof v === 'string') {
        const upper = v.toUpperCase();
        if (upper.includes("DROP TABLE") || upper.includes("DELETE FROM") || upper.includes("UPDATE ") || upper.includes("ALTER TABLE")) {
          return res.status(403).json({ status: "error", message: "Acao bloqueada por regras de Human-in-the-Loop (Mutacoes nao autorizadas)." });
        }
      }
    }

    const resposta = executarEspecialistaLukos(delegation, payload, false);
    if (resposta.status === "ERRO_LEITURA_ARQUIVO") {
      res.status(400).json(resposta);
    } else {
      res.json(resposta);
    }
  } catch (err: any) {
    logError("Erro ao realizar conciliacao", err);
    res.status(500).json({ status: "error", message: `Erro ao realizar conciliação: ${err.message}` });
  }
});

app.post('/api/analisar_arquivo', (req, res) => {
  try {
    const payload = req.body;
    if (!payload || Object.keys(payload).length === 0) {
      return res.status(400).json({ status: "error", message: "Corpo da requisição está vazio." });
    }

    const caminhoLocal = payload.caminho_local || "";
    const filename = payload.filename || "";
    const fileDataB64 = payload.file_data || "";

    if (!caminhoLocal && (!filename || !fileDataB64)) {
      return res.status(400).json({ status: "error", message: "Campos obrigatórios ausentes (caminho_local ou filename/file_data)." });
    }

    if (caminhoLocal && !validarCaminhoLocal(caminhoLocal)) {
      return res.status(403).json({ status: "error", message: "Caminho de arquivo local não autorizado ou inexistente." });
    }

    const delegation = triagemMain(payload);
    const resposta = executarEspecialistaLukos(delegation, payload, true);
    
    if (resposta.status === "ERRO_LEITURA_ARQUIVO") {
      res.status(400).json(resposta);
    } else {
      res.json(resposta);
    }
  } catch (err: any) {
    logError("Erro ao analisar arquivo", err);
    res.status(500).json({ status: "error", message: `Erro ao analisar arquivo: ${err.message}` });
  }
});

// Arquivos Estáticos (Servir index.html, etc. na raiz)
app.use(express.static(BASE_DIR));

// Inicializar Servidor
async function startServer() {
  const port = await encontrarPortaLivre(DEFAULT_PORT);
  const ipRede = obterIpLocal();
  const urlLocal = `http://localhost:${port}`;
  const urlRede = `http://${ipRede}:${port}`;

  app.listen(port, '0.0.0.0', () => {
    console.log(`\nIniciando servidor Node/TypeScript na pasta: ${BASE_DIR}`);
    console.log(`Endereço local (neste computador): ${urlLocal}`);
    console.log(`Endereço na rede local (para compartilhar): ${urlRede}`);
    console.log("Para parar o servidor, pressione Ctrl+C\n");

    try {
      if (!abrirComoApp(urlLocal)) {
        const startCmd = process.platform === 'win32' ? `start "" "${urlLocal}"` : process.platform === 'darwin' ? `open "${urlLocal}"` : `xdg-open "${urlLocal}"`;
        exec(startCmd);
        logInfo("Navegador padrão aberto automaticamente.");
      }
    } catch (e: any) {
      logError("Não foi possível abrir o navegador automaticamente", e);
    }
  });
}

startServer().catch(err => {
  logError("Erro crítico na inicialização do servidor", err);
});
