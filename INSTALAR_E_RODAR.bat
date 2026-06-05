@echo off
chcp 65001 >nul
title Conciliador — Instalação e Inicialização

echo.
echo ============================================================
echo   CONCILIADOR — Instalação Automática
echo ============================================================
echo.

REM ── Verificar Python ──────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. 
    echo Acesse https://www.python.org/downloads/ e instale o Python 3.10 ou superior.
    echo Marque a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [OK] Python encontrado.

REM ── Instalar dependências Python ──────────────────────────────
echo.
echo [1/3] Instalando dependencias Python (pandas, openpyxl, chardet)...
pip install pandas openpyxl chardet xlrd --quiet --disable-pip-version-check

if %errorlevel% neq 0 (
    echo [AVISO] Houve um problema ao instalar dependencias. Tentando continuar...
) else (
    echo [OK] Dependencias Python instaladas.
)

REM ── Verificar se o arquivo principal existe ───────────────────
if not exist "%~dp0app.py" (
    echo [ERRO] Arquivo app.py nao encontrado nesta pasta!
    echo Verifique se extraiu o ZIP corretamente.
    pause
    exit /b 1
)

if not exist "%~dp0conciliacao.py" (
    echo [ERRO] Arquivo conciliacao.py nao encontrado nesta pasta!
    pause
    exit /b 1
)

if not exist "%~dp0index.html" (
    echo [ERRO] Arquivo index.html nao encontrado nesta pasta!
    pause
    exit /b 1
)

echo [OK] Todos os arquivos principais encontrados.

REM ── Iniciar servidor ──────────────────────────────────────────
echo.
echo [3/3] Iniciando o Conciliador...
echo O navegador abrira automaticamente em http://localhost:8000
echo.
echo Para encerrar o sistema, feche esta janela ou pressione Ctrl+C
echo.
echo ============================================================
echo.

cd /d "%~dp0"
python app.py

pause
