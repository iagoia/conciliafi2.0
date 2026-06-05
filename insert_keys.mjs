/**
 * insert_keys.mjs — Insere as chaves de API no banco do OmniRoute
 * Detecta automaticamente o caminho do OmniRoute na máquina atual.
 */
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

// ── Detectar o caminho global do OmniRoute automaticamente ─────
function detectOmniRouteDir() {
  try {
    const npmRoot = execSync("npm root -g", { encoding: "utf-8" }).trim();
    return path.join(npmRoot, "omniroute");
  } catch {
    // Fallback: tentar caminhos comuns do Windows
    const candidates = [
      path.join(process.env.APPDATA || "", "npm", "node_modules", "omniroute"),
      path.join("C:\\Users", process.env.USERNAME || "", "AppData", "Roaming", "npm", "node_modules", "omniroute"),
    ];
    for (const c of candidates) {
      if (fs.existsSync(c)) return c;
    }
    throw new Error("OmniRoute não encontrado. Instale com: npm install -g omniroute");
  }
}

const OMNIROUTE_DIR = detectOmniRouteDir();
console.log("OmniRoute encontrado em:", OMNIROUTE_DIR);

// ── Carregar variáveis do .env do OmniRoute ────────────────────
const envPath = path.join(OMNIROUTE_DIR, ".env");
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, "utf-8");
  for (const line of envContent.split("\n")) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith("#")) {
      const idx = trimmed.indexOf("=");
      if (idx !== -1) {
        const key = trimmed.slice(0, idx).trim();
        const val = trimmed.slice(idx + 1).trim();
        process.env[key] = val;
      }
    }
  }
  console.log("Variáveis de ambiente carregadas.");
} else {
  console.warn("AVISO: .env não encontrado em", envPath);
}

// ── Importar módulos do OmniRoute ─────────────────────────────
const sqlitePath = path.join(OMNIROUTE_DIR, "bin", "cli", "sqlite.mjs");
const providerStorePath = path.join(OMNIROUTE_DIR, "bin", "cli", "provider-store.mjs");

const { openOmniRouteDb } = await import(new URL(`file:///${sqlitePath.replace(/\\/g, "/")}`).href);
const { upsertApiKeyProviderConnection } = await import(new URL(`file:///${providerStorePath.replace(/\\/g, "/")}`).href);

// ── Chaves de API a inserir ────────────────────────────────────
const providersKeys = [
  { provider: "openrouter", key: "INSIRA_SUA_CHAVE_OPENROUTER_AQUI" },
  { provider: "mistral",    key: "INSIRA_SUA_CHAVE_MISTRAL_AQUI" },
  { provider: "groq",       key: "INSIRA_SUA_CHAVE_GROQ_AQUI" },
  { provider: "google",     key: "INSIRA_SUA_CHAVE_GOOGLE_AQUI" },
];

console.log("\nAbrindo banco de dados do OmniRoute...");
const { db, dbPath } = await openOmniRouteDb();
console.log("Banco aberto em:", dbPath);

try {
  for (const item of providersKeys) {
    console.log(`  → Inserindo chave para: ${item.provider}`);
    upsertApiKeyProviderConnection(db, {
      provider: item.provider,
      name: item.provider,
      apiKey: item.key,
    });
    console.log(`  [OK] ${item.provider}`);
  }
  console.log("\nTodas as chaves foram inseridas com sucesso!");
} catch (err) {
  console.error("Erro ao inserir chaves:", err);
} finally {
  db.close();
  console.log("Banco de dados fechado.");
}
