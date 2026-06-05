import { carregarArquivo, mapearColunas, limparValorMonetario, normalizarDatas, formatarMoedaBr } from './conciliacao.js';
import path from 'node:path';

interface TestCase {
  name: string;
  file: string;
  dtInicio: Date;
  dtFim: Date;
  expTotal: number;
  expInPeriod: number;
  expCreditosVal: string;
  expEstornosVal: string;
  expVolTotalVal: string;
  expDescartados: number;
}

const testCases: TestCase[] = [
  {
    name: "CIELO",
    file: "teste_cielo.csv",
    dtInicio: new Date(2024, 0, 1),
    dtFim: new Date(2024, 11, 31, 23, 59, 58),
    expTotal: 10,
    expInPeriod: 10,
    expCreditosVal: "R$ 16.846,30",
    expEstornosVal: "-R$ 59.957,25",
    expVolTotalVal: "-R$ 43.110,95",
    expDescartados: 0
  },
  {
    name: "PAGSEGURO",
    file: "teste_pagseguro.csv",
    dtInicio: new Date(2024, 0, 1),
    dtFim: new Date(2024, 11, 31, 23, 59, 58),
    expTotal: 7,
    expInPeriod: 7,
    expCreditosVal: "R$ 8.555,80",
    expEstornosVal: "-R$ 980,50",
    expVolTotalVal: "R$ 7.575,30",
    expDescartados: 0
  },
  {
    name: "STONE",
    file: "teste_stone.csv",
    dtInicio: new Date(2024, 0, 1),
    dtFim: new Date(2024, 11, 31, 23, 59, 58),
    expTotal: 7,
    expInPeriod: 7,
    expCreditosVal: "R$ 10.046,30",
    expEstornosVal: "R$ 0,00",
    expVolTotalVal: "R$ 10.046,30",
    expDescartados: 0
  },
  {
    name: "VSPAGUE",
    file: "Importar_Conciliacao/Importar Conciliação/Destaxa/VSPague_38991675000112_TransacoesDe20251223.csv",
    dtInicio: new Date(2025, 11, 1),
    dtFim: new Date(2025, 11, 31, 23, 59, 58),
    expTotal: 166,
    expInPeriod: 166,
    expCreditosVal: "R$ 10.427,02",
    expEstornosVal: "R$ 0,00",
    expVolTotalVal: "R$ 10.427,02",
    expDescartados: 0
  },
  {
    name: "BRINKS",
    file: "Importar_Conciliacao/Importar Conciliação/Brinks/paulicar1234.xlsx",
    dtInicio: new Date(2020, 0, 1),
    dtFim: new Date(2026, 11, 31, 23, 59, 58),
    expTotal: 1034,
    expInPeriod: 977,
    expCreditosVal: "R$ 503.248,00",
    expEstornosVal: "R$ 0,00",
    expVolTotalVal: "R$ 503.248,00",
    expDescartados: 57
  }
];

