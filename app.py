#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Servidor Local com Interface Web para Conciliação Financeira
=============================================================================
Inicia um servidor web local na porta 8000, serve a interface visual (index.html)
e fornece uma API para processar e analisar relatórios financeiros de adquirentes.

Uso:
    python app.py
"""

import http.server
import socketserver
import json
import base64
import sys
import webbrowser
import tempfile
import socket
import logging
import traceback
from pathlib import Path
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Definir caminhos para execução normal ou compilada (PyInstaller)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS).resolve()
    EXE_DIR = Path(sys.executable).parent.resolve()
else:
    BASE_DIR = Path(__file__).parent.resolve()
    EXE_DIR = BASE_DIR

LOG_FILE = EXE_DIR / "conciliacao.log"

# Em modo executável sem console (console=False), não adicionar StreamHandler para evitar crash
_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if not getattr(sys, 'frozen', False):
    _handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_handlers
)

# Importar as funções de processamento do conciliacao.py
try:
    from conciliacao import (
        carregar_arquivo,
        mapear_colunas,
        limpar_valor_monetario,
        normalizar_datas,
        formatar_moeda_br
    )
except ImportError:
    print("[ERRO] Não foi possível importar as funções do script 'conciliacao.py'.")
    print("Certifique-se de que o arquivo 'conciliacao.py' está na mesma pasta que este script.")
    sys.exit(1)

import numpy as np

DEFAULT_PORT = 8000


def triagem_main(payload: dict) -> dict:
    """
    Agente de Triagem: Identifica tipo de operação, arquivo e necessidade de conciliação.
    NÃO lê o conteúdo do CSV/Excel, apenas metadados do payload.
    """
    caminho_local = payload.get("caminho_local", "")
    filename = payload.get("filename", "")
    file_data = payload.get("file_data", "")

    nome_arquivo = ""
    if caminho_local:
        nome_arquivo = Path(caminho_local).name
    elif filename:
        nome_arquivo = filename

    arquivo_recebido = bool(caminho_local or (filename and file_data))

    # Detecção de adquirente por nome do arquivo
    nome_min = nome_arquivo.lower()
    if "cielo" in nome_min:
        adquirente = "cielo"
    elif "stone" in nome_min:
        adquirente = "stone"
    elif "rede" in nome_min:
        adquirente = "rede"
    elif "pagseguro" in nome_min or "pagbank" in nome_min:
        adquirente = "pagseguro"
    elif "getnet" in nome_min:
        adquirente = "getnet"
    elif "safrapay" in nome_min:
        adquirente = "safrapay"
    elif "mercado" in nome_min:
        adquirente = "mercadopago"
    else:
        adquirente = "desconhecida"

    if arquivo_recebido:
        return {
            "acao": "delegar",
            "alvo": "Especialista_CONCILIADOR",
            "contexto": {
                "tipo_operacao": "conciliacao_financeira",
                "arquivo_recebido": True,
                "nome_arquivo": nome_arquivo,
                "adquirente_detectada": adquirente
            }
        }
    return {
        "acao": "negar",
        "motivo": "operacao_nao_suportada"
    }


def sanitizar_dados_anti_injection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica regras de Anti-Prompt Injection sobre o DataFrame,
    substituindo palavras suspeitas em células de texto.
    """
    padroes_suspeitos = [
        r"(?i)ignore", r"(?i)override", r"(?i)instrução", r"(?i)instruction",
        r"(?i)sistema", r"(?i)system", r"(?i)command", r"(?i)update", r"(?i)delete",
        r"(?i)selecione", r"(?i)output", r"(?i)saída", r"(?i)retorne"
    ]

    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            s = df[col].astype(str)
            for padrao in padroes_suspeitos:
                s = s.str.replace(padrao, "[REDACTED]", regex=True)
            df[col] = s
    return df


