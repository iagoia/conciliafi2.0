import { carregarArquivo, mapearColunas, normalizarDatas } from './src/conciliacao.js';
import fs from 'fs';

const filePath = "C:\\Users\\supor\\Downloads\\Rede_Rel_Vendas_09_06_2026-09_06_2026-138965f9-0af2-439a-98aa-60d46b295443 (1).xlsx";

if (!fs.existsSync(filePath)) {
  console.error("Test file not found!");
  process.exit(1);
}

try {
  const { columns, rows } = carregarArquivo(filePath);
  console.log("Columns:", JSON.stringify(columns.slice(0, 3)));
  const mapped = mapearColunas(columns, rows);
  const dates = normalizarDatas(mapped.rows, filePath);
  
  console.log("\nSample Rows after Normalization:");
  for (let i = 0; i < Math.min(5, mapped.rows.length); i++) {
    const rawRow = rows[i];
    const normDate = dates[i];
    console.log(`Row ${i}:`);
    console.log(`  Raw Date:`, rawRow["data da venda"]);
    console.log(`  Raw Hour:`, rawRow["hora da venda"]);
    console.log(`  Normalized Date (Local Time):`, normDate ? normDate.toLocaleString() : "null");
  }
} catch (e: any) {
  console.error("Error running test:", e.stack);
}