function runTests() {
  let allPass = true;
  console.log("================================================================================");
  console.log("             SUIÇA DE TESTES DE REGRESSÃO - PYTHON VS TYPESCRIPT               ");
  console.log("================================================================================\n");

  for (const tc of testCases) {
    console.log(`[TESTE] Rodando ${tc.name}...`);
    try {
      const filePath = path.resolve(tc.file);
      const { columns, rows } = carregarArquivo(filePath);
      const totalBruto = rows.length;

      const mapped = mapearColunas(columns, rows);
      const mappedRows = mapped.rows;

      mappedRows.forEach(row => {
        for (const col of ["valor_bruto", "valor_liquido", "valor_repasse", "valor_taxa"]) {
          if (row[col] !== undefined && row[col] !== null) {
            row[col] = limparValorMonetario(row[col]);
          } else {
            row[col] = NaN;
          }
        }
      });

      const datas = normalizarDatas(mappedRows, filePath);
      mappedRows.forEach((row, idx) => {
        row["data_transacao"] = datas[idx];
      });

      // Dedução inteligente
      mappedRows.forEach(row => {
        if (isNaN(row["valor_bruto"])) row["valor_bruto"] = row["valor_liquido"];
        if (isNaN(row["valor_liquido"])) row["valor_liquido"] = row["valor_bruto"];
        if (isNaN(row["valor_bruto"]) && isNaN(row["valor_liquido"])) {
          const baseCol = mapped.columns.includes("valor_repasse") ? "valor_repasse" : "valor_taxa";
          if (mapped.columns.includes(baseCol)) {
            row["valor_bruto"] = row[baseCol];
            row["valor_liquido"] = row[baseCol];
          }
        }
        if (isNaN(row["valor_repasse"])) {
          row["valor_repasse"] = row["valor_liquido"];
        }
        row["valor_transacao"] = row["valor_liquido"];
      });

      const validRows = mappedRows.filter(r => r["valor_transacao"] !== null && !isNaN(r["valor_transacao"]) && r["data_transacao"] instanceof Date);
      const filtered = validRows.filter(r => {
        const dt = r["data_transacao"] as Date;
        return dt >= tc.dtInicio && dt <= tc.dtFim;
      });

      const estornos = filtered.filter(r => r["valor_transacao"] < 0);
      const creditos = filtered.filter(r => r["valor_transacao"] > 0);

      const valorEstornos = estornos.reduce((acc, r) => acc + r["valor_transacao"], 0);
      const valorCreditos = creditos.reduce((acc, r) => acc + r["valor_transacao"], 0);
      const volumeTotal = filtered.reduce((acc, r) => acc + r["valor_transacao"], 0);

      const descartados = totalBruto - validRows.length;

      // Formatar valores
      const resCred = formatarMoedaBr(valorCreditos);
      const resEst = formatarMoedaBr(valorEstornos);
      const resVol = formatarMoedaBr(volumeTotal);

      // Asserções
      const checkTotal = totalBruto === tc.expTotal;
      const checkInPeriod = filtered.length === tc.expInPeriod;
      const checkCred = resCred === tc.expCreditosVal;
      const checkEst = resEst === tc.expEstornosVal;
      const checkVol = resVol === tc.expVolTotalVal;
      const checkDesc = descartados === tc.expDescartados;

      const passed = checkTotal && checkInPeriod && checkCred && checkEst && checkVol && checkDesc;

      console.log(`  -> Registros Totais:   TS = ${totalBruto} vs PY = ${tc.expTotal} (${checkTotal ? 'OK' : 'FAIL'})`);
      console.log(`  -> No Período:         TS = ${filtered.length} vs PY = ${tc.expInPeriod} (${checkInPeriod ? 'OK' : 'FAIL'})`);
      console.log(`  -> Créditos:           TS = ${resCred} vs PY = ${tc.expCreditosVal} (${checkCred ? 'OK' : 'FAIL'})`);
      console.log(`  -> Estornos:           TS = ${resEst} vs PY = ${tc.expEstornosVal} (${checkEst ? 'OK' : 'FAIL'})`);
      console.log(`  -> Volume Total:       TS = ${resVol} vs PY = ${tc.expVolTotalVal} (${checkVol ? 'OK' : 'FAIL'})`);
      console.log(`  -> Descartados:        TS = ${descartados} vs PY = ${tc.expDescartados} (${checkDesc ? 'OK' : 'FAIL'})`);

      if (passed) {
        console.log(`>>> [PASS] ${tc.name} BATE COM PYTHON 100%\n`);
      } else {
        allPass = false;
        console.log(`>>> [FAIL] ${tc.name} APRESENTOU DIVERGÊNCIAS!\n`);
      }

    } catch (err: any) {
      allPass = false;
      console.log(`>>> [ERRO] Falha crítica ao processar ${tc.name}: ${err.message}\n`);
      console.error(err);
    }
  }

  console.log("================================================================================");
  if (allPass) {
    console.log("            RESULTADO GERAL: TODOS OS TESTES PASSARAM COM EXATIDÃO!            ");
  } else {
    console.log("            RESULTADO GERAL: HOUVE DIVERGÊNCIAS NOS TESTES!                     ");
  }
  console.log("================================================================================");
}

runTests();
