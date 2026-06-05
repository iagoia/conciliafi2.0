#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conciliacao.py — Script de Auditoria e Conciliação Financeira de Adquirentes
=============================================================================
Lê relatórios financeiros de adquirentes (Cielo, Stone, PagSeguro, etc.),
trata os dados de forma agnóstica e calcula o volume transacionado em um período.

Uso:
    python conciliacao.py <arquivo> <data_inicio> <data_fim>
    python conciliacao.py relatorio_cielo.csv 01/01/2024 31/12/2024
"""

import argparse
import sys
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import re
import datetime
import unicodedata
import os

import chardet
import numpy as np
import pandas as pd

# Forçar saída UTF-8 no Windows para evitar erros de encoding no console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — Mapeamento Semântico de Colunas
# ═══════════════════════════════════════════════════════════════════════════════

VARIACOES_DATA_PRIMARIA = frozenset([
    "data da transação", "data da transacao", "data transação", "data transacao",
    "data de venda", "data venda", "data da venda", "dt_venda", "dt_transacao",
    "dt venda", "dt transacao", "date", "transaction_date", "timestamp", "data",
    "data_criacao", "date_created", "data da criação", "data_transacao",
    "data do abastecimento", "data abastecimento", "dt_abastecimento", "dt abastecimento", "abastecimento",
    "data/hora da venda", "data/hora venda", "data/hora", "data hora", "data e hora", "data e hora da venda",
    "data/hora da transação", "data/hora da transacao", "data_venda",
    "data da venda/transação", "data da venda/transacao",
    "dia", "dataehora", "data e hora", "dataEHora",
    "dh abast", "dh abast.", "dh_abast", "dh abast/leitura", "dh leitura", "dh_leitura", "dh",
    "created_at", "data_criacao",
    "order_created_at", "data da compra (date_created)", "date_created", "dt_trans",
    "date e hora da venda", "date e hora", "date/hora da venda", "date/hora"
])

VARIACOES_DATA_SECUNDARIA = frozenset([
    "data lançamento", "data lancamento", "dt lançamento", "dt lancamento", "lançamento", "data lancamento/venda",
    "data/hora faturamento", "data de faturamento", "data faturamento", "data_faturamento", "dt_faturamento", "dt faturamento",
    "data da operacao", "data_operacao", "data operacao", "dt_operacao", "dt operacao",
    "data do depósito", "data do deposito", "data depósito", "data deposito", "dt_deposito", "dt deposito", "depósito", "deposito",
    "data de lançamento", "data de lancamento", "data_lancamento", "data do lançamento", "data do lancamento",
    "data de faturamento", "data de autorização", "data de autorizacao",
    "data da autorização da venda", "data da autorizacao da venda", "data de autoriza o", "data da autoriza o da venda",
    "data de pagamento", "data pagamento", "data do pagamento", "dt_pagamento", "dt pagamento", "payment_date", "order_payment_date", "data_pagamento",
    "data prevista de pagamento da venda", "data efetiva do pagamento da venda"
])

VARIACOES_DATA = VARIACOES_DATA_PRIMARIA | VARIACOES_DATA_SECUNDARIA

VARIACOES_HORA = frozenset([
    "hora", "horário", "horario", "hora da transação", "hora da transacao",
    "hora da venda", "horário da transação", "horario da transacao",
    "horário da venda", "horario da venda", "hora do depósito", "hora do deposito",
    "hora depósito", "hora deposito", "dt_hora", "horário de faturamento", "horario de faturamento",
    "horário da transação", "hr_trans"
])

VARIACOES_BRUTO = frozenset([
    "valor bruto", "valor parcela bruto", "valor bruto da venda", "valor da transação",
    "valor da transacao", "valor", "valor total", "montante", "valor_bruto", "valor_total",
    "vl_bruto", "vl_total", "vl. bruto", "amount", "total", "valor da venda original",
    "bruto", "vlr bruto", "valor original", "valor_total_liquidado_recebível", 
    "valor_total_liquidado", "valor total original(r$)", "preço original(r$)", "valor total original",
    "valor do depósito", "valor do deposito", "valor depósito", "valor deposito", 
    "vl_deposito", "vl deposito", "valor_deposito",
    "val total (r$)", "val total", "valor total", "val total original",
    "valor_trans", "valor trans", "vl_trans", "vl trans", "volume",
    "valor bruto da transação", "valor bruto da transacao", "valor bruto da parcela", "valor bruto total",
    "total_order", "quantia", "quantia da retirada",
    "valor venda", "valor a receber", "valor do produto (transaction_amount)", "transaction_amount",
    "r$ valor", "valor nf.", "valor nf", "valor_nf",
    "valor (r$)", "valor r", "valor total (r$)", "vlr. declarado", "vlr declarado", "declarado",
    "valor declarado", "vlr. validado", "vlr validado", "validado", "valor validado",
    "valor em r$", "valor em r", "valor r$"
])

VARIACOES_LIQUIDO = frozenset([
    "valor líquido", "valor liquido", "valor parcela liquido", "valor parcela líquido",
    "valor_liquido", "valor_líquido", "vlr liquido", "valor recebido", "valor creditado",
    "vl_liquido", "liquido", "net_amount",
    "valor líquido da parcela/transação", "valor liquido da parcela/transacao", "valor líquido da parcela transação", "valor liquido da parcela transacao",
    "valor líquido da parcela", "valor liquido da parcela",
    "valor líquido da transação", "valor liquido da transacao",
    "valor_recebido", "valor recebido", "valor creditado",
    "paid_amount", "paid_value", "order_balance",
    "valor a receber", "valor do produto (transaction_amount)", "transaction_amount",
    "r$ valor", "valor nf.", "valor nf", "valor_nf",
    "liquido (r$)", "liquido r", "valor liquido (r$)", "valor liquido r", "recebido (r$)", "recebido r",
    "saldo total", "saldo"
])

VARIACOES_REPASSE = frozenset([
    "valor do repasse", "valor repasse", "valor pago", "valor pago repasse",
    "repasse", "pago", "valor net", "valor_repasse", "valor_pago", "dt_repasse",
    "valor pago(r$)"
])

VARIACOES_TAXA = frozenset([
    "desconto", "taxa", "tarifa", "valor taxa", "valor desconto", "desconto parcela",
    "valor_taxa", "valor_desconto", "comissão", "comissao", "fee", "mdr",
    "valor taxa adm", "taxa adm", "taxa administração", "taxa administracao", "taxa_adm",
    "mdr_venda_taxa", "desconto total(r$)", "valor descontado",
    "valor da taxa (mdr)", "valor da taxa mdr", "taxa (mdr)", "taxa mdr", "taxas"
])
VARIACOES_PRODUTO = frozenset([
    "produto", "tipo de produto", "tipo produto", "tipo de transação", "tipo transacao", 
    "tipo", "operacao", "tipo operacao", "meio de pagamento", "bandeira", "modalidade", 
    "captura", "transacao", "payment_method", "method", "type", "product", "tipo_produto",
    "tipo_transacao", "descrição", "descricao", "descrição do serviço", "serviço", "plano", "bandeira/produto"
])
VARIACOES_TERMINAL = frozenset([
    # Genéricos
    "pos", "terminal", "equipamento", "logica", "lógica", "nº pos", "numero pos",
    "id_terminal", "id terminal", "nº terminal", "nro terminal", "nro_terminal", "serial", "serial number",
    # Maquininha / código da maquina
    "código da maquininha", "codigo da maquininha", "nº da maquininha", "numero da maquininha",
    "maquininha", "numero_serie", "num_serie", "nº série", "numero de série", "no_serie",
    # IDs de terminal
    "terminal_id", "codigo_terminal", "código_terminal", "numero_terminal", "número_terminal",
    "nsu_terminal", "store_pos_name", "numero do caixa (pos_id)", "numero do caixa", "pos_id",
    # PDV / Loja / Posto (SITEF, AbasteceAI, Xodó, Verificados)
    "pdv", "loja", "posto", "ponto de venda", "ponto venda",
    # SITEF específico
    "terminal lógico", "terminal logico", "código loja", "codigo loja",
    "descrição loja", "descricao loja", "código do terminal", "codigo do terminal",
    # GetNet específico
    "número do terminal", "numero do terminal", "número terminal", "numero terminal",
    # Premmia / Posto específico
    "cód. do posto", "cod. do posto", "código do posto", "codigo do posto",
    # Stone específico
    "n de serie", "n° de série", "n. de serie", "numero de serie", "stonecode", "stone id",
    # Rede Frota — placa como identificador do veículo/terminal
    "placa",
    # Expers / Granito
    "estabelecimento", "pdv granito",
    # Outros
    "identificador", "id_loja", "id loja", "numero do caixa"
])


# ═══════════════════════════════════════════════════════════════════════════════
# AUXILIARES DE NORMALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def remover_acentos(texto: str) -> str:
    """Remove acentuação gráfica de uma string."""
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def normalizar_para_busca(texto: str) -> str:
    """Normaliza strings de cabeçalho para comparação semântica robusta."""
    s = remover_acentos(texto).strip().lower().rstrip(':').strip()
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE INGESTÃO
# ═══════════════════════════════════════════════════════════════════════════════

def detectar_encoding(caminho_arquivo: str) -> str:
    """Detecta o encoding de um arquivo usando chardet."""
    tamanho_amostra = 50_000
    with open(caminho_arquivo, "rb") as f:
        amostra = f.read(tamanho_amostra)
    resultado = chardet.detect(amostra)
    encoding = resultado.get("encoding", "utf-8")
    confianca = resultado.get("confidence", 0.0)
    if encoding is None or confianca < 0.5:
        print(f"  [!] Encoding detectado com baixa confianca ({confianca:.0%}). Usando UTF-8.")
        return "utf-8"
    print(f"  [OK] Encoding detectado: {encoding} (confianca: {confianca:.0%})")
    return encoding


def detectar_linhas_ignorar(caminho_arquivo: str, encoding: str) -> int:
    """Analisa as primeiras linhas do arquivo para pular cabeçalhos de metadados."""
    separadores = [";", ",", "\t"]
    chaves_data = VARIACOES_DATA
    chaves_valor = VARIACOES_BRUTO | VARIACOES_LIQUIDO | VARIACOES_REPASSE | VARIACOES_TAXA
    try:
        with open(caminho_arquivo, "r", encoding=encoding, errors="ignore") as f:
            for i in range(40):
                linha = f.readline()
                if not linha:
                    break
                for sep in separadores:
                    partes = [p.strip().lower() for p in linha.split(sep)]
                    tem_data = any(p in chaves_data for p in partes)
                    tem_valor = any(p in chaves_valor or any(cv in p for cv in chaves_valor) for p in partes)
                    if tem_data and tem_valor:
                        if i > 0:
                            print(f"  [!] Detectadas {i} linha(s) de metadados a serem ignoradas no cabeçalho.")
                        return i
    except Exception as e:
        print(f"  [!] Erro ao detectar linhas a ignorar: {e}")
    return 0


def promover_cabecalho_excel(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Promove a linha que contém data e valores a cabeçalho do DataFrame."""
    chaves_data = {normalizar_para_busca(v) for v in VARIACOES_DATA}
    chaves_valor = {normalizar_para_busca(v) for v in VARIACOES_BRUTO | VARIACOES_LIQUIDO | VARIACOES_REPASSE | VARIACOES_TAXA}

    cols_normalizadas = [normalizar_para_busca(c) for c in df.columns]
    tem_data = any(c in chaves_data for c in cols_normalizadas)
    tem_valor = any(c in chaves_valor or any(cv in c for cv in chaves_valor) for c in cols_normalizadas)

    if tem_data and tem_valor:
        return df, 2

    for i in range(min(40, len(df))):
        linha = [normalizar_para_busca(val) for val in df.iloc[i].fillna("").tolist()]
        tem_data_linha = any(p in chaves_data for p in linha)
        tem_valor_linha = any(p in chaves_valor or any(cv in p for cv in chaves_valor) for p in linha)
        if tem_data_linha and tem_valor_linha:
            print(f"  [!] Detectadas {i + 1} linha(s) de metadados ignoradas no Excel.")
            novas_colunas = df.iloc[i].tolist()
            novas_colunas = [str(c).strip() if pd.notna(c) and str(c).strip() != "" else f"Unnamed_{idx}" for idx, c in enumerate(novas_colunas)]
            df_slice = df.iloc[i+1:].copy()
            df_slice.columns = novas_colunas
            return df_slice, i + 2
    return df, 2


