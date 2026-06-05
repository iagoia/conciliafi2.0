@echo off
chcp 65001 >nul
title Conciliador + OmniRoute — Configuração Completa

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     CONFIGURAÇÃO COMPLETA — NOVA MÁQUINA                    ║
echo ║     Instala Python, Node.js, OmniRoute e chaves de API      ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM ── Verificar Python ──────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado.
    echo.
    echo Instale o Python 3.10 ou superior em: https://www.python.org/downloads/
    echo IMPORTANTE: Marque "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)
echo [OK] Python encontrado.

REM ── Verificar Node.js ─────────────────────────────────────────
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Node.js nao encontrado.
    echo.
    echo Instale o Node.js LTS em: https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo [OK] Node.js encontrado.

REM ── Instalar dependências Python ──────────────────────────────
echo.
echo [1/5] Instalando dependencias Python...
pip install pandas openpyxl chardet xlrd --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [AVISO] Alguns pacotes Python podem nao ter sido instalados. Continuando...
) else (
    echo [OK] Dependencias Python instaladas.
)

REM ── Instalar OmniRoute globalmente ────────────────────────────
echo.
echo [2/5] Instalando OmniRoute globalmente via npm...
npm install -g omniroute --quiet
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar OmniRoute. Verifique sua conexao com a internet.
    pause
    exit /b 1
)
echo [OK] OmniRoute instalado.

REM ── Detectar pasta de instalação do OmniRoute ─────────────────
echo.
echo [3/5] Configurando OmniRoute...

for /f "delims=" %%i in ('npm root -g') do set NPM_GLOBAL_ROOT=%%i
set OMNIROUTE_DIR=%NPM_GLOBAL_ROOT%\omniroute

if not exist "%OMNIROUTE_DIR%" (
    echo [ERRO] Pasta do OmniRoute nao encontrada em: %OMNIROUTE_DIR%
    pause
    exit /b 1
)

REM ── Copiar o .env configurado ─────────────────────────────────
if exist "%~dp0omniroute.env" (
    copy /Y "%~dp0omniroute.env" "%OMNIROUTE_DIR%\.env" >nul
    echo [OK] Configuracoes do OmniRoute (.env) aplicadas.
) else (
    echo [AVISO] Arquivo omniroute.env nao encontrado. OmniRoute usara configuracoes padrao.
)

REM ── Inserir chaves de API no banco ────────────────────────────
echo.
echo [4/5] Inserindo chaves de API no banco de dados...

if exist "%~dp0insert_keys.mjs" (
    REM Atualizar o caminho do .env no script para a nova maquina
    powershell -Command "(Get-Content '%~dp0insert_keys.mjs') -replace 'C:\\\\Users\\\\supor\\\\AppData\\\\Roaming\\\\npm\\\\node_modules\\\\omniroute', '%OMNIROUTE_DIR:\=\\%' | Set-Content '%~dp0insert_keys_local.mjs'"
    
    node "%~dp0insert_keys_local.mjs"
    if %errorlevel% neq 0 (
        echo [AVISO] Houve um problema ao inserir as chaves. Tente rodar o OmniRoute primeiro e depois reinserir.
    ) else (
        echo [OK] Chaves de API inseridas no banco de dados.
    )
    del "%~dp0insert_keys_local.mjs" >nul 2>&1
) else (
    echo [AVISO] Arquivo insert_keys.mjs nao encontrado. Chaves nao foram inseridas automaticamente.
)

REM ── Iniciar OmniRoute em segundo plano ────────────────────────
echo.
echo [5/5] Iniciando OmniRoute...
start "OmniRoute" cmd /c "omniroute && pause"
echo [OK] OmniRoute iniciando em segundo plano (porta 20128)...
echo      Acesse: http://localhost:20128
echo.

timeout /t 5 /nobreak >nul

REM ── Iniciar Conciliador ────────────────────────────────────────
echo Iniciando Conciliador...
echo O navegador abrira automaticamente em http://localhost:8000
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  Para encerrar: feche esta janela ou pressione Ctrl+C       ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"
python app.py

pause