def classificar_meio(row) -> str:
    """
    Classifica o meio de pagamento de uma linha do DataFrame.
    Prioridade: Estorno > Pix > Débito > Crédito.
    """
    try:
        val_liquido = float(row.get("valor_liquido", 0) or 0)
    except (TypeError, ValueError):
        val_liquido = 0.0
    if pd.isna(val_liquido):
        val_liquido = 0.0

    prod_val = ""
    if "produto_original" in row and pd.notna(row.get("produto_original")):
        prod_val = str(row["produto_original"]).strip()
    bandeira = prod_val.upper()

    # Verificar colunas de tipo/modalidade
    tipo_compra = ""
    for col in ["Tipo de compra", "tipo_compra", "tipo de compra", "modalidade", "tipo", "bandeira"]:
        if col in row.index and pd.notna(row.get(col)):
            tipo_compra = str(row[col]).strip().upper()
            break

    # Concatenar todos os valores de texto da linha para busca robusta
    row_values_upper = [str(val).upper() for val in row.values if pd.notna(val)]
    row_text_joined = " | ".join(row_values_upper)

    # Estorno: palavra-chave ou valor negativo
    if ("ESTORNO" in row_text_joined or "REVERSAO" in row_text_joined
            or "REVERSÃO" in row_text_joined or val_liquido < 0):
        return "Estorno"

    # Pix
    pix_keywords = ["PIX", "PIX QR", "PIX DINAMICO", "PIX DINÂMICO", "PIX ESTATICO", "PIX ESTÁTICO"]
    if any(kw in bandeira or kw in tipo_compra or any(kw in v for v in row_values_upper) for kw in pix_keywords):
        return "Pix"

    # Débito
    debito_keywords = ["DEB", "DEBIT", "DEBITO", "DÉBITO"]
    if any(kw in bandeira or kw in tipo_compra or any(kw in v for v in row_values_upper) for kw in debito_keywords):
        return "Débito"

    return "Crédito"


