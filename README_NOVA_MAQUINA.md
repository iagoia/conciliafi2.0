# 🖥️ Como configurar na nova máquina

## O que está neste pacote

| Arquivo | Descrição |
|---|---|
| `app.py` | Servidor principal do Conciliador |
| `conciliacao.py` | Motor de conciliação financeira |
| `index.html` | Interface web |
| `omniroute.env` | Configurações do OmniRoute (chaves JWT, encryption, OAuth) |
| `insert_keys.mjs` | Script que insere as chaves de API (OpenRouter, Groq, etc.) |
| `CONFIGURAR_NOVA_MAQUINA.bat` | **Script de setup automático — dê duplo clique aqui** |
| `INSTALAR_E_RODAR.bat` | Apenas sobe o Conciliador (sem OmniRoute) |

---

## Pré-requisitos (instale antes)

1. **Python 3.10+** → https://www.python.org/downloads/
   - ⚠️ Marque **"Add Python to PATH"** na instalação

2. **Node.js LTS** → https://nodejs.org/
   - Instalar normalmente, sem opções extras

---

## Instalação em 1 clique

Após instalar Python e Node.js, dê **duplo clique** em:

```
CONFIGURAR_NOVA_MAQUINA.bat
```

O script vai:
- ✅ Instalar dependências Python (pandas, openpyxl, chardet)
- ✅ Instalar o OmniRoute globalmente via npm
- ✅ Copiar as configurações (.env) para o OmniRoute
- ✅ Inserir todas as chaves de API no banco de dados
- ✅ Subir o OmniRoute na porta `20128`
- ✅ Abrir o Conciliador na porta `8000`

---

## Chaves de API incluídas

| Provedor | Tipo |
|---|---|
| OpenRouter | API Key |
| Mistral | API Key |
| Groq | API Key |
| Google (Gemini) | API Key |

---

## Uso diário (após instalação)

Para usar no dia a dia, basta rodar:

```
INSTALAR_E_RODAR.bat
```

Ou manualmente:
```bash
# Terminal 1 — OmniRoute
omniroute

# Terminal 2 — Conciliador
python app.py
```

---

## Acesso

- **Conciliador**: http://localhost:8000
- **OmniRoute Dashboard**: http://localhost:20128
  - Senha inicial: `CHANGEME` (mude no dashboard após o primeiro login)
