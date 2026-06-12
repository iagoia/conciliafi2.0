import { carregarArquivo, mapearColunas, normalizarDatas } from './src/conciliacao.ts';
import fs from 'fs';

const filePath = "C:\\Users\\supor\\Downloads\\Rede_Rel_Vendas_09_06_2026-09_06_2026-138965f9-0af2-439a-98aa-60d46b295443 (1).xlsx";

if (!fs.existsSync(filePath)) {
  console.error("Test file not found!");
  process.exit(1);
}

try {
  const { columns, rows } = carregarArquivo(filePath);
  const mapped = mapearColunas(columns, rows);
  
  // Normalizacoes de datas
  const dates = normalizarDatas(mapped.rows, filePath);
  mapped.rows.forEach((row, idx) => {
    row["data_transacao"] = dates[idx];
  });

  // Limpeza de Valores Monetários
  const limparValorMonetario = (val: any): number => {
    if (val === null || val === undefined) return NaN;
    if (typeof val === 'number') return val;
    let s = String(val).trim();
    if (s === "" || s === "-" || s === "—") return NaN;
    s = s.replace("R$", "").replace(/\s+/g, "");
    s = s.replace(/^(.*?)\s*-\s*$/, '-$1');
    if (s.includes(',')) {
      s = s.replace(/\./g, '').replace(',', '.');
    }
    const num = parseFloat(s);
    return num;
  };

  mapped.rows.forEach(row => {
    for (const col of ["valor_bruto", "valor_liquido", "valor_repasse", "valor_taxa"]) {
      if (row[col] !== undefined && row[col] !== null) {
        row[col] = limparValorMonetario(row[col]);
      } else {
        row[col] = NaN;
      }
    }
  });

  // Dedução inteligente
  mapped.rows.forEach(row => {
    if (isNaN(row["valor_bruto"])) {
      row["valor_bruto"] = row["valor_liquido"];
    }
    if (isNaN(row["valor_liquido"])) {
      row["valor_liquido"] = row["valor_bruto"];
    }
    if (isNaN(row["valor_bruto"]) && isNaN(row["valor_liquido"])) {
      row["valor_bruto"] = 0;
      row["valor_liquido"] = 0;
    }
    if (isNaN(row["valor_repasse"])) {
      row["valor_repasse"] = row["valor_liquido"];
    }
    if (isNaN(row["valor_taxa"])) {
      row["valor_taxa"] = row["valor_bruto"] - row["valor_liquido"];
    }
    row["valor_transacao"] = row["valor_liquido"];
  });

  const validRows = mapped.rows.filter(row => {
    if (row["valor_transacao"] === null || isNaN(row["valor_transacao"]) || !(row["data_transacao"] instanceof Date)) {
      return false;
    }
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

  console.log("Total valid rows count:", validRows.length);
  const pix = validRows.filter(r => String(r["modalidade"]).toLowerCase() === "pix");
  console.log("Pix rows count:", pix.length);
  const pixBrutoSum = pix.reduce((acc, r) => acc + r["valor_bruto"], 0);
  const pixLiquidoSum = pix.reduce((acc, r) => acc + r["valor_liquido"], 0);
  console.log("Pix Bruto Sum:", pixBrutoSum);
  console.log("Pix Liquido Sum:", pixLiquidoSum);

  const totalBruto = validRows.reduce((acc, r) => acc + r["valor_bruto"], 0);
  const totalLiquido = validRows.reduce((acc, r) => acc + r["valor_liquido"], 0);
  const totalTaxas = validRows.reduce((acc, r) => acc + r["valor_taxa"], 0);
  console.log("\nDashboard Totals expected:");
  console.log("  Bruto Total:", totalBruto);
  console.log("  Liquido Total:", totalLiquido);
  console.log("  Taxas Total:", totalTaxas);

} catch (e: any) {
  console.error(e);
}