def executar_especialista_lukos(delegation: dict, payload: dict, apenas_analise: bool = False) -> dict:
    """
    Agente Especialista (Especialista_LUKOS):
    Executa a leitura segura, higienização, mapeamento de colunas, fallbacks e validações financeiras.
    """
    contexto = delegation.get("contexto", {})
    nome_arquivo = contexto.get("nome_arquivo", "")
    caminho_local = payload.get("caminho_local", "")
    file_data_b64 = payload.get("file_data", "")
    data_inicio_str = payload.get("data_inicio", "")
    data_fim_str = payload.get("data_fim", "")
    
    # 1. Validar e carregar datas (se não for apenas análise de período inicial)
    dt_inicio, dt_fim = None, None
    if not apenas_analise:
        try:
            dt_inicio = pd.to_datetime(data_inicio_str, dayfirst=True)
            dt_fim = pd.to_datetime(data_fim_str, dayfirst=True)
            if dt_fim.second == 0 or dt_fim.second == 59:
                dt_fim = dt_fim.replace(second=58)
        except Exception:
            raise ValueError(f"Datas inválidas: {data_inicio_str} a {data_fim_str}")
        
    # 2. Carregar arquivo com encoding seguro (Etapa 1)
    usando_temp = False
    temp_path = None
    
    if caminho_local:
        temp_path = caminho_local
    else:
        file_bytes = base64.b64decode(file_data_b64)
        sufixo = Path(nome_arquivo).suffix.lower()
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo)
        temp_path = temp_file.name
        usando_temp = True
        temp_file.write(file_bytes)
        temp_file.close()
        
    try:
        # Carregamento seguro (Tentar os encodings em ordem)
        # Observação: a lógica interna do `carregar_arquivo` em conciliacao.py 
        # já tenta os encodings ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1'] e gera exceção se todos falharem.
        try:
            df = carregar_arquivo(temp_path)
        except Exception as read_err:
            err_str = str(read_err)
            # Retornar o JSON padrão de erro da especificação se falhar encoding
            return {
                "status": "ERRO_LEITURA_ARQUIVO",
                "motivo": "encoding_nao_suportado",
                "message": f"Falha ao ler arquivo: {err_str}"
            }
            
        total_bruto = len(df)
        
        # Anti Prompt Injection
        df = sanitizar_dados_anti_injection(df)
        
        # Mapeamento de colunas (Etapa 2)
        df = mapear_colunas(df)
        
        # Se for apenas análise para obter o range de datas
        if apenas_analise:
            if "valor_liquido" in df.columns:
                df["valor_transacao"] = df["valor_liquido"]
            elif "valor_bruto" in df.columns:
                df["valor_transacao"] = df["valor_bruto"]
            else:
                for col in ["valor_repasse", "valor_taxa"]:
                    if col in df.columns:
                        df["valor_transacao"] = df[col]
                        break
            df["data_transacao"] = normalizar_datas(df["data_transacao"], temp_path)
            
            datas_validas = df["data_transacao"].dropna()
            if datas_validas.empty:
                raise ValueError("Nenhuma data válida encontrada no arquivo.")
                
            min_date = datas_validas.min()
            max_date = datas_validas.max()
            
            return {
                "status": "success",
                "delegacao_trace": delegation,
                "min_date": min_date.strftime("%Y-%m-%dT%H:%M"),
                "max_date": max_date.strftime("%Y-%m-%dT%H:%M"),
                "min_date_formatted": min_date.strftime("%d/%m/%Y %H:%M:%S"),
                "max_date_formatted": max_date.strftime("%d/%m/%Y %H:%M:%S"),
                "total_registros": total_bruto
            }
            
        colunas_originais = set(df.columns)
        
        # Limpar valores monetários (Etapa 3)
        for col in ["valor_bruto", "valor_liquido", "valor_repasse", "valor_taxa"]:
            if col in df.columns:
                df[col] = limpar_valor_monetario(df[col])
            else:
                df[col] = np.nan
                
        # Dedução Inteligente (Etapa 4)
        if "valor_bruto" not in colunas_originais:
            df["valor_bruto"] = df["valor_liquido"]
        if "valor_liquido" not in colunas_originais:
            df["valor_liquido"] = df["valor_bruto"]
        if "valor_bruto" not in colunas_originais and "valor_liquido" not in colunas_originais:
            base_col = "valor_repasse" if "valor_repasse" in colunas_originais else "valor_taxa"
            if base_col in colunas_originais:
                df["valor_bruto"] = df[base_col]
                df["valor_liquido"] = df[base_col]
        if "valor_repasse" not in colunas_originais:
            df["valor_repasse"] = df["valor_liquido"]
            
        # Se a taxa foi mapeada mas os valores contêm taxas/percentuais inconsistentes, calcula a taxa real
        if "valor_taxa" in colunas_originais and "valor_bruto" in colunas_originais and "valor_liquido" in colunas_originais:
            diferenca_real = df["valor_bruto"] - df["valor_liquido"]
            # Threshold de R$1,00 por transação para filtrar adquirentes que arredondam a taxa
            inconsistente = (df["valor_taxa"].fillna(0) - diferenca_real).abs() > 1.0
            proporcao_inconsistente = inconsistente.sum() / max(len(df), 1)
            if proporcao_inconsistente > 0.5:  # Só substitui se mais de 50% das linhas inconsistentes
                df["valor_taxa"] = diferenca_real
                
        if "valor_taxa" not in colunas_originais:
            df["valor_taxa"] = df["valor_bruto"] - df["valor_liquido"]
            
        # Definir alias e normalizar datas
        df["valor_transacao"] = df["valor_liquido"]
        df["data_transacao"] = normalizar_datas(df["data_transacao"], temp_path)
        
        # Filtragem por período
        mascara_periodo = (df["data_transacao"] >= dt_inicio) & (df["data_transacao"] <= dt_fim)
        mascara_valido = df["valor_transacao"].notna() & df["data_transacao"].notna()
        
        df_valido = df[mascara_valido].copy()
        df_filtrado = df[mascara_periodo & mascara_valido].copy()
        
        total_no_periodo = len(df_filtrado)
        volume_total = float(df_filtrado["valor_transacao"].sum())
        volume_bruto = float(df_filtrado["valor_bruto"].sum()) if total_no_periodo > 0 else 0.0
        volume_liquido = float(df_filtrado["valor_liquido"].sum()) if total_no_periodo > 0 else 0.0
        volume_repasse = float(df_filtrado["valor_repasse"].sum()) if total_no_periodo > 0 else 0.0
        volume_taxa = float(df_filtrado["valor_taxa"].sum()) if total_no_periodo > 0 else 0.0
        
        # Aplicar classificação ao DataFrame filtrado (usa função de nível de módulo)
        if not df_filtrado.empty:
            df_filtrado["meio_pagamento"] = df_filtrado.apply(classificar_meio, axis=1)
        else:
            df_filtrado["meio_pagamento"] = pd.Series(dtype=str)

        # Estornos e créditos/débitos/pix
        df_creditos = df_filtrado[df_filtrado["meio_pagamento"] == "Crédito"]
        qtd_creditos = len(df_creditos)
        valor_creditos = float(df_creditos["valor_transacao"].sum()) if qtd_creditos > 0 else 0.0

        df_debitos = df_filtrado[df_filtrado["meio_pagamento"] == "Débito"]
        qtd_debitos = len(df_debitos)
        valor_debitos = float(df_debitos["valor_transacao"].sum()) if qtd_debitos > 0 else 0.0

        df_pix = df_filtrado[df_filtrado["meio_pagamento"] == "Pix"]
        qtd_pix = len(df_pix)
        valor_pix = float(df_pix["valor_transacao"].sum()) if qtd_pix > 0 else 0.0

        df_estornos = df_filtrado[df_filtrado["meio_pagamento"] == "Estorno"]
        qtd_estornos = len(df_estornos)
        valor_estornos = float(df_estornos["valor_transacao"].sum()) if qtd_estornos > 0 else 0.0
        
        descartados = int(total_bruto - len(df_valido))
        
        # Capturar detalhes dos registros descartados
        df_descartados = df[~mascara_valido].copy()
        descartados_detalhes = []
        colunas_reais = [c for c in df.columns if c not in ["valor_transacao", "data_transacao", "diferenca_validacao", "linha_arquivo"]]
        for _, row in df_descartados.iterrows():
            linha_num = int(row.get("linha_arquivo", 0))
            row_dict = {k: str(v) for k, v in row.to_dict().items() if k in colunas_reais and pd.notna(v) and str(v).strip() != ""}
            descartados_detalhes.append({
                "linha": linha_num,
                "conteudo": row_dict
            })
        
        # Validação Matemática Principal (Etapa 5)
        # Diferença tolerada de R$ 0,02
        df_filtrado["diferenca_validacao"] = ((df_filtrado["valor_bruto"] - df_filtrado["valor_taxa"]) - df_filtrado["valor_liquido"]).abs()
        excedeu_tolerancia = (df_filtrado["diferenca_validacao"] > 0.02).any()
        
        status_reconciliacao = "success"
        if excedeu_tolerancia:
            status_reconciliacao = "DISCREPANCIA_FINANCEIRA"
            
        # Preparar transações detalhadas para exibição na tabela
        df_filtrado_sorted = df_filtrado.sort_values("data_transacao", ascending=False)
        transacoes_list = []
        for _, row in df_filtrado_sorted.head(500).iterrows():
            data_formatada = row["data_transacao"].strftime("%d/%m/%Y %H:%M:%S")
            val_bruto = float(row["valor_bruto"])
            val_liquido = float(row["valor_liquido"])
            val_repasse = float(row["valor_repasse"])
            val_taxa = float(row["valor_taxa"])
            
            prod_val = ""
            if "produto_original" in row and pd.notna(row["produto_original"]):
                prod_val = str(row["produto_original"]).strip()
                
            term_val = ""
            if "terminal_original" in row and pd.notna(row["terminal_original"]):
                term_val = str(row["terminal_original"]).strip()
                
            meio = row["meio_pagamento"]
            
            transacoes_list.append({
                "data": data_formatada,
                # Campos obrigatórios da serialização de transações da especificação
                "valor_bruto": val_bruto,
                "valor_liquido": val_liquido,
                "valor_repasse": val_repasse,
                "valor_taxa": val_taxa,
                # Campos extras de exibição
                "valor": val_liquido,
                "valor_formatado": formatar_moeda_br(val_liquido),
                "valor_bruto_formatado": formatar_moeda_br(val_bruto),
                "valor_liquido_formatado": formatar_moeda_br(val_liquido),
                "valor_repasse_formatado": formatar_moeda_br(val_repasse),
                "valor_taxa_formatado": formatar_moeda_br(val_taxa),
                "tipo": meio,
                "produto": prod_val,
                "terminal": term_val,
                "meio_pagamento": meio
            })
            
        df_grafico = df_filtrado.groupby(df_filtrado["data_transacao"].dt.date)["valor_transacao"].sum().reset_index()
        df_grafico = df_grafico.sort_values("data_transacao")
        chart_data = {
            "labels": [d.strftime("%d/%m/%Y") for d in df_grafico["data_transacao"]],
            "valores": [float(v) for v in df_grafico["valor_transacao"]]
        }
        
        # Resposta com métricas consolidadas exatas
        resposta = {
            "status": status_reconciliacao,
            "delegacao_trace": delegation,
            "resumo": {
                "arquivo": nome_arquivo,
                "periodo": f"{data_inicio_str} a {data_fim_str}",
                "total_registros": total_bruto,
                "no_periodo": total_no_periodo,
                
                # Novos campos estruturados recomendados
                "volume_bruto": volume_bruto,
                "taxas": volume_taxa,
                "liquido": volume_liquido,
                "repasse": volume_repasse,
                "credito": {
                    "valor": valor_creditos,
                    "qtd": qtd_creditos,
                    "valor_formatado": formatar_moeda_br(valor_creditos)
                },
                "debito": {
                    "valor": valor_debitos,
                    "qtd": qtd_debitos,
                    "valor_formatado": formatar_moeda_br(valor_debitos)
                },
                "pix": {
                    "valor": valor_pix,
                    "qtd": qtd_pix,
                    "valor_formatado": formatar_moeda_br(valor_pix)
                },
                "estorno": {
                    "valor": valor_estornos,
                    "qtd": qtd_estornos,
                    "valor_formatado": formatar_moeda_br(valor_estornos)
                },
                
                # Mantendo compatibilidade com as chaves antigas
                "creditos_qtd": qtd_creditos,
                "creditos_valor": valor_creditos,
                "creditos_formatado": formatar_moeda_br(valor_creditos),
                "debitos_qtd": qtd_debitos,
                "debitos_valor": valor_debitos,
                "debitos_formatado": formatar_moeda_br(valor_debitos),
                "pix_qtd": qtd_pix,
                "pix_valor": valor_pix,
                "pix_formatado": formatar_moeda_br(valor_pix),
                "estornos_qtd": qtd_estornos,
                "estornos_valor": valor_estornos,
                "estornos_formatado": formatar_moeda_br(valor_estornos),
                
                "descartados": descartados,
                # Métricas Consolidadas obrigatórias
                "valor_bruto_total": volume_bruto,
                "valor_liquido_total": volume_liquido,
                "valor_repasse_total": volume_repasse,
                "valor_taxa_total": volume_taxa,
                # Extras para compatibilidade
                "volume_total": volume_liquido,
                "volume_total_formatado": formatar_moeda_br(volume_liquido),
                "volume_bruto_formatado": formatar_moeda_br(volume_bruto),
                "volume_liquido_formatado": formatar_moeda_br(volume_liquido),
                "volume_repasse_formatado": formatar_moeda_br(volume_repasse),
                "volume_taxa_formatado": formatar_moeda_br(volume_taxa)
            },
            "transacoes": transacoes_list,
            "chart_data": chart_data,
            "descartados_detalhes": descartados_detalhes
        }
        return resposta
        
    finally:
        if usando_temp and temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass



