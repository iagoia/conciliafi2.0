const fs = require('fs');
const content = fs.readFileSync('src/conciliacao.ts', 'utf-8');

const regex = /export function normalizarDatas/gi;
const match = regex.exec(content);
if (match) {
  const index = match.index;
  const start = Math.max(0, index - 20);
  const end = Math.min(content.length, index + 2000);
  console.log("CONTEXT:\n", content.substring(start, end));
} else {
  console.log("No match found for normalizarDatas");
}