def obter_melhor_sheet(sheet_names: list[str]) -> str:
    """Seleciona dinamicamente a aba mais provável de conter transações."""
    keywords = ["recebimentos", "vendas", "transacoes", "transações", "movimentacao", "movimentação", 
                "lancamentos", "lançamentos", "extrato", "relatorio", "relatório", "venda", "recebimento", "detalhes"]
    for sheet in sheet_names:
        s_low = sheet.lower()
        if any(kw in s_low for kw in keywords):
            if "instru" not in s_low and "como usar" not in s_low and "help" not in s_low:
                return sheet
    for sheet in sheet_names:
        s_low = sheet.lower()
        if "instru" not in s_low and "como usar" not in s_low and "help" not in s_low:
            return sheet
    return sheet_names[0]


def carregar_xlsx_via_xml(caminho_arquivo: str, sheet_target_name: str = None) -> pd.DataFrame:
    """Leitura direta do XML interno do .xlsx para contornar problemas do openpyxl."""
    with zipfile.ZipFile(caminho_arquivo, 'r') as z:
        wb_xml = z.read("xl/workbook.xml")
        root_wb = ET.fromstring(wb_xml)
        ns = {
            'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        }
        sheets_info = []
        for sheet in root_wb.findall('.//main:sheet', ns):
            name = sheet.get('name')
            rId = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            sheets_info.append({"name": name, "rId": rId})
            
        if not sheets_info:
            raise ValueError("Nenhuma aba encontrada no arquivo Excel.")
            
        selected_sheet = sheets_info[0]
        if sheet_target_name:
            for s in sheets_info:
                if s["name"].lower().strip() == sheet_target_name.lower().strip():
                    selected_sheet = s
                    break
                    
        rels_xml = z.read("xl/_rels/workbook.xml.rels")
        root_rels = ET.fromstring(rels_xml)
        ns_rel = {'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}
        rels_map = {}
        for rel in root_rels.findall('.//rel:Relationship', ns_rel):
            rId = rel.get('Id')
            target = rel.get('Target')
            rels_map[rId] = target
            
        target_path = rels_map.get(selected_sheet["rId"])
        target_path = target_path.lstrip('/')
        zip_path = f"xl/{target_path}" if not target_path.startswith("xl/") else target_path
        zip_path = zip_path.replace("//", "/")
        
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss_xml = z.read("xl/sharedStrings.xml")
            root_ss = ET.fromstring(ss_xml)
            for si in root_ss.findall('.//main:si', ns):
                t_elements = si.findall('.//main:t', ns)
                val = "".join([t.text for t in t_elements if t.text is not None])
                shared_strings.append(val)
                
        sheet_xml = z.read(zip_path)
        root_sheet = ET.fromstring(sheet_xml)
        
        data_dict = {}
        max_row = 0
        max_col_idx = 0
        
        def col_to_idx(col_str):
            exp = 0
            idx = 0
            for char in reversed(col_str):
                idx += (ord(char) - 64) * (26 ** exp)
                exp += 1
            return idx - 1
            
        for row in root_sheet.findall('.//main:row', ns):
            r_idx = int(row.get('r')) - 1
            max_row = max(max_row, r_idx + 1)
            row_data = {}
            for cell in row.findall('.//main:c', ns):
                r_ref = cell.get('r')
                col_ref = "".join([c for c in r_ref if c.isalpha()])
                c_idx = col_to_idx(col_ref)
                max_col_idx = max(max_col_idx, c_idx + 1)
                
                t_type = cell.get('t')
                val_el = cell.find('main:v', ns)
                
                if val_el is not None and val_el.text is not None:
                    raw_val = val_el.text
                    if t_type == 's':
                        try:
                            val = shared_strings[int(raw_val)]
                        except (ValueError, IndexError):
                            val = raw_val
                    else:
                        val = raw_val
                else:
                    inline_t = cell.find('.//main:is/main:t', ns)
                    if inline_t is not None and inline_t.text is not None:
                        val = inline_t.text
                    else:
                        val = ""
                row_data[c_idx] = val
            data_dict[r_idx] = row_data
            
        grid = []
        for r in range(max_row):
            row_data = data_dict.get(r, {})
            row_list = [row_data.get(c, "") for c in range(max_col_idx)]
            grid.append(row_list)
            
        df = pd.DataFrame(grid)
        return df


def carregar_spreadsheet_ml(caminho_arquivo: str) -> pd.DataFrame:
    """Lê documentos legados baseados em SpreadsheetML 2003 XML."""
    with open(caminho_arquivo, "rb") as f_in:
        content_bytes = f_in.read()
        
    for enc in ["utf-8", "cp1252", "latin-1"]:
        try:
            content_str = content_bytes.decode(enc)
            break
        except Exception:
            continue
    else:
        content_str = content_bytes.decode("utf-8", errors="ignore")
        
    # Unescape HTML entities (e.g. &ccedil;, &nbsp;) that break standard XML parsing
    import html
    content_unescaped = html.unescape(content_str)
    content_unescaped = re.sub(r"&(?!(amp|lt|gt|quot|apos);)", "&amp;", content_unescaped)
    
    try:
        root = ET.fromstring(content_unescaped)
    except Exception as e:
        # Fallback using BeautifulSoup if ElementTree parsing fails
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content_unescaped, "xml")
            rows_data = []
            table = soup.find('Table') or soup.find('table')
            if table is not None:
                for row in table.find_all(['Row', 'row']):
                    row_list = []
                    for cell in row.find_all(['Cell', 'cell']):
                        index = cell.get('ss:Index') or cell.get('Index')
                        if index:
                            idx = int(index) - 1
                            while len(row_list) < idx:
                                row_list.append("")
                        data_el = cell.find(['Data', 'data'])
                        if data_el is not None and data_el.text is not None:
                            row_list.append(data_el.text.strip())
                        else:
                            row_list.append("")
                    rows_data.append(row_list)
            if rows_data:
                max_len = max(len(r) for r in rows_data)
                for r in rows_data:
                    while len(r) < max_len:
                        r.append("")
                return pd.DataFrame(rows_data)
        except Exception:
            pass
        raise e
        
    ns_uri = 'urn:schemas-microsoft-com:office:spreadsheet'
    table = root.find(f'.//{{{ns_uri}}}Table')
    if table is None:
        table = root.find('.//Table')
        if table is None:
            raise ValueError("Tabela não encontrada no XML SpreadsheetML.")
            
    rows_data = []
    for row in table.findall(f'.//{{{ns_uri}}}Row'):
        row_list = []
        for cell in row.findall(f'.//{{{ns_uri}}}Cell'):
            index = cell.get(f'{{{ns_uri}}}Index')
            if index:
                idx = int(index) - 1
                while len(row_list) < idx:
                    row_list.append("")
            
            data_el = cell.find(f'.//{{{ns_uri}}}Data')
            if data_el is not None and data_el.text is not None:
                row_list.append(data_el.text.strip())
            else:
                row_list.append("")
        rows_data.append(row_list)
        
    if not rows_data:
        raise ValueError("Nenhum registro encontrado na tabela XML.")
        
    max_len = max(len(r) for r in rows_data)
    for r in rows_data:
        while len(r) < max_len:
            r.append("")
            
    return pd.DataFrame(rows_data)


def inline_quotes_wrapped(line: str) -> bool:
    line_strip = line.strip()
    return line_strip.startswith('"') and line_strip.endswith('"') and ',"' in line_strip


def carregar_arquivo(caminho_arquivo: str) -> pd.DataFrame:
    """Carrega de forma genérica e robusta planilhas (XLSX, XLS, CSV, TXT, XML)."""
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")
        
    extensao = caminho.suffix.lower()
    is_vspague = "vspague_" in caminho.name.lower()
    
    # ── Assinatura Especial: Brinks headerless Excel
    if "brinks" in caminho_arquivo.lower() or "brinks" in caminho.parent.name.lower():
        print("  [OK] Brinks headerless Excel detectado.")
        try:
            df = pd.read_excel(caminho_arquivo, header=None, dtype=str)
            df = df.rename(columns={
                2: "data",
                5: "hora",
                4: "valor",
                1: "terminal"
            })
            df["linha_arquivo"] = df.index + 1
            return df
        except Exception as e:
            print(f"  [!] Falha na assinatura especial Brinks: {e}")
    
    # ── Assinatura Especial: Destaxa VSPague (CSV sem cabeçalho)
    if is_vspague and not caminho.name.lower().endswith(".zip"):
        # verificar se é na verdade um ZIP com extensão .csv
        try:
            with open(caminho_arquivo, "rb") as f_in:
                head = f_in.read(4)
            is_zip = head.startswith(b"PK\x03\x04")
        except Exception:
            is_zip = False
            
        if not is_zip:
            print("  [OK] Destaxa VSPague headerless CSV detectado.")
            encoding_detectado = detectar_encoding(caminho_arquivo)
            df = pd.read_csv(caminho_arquivo, header=None, sep=';', encoding=encoding_detectado or 'latin-1', dtype=str)
            df = df.rename(columns={
                1: "data_transacao",
                19: "valor_bruto",
                24: "valor_taxa",
                26: "valor_liquido"
            })
            df["linha_arquivo"] = df.index + 1
            return df

    try:
        with open(caminho_arquivo, "rb") as f_in:
            head = f_in.read(200)
    except Exception:
        head = b""
        
    is_zip = head.startswith(b"PK\x03\x04")
    is_xml = (b"<?xml" in head or b"<Workbook" in head) and not is_zip
    is_html = (b"<html" in head or b"<table" in head.lower() or b"<body" in head.lower()) and not is_zip
    
    # Tratar como Excel se a extensão for do tipo planilha ou se a assinatura do arquivo for PK, XML ou HTML
    if extensao in {".xlsx", ".xls"} or is_zip or is_xml or is_html:
        sheet_name = None
        if not is_xml and not is_html:
            try:
                if is_zip or extensao == ".xlsx":
                    with zipfile.ZipFile(caminho_arquivo, 'r') as z:
                        wb_xml = z.read("xl/workbook.xml")
                        root_wb = ET.fromstring(wb_xml)
                        ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                        sheet_names = [sheet.get('name') for sheet in root_wb.findall('.//main:sheet', ns)]
                else:
                    xl = pd.ExcelFile(caminho_arquivo)
                    sheet_names = xl.sheet_names
                sheet_name = obter_melhor_sheet(sheet_names)
                print(f"  [OK] Aba selecionada: '{sheet_name}' de {sheet_names}")
            except Exception:
                pass
                
        header_val = None if is_vspague else 0
        
        if is_xml:
            print("  [OK] SpreadsheetML XML detectado.")
            df = carregar_spreadsheet_ml(caminho_arquivo)
            if not is_vspague:
                df, offset = promover_cabecalho_excel(df)
            else:
                offset = 1
            df['linha_arquivo'] = df.index + offset
            return df
        elif is_html:
            print("  [OK] Tabela HTML disfarçada de Excel detectada.")
            tables = pd.read_html(caminho_arquivo)
            if not tables:
                raise ValueError("Nenhuma tabela encontrada no HTML.")
            df = tables[0]
            if not is_vspague:
                df, offset = promover_cabecalho_excel(df)
            else:
                offset = 1
            df['linha_arquivo'] = df.index + offset
            return df
        else:
            # 1. Tentar openpyxl
            try:
                df = pd.read_excel(caminho_arquivo, sheet_name=sheet_name, dtype=str, engine='openpyxl', header=header_val)
                if not is_vspague:
                    df, offset = promover_cabecalho_excel(df)
                else:
                    offset = 1
                df['linha_arquivo'] = df.index + offset
                return df
            except Exception as err_openpyxl:
                # 2. Tentar xlrd
                try:
                    df = pd.read_excel(caminho_arquivo, sheet_name=sheet_name, dtype=str, engine='xlrd', header=header_val)
                    if not is_vspague:
                        df, offset = promover_cabecalho_excel(df)
                    else:
                        offset = 1
                    df['linha_arquivo'] = df.index + offset
                    return df
                except Exception as err_xlrd:
                    # 3. Fallback XML
                    try:
                        df = carregar_xlsx_via_xml(caminho_arquivo, sheet_name)
                        if not is_vspague:
                            df, offset = promover_cabecalho_excel(df)
                        else:
                            offset = 1
                        df['linha_arquivo'] = df.index + offset
                        return df
                    except Exception as err_xml:
                        raise ValueError(f"Não foi possível ler o arquivo Excel: {err_openpyxl} | {err_xlrd} | {err_xml}")
    else:
        # Carregar CSV/TXT
        encoding_detectado = detectar_encoding(caminho_arquivo)
        encodings_tentar = [encoding_detectado] if encoding_detectado else []
        for fallback in ["cp1252", "latin-1", "utf-8", "utf-8-sig"]:
            if fallback not in encodings_tentar:
                encodings_tentar.append(fallback)
                
        erro_final = None
        for enc in encodings_tentar:
            try:
                skiprows = detectar_linhas_ignorar(caminho_arquivo, enc)
                
                # Tratar caso o arquivo CSV esteja malformado com aspas ao redor da linha inteira
                try:
                    with open(caminho_arquivo, "r", encoding=enc, errors="ignore") as f:
                        first_line = f.readline()
                    if inline_quotes_wrapped(first_line):
                        print("  [!] Detectado CSV malformado com aspas externas. Sanitizando em memória...")
                        import io
                        with open(caminho_arquivo, "r", encoding=enc, errors="ignore") as f:
                            sanitized_lines = []
                            for line in f:
                                line_strip = line.strip()
                                if line_strip.startswith('"') and line_strip.endswith('"'):
                                    line_strip = line_strip[1:-1].replace('""', '"')
                                sanitized_lines.append(line_strip + "\n")
                        sanitized_content = "".join(sanitized_lines)
                        df = pd.read_csv(io.StringIO(sanitized_content), sep=",", engine="python", dtype=str, skiprows=skiprows, index_col=False)
                        df['linha_arquivo'] = np.arange(len(df)) + skiprows + 2
                        return df
                except Exception as e_san:
                    print(f"  [!] Erro ao sanitizar CSV em memória: {e_san}")
                
                # Tentar ler com separadores comuns primeiro
                for sep in [None, ";", ",", "\t"]:
                    try:
                        df = pd.read_csv(caminho_arquivo, sep=sep, engine="python", encoding=enc, dtype=str, skiprows=skiprows, index_col=False)
                        if len(df.columns) > 1:
                            df['linha_arquivo'] = np.arange(len(df)) + skiprows + 2
                            return df
                    except Exception:
                        pass
                        
                # Fallback: ler com sep=None (inferncia) se outros falharam ou resultaram em 1 única coluna
                df = pd.read_csv(caminho_arquivo, sep=None, engine="python", encoding=enc, dtype=str, skiprows=skiprows, index_col=False)
                df['linha_arquivo'] = np.arange(len(df)) + skiprows + 2
                return df
            except Exception as e:
                erro_final = e
        raise ValueError(f"Não foi possível carregar o arquivo CSV/TXT: {erro_final}")


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE TRANSFORMAÇÃO E MAPEAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

def mapear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Mapeia dinamicamente e renomeia as colunas para o padrão do conciliador."""
    # Achatar colunas do tipo MultiIndex/tuplas para strings simples
    if isinstance(df.columns, pd.MultiIndex) or (len(df.columns) > 0 and isinstance(df.columns[0], tuple)):
        new_cols = []
        for col in df.columns:
            chosen = ""
            for part in col:
                part_str = str(part).strip()
                if part_str and not part_str.lower().startswith("unnamed"):
                    chosen = part_str
                    break
            if not chosen:
                chosen = str(col[0]) if col else "unnamed"
            new_cols.append(chosen)
        df.columns = new_cols

    # Detectar se é VSPague com base nas colunas numéricas ou no primeiro elemento sendo um NSU/ID
    # Requer 28+ colunas E os 10 primeiros cabeçalhos sendo todos numéricos para evitar falsos positivos
    is_vspague = False
    if len(df.columns) >= 28:
        first_col_str = str(df.columns[0]).strip()
        if first_col_str.isdigit() and len(first_col_str) >= 10:
            is_vspague = True
        elif all(str(c).strip().isdigit() for c in list(df.columns)[:10]):
            is_vspague = True

    if is_vspague:
        print("  [OK] Renomeando colunas do formato VSPague...")
        orig_cols = list(df.columns)
        df = df.rename(columns={
            orig_cols[1]: "data_transacao",
            orig_cols[19]: "valor_bruto",
            orig_cols[24]: "valor_taxa",
            orig_cols[26]: "valor_liquido"
        })
        if "data_transacao" not in df.columns:
            raise ValueError("Coluna de data ('data_transacao') nao encontrada após o mapeamento.")
        return df

    colunas_originais = {normalizar_para_busca(col): col for col in df.columns}
    renomeacao = {}
    
    def buscar_candidato(variacoes, target):
        sorted_vars = sorted(variacoes, key=len, reverse=True)
        for var in sorted_vars:
            norm_var = normalizar_para_busca(var)
            if norm_var in colunas_originais:
                col_orig = colunas_originais[norm_var]
                if col_orig not in renomeacao:
                    renomeacao[col_orig] = target
                    return col_orig
        return None

    col_data = buscar_candidato(VARIACOES_DATA_PRIMARIA, "data_transacao")
    if col_data is None:
        col_data = buscar_candidato(VARIACOES_DATA_SECUNDARIA, "data_transacao")
    buscar_candidato(VARIACOES_BRUTO, "valor_bruto")
    buscar_candidato(VARIACOES_LIQUIDO, "valor_liquido")
    buscar_candidato(VARIACOES_REPASSE, "valor_repasse")
    buscar_candidato(VARIACOES_TAXA, "valor_taxa")
    buscar_candidato(VARIACOES_PRODUTO, "produto_original")
    buscar_candidato(VARIACOES_TERMINAL, "terminal_original")
    
    col_hora = None
    for var in sorted(VARIACOES_HORA, key=len, reverse=True):
        norm_var = normalizar_para_busca(var)
        if norm_var in colunas_originais:
            col_orig = colunas_originais[norm_var]
            if col_orig != col_data:
                col_hora = col_orig
                break
                
    if renomeacao:
        df = df.rename(columns=renomeacao)
        mapeados = ", ".join(f"'{k}' \u2192 '{v}'" for k, v in renomeacao.items())
        print(f"  [OK] Colunas mapeadas: {mapeados}")

    # Detec\u00e7\u00e3o de serial Excel: se data_transacao tem n\u00fameros no range v\u00e1lido (1-2958465),
    # converte para timestamps reais. Corrige arquivos como GetNet PIX que armazenam datas como seriais.
    if "data_transacao" in df.columns:
        amostra_dt = df["data_transacao"].dropna().head(30)
        try:
            numericos = pd.to_numeric(amostra_dt, errors="coerce").dropna()
            seriais_ok = numericos[(numericos >= 1) & (numericos <= 2958465)]
            if len(numericos) > 0 and len(seriais_ok) >= len(numericos) * 0.8:
                print(f"  [FIX] Seriais Excel detectados na coluna de data ({len(seriais_ok)} valores). Convertendo...")
                _EXCEL_EPOCH = pd.Timestamp("1899-12-30")
                def _serial_to_ts(v):
                    try:
                        n = float(v)
                        if 1 <= n <= 2958465:
                            return _EXCEL_EPOCH + pd.Timedelta(days=int(n)) + pd.Timedelta(seconds=round((n % 1) * 86400))
                    except Exception:
                        pass
                    return v
                df["data_transacao"] = df["data_transacao"].apply(_serial_to_ts)
        except Exception:
            pass

    if "data_transacao" in df.columns and col_hora is not None:
        # Validar que a coluna hora realmente contém valores de tempo (HH:MM)
        # Evita mesclar colunas de texto como 'Nome', 'CPF' que foram mal-detectadas como hora
        hora_amostra = df[col_hora].dropna().astype(str).head(50)
        if len(hora_amostra) > 0:
            tempo_validos = hora_amostra.str.match(r'^\s*\d{1,2}:\d{2}', na=False).sum()
            if tempo_validos / len(hora_amostra) < 0.25:
                print(f"  [!] Coluna hora '{col_hora}' descartada (apenas {tempo_validos}/{len(hora_amostra)} valores com padrão HH:MM).")
                col_hora = None

    if "data_transacao" in df.columns and col_hora is not None:
        def extrair_apenas_hora(val_str):
            val_str = str(val_str).strip()
            if not val_str or val_str.lower() in ("nan", "nat", "<na>"):
                return "00:00:00"
            if " " in val_str:
                val_str = val_str.split(" ")[-1]
            match = re.search(r"(\d{2}:\d{2}(:\d{2})?)", val_str)
            if match:
                return match.group(1)
            return "00:00:00"

        def extrair_apenas_data(val_str):
            val_str = str(val_str).strip()
            if not val_str or val_str.lower() in ("nan", "nat", "<na>"):
                return ""
            if " " in val_str:
                val_str = val_str.split(" ")[0]
            return val_str

        df["data_transacao"] = df["data_transacao"].fillna("").astype(str)
        df[col_hora] = df[col_hora].fillna("").astype(str)
        
        datas = df["data_transacao"].apply(extrair_apenas_data)
        horas = df[col_hora].apply(extrair_apenas_hora)
        
        df["data_transacao"] = datas.where(datas != "", "")
        df.loc[datas != "", "data_transacao"] = datas + " " + horas
        
    if "data_transacao" not in df.columns:
        raise ValueError("Coluna de data ('data_transacao') nao encontrada após o mapeamento.")
        
    valores_mapeados = [col for col in ["valor_bruto", "valor_liquido", "valor_repasse", "valor_taxa"] if col in df.columns]
    if not valores_mapeados:
        raise ValueError("Nenhuma coluna de valor encontrada na planilha.")
        
    return df


def limpar_valor_monetario(serie: pd.Series) -> pd.Series:
    """Converte valores monetários em formato brasileiro ou americano para float."""
    s = serie.astype(str).str.strip()
    s = s.str.replace("R$", "", regex=False)
    s = s.str.replace(r"\s+", "", regex=True)

    # Corrigir trailing minus (ex: "100.00-")
    s = s.str.replace(r'^(.*?)\s*-\s*$', r'-\1', regex=True)
    
    mask_br = s.str.contains(',', na=False)
    s.loc[mask_br] = s.loc[mask_br].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    
    return pd.to_numeric(s, errors='coerce')


def extrair_ano_do_arquivo(caminho_arquivo: str, df: pd.DataFrame = None) -> int:
    """Infere o ano a partir do nome do arquivo, metadados ou última data de modificação."""
    if not caminho_arquivo:
        return datetime.datetime.now().year
    path = Path(caminho_arquivo)
    years = re.findall(r"\b(20\d{2})\b", str(path.resolve()))
    if years:
        return int(years[0])
    if df is not None:
        for col in ["idOperacao", "txId", "id_operacao", "tx_id"]:
            if col in df.columns:
                non_nulls = df[col].dropna()
                if not non_nulls.empty:
                    val = str(non_nulls.iloc[0])
                    matches = re.findall(r"\b(20\d{2})\b", val)
                    if matches:
                        return int(matches[0])
                    matches_long = re.findall(r"(20\d{2})\d{4}", val)
                    if matches_long:
                        return int(matches_long[0])
    try:
        mtime = os.path.getmtime(caminho_arquivo)
        return datetime.datetime.fromtimestamp(mtime).year
    except Exception:
        return datetime.datetime.now().year


def limpar_data_customizada(val: str, ano: int) -> str:
    """Higieniza datas em formatos atípicos (ex: '17/Ago • 23h58m52s')."""
    if not isinstance(val, str):
        return val

    val_clean = val.strip()
    # Strip invisible/zero-width Unicode characters (ZWNJ, ZWS, BOM, NBSP, SHY, etc.)
    # Causa: Vegas Card exporta datas com \u200c na frente, virando 100% NaT
    val_clean = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\xa0\u00ad\u2028\u2029]+', '', val_clean).strip()
    val_clean = re.sub(r'\s+às\s+', ' ', val_clean, flags=re.IGNORECASE)
    val_clean = re.sub(r'\s+as\s+', ' ', val_clean, flags=re.IGNORECASE)
    meses = {
        "jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
        "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"
    }
    
    if "•" in val_clean or re.search(r"[a-zA-Z]{3}", val_clean):
        val_clean = val_clean.replace("•", " ").replace("  ", " ")
        val_clean = re.sub(r"(\d{1,2})h(\d{1,2})m(\d{1,2})s", r"\1:\2:\3", val_clean)
        val_clean = re.sub(r"(\d{1,2})h(\d{1,2})m", r"\1:\2:00", val_clean)
        val_clean = re.sub(r"(\d{1,2})h", r"\1:00:00", val_clean)
        
        has_4_digit_year = re.search(r"\b(20\d{2})\b", val_clean)
        for pt_m, num in meses.items():
            val_clean = re.sub(pt_m, num, val_clean, flags=re.IGNORECASE)
            
        if has_4_digit_year:
            return val_clean
            
        m = re.search(r"(\d{1,2})\s*[-/]?\s*(\d{2})", val_clean)
        if m:
            dia = m.group(1).zfill(2)
            mes = m.group(2)
            time_part = ""
            time_match = re.search(r"(\d{1,2}:\d{1,2}(:\d{1,2})?)", val_clean)
            if time_match:
                time_part = " " + time_match.group(1)
            return f"{dia}/{mes}/{ano}{time_part}"
            
    return val_clean


# Strings que representam ausência de data — filtradas antes do parse
_INVALID_DATE_STRINGS = frozenset(["nan", "nat", "<na>", "none", "n/a", "nd", "-", "", "null"])

# Padrão regex para linhas de rodapé/metadados que nunca são datas válidas
_RODAPE_RE = re.compile(
    r'^(total|filtro|valor\s*total|subtotal|m[eé]dia|observa|legenda|nota|relat[oó]|emiss[aã]o|'
    r'nome\b|cpf\b|tipo\b|forma\b|rede\b|status\b|n[uú]mero\b|descri|'
    r'dep[oó]sito|depos|c[eé]dula|envelope|recibo|lan[cç]amento\b)',
    re.IGNORECASE
)


def normalizar_datas(serie: pd.Series, caminho_arquivo: str = None) -> pd.Series:
    """Converte e padroniza datas de múltiplos formatos para datetime64."""
    serie_str = serie.astype(str).str.strip()
    # Strip invisible/zero-width Unicode chars em toda a série antes de qualquer parse
    serie_str = serie_str.str.replace(
        r'[\u200b\u200c\u200d\u200e\u200f\ufeff\xa0\u00ad]+', '', regex=True
    ).str.strip()

    # Marcar valores inválidos (vazios, null, NaT) e linhas de rodapé/metadados
    mascara_invalida = serie_str.str.lower().isin(_INVALID_DATE_STRINGS)
    mascara_rodape = serie_str.apply(
        lambda x: bool(_RODAPE_RE.match(x)) if (x and pd.notna(x)) else False
    )
    mascara_excluir = mascara_invalida | mascara_rodape

    ano = extrair_ano_do_arquivo(caminho_arquivo)
    serie_cleaned = serie_str.apply(lambda x: limpar_data_customizada(x, ano))
    serie_cleaned.loc[mascara_excluir] = ''

    validas = serie_cleaned[~mascara_excluir]
    padrao_iso = validas.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", na=False)
    proporcao_iso = padrao_iso.sum() / max(len(validas), 1)

    if proporcao_iso > 0.5:
        resultado = pd.to_datetime(serie_cleaned, format="mixed", dayfirst=False, errors="coerce")
    else:
        resultado = pd.to_datetime(serie_cleaned, format="mixed", dayfirst=True, errors="coerce")

    nulos = resultado.isna().sum() - int(mascara_excluir.sum())
    if nulos > 0:
        print(f"  [!] {nulos} data(s) nao puderam ser convertidas (NaT)")
    return resultado



# ═══════════════════════════════════════════════════════════════════════════════
# CONCILIAÇÃO E RELATÓRIO
# ═══════════════════════════════════════════════════════════════════════════════

def formatar_moeda_br(valor) -> str:
    """Formata valor (int, float ou None) em string no padrão monetário brasileiro."""
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"
    if np.isnan(valor):
        return "R$ 0,00"
    negativo = valor < 0
    valor_abs = abs(valor)
    parte_inteira = int(valor_abs)
    parte_decimal = round((valor_abs - parte_inteira) * 100)
    inteira_str = f"{parte_inteira:,}".replace(",", ".")
    resultado = f"R$ {inteira_str},{parte_decimal:02d}"
    if negativo:
        resultado = f"-{resultado}"
    return resultado


def conciliar(caminho_arquivo: str, data_inicio: str, data_fim: str) -> None:
    """Executa o pipeline completo de conciliação financeira."""
    nome_arquivo = Path(caminho_arquivo).name
    largura = 60

    print()
    print("=" * largura)
    print("  CONCILIACAO FINANCEIRA - PIPELINE DE PROCESSAMENTO")
    print("=" * largura)
    print(f"\n  Arquivo: {nome_arquivo}")
    print(f"  Periodo: {data_inicio} a {data_fim}\n")

    # ── Etapa 1: Carregar arquivo
    print("─" * largura)
    print("  [1/4] Carregando arquivo...")
    df = carregar_arquivo(caminho_arquivo)
    total_bruto = len(df)
    print(f"  [OK] {total_bruto} registros carregados")

    # ── Etapa 2: Mapear colunas
    print("\n" + "─" * largura)
    print("  [2/4] Mapeando colunas...")
    df = mapear_colunas(df)

    # ── Etapa 3: Limpar valores monetários
    print("\n" + "─" * largura)
    print("  [3/4] Limpando valores monetários...")
    colunas_originais = set(df.columns)
    
    for col in ["valor_bruto", "valor_liquido", "valor_repasse", "valor_taxa"]:
        if col in df.columns:
            df[col] = limpar_valor_monetario(df[col])
        else:
            df[col] = np.nan

    # Dedução inteligente
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
        
    # Se a taxa foi mapeada mas os valores contêm taxas/percentuais inconsistentes (como 1.05% representado por 105), calcula a taxa real
    if "valor_taxa" in colunas_originais and "valor_bruto" in colunas_originais and "valor_liquido" in colunas_originais:
        diferenca_real = df["valor_bruto"] - df["valor_liquido"]
        # Threshold de R$1,00 por transação para filtrar adquirentes que arredondam a taxa
        inconsistente = (df["valor_taxa"].fillna(0) - diferenca_real).abs() > 1.0
        proporcao_inconsistente = inconsistente.sum() / max(len(df), 1)
        if proporcao_inconsistente > 0.5:  # Só substitui se mais de 50% das linhas inconsistentes
            print("  [!] Detectada coluna de taxa com valores inconsistentes ou formato percentual. Utilizando Bruto - Líquido.")
            df["valor_taxa"] = diferenca_real
            
    if "valor_taxa" not in colunas_originais:
        df["valor_taxa"] = df["valor_bruto"] - df["valor_liquido"]

    df["valor_transacao"] = df["valor_liquido"]

    # Validação Matemática
    df["diferenca_validacao"] = ((df["valor_bruto"] - df["valor_taxa"]) - df["valor_liquido"]).abs()
    excedeu_tolerancia = (df["diferenca_validacao"] > 0.02).any()
    if excedeu_tolerancia:
        print("  [AVISO] Discrepancia financeira detectada! Excedeu a tolerancia de R$ 0,02.")

    nulos_valor = df["valor_transacao"].isna().sum()
    if nulos_valor > 0:
        print(f"  [!] {nulos_valor} valor(es) nao puderam ser convertidos (NaN)")

    # ── Etapa 4: Normalizar datas
    print("\n" + "─" * largura)
    print("  [4/4] Normalizando datas...")
    df["data_transacao"] = normalizar_datas(df["data_transacao"], caminho_arquivo)

    # ── Filtragem por período
    dt_inicio = pd.to_datetime(data_inicio, dayfirst=True)
    dt_fim = pd.to_datetime(data_fim, dayfirst=True)
    if dt_fim.second == 0 or dt_fim.second == 59:
        dt_fim = dt_fim.replace(second=58)

    mascara_periodo = (df["data_transacao"] >= dt_inicio) & (df["data_transacao"] <= dt_fim)
    mascara_valido = df["valor_transacao"].notna() & df["data_transacao"].notna()

    df_filtrado = df[mascara_periodo & mascara_valido].copy()

    # ── Cálculos
    total_no_periodo = len(df_filtrado)
    volume_total = df_filtrado["valor_transacao"].sum()

    estornos = df_filtrado[df_filtrado["valor_transacao"] < 0]
    qtd_estornos = len(estornos)
    valor_estornos = estornos["valor_transacao"].sum() if qtd_estornos > 0 else 0.0

    transacoes_positivas = df_filtrado[df_filtrado["valor_transacao"] > 0]
    qtd_positivas = len(transacoes_positivas)
    valor_positivas = transacoes_positivas["valor_transacao"].sum() if qtd_positivas > 0 else 0.0

    descartados = total_bruto - len(df[mascara_valido])

    # Imprimir registros inválidos ou nulos descartados
    df_descartados = df[~mascara_valido].copy()
    if not df_descartados.empty:
        colunas_reais = [c for c in df.columns if c not in ["valor_transacao", "data_transacao", "diferenca_validacao", "linha_arquivo"]]
        print("\n" + "─" * largura)
        print("  REGISTROS DESCARTADOS (NULOS OU INVÁLIDOS):")
        for _, row in df_descartados.iterrows():
            linha_num = row["linha_arquivo"]
            row_dict = {k: v for k, v in row.to_dict().items() if k in colunas_reais and pd.notna(v) and str(v).strip() != ""}
            row_str = ", ".join(f"{k}: '{v}'" for k, v in row_dict.items())
            print(f"  [Linha {linha_num}]: {row_str}")

    # ── Relatório Final
    print("\n")
    print("╔" + "═" * (largura - 2) + "╗")
    print("║" + "RELATORIO DE CONCILIACAO FINANCEIRA".center(largura - 2) + "║")
    print("╠" + "═" * (largura - 2) + "╣")
    print("║" + f"  Arquivo:     {nome_arquivo}".ljust(largura - 2) + "║")
    print("║" + f"  Periodo:     {data_inicio} a {data_fim}".ljust(largura - 2) + "║")
    print("║" + f"  Registros:   {total_bruto} no arquivo".ljust(largura - 2) + "║")
    print("║" + f"  No periodo:  {total_no_periodo} transacoes".ljust(largura - 2) + "║")
    print("║" + f"  Estornos:    {qtd_estornos} transacao(oes) negativa(s)".ljust(largura - 2) + "║")
    print("║" + f"  Invalidos:   {descartados} registro(s) descartados (NaT/NaN)".ljust(largura - 2) + "║")
    print("╠" + "═" * (largura - 2) + "╣")
    print("║" + f"  Creditos:    {formatar_moeda_br(valor_positivas)} ({qtd_positivas} transacoes)".ljust(largura - 2) + "║")
    print("║" + f"  Estornos:    {formatar_moeda_br(valor_estornos)} ({qtd_estornos} transacoes)".ljust(largura - 2) + "║")
    print("╠" + "═" * (largura - 2) + "╣")
    print("║" + f"  VOLUME TOTAL:  {formatar_moeda_br(volume_total)}".ljust(largura - 2) + "║")
    print("╚" + "═" * (largura - 2) + "╝")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI — INTERFACE DE LINHA DE COMANDO
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Ponto de entrada do script via linha de comando."""
    parser = argparse.ArgumentParser(
        description=(
            "Conciliacao Financeira - Auditoria de relatorios de adquirentes "
            "(Cielo, Stone, PagSeguro, etc.)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos de uso:\n"
            "  python conciliacao.py relatorio_cielo.csv 01/01/2024 31/12/2024\n"
            "  python conciliacao.py vendas_stone.xlsx 15/03/2024 15/06/2024\n"
        ),
    )

    parser.add_argument(
        "arquivo",
        type=str,
        help="Caminho para o arquivo de relatorio do adquirente (CSV, TXT ou XLSX)",
    )
    parser.add_argument(
        "data_inicio",
        type=str,
        help="Data de inicio do periodo no formato DD/MM/AAAA",
    )
    parser.add_argument(
        "data_fim",
        type=str,
        help="Data de fim do periodo no formato DD/MM/AAAA",
    )

    args = parser.parse_args()

    if not Path(args.arquivo).exists():
        print(f"\n[ERRO] Arquivo '{args.arquivo}' nao encontrado.")
        sys.exit(1)

    try:
        pd.to_datetime(args.data_inicio, dayfirst=True)
        pd.to_datetime(args.data_fim, dayfirst=True)
    except (ValueError, TypeError):
        print(
            f"\n[ERRO] Datas invalidas. Use o formato DD/MM/AAAA.\n"
            f"   Recebido: inicio='{args.data_inicio}', fim='{args.data_fim}'"
        )
        sys.exit(1)

    conciliar(args.arquivo, args.data_inicio, args.data_fim)


if __name__ == "__main__":
    main()