def encontrar_porta_livre(porta_inicial: int) -> int:
    """Encontra uma porta TCP livre a partir da porta inicial informada."""
    porta = porta_inicial
    while porta < 9000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                porta += 1
    return porta_inicial


def escaneia_pastas_comuns() -> list[dict]:
    """
    Escaneia pastas comuns do computador do usuário (Downloads, Documentos, Desktop,
    Importar_Conciliacao, Músicas, OneDrive, Pasta Atual) em busca de planilhas financeiras.
    Retorna uma lista de dicionários com informações dos arquivos.
    """
    pastas = [
        Path.cwd(),
        Path.cwd() / "Importar_Conciliacao",
        Path.home() / "Downloads",
        Path.home() / "Documents",
        Path.home() / "Desktop",
        Path.home() / "Músicas",
        Path.home() / "Music",
        Path.home() / "Área de Trabalho",
        Path.home() / "OneDrive" / "Downloads",
        Path.home() / "OneDrive" / "Documents",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "OneDrive" / "Área de Trabalho",
        Path.home() / "OneDrive" / "Imagens" / "Nova pasta",
        Path.home() / "OneDrive" / "Imagens" / "Nova pasta" / "Importar_Conciliacao",
    ]
    
    arquivos_encontrados = []
    formatos = {".csv", ".xlsx", ".xls", ".txt", ".tsv"}
    
    # Palavras-chave para filtrar possíveis relatórios de adquirentes
    palavras_chave = {"venda", "transac", "relatorio", "cielo", "stone", "pagseguro", "concilia", "extrato", "financeiro", "rede", "getnet", "safrapay", "mercado"}
    
    arquivos_adicionados = set()
    
    for pasta in pastas:
        if not pasta.exists():
            continue
        try:
            for item in pasta.iterdir():
                if item.is_file() and item.suffix.lower() in formatos:
                    nome_minusculo = item.name.lower()
                    if any(pw in nome_minusculo for pw in palavras_chave):
                        caminho_str = str(item.resolve())
                        if caminho_str not in arquivos_adicionados:
                            arquivos_adicionados.add(caminho_str)
                            arquivos_encontrados.append({
                                "nome": item.name,
                                "caminho": caminho_str,
                                "tamanho": item.stat().st_size,
                                "pasta_origem": pasta.name if pasta.name else str(pasta)
                            })
        except Exception as e:
            # Ignorar erros de permissão em pastas do sistema
            logging.warning(f"Erro ao escanear pasta {pasta}: {e}")
            
    # Ordenar por nome
    arquivos_encontrados.sort(key=lambda x: x["nome"])
    return arquivos_encontrados


def validar_caminho_local(caminho_str: str) -> bool:
    """
    Valida se o caminho local está contido dentro das pastas comuns permitidas.
    Evita ataques de Path Traversal.
    """
    if not caminho_str:
        return False

    pastas_permitidas = [
        Path.cwd().resolve(),
        (Path.cwd() / "Importar_Conciliacao").resolve(),
        (Path.home() / "Downloads").resolve(),
        (Path.home() / "Documents").resolve(),
        (Path.home() / "Desktop").resolve(),
        (Path.home() / "Músicas").resolve(),
        (Path.home() / "Music").resolve(),
        (Path.home() / "Área de Trabalho").resolve(),
        (Path.home() / "OneDrive" / "Downloads").resolve(),
        (Path.home() / "OneDrive" / "Documents").resolve(),
        (Path.home() / "OneDrive" / "Desktop").resolve(),
        (Path.home() / "OneDrive" / "Área de Trabalho").resolve(),
        (Path.home() / "OneDrive" / "Imagens" / "Nova pasta").resolve(),
        (Path.home() / "OneDrive" / "Imagens" / "Nova pasta" / "Importar_Conciliacao").resolve(),
    ]

    try:
        caminho = Path(caminho_str).resolve()
        if not caminho.exists():
            return False
        for pasta in pastas_permitidas:
            if pasta.exists() and (caminho == pasta or caminho.is_relative_to(pasta)):
                return True
    except Exception:
        pass

    return False


class ConciliadorAPIHandler(http.server.SimpleHTTPRequestHandler):
    """Handler customizado para servir a interface e expor a rota de API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def log_message(self, format, *args):
        """Sobrescreve log_message para registrar via logging de forma segura, evitando erros de console no Windows."""
        try:
            logging.info(f"{self.address_string()} - {format % args}")
        except Exception:
            pass

    def do_OPTIONS(self):
        """Trata requisições OPTIONS prévias (CORS)."""
        self.send_response(200, "ok")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Trata requisições GET para a interface e rotas de API."""
        if self.path == "/api/listar_arquivos_locais":
            try:
                arquivos = escaneia_pastas_comuns()
                self._enviar_json(200, {
                    "status": "success",
                    "arquivos": arquivos
                })
            except Exception as e:
                self._enviar_erro(500, f"Erro ao listar arquivos locais: {str(e)}")
        elif self.path == "/api/checar_atualizacao":
            try:
                res = verificar_atualizacao()
                self._enviar_json(200, res)
            except Exception as e:
                self._enviar_erro(500, f"Erro ao verificar atualizações: {str(e)}")
        else:
            super().do_GET()

    def do_POST(self):
        """Trata requisições POST para a rota da API."""
        if self.path == "/api/conciliar":
            try:
                # 1. Obter o tamanho do corpo da requisição
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self._enviar_erro(400, "Corpo da requisição está vazio.")
                    return

                # 2. Ler e decodificar o payload JSON
                corpo_bytes = self.rfile.read(content_length)
                payload = json.loads(corpo_bytes.decode("utf-8"))

                # 3. Chamar Agente de Triagem (triagem_main)
                delegation = triagem_main(payload)
                if delegation.get("acao") == "negar":
                    self._enviar_erro(400, f"Triagem recusou a operacao: {delegation.get('motivo')}")
                    return
                
                # Human-in-the-Loop: Garantir que não há parâmetros maliciosos tentando mutações
                for k, v in payload.items():
                    if isinstance(v, str) and any(cmd in v.upper() for cmd in ["DROP TABLE", "DELETE FROM", "UPDATE ", "ALTER TABLE"]):
                        self._enviar_erro(403, "Acao bloqueada por regras de Human-in-the-Loop (Mutacoes nao autorizadas).")
                        return

                # 4. Chamar Agente Especialista (Especialista_LUKOS)
                resposta = executar_especialista_lukos(delegation, payload, apenas_analise=False)
                
                # Se falhar a leitura
                if resposta.get("status") == "ERRO_LEITURA_ARQUIVO":
                    self._enviar_json(400, resposta)
                else:
                    self._enviar_json(200, resposta)

            except json.JSONDecodeError as decode_err:
                logging.error(f"Erro de decodificação JSON: {decode_err}")
                self._enviar_erro(400, "Corpo da requisição não é um JSON válido.")
            except Exception as e:
                tb_str = traceback.format_exc()
                logging.error(f"Erro interno no servidor: {str(e)}\nTraceback:\n{tb_str}")
                self._enviar_erro(500, f"Erro ao realizar conciliação: {str(e)}")
        elif self.path == "/api/analisar_arquivo":
            try:
                # 1. Obter o tamanho do corpo da requisição
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self._enviar_erro(400, "Corpo da requisição está vazio.")
                    return

                # 2. Ler e decodificar o payload JSON
                corpo_bytes = self.rfile.read(content_length)
                payload = json.loads(corpo_bytes.decode("utf-8"))

                caminho_local = payload.get("caminho_local", "")
                filename = payload.get("filename", "")
                file_data_b64 = payload.get("file_data", "")

                if not caminho_local and (not filename or not file_data_b64):
                    self._enviar_erro(400, "Campos obrigatórios ausentes (caminho_local ou filename/file_data).")
                    return

                # 3. Validar e carregar caminho local ou criar arquivo temporário
                if caminho_local:
                    if not validar_caminho_local(caminho_local):
                        self._enviar_erro(403, "Caminho de arquivo local não autorizado ou inexistente.")
                        return

                usando_temp = False
                temp_path = None
                try:
                    if caminho_local:
                        temp_path = caminho_local
                        filename = Path(caminho_local).name
                    else:
                        # Decodificar arquivo base64 para bytes
                        try:
                            file_bytes = base64.b64decode(file_data_b64)
                        except Exception as e:
                            self._enviar_erro(400, f"Erro ao decodificar arquivo em base64: {str(e)}")
                            return

                        # Salvar temporariamente o arquivo para processamento
                        sufixo = Path(filename).suffix.lower()
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=sufixo)
                        temp_path = temp_file.name
                        usando_temp = True
                        temp_file.write(file_bytes)
                        temp_file.close()

                    # 5. Executar parte do pipeline para extrair datas
                    print(f"\n[API] Analisando arquivo '{filename}' para extracao de periodo...")
                    df = carregar_arquivo(temp_path)
                    df = mapear_colunas(df)
                    if "valor_liquido" in df.columns:
                        df["valor_transacao"] = df["valor_liquido"]
                    elif "valor_bruto" in df.columns:
                        df["valor_transacao"] = df["valor_bruto"]
                    else:
                        for col in ["valor_repasse", "valor_taxa"]:
                            if col in df.columns:
                                df["valor_transacao"] = df[col]
                                break
                    df["data_transacao"] = normalizar_datas(df["data_transacao"], temp_path)

                    # Limpar datas vazias
                    datas_validas = df["data_transacao"].dropna()
                    if datas_validas.empty:
                        self._enviar_erro(400, "Nenhuma data válida encontrada no arquivo.")
                        return

                    min_date = datas_validas.min()
                    max_date = datas_validas.max()

                    min_date_iso = min_date.strftime("%Y-%m-%dT%H:%M")
                    max_date_iso = max_date.strftime("%Y-%m-%dT%H:%M")
                    min_date_fmt = min_date.strftime("%d/%m/%Y %H:%M:%S")
                    max_date_fmt = max_date.strftime("%d/%m/%Y %H:%M:%S")

                    resposta = {
                        "status": "success",
                        "min_date": min_date_iso,
                        "max_date": max_date_iso,
                        "min_date_formatted": min_date_fmt,
                        "max_date_formatted": max_date_fmt,
                        "total_registros": len(df)
                    }
                    self._enviar_json(200, resposta)

                except Exception as e:
                    tb_str = traceback.format_exc()
                    error_msg = f"Erro ao analisar datas do arquivo: {str(e)}"
                    logging.error(f"{error_msg}\nTraceback:\n{tb_str}")

                    if temp_path:
                        # Tentar logar as primeiras 10 linhas do arquivo para ajudar na auditoria
                        try:
                            with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                                linhas = [f.readline().strip() for _ in range(10)]
                            linhas_filtradas = [l for l in linhas if l]
                            preview = "\n".join(f"  [Linha {i+1}]: {l}" for i, l in enumerate(linhas_filtradas))
                            logging.error(f"Estrutura do arquivo enviado (primeiras 10 linhas):\n{preview}")
                        except Exception as preview_err:
                            logging.error(f"Não foi possível ler as primeiras linhas do arquivo: {preview_err}")

                    self._enviar_erro(500, error_msg)
                finally:
                    # Remover o arquivo temporário se criado
                    if usando_temp and temp_path:
                        try:
                            Path(temp_path).unlink(missing_ok=True)
                        except Exception:
                            pass
            except Exception as e:
                self._enviar_erro(500, f"Erro interno do servidor: {str(e)}")
        else:
            self._enviar_erro(404, "Rota não encontrada.")

    def _enviar_json(self, status: int, data: dict):
        """Envia uma resposta formatada em JSON com status HTTP adequado."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _enviar_erro(self, status: int, mensagem: str):
        """Envia um erro formatado em JSON."""
        print(f"[API ERRO] Status {status}: {mensagem}")
        self._enviar_json(status, {
            "status": "error",
            "message": mensagem
        })


class ThreadPoolTCPServer(socketserver.TCPServer):
    """
    Servidor TCP com limite de conexões simultâneas usando ThreadPoolExecutor.
    """
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, max_workers=10, bind_and_activate=True):
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def process_request(self, request, client_address):
        # Envia a requisição para o pool usando nosso próprio método seguro
        self.executor.submit(self._process_request_safe, request, client_address)

    def _process_request_safe(self, request, client_address):
        """Wrapper necessário para processar e encerrar o socket na thread."""
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

    def server_close(self):
        super().server_close()
        self.executor.shutdown(wait=True)


def verificar_atualizacao() -> dict:
    """Verifica na nuvem se existe uma versão mais recente do executável."""
    import urllib.request
    import urllib.error
    
    version = "1.0.0"
    update_url = "https://raw.githubusercontent.com/iagoia/concilia-fi-update/main/update.json"
    
    try:
        req = urllib.request.Request(
            update_url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=2.0) as response:
            data = json.loads(response.read().decode('utf-8'))
            latest_version = data.get("versao_mais_recente", "1.0.0")
            url_download = data.get("url_download", "")
            novidades = data.get("novidades", "")
            
            v_local = [int(x) for x in version.split(".") if x.isdigit()]
            v_online = [int(x) for x in latest_version.split(".") if x.isdigit()]
            
            update_available = v_online > v_local
            
            return {
                "update_available": update_available,
                "latest_version": latest_version,
                "current_version": version,
                "url_download": url_download,
                "novidades": novidades
            }
    except Exception as e:
        return {
            "update_available": False,
            "error": str(e),
            "current_version": version
        }


def obter_ip_local() -> str:
    """Resolve o IP local da máquina na rede local activa."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Conexão fantasma para obter interface ativa
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def abrir_como_app(url: str) -> bool:
    """Tenta abrir a URL em modo aplicativo no Chrome ou no Edge (Chromium). Retorna True se conseguir."""
    import os
    import subprocess
    
    # Caminhos típicos do Google Chrome
    caminhos_chrome = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    
    # Caminhos típicos do Microsoft Edge
    caminhos_edge = [
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    ]
    
    for caminho in caminhos_chrome:
        if os.path.exists(caminho):
            try:
                subprocess.Popen([caminho, f"--app={url}"])
                print("  [OK] Google Chrome aberto em modo aplicativo.")
                return True
            except Exception:
                pass
                
    for caminho in caminhos_edge:
        if os.path.exists(caminho):
            try:
                subprocess.Popen([caminho, f"--app={url}"])
                print("  [OK] Microsoft Edge aberto em modo aplicativo.")
                return True
            except Exception:
                pass
                
    return False


def main():
    # Garantir que a pasta atual tem o index.html
    pasta_atual = BASE_DIR
    
    # Encontrar porta livre a partir da 8000
    port = encontrar_porta_livre(DEFAULT_PORT)
    url_local = f"http://localhost:{port}"
    ip_rede = obter_ip_local()
    url_rede = f"http://{ip_rede}:{port}"

    print(f"\nIniciando servidor na pasta: {pasta_atual}")
    print(f"Endereço local (neste computador): {url_local}")
    print(f"Endereço na rede local (para compartilhar): {url_rede}")
    print("Para parar o servidor, pressione Ctrl+C")

    # Iniciar o servidor HTTP escutando em todas as interfaces de rede (0.0.0.0)
    with ThreadPoolTCPServer(("0.0.0.0", port), ConciliadorAPIHandler) as httpd:
        # Abrir automaticamente em modo app ou navegador padrão
        try:
            if not abrir_como_app(url_local):
                webbrowser.open(url_local)
                print("  [OK] Navegador padrão aberto automaticamente.")
        except Exception as e:
            print(f"  [!] Não foi possível abrir o navegador automaticamente: {e}")
            print(f"  Por favor, abra manualmente no seu navegador: {url_local}")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor finalizado pelo usuário (Ctrl+C).")
            sys.exit(0)


if __name__ == "__main__":
    main()
