import argparse
import math
import pandas as pd
import time
import os
import re
import threading
import json
import unicodedata
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import gspread
from google.oauth2.service_account import Credentials

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# ============================================================
# 1. CONFIGURAÇÕES DE PLANILHAS E GOOGLE SHEETS
# ============================================================
ID_PLANILHA_ENTRADA = "1AKk5NmzBqrMJ6JmKe5XCjj6XqRU7FFIyh0xqN1KQvBw" 
ID_PLANILHA_SAIDA = "1ctHPw2mRao_mm9OznkFiD6ko1AvS9lHc85lgA7ApFjE"

ABA_ENTRADA = "Checkout"
ABA_SAIDA = "Resultados"

COLUNA_NOME = "Nome comercial"
COLUNA_STORE_ID = "Store ID"
COLUNA_URL = "URL_PRODUTO"
COLUNAS_BACKUP = ["URL_BACKUP_1", "URL_BACKUP_2"]

MAX_WORKERS = 2  
LISTA_CEPS = ["05417001", "30112000", "89010000"]

TIMEOUT_PAGINA = 35
TIMEOUT_DOM_PRONTO = 20
TIMEOUT_CALCULADORA = 18
TIMEOUT_INPUT_CEP = 15
JANELA_CAPTURA_FRETE = 30

# ============================================================
# 2. CLASSIFICADOR DE FRETE (v6.4)
# ============================================================
MODALIDADES_VALIDAS = ['Econômico', 'Rápido', 'SEDEX', 'PAC', 'Envio Módico', 'Padrão', 'Expresso', 'Mini', 'Promocional', 'Full', 'Registro Módico', 'Rodoviário', 'Porta x Porta']
PALAVRAS_MODALIDADE = {'econômico': 'Econômico', 'economico': 'Econômico', 'eco': 'Econômico', 'rápido': 'Rápido', 'rapido': 'Rápido', 'fast': 'Rápido', 'sedex': 'SEDEX', 'pac': 'PAC', 'módico': 'Envio Módico', 'modico': 'Envio Módico', 'expresso': 'Expresso', 'expressa': 'Expresso', 'express': 'Expresso', 'mini': 'Mini', 'promocional': 'Promocional', 'promo': 'Promocional', 'full': 'Full', 'fulfillment': 'Full', 'fba': 'Full', 'rodoviário': 'Rodoviário', 'rodoviaria': 'Rodoviário', 'rodoviária': 'Rodoviário', 'standard': 'Padrão', 'default': 'Padrão', 'padrão': 'Padrão', 'padrao': 'Padrão', 'normal': 'Padrão', 'convencional': 'Padrão', 'porta a porta': 'Porta x Porta', 'porta x porta': 'Porta x Porta'}
MESES_EXTENSO = {'jan': 1, 'janeiro': 1, 'fev': 2, 'fevereiro': 2, 'mar': 3, 'março': 3, 'marco': 3, 'abr': 4, 'abril': 4, 'mai': 5, 'maio': 5, 'jun': 6, 'junho': 6, 'jul': 7, 'julho': 7, 'ago': 8, 'agosto': 8, 'set': 9, 'setembro': 9, 'out': 10, 'outubro': 10, 'nov': 11, 'novembro': 11, 'dez': 12, 'dezembro': 12}
TRANSPORTADORAS = ['Jadlog', 'Correios', 'J&T Express', 'J&T', 'JeT', 'Loggi', 'Total Express', 'Braspress', 'TNT', 'DHL', 'FedEx', 'UPS', 'Azul Cargo', 'Azul Logistica', 'LATAM CARGO ÉFÁCIL', 'LATAM CARGO', 'GolLog', 'RTE Rodonaves', 'Rodonaves', 'RTE', 'Jamef', 'Sequoia', 'Rapidão Cometa', 'Bertolini', 'Solistica', 'Brudam', 'Directlog', 'Direct Log', 'Mercado Envios', 'Shopee Xpress', 'Kangu', 'Bee Express', 'MOVVI', 'Movvi', 'Uello', '99Frete', '99 Frete', 'iFood Envios', 'Olist Envios Pax', 'Olist Envios', 'Expresso São Miguel', 'Buslog', 'Pajuçara', 'Flex', 'FM Transportes', 'Direcional', 'Lalamove', 'MagaLog', 'Postex Express', 'Postex', 'Postal BR', 'Dialogo', 'Smart2c', 'Smart2C', 'G2M Cargo', 'CW Log', 'Transoliveira', 'Blumenau Express', 'Total Points', 'Daytona Express', 'Multi Express', 'Entrega Koerich', 'Tex Courier Ltda', 'Tex Courier', 'Alfa VIP', 'Alfa Transportes', 'Reunidas Cargas', 'AC Express Transportes', 'AC Express', 'Carvalima', 'Coopex', 'Super Frete', 'Cruzeiro do Sul', 'Ícaro', 'Icaro', 'VITOM', 'Taybe Express', 'Aceville Transportes', 'Aceville', 'Disk&Tenha', 'Disk Tenha', 'Disk e Tenha', 'Disketenha', 'Disktenha', 'Disk & Tenha', 'Le Bambino', 'LEBAMBINO', 'Bambino', 'Arlete Transportes', 'Arlete', 'Azurelog', 'Fluorita', 'Gritsch', 'JJSUL', 'Leomar', 'Montti', 'Pacote', 'Rede Sul', 'Ropek', 'Schreiber', 'TO COM PRESSA', 'Epacket', 'Pronta Entrega Copa', 'Frete Turbo', 'Frete Nacional', 'Envio Econômico', 'J3 Envios', 'J3 Express', 'J3', 'ONLOG', 'Onlog', 'Envio IN Makeup', 'Sinergia Log', 'ID Logistics', 'IDLog', 'CargoBR', 'Cargo BR', 'KamiLog', 'LogPost', 'SM Express', 'Kingston Log']
INTEGRADORES = ['Melhor Envio', 'SmartEnvios', 'Frenet', 'Kangu', 'Bling', 'Envio Fácil', 'Envio Facil', 'Frete Rápido', 'Frete Rapido', 'Nuvem Envio', 'Olist Envios', 'Olist Envios Pax', 'Shippy', 'Shippy Pro', 'Super Frete', 'Central do Frete', 'Frete Certo', 'eFrete', 'Envio Barato', 'Cliquer', 'Envios']
ESTADOS_BR = ['São Paulo', 'Rio de Janeiro', 'Minas Gerais', 'Santa Catarina', 'Paraná', 'Rio Grande do Sul', 'Bahia', 'Ceará', 'Pernambuco', 'Goiás', 'Distrito Federal', 'Amazonas', 'Pará', 'Espírito Santo', 'Maranhão', 'Piauí', 'Alagoas', 'Sergipe', 'Paraíba', 'Rio Grande do Norte', 'Mato Grosso', 'Mato Grosso do Sul', 'Rondônia', 'Acre', 'Amapá', 'Roraima', 'Tocantins']
REGIOES_BR = ['Sul', 'Sudeste', 'Nordeste', 'Norte', 'Centro-Oeste']
PALAVRAS_GENERICAS_INICIO = ['Frete', 'Loja', 'Envio', 'Entrega', 'Receba', 'Grátis', 'FRETE', 'Econômico', 'Expresso', 'Rápido', 'Standard', 'Promocional', 'Sudeste', 'Sul', 'Norte', 'Nordeste', 'Brasil', 'Centro-Oeste', 'SP', 'RJ', 'MG', 'PR', 'SC', 'RS', 'BA', 'CE', 'GO', 'PE', 'Ônibus', 'Onibus', 'Rodoviária', 'Rodoviaria', 'Mini', 'Ultra', 'Sameday']
PALAVRAS_PRAZO_OU_LIXO = {'chega', 'chegará', 'chegara', 'chegando', 'previsão', 'previsao', 'previsto', 'entrega', 'entregue', 'receba', 'em', 'até', 'ate', 'entre', 'hoje', 'amanhã', 'amanha', 'segunda', 'terça', 'terca', 'quarta', 'quinta', 'sexta', 'sábado', 'sabado', 'domingo'}
PALAVRAS_MODALIDADE_PARA_SEPARAR = {'express': 'Expresso', 'expresso': 'Expresso', 'expressa': 'Expresso', 'econômico': 'Econômico', 'economico': 'Econômico', 'econômica': 'Econômico', 'standard': 'Padrão', 'padrão': 'Padrão', 'padrao': 'Padrão', 'rápido': 'Rápido', 'rapido': 'Rápido', 'rápida': 'Rápido', 'promocional': 'Promocional'}
NOMES_PROTEGIDOS = {'envio padrão', 'envio módico', 'envio promocional', 'envio customizado', 'envio econômico', 'envio in makeup', 'frete fixo', 'frete nacional', 'frete turbo', 'frete grátis', 'entrega full', 'entrega local', 'entrega normal', 'entrega econômica', 'entrega expressa', 'entrega rápida', 'transporte econômico', 'transporte rápido', 'mini envios', 'encomenda rodoviária', 'sameday', 'motoboy', 'convencional', 'mandaê', 'retirada', 'stone', 'a10', 'gfl', 'log manager', 'gênesis', 'pronta entrega copa', 'to com pressa', 'epacket', 'j3', 'j3 envios', 'j3 express', 'onlog'}
NORMALIZACAO_NOMES = {'icaro': 'Ícaro', 'ícaro': 'Ícaro', 'latam cargo éfácil': 'LATAM CARGO', 'latam cargo efacil': 'LATAM CARGO', 'latam cargo': 'LATAM CARGO', 'latam': 'LATAM CARGO', 'azul': 'Azul Cargo', 'azul cargo': 'Azul Cargo', 'smart2c': 'Smart2c', 'disk tenha': 'Disk&Tenha', 'disk&tenha': 'Disk&Tenha', 'disketenha': 'Disk&Tenha', 'disktenha': 'Disk&Tenha', 'disk e tenha': 'Disk&Tenha', 'disk & tenha': 'Disk&Tenha', 'lebambino': 'Le Bambino', 'bambino': 'Le Bambino', 'le bambino': 'Le Bambino', 'aceville transportes': 'Aceville', 'alfa transportes': 'Alfa VIP', 'arlete transportes': 'Arlete', 'postex': 'Postex Express', 'rodonaves': 'RTE Rodonaves', 'rte': 'RTE Rodonaves', 'econômico': 'Entrega Econômica', 'economico': 'Entrega Econômica', 'normal': 'Entrega Normal', 'rápido': 'Entrega Rápida', 'rapido': 'Entrega Rápida', 'expresso': 'Entrega Expressa', 'expressa': 'Entrega Expressa', 'transportadora': 'Envio Customizado', 'rodoviário ii': 'Encomenda Rodoviária', 'rodoviario ii': 'Encomenda Rodoviária', 'nacional': 'Frete Nacional', 'fixo': 'Frete Fixo', 'j3 envios': 'J3', 'j3 express': 'J3', 'movvi': 'MOVVI', 'onlog': 'ONLOG', 'direct log': 'Directlog', '99 frete': '99Frete'}

REGRAS_ESPECIFICAS = [
    (r'^Frete\s+Gr[áa]tis\b', 'Frete Grátis', None, True),
    (r'^FRETE\s+GR[ÁA]TIS\b', 'Frete Grátis', None, True),
    (r'^Frete\s+\d+,\d{2}\b', 'Frete Fixo', 'Padrão', False),
    (r'^Olist\s+Super\s+Econ[ôo]mic[oa]?', 'Olist Envios', 'Econômico', False),
    (r'^Estimativa\s+de\s+prazo', 'Envio Padrão', 'Padrão', False),
    (r'^Envio\s+R[áa]pid[oa]?\b', 'Entrega Rápida', 'Rápido', False),
    (r'^Envio\s+Express(?:o|a)?\b', 'Entrega Expressa', 'Expresso', False),
    (r'^Super\s+Express(?:o|a)?\b', 'Entrega Expressa', 'Expresso', False),
    (r'^Entrega\s+Amanh[ãa]\b', 'Entrega Rápida', 'Rápido', False),
    (r'^Entrega\s+Express(?:o|a)?\b', 'Entrega Expressa', 'Expresso', False),
    (r'^Entrega\s+R[áa]pid[oa]?\b', 'Entrega Rápida', 'Rápido', False),
    (r'^Entrega\s+Econ[ôo]mic[oa]?\b', 'Entrega Econômica', 'Econômico', False),
    (r'^Entrega\s+Normal\b', 'Entrega Normal', 'Padrão', False),
    (r'^Entrega\s+Padr[ãa]o\b', 'Envio Padrão', 'Padrão', False),
    (r'^Entrega\s+Full\b', 'Entrega Full', 'Full', False),
    (r'^Transporte\s+Econ[ôo]mic[oa]?\b', 'Transporte Econômico', 'Econômico', False),
    (r'^Transporte\s+R[áa]pid[oa]?\b', 'Transporte Rápido', 'Rápido', False),
    (r'^Mais\s+Econ[ôo]mic', 'Entrega Econômica', 'Econômico', False),
    (r'^Mais\s+R[áa]pid', 'Entrega Rápida', 'Rápido', False),
    (r'^Ultra\s+R[áa]pid', 'Entrega Rápida', 'Rápido', False),
    (r'^Frete\s+R[áa]pid[oa]?\b', 'Entrega Rápida', 'Rápido', False),
    (r'^Frete\s+Express(?:o|a)?\b', 'Entrega Expressa', 'Expresso', False),
    (r'^Frete\s+Econ[ôo]mic[oa]?\b', 'Entrega Econômica', 'Econômico', False),
    (r'^Frete\s+Promocional\b', 'Envio Promocional', 'Promocional', False),
    (r'^Econ[ôo]mic[oa]?\b', 'Entrega Econômica', 'Econômico', False),
    (r'^Express(?:o|a)?\b', 'Entrega Expressa', 'Expresso', False),
    (r'^R[áa]pid[oa]?\b', 'Entrega Rápida', 'Rápido', False),
    (r'^Normal\b', 'Entrega Normal', 'Padrão', False),
    (r'^Convencional\b', 'Convencional', 'Padrão', False),
    (r'^(?:Envio\s+)?Padr[ãa]o\b', 'Envio Padrão', 'Padrão', False),
    (r'^Standard\b', 'Envio Padrão', 'Padrão', False),
    (r'^Mini\s+Envios?\b', 'Mini Envios', 'Mini', False),
    (r'^ENVIO\s+MINI', 'Mini Envios', 'Mini', False),
    (r'^Custo\s+e\s+prazo\s+de\s+entrega', 'Envio Padrão', None, True),
    (r'^Entrega\s+direta', 'Entrega Local', 'Padrão', False),
    (r'^ENTREGA\s+NO\s+BR[ÁA]S', 'Encomenda Rodoviária', 'Rodoviário', False),
    (r'^(?:BH\s+e\s+Regi[ãa]o|S[ãa]o\s+Paulo\s+Capital|Belo\s+Horizonte|Capital\s+e\s+Regi[ãa]o|Entrega\s+(?:Belo|S[ãa]o|Capital)|Entrega\s+própria)', 'Entrega Local', 'Padrão', False),
    (r'^(?:SEDEX|Sedex)\b', 'Correios', 'SEDEX', False),
    (r'^PAC\b', 'Correios', 'PAC', False),
    (r'^Registro\s+Módico', 'Correios', 'Registro Módico', False),
    (r'^Encomenda\s+SEDEX', 'Correios', 'SEDEX', False),
    (r'^Encomenda\s+PAC', 'Correios', 'PAC', False),
    (r'^FIXO\b', 'Frete Fixo', 'Padrão', False),
    (r'^FRETE\s+[A-ZÀ-Ý][A-ZÀ-Ý\s]{2,}', 'Frete Fixo', 'Padrão', False),
    (r'^Frete\s+(?:S[ãa]o Paulo|SP|Sudeste|Sul|Norte|Nordeste|Centro)', 'Frete Fixo', 'Padrão', False),
    (r'^Encomenda\s+Rodovi[áa]ria', 'Encomenda Rodoviária', 'Rodoviário', False),
]

_PT_PAL = r'(?:[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)*)'

def extrair_valor(texto):
    if not texto: return '0.00'
    if re.search(r'\b(?:grátis|gratis|gratuito|gratuita|free|isento|cortesia|sem\s+custo|por\s+conta\s+do)\b', texto, re.IGNORECASE): return '0.00'
    if re.search(r'R\$\s*0(?:[.,]0{1,2})?(?![\d,.])', texto): return '0.00'
    m = re.search(r'R\$\s*([\d.]*\d+,\d{2})', texto)
    if m:
        v = m.group(1).replace('.', '').replace(',', '.')
        try: return f'{float(v):.2f}'
        except ValueError: pass
    m = re.search(r'R\$\s*(\d+\.\d{2})(?!\d)', texto)
    if m:
        try: return f'{float(m.group(1)):.2f}'
        except ValueError: pass
    m = re.search(r'R\$\s*(\d{1,4})(?!\d|[,.])', texto)
    if m:
        try: return f'{float(m.group(1)):.2f}'
        except ValueError: pass
    m = re.search(r'(\d+,\d{2})\s*reais?', texto, re.IGNORECASE)
    if m:
        try: return f'{float(m.group(1).replace(",", ".")):.2f}'
        except ValueError: pass
    return '0.00'

def calcular_diferenca_dias(dia_c, mes_c, dia_f, mes_f, ano):
    try:
        d_c = datetime(ano, mes_c, dia_c)
        d_f = datetime(ano, mes_f, dia_f)
        if d_f < d_c: d_f = datetime(ano + 1, mes_f, dia_f)
        return (d_f - d_c).days
    except ValueError: return -1

def _prazo_valido(dia_c, mes_c, dia_f, mes_f, ano_c, limite=90):
    prazo = calcular_diferenca_dias(dia_c, mes_c, dia_f, mes_f, ano_c)
    if 0 <= prazo <= limite: return str(prazo)
    return None

def limpar_prazo_producao(texto):
    limpo = re.sub(r'\+\s*\d+\s*(?:dias?\s*úteis?|dias?)\s*(?:de\s*)?(?:produção|producao|confecção|confeccao)', '', texto, flags=re.IGNORECASE)
    limpo = re.sub(r'APÓS\s+(?:O\s+)?PRAZO\s+DE\s+(?:CONFECÇÃO|CONFECCAO|PRODUÇÃO|PRODUCAO)\s*\+?\s*\d*\s*dias?(?:\s+úteis?)?', '', limpo, flags=re.IGNORECASE)
    limpo = re.sub(r'prazo\s+de\s+(?:produção|producao|confecção|confeccao)[\s:]+\d+\s*dias?', '', limpo, flags=re.IGNORECASE)
    return limpo

def extrair_prazo(texto, data_consulta):
    if not texto: return '0'
    tl = limpar_prazo_producao(texto)
    for pat in [r'Prazo\s+estimado[:\s]+(\d+)\s*dia(?:\(s\)|s)?', r'Prazo\s+de\s+entrega[:\s]+(?:de\s+)?(?:até\s+)?(\d+)\s*dia(?:\(s\)|s)?', r'Prazo\s+de\s+até\s+(\d+)\s*dia(?:\(s\)|s)?', r'até\s+(\d+)\s+úte(?:is|l)\b', r'até\s+(\d+)\s*dia(?:\(s\)|s)?', r'Previsto\s+para\s+(\d+)\s*dia(?!\s*[/])']:
        m = re.search(pat, tl, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            if 0 <= n <= 90: return str(n)

    m = re.search(r'Prazo\s+do\s+frete[:\s]+(\d+)\s+(?:e|a)\s+(\d+)\s*dias?', tl, re.IGNORECASE)
    if m: return str(max(int(m.group(1)), int(m.group(2))))

    tem_dc = False
    dia_c = mes_c = ano_c = 0
    try:
        p = data_consulta.split('/')
        dia_c, mes_c, ano_c = int(p[0]), int(p[1]), int(p[2])
        tem_dc = True
    except (ValueError, IndexError): pass

    if tem_dc:
        m = re.search(r'Previsto\s+para\s+(\d{1,2})[/.-](\d{1,2})(?:[/.-]\d{2,4})?', tl, re.IGNORECASE)
        if m:
            p = _prazo_valido(dia_c, mes_c, int(m.group(1)), int(m.group(2)), ano_c)
            if p: return p
        m = re.search(r'entre\s+(?:[A-Za-zÀ-ÿ,-]+\s+)?(\d{1,2})[/.-](\d{1,2})\s+e\s+(?:[A-Za-zÀ-ÿ,-]+\s+)?(\d{1,2})[/.-](\d{1,2})', tl, re.IGNORECASE)
        if m:
            p = _prazo_valido(dia_c, mes_c, int(m.group(3)), int(m.group(4)), ano_c)
            if p: return p
        m = re.search(rf'entre\s+(?:{_PT_PAL},?\s+)?(\d{{1,2}})(?:\s+de\s+{_PT_PAL})?\.?\s+e\s+(?:{_PT_PAL},?\s+)?(\d{{1,2}})\s+de\s+({_PT_PAL})', tl, re.IGNORECASE)
        if m:
            mes_str = m.group(3).lower()[:3]
            if mes_str in MESES_EXTENSO:
                p = _prazo_valido(dia_c, mes_c, int(m.group(2)), MESES_EXTENSO[mes_str], ano_c)
                if p: return p
        m = re.search(r'(\d{1,2})[/.-](\d{1,2})\s+[àa]\s+(\d{1,2})[/.-](\d{1,2})', tl, re.IGNORECASE)
        if m:
            p = _prazo_valido(dia_c, mes_c, int(m.group(3)), int(m.group(4)), ano_c)
            if p: return p
        m = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}\s+até\s+(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}', tl, re.IGNORECASE)
        if m:
            p = _prazo_valido(dia_c, mes_c, int(m.group(3)), int(m.group(4)), ano_c)
            if p: return p
        m = re.search(r'(?:chega|previsão de chegada|previsao de chegada|chegará|chegara|chegada|chega até).*?(\d{1,2})[/.-](\d{1,2})(?![/.-]\d)', tl, re.IGNORECASE)
        if m:
            p = _prazo_valido(dia_c, mes_c, int(m.group(1)), int(m.group(2)), ano_c)
            if p: return p
        m = re.search(rf'(?:chega(?:rá|ra)?|previs(?:ão|ao)|previsto|chegada)\s+(?:{_PT_PAL},?\s+)?(\d{{1,2}})\s+de\s+({_PT_PAL})', tl, re.IGNORECASE)
        if m:
            mes_str = m.group(2).lower()[:3]
            if mes_str in MESES_EXTENSO:
                p = _prazo_valido(dia_c, mes_c, int(m.group(1)), MESES_EXTENSO[mes_str], ano_c)
                if p: return p
        m = re.search(r'\bem\s+(\d{1,2})[/.-](\d{1,2})(?:[/.-]\d{2,4})?\b', tl, re.IGNORECASE)
        if m:
            p = _prazo_valido(dia_c, mes_c, int(m.group(1)), int(m.group(2)), ano_c)
            if p: return p

    if re.search(r'em\s+até\s+(?:2|3)\s*h(?:oras?)?|mesmo\s+dia|sameday|same\s+day|entrega\s+hoje|receba\s+hoje|(?:chega|chegar[áa])\s+(?:até\s+)?hoje', tl, re.IGNORECASE): return '0'
    if re.search(r'em\s+até\s+24\s*h(?:oras?)?|entrega\s+em\s+até\s+24\s*horas?|amanh[ãa]|próximo\s+dia\s+útil|dia\s+seguinte', tl, re.IGNORECASE): return '1'
    if re.search(r'Chega\s+entre\s+hoje\s+e\s+1\s+dia\s+útil', tl, re.IGNORECASE): return '1'

    fallback = _extrair_prazo_sem_data_consulta(tl)
    if fallback != '0': return fallback

    if tem_dc:
        m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b', tl)
        if m:
            p = _prazo_valido(dia_c, mes_c, int(m.group(1)), int(m.group(2)), ano_c)
            if p: return p
        m = re.search(r'(?:^|[\s\-])\s*(\d{1,2})[/.-](\d{1,2})\b(?![/.-])', tl)
        if m:
            dia_f, mes_f = int(m.group(1)), int(m.group(2))
            if 1 <= dia_f <= 31 and 1 <= mes_f <= 12:
                p = _prazo_valido(dia_c, mes_c, dia_f, mes_f, ano_c)
                if p: return p
    return '0'

def _extrair_prazo_sem_data_consulta(tl):
    m = re.search(r'entre\s+(\d+)\s+(?:e|a)\s+(\d+)\s*dias?', tl, re.IGNORECASE)
    if m: return str(max(int(m.group(1)), int(m.group(2))))
    m = re.search(r'~\s*(\d+)\s*dias?(?:\s+úteis?)?', tl, re.IGNORECASE)
    if m: return str(int(m.group(1)))
    m = re.search(r'\b(\d+)\s+a\s+(\d+)\s*dias?(?:\s+úteis?)?', tl, re.IGNORECASE)
    if m: return str(max(int(m.group(1)), int(m.group(2))))
    m = re.search(r'(?:chega|chegará|chegara|receba)?\s*em\s+(?:até\s+)?(\d+)\s*dias?(?:\s+úte(?:is|l))?', tl, re.IGNORECASE)
    if m: return str(int(m.group(1)))
    m = re.search(r'por\s+R\$\s*[\d.,]+\s*-\s*(\d+)\s*dias?(?:\s+úteis?)?', tl, re.IGNORECASE)
    if m: return str(int(m.group(1)))
    m = re.search(r'de\s+(\d+)\s+a\s+(\d+)\s*dias?', tl, re.IGNORECASE)
    if m: return str(max(int(m.group(1)), int(m.group(2))))
    if re.search(r'em\s+1\s+dia\s+útil', tl, re.IGNORECASE): return '1'
    m = re.search(r'(\d+)\s*dia\(s\)\s*útil', tl, re.IGNORECASE)
    if m: return str(int(m.group(1)))
    m = re.search(r'\b(\d+)\s*dia(?:\s+útil)?(?!\s*\(s\))(?!\w)', tl, re.IGNORECASE)
    if m: return str(int(m.group(1)))
    m = re.search(r'\b(\d+)\s*dias?\s+úteis?\b', tl, re.IGNORECASE)
    if m: return str(int(m.group(1)))
    m = re.search(r'R\$\s*[\d.]*\d+,\d{2}\s+(\d{1,2})(?:\s|$)', tl)
    if m:
        pc = int(m.group(1))
        if 1 <= pc <= 60: return str(pc)
    return '0'

def detectar_integrador_via(texto):
    m = re.search(r'\(?\s*via\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]+?)(?:\s*\)|\s+-|\s+\(|$)', texto, re.IGNORECASE)
    if not m: return None
    nome = re.sub(r'\s+(Chega|chegará|chegara|-|R\$).*$', '', m.group(1).strip(), flags=re.IGNORECASE).strip()
    for integ in INTEGRADORES:
        if integ.lower() in nome.lower(): return integ
    return nome

def detectar_retirada(texto):
    if re.search(r'retirada|retirar|retire|pickup|buscar na loja|ponto de retirada|PUDO|RETIRAR NA LOJA|RETIRA NA LOJA', texto, re.IGNORECASE): return True
    tem_endereco = bool(re.search(r'(?:Rua|R\.|Av\.|Avenida|Travessa|Estrada|Rodovia)\s+[A-Za-zÀ-ÿ][^,]*,?\s*\d+', texto, re.IGNORECASE) or re.search(r'\b\d{5}-?\d{3}\b', texto) or re.search(r'(?:Loja|loja)\s+[A-Za-zÀ-ÿ][\w\sÀ-ÿ]+\s*-\s*(?:R\.|Rua|Av\.|Avenida)', texto, re.IGNORECASE))
    tem_transp = any(re.search(rf'\b{re.escape(t)}\b', texto, re.IGNORECASE) for t in TRANSPORTADORAS)
    return tem_endereco and not tem_transp

def detectar_modalidade_no_texto(texto):
    if not texto: return 'Padrão'
    lt = texto.lower()
    lt_sem_acento = ''.join(c for c in unicodedata.normalize('NFD', lt) if unicodedata.category(c) != 'Mn')
    mapa = {
        'expresso': 'Expresso', 'expressa': 'Expresso', 'express': 'Expresso', 'economico': 'Econômico', 'economica': 'Econômico', 'eco': 'Econômico', 'rapido': 'Rápido', 'rapida': 'Rápido', 'fast': 'Rápido', 'sedex': 'SEDEX', 'pac': 'PAC', 'modico': 'Envio Módico', 'mini': 'Mini', 'promocional': 'Promocional', 'promo': 'Promocional', 'full': 'Full', 'fulfillment': 'Full', 'fba': 'Full', 'rodoviario': 'Rodoviário', 'rodoviaria': 'Rodoviário', 'standard': 'Padrão', 'default': 'Padrão', 'padrao': 'Padrão', 'convencional': 'Padrão', 'porta a porta': 'Porta x Porta', 'porta x porta': 'Porta x Porta'
    }
    for p, mod in mapa.items():
        if re.search(rf'\b{re.escape(p)}\b', lt_sem_acento): return mod
    return 'Padrão'

def normalizar_modalidade(palavra):
    if not palavra: return 'Padrão'
    lower = palavra.lower().strip()
    if lower in PALAVRAS_MODALIDADE: return PALAVRAS_MODALIDADE[lower]
    for k, v in PALAVRAS_MODALIDADE.items():
        if k in lower: return v
    return 'Padrão'

def separar_modalidade_do_nome(nome):
    if not nome: return nome, None
    nome = nome.strip()
    nome_lower = nome.lower()
    if nome_lower in [t.lower() for t in TRANSPORTADORAS]: return nome, None
    if nome_lower in NOMES_PROTEGIDOS: return nome, None
    palavras = nome.rsplit(maxsplit=1)
    if len(palavras) == 2:
        ultima = palavras[1].lower()
        if ultima in PALAVRAS_MODALIDADE_PARA_SEPARAR: return palavras[0].strip(), PALAVRAS_MODALIDADE_PARA_SEPARAR[ultima]
    return nome, None

def normalizar_nome_transportadora(nome):
    if not nome: return nome
    nome_lower = nome.strip().lower()
    if nome_lower in NORMALIZACAO_NOMES: return NORMALIZACAO_NOMES[nome_lower]
    return nome.strip()

def normalizar_integrador(integrador, transportadora):
    if not integrador or integrador == 'Direto': return 'Direto'
    if transportadora and integrador.strip().lower() == transportadora.strip().lower(): return 'Direto'
    mapa = {'correios': 'Correios', 'super frete': 'Super Frete', 'superfrete': 'Super Frete', 'melhor envio': 'Melhor Envio', 'smartenvios': 'SmartEnvios', 'olist envios': 'Olist Envios', 'olist envios pax': 'Olist Envios Pax', 'nuvem envio': 'Nuvem Envio'}
    il = integrador.strip().lower()
    if il in mapa:
        novo = mapa[il]
        if transportadora and novo.lower() == transportadora.strip().lower(): return 'Direto'
        return novo
    return integrador.strip()

def buscar_transportadora_em_qualquer_posicao(texto):
    for t in sorted(TRANSPORTADORAS, key=len, reverse=True):
        if re.search(rf'\b{re.escape(t)}\b', texto, re.IGNORECASE): return t
    return None

def e_palavra_generica(palavra):
    return any(palavra.lower() == g.lower() for g in PALAVRAS_GENERICAS_INICIO)

def texto_tem_indicacao_de_prazo(texto):
    if not texto: return False
    tl = limpar_prazo_producao(texto)
    return bool(re.search(r'\b(?:chega|chegar[áa]|prazo\s+de\s+entrega|dias?\s+úte(?:is|l)|hora|horas?|amanh[ãa]|hoje|previs[ãa]o|previsto)\b', tl, re.IGNORECASE))

def texto_indica_prazo_zero_esperado(texto):
    if not texto: return False
    return bool(re.search(r'(?:chega|chegar[áa]|receba)\s+(?:até\s+)?hoje|mesmo\s+dia|em\s+até\s+(?:2|3|24)\s*h(?:oras?)?|sameday|same\s+day|hoje\s+mesmo|receb[aer]\s+hoje', texto, re.IGNORECASE))

def texto_indica_valor_zero_esperado(texto):
    if not texto: return False
    return bool(re.search(r'excurs(?:ão|oes|ões)|combinar.*(?:WhatsApp|whats|entrega)|entrega\s+combinada|a\s+combinar|sob\s+consulta', texto, re.IGNORECASE))

def comeca_com_estado_ou_regiao(texto):
    for est in ESTADOS_BR:
        if re.match(rf'^{re.escape(est)}\b', texto, re.IGNORECASE): return True
    for reg in REGIOES_BR:
        if re.match(rf'^{re.escape(reg)}\s*[-(]', texto, re.IGNORECASE): return True
    return False

def _b(texto, transp, integ, mod, prazo, valor, precisa_llm=False):
    return {'transportadora': transp, 'integrador': integ, 'modalidade': mod, 'prazo': prazo, 'valor': valor, 'precisa_llm': precisa_llm}

def _classificar_nuvem(texto, prazo, valor):
    apos = re.split(r'Nuvem Envio', texto, maxsplit=1, flags=re.IGNORECASE)
    limpo = re.sub(r'^[\s\-:]+', '', apos[1] if len(apos) > 1 else '')
    m = re.match(r'([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ&]*)', limpo)
    if m:
        palavra = m.group(1)
        for t in TRANSPORTADORAS:
            primeiro = t.split(' ')[0]
            if palavra.lower() == t.lower() or palavra.lower() == primeiro.lower():
                apos_t = re.sub(r'^[\s\-:]+', '', limpo[len(palavra):])
                mm = re.match(r'([A-Za-zÀ-ÿ]+)', apos_t)
                mod = normalizar_modalidade(mm.group(1)) if mm else 'Padrão'
                return _b(texto, t, 'Nuvem Envio', mod, prazo, valor)
        if palavra.lower() in PALAVRAS_PRAZO_OU_LIXO: return _b(texto, 'Nuvem Envio', 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
        return _b(texto, 'Nuvem Envio', 'Direto', normalizar_modalidade(palavra), prazo, valor)
    return _b(texto, 'Nuvem Envio', 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)

def _classificar_olist(texto, prazo, valor, integrador_via):
    m = re.match(r'^(Olist Envios(?:\s+Pax)?)\s+([A-Za-zÀ-ÿ&]+)(?:\s+([A-Za-zÀ-ÿ]+))?', texto, re.IGNORECASE)
    if not m: return None
    olist_tipo = m.group(1).strip()
    poss_transp = m.group(2)
    poss_mod = m.group(3)
    for t in TRANSPORTADORAS:
        primeiro = t.split(' ')[0]
        if poss_transp.lower() == t.lower() or poss_transp.lower() == primeiro.lower():
            if not t.lower().startswith('olist'):
                mod = normalizar_modalidade(poss_mod) if poss_mod else 'Padrão'
                return _b(texto, t, olist_tipo, mod, prazo, valor)
    return _b(texto, olist_tipo, 'Direto', normalizar_modalidade(poss_mod) if poss_mod else 'Padrão', prazo, valor)

def _regras_especiais(texto, prazo, valor, integrador_via):
    m = re.match(r'^Jet(Standard|Express)', texto, re.IGNORECASE)
    if m: return _b(texto, 'JeT', integrador_via or 'Direto', 'Expresso' if m.group(1).lower() == 'express' else 'Padrão', prazo, valor)
    m = re.match(r'^(J&T|JeT)\s+(Express|Standard)', texto, re.IGNORECASE)
    if m: return _b(texto, 'JeT' if m.group(1).lower() == 'jet' else 'J&T', integrador_via or 'Direto', 'Expresso' if m.group(2).lower() == 'express' else 'Padrão', prazo, valor)
    if re.match(r'^Transportadora\s*[\(\|]', texto, re.IGNORECASE):
        if re.search(r'(?:via\s+)?(Gênesis|Genesis)', texto, re.IGNORECASE): return _b(texto, 'Gênesis', 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
    if re.match(r'^Stone\s+Entrega', texto, re.IGNORECASE): return _b(texto, 'Stone', 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
    if re.match(r'^A10\s+(?:Flash|Express|Mini)', texto, re.IGNORECASE):
        m = re.match(r'^A10\s+(\w+)(?:\s+(\w+))?', texto, re.IGNORECASE)
        prim = m.group(1).lower() if m else ''
        seg = m.group(2).lower() if m and m.group(2) else ''
        mod = 'Expresso' if prim == 'express' else ('Mini' if 'mini' in (prim, seg) else 'Rápido')
        return _b(texto, 'A10', 'Direto', mod, prazo, valor)
    if re.match(r'^GFL\s+', texto, re.IGNORECASE): return _b(texto, 'GFL', integrador_via or 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
    if re.match(r'^Log\s+Manager', texto, re.IGNORECASE): return _b(texto, 'Log Manager', integrador_via or 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
    if re.match(r'^Nacional\s*-\s*Frete\s+(?:Express(?:o|a)?)', texto, re.IGNORECASE): return _b(texto, 'Frete Nacional', 'Direto', 'Expresso', prazo, valor)
    if re.match(r'^Nacional\s*-\s*Frete', texto, re.IGNORECASE): return _b(texto, 'Frete Nacional', 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
    return None

def _detect_transp_inicio(texto):
    for t in sorted(TRANSPORTADORAS, key=len, reverse=True):
        if re.match(rf'^{re.escape(t)}\b', texto, re.IGNORECASE): return t
    return None

def _mod_apos_transp(texto, transp):
    apos = re.sub(r'^[\s\-:]+', '', texto[len(transp):])
    m = re.match(r'([A-Za-zÀ-ÿ]+)', apos)
    mod = normalizar_modalidade(m.group(1)) if m else 'Padrão'
    if mod == 'Padrão':
        fb = detectar_modalidade_no_texto(apos)
        if fb != 'Padrão': mod = fb
    return mod

def _heuristicas_fracas(texto, prazo, valor, integrador_via):
    if re.match(r'^Transportadora\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ&\s]+?)(?:\s*-|\s+Chega|$)', texto, re.IGNORECASE):
        m = re.match(r'^Transportadora\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ&\s]+?)(?:\s*-|\s+Chega|$)', texto, re.IGNORECASE)
        return _b(texto, m.group(1).strip(), integrador_via or 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
    if re.search(r'motoboy|VIA MOTOBOY|tele-entrega|entrega local|delivery', texto, re.IGNORECASE): return _b(texto, 'Motoboy', 'Direto', 'Padrão', prazo, valor)
    if re.search(r'sameday|same day|mesmo dia|receba hoje|em até 3h|entrega em até 24horas|em até 24h|chega\s+hoje', texto, re.IGNORECASE): return _b(texto, 'Sameday', 'Direto', 'Padrão', prazo, valor)
    if re.search(r'módico|modico', texto, re.IGNORECASE) and not re.search(r'Registro Módico', texto, re.IGNORECASE): return _b(texto, 'Envio Módico', 'Direto', 'Envio Módico', prazo, valor)
    if re.search(r'\bFull\b|ME Full|Fulfillment', texto, re.IGNORECASE): return _b(texto, 'Entrega Full', 'Direto', 'Full', prazo, valor)
    if re.search(r'Ônibus|Onibus|rodoviária|rodoviaria|Brás', texto, re.IGNORECASE): return _b(texto, 'Encomenda Rodoviária', 'Direto', 'Rodoviário', prazo, valor)
    if (re.search(r'FRETE\s+FIXO|Frete\s+Fixo|frete\s+fixo|FRETE\s+ÚNICO|Frete\s+Único|taxa\s+única|taxa\s+fixa|valor\s+fixo', texto, re.IGNORECASE) or re.search(r'Frete por R\$.*acima de R\$', texto, re.IGNORECASE)): return _b(texto, 'Frete Fixo', 'Direto', 'Padrão', prazo, valor)
    if comeca_com_estado_ou_regiao(texto): return _b(texto, 'Frete Fixo', 'Direto', 'Padrão', prazo, valor)
    if re.search(r'\bSEDEX\b', texto, re.IGNORECASE): return _b(texto, 'Correios', integrador_via or 'Direto', 'SEDEX', prazo, valor)
    if re.search(r'\bPAC\b', texto, re.IGNORECASE): return _b(texto, 'Correios', integrador_via or 'Direto', 'PAC', prazo, valor)
    if re.search(r'\bMINI\s+ENVIOS?\b', texto, re.IGNORECASE): return _b(texto, 'Mini Envios', 'Direto', 'Mini', prazo, valor)
    if re.search(r'a combinar|combinar com o vendedor|consulte o vendedor|indique sua transportadora|frete sob consulta|este frete não é gratuito|personalizada|especial', texto, re.IGNORECASE): return _b(texto, 'Envio Customizado', 'Direto', 'Padrão', prazo, valor)
    return None

def _fallback_inteligente(texto, prazo, valor, integrador_via):
    t = buscar_transportadora_em_qualquer_posicao(texto)
    if t: return _b(texto, t, integrador_via or 'Direto', detectar_modalidade_no_texto(texto), prazo, valor)
    m = re.match(r'^([A-ZÀ-Ý][A-Za-zÀ-ÿ&]+(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ&]+)?)\s*[-:]', texto)
    if m:
        nome = m.group(1).strip()
        primeira = nome.split()[0]
        if not e_palavra_generica(primeira):
            apos = re.sub(r'^[\s\-:]+', '', texto[len(nome):])
            mm = re.match(r'([A-Za-zÀ-ÿ]+)', apos)
            modalidade = normalizar_modalidade(mm.group(1)) if mm else 'Padrão'
            return _b(texto, nome, integrador_via or 'Direto', modalidade, prazo, valor)
    return None

def _pos_processar(resultado, texto_original):
    if resultado.get('transportadora'):
        nome_sep, mod_extra = separar_modalidade_do_nome(resultado['transportadora'])
        if mod_extra:
            resultado['transportadora'] = nome_sep
            if resultado.get('modalidade') in (None, '', 'Padrão'): resultado['modalidade'] = mod_extra
        resultado['transportadora'] = normalizar_nome_transportadora(resultado['transportadora'])

    if resultado.get('modalidade') in (None, '', 'Padrão'):
        mod_texto = detectar_modalidade_no_texto(texto_original)
        if mod_texto != 'Padrão': resultado['modalidade'] = mod_texto

    resultado['integrador'] = normalizar_integrador(resultado.get('integrador'), resultado.get('transportadora'))
    if resultado.get('modalidade') and resultado['modalidade'] not in MODALIDADES_VALIDAS: resultado['modalidade'] = 'Padrão'
    if resultado.get('transportadora') and resultado['transportadora'].lower() == 'direto': resultado['transportadora'] = 'Envio Customizado'
    if resultado['integrador'] == 'Direto': resultado['integrador_transportadora'] = resultado['transportadora']
    else: resultado['integrador_transportadora'] = f"{resultado['integrador']} {resultado['transportadora']}"
    return resultado

def classificar_frete(texto, data_consulta):
    texto_original = texto or ''
    texto = texto_original
    data_consulta = data_consulta or ''
    texto = re.sub(r'^[\s\-:•·,\.]+', '', texto)

    valor = extrair_valor(texto)
    prazo = extrair_prazo(texto, data_consulta)
    integrador_via = detectar_integrador_via(texto)

    if not integrador_via and re.search(r'\bSuper\s+Frete\b', texto, re.IGNORECASE): integrador_via = 'Super Frete'

    resultado = None
    if re.search(r'Mandaê|Mandae', texto, re.IGNORECASE):
        m = re.search(r'Mandaê[:\s\-]+([A-Za-zÀ-ÿ]+)', texto, re.IGNORECASE)
        modalidade = normalizar_modalidade(m.group(1)) if m else 'Padrão'
        resultado = _b(texto, 'Mandaê', integrador_via or 'Direto', modalidade, prazo, valor)
    elif re.search(r'Nuvem Envio', texto, re.IGNORECASE): resultado = _classificar_nuvem(texto, prazo, valor)
    elif detectar_retirada(texto): resultado = _b(texto, 'Retirada', 'Direto', 'Padrão', prazo, '0.00')
    elif re.match(r'^Olist Envios(?:\s+Pax)?\s+', texto, re.IGNORECASE): resultado = _classificar_olist(texto, prazo, valor, integrador_via)
    else: resultado = _regras_especiais(texto, prazo, valor, integrador_via)

    if resultado is None:
        for pat, transp, mod, usa_detec in REGRAS_ESPECIFICAS:
            if re.match(pat, texto, re.IGNORECASE):
                modalidade = mod if not usa_detec else detectar_modalidade_no_texto(texto)
                resultado = _b(texto, transp, 'Direto', modalidade, prazo, valor)
                break

    if resultado is None:
        t = _detect_transp_inicio(texto)
        if t:
            mod = _mod_apos_transp(texto, t)
            resultado = _b(texto, t, integrador_via or 'Direto', mod, prazo, valor)

    if resultado is None: resultado = _heuristicas_fracas(texto, prazo, valor, integrador_via)
    if resultado is None: resultado = _fallback_inteligente(texto, prazo, valor, integrador_via)
    if resultado is None:
        if valor == '0.00' and (re.search(r'\b(?:grátis|gratis|gratuito|free|isento|cortesia)\b', texto, re.IGNORECASE) or re.search(r'R\$\s*0(?:[.,]0{1,2})?(?![\d,.])', texto)):
            resultado = _b(texto, 'Frete Grátis', 'Direto', 'Padrão', prazo, '0.00')
        else:
            resultado = _b(texto, 'Envio Customizado', 'Direto', 'Padrão', prazo, valor, precisa_llm=True)
    return _pos_processar(resultado, texto_original)


# ============================================================
# 3. INTEGRAÇÃO DOS RESULTADOS (EXATAMENTE AS 11 COLUNAS)
# ============================================================
def padronizar_resultados(linha_original, cep, texto_frete):
    data_consulta = datetime.now().strftime("%d/%m/%Y")
    nome_comercial = linha_original.get(COLUNA_NOME, "")
    store_id = linha_original.get(COLUNA_STORE_ID, "")
    
    r = classificar_frete(texto_frete, data_consulta)
    
    linha_formatada = [
        data_consulta,                          # A: Data Consulta
        nome_comercial,                         # B: Nome Comercial
        store_id,                               # C: Store ID
        cep,                                    # D: CEP Consultado
        texto_frete,                            # E: Texto Frete
        r.get('transportadora', ''),            # F: Transportadora
        r.get('integrador', ''),                # G: Integrador
        r.get('integrador_transportadora', ''), # H: Integrador + Transportadora
        r.get('modalidade', ''),                # I: Modalidade
        r.get('prazo', ''),                     # J: Prazo
        r.get('valor', '')                      # K: Valor
    ]
    return linha_formatada


# ============================================================
# 4. SELENIUM CORE E AUTENTICAÇÃO
# ============================================================
def conectar_google_sheets():
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json:
        raise ValueError("ERRO: Credenciais do Google Sheets não encontradas nas variáveis de ambiente.")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
    return gspread.authorize(creds)

def configurar_driver(tentativas=3):
    ultimo_erro = None
    for tentativa in range(tentativas):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--incognito")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-background-networking")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--disable-translate")
            chrome_options.add_argument("--mute-audio")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)

            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.media_stream": 2,
                "profile.managed_default_content_settings.notifications": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.managed_default_content_settings.geolocation": 2,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
            chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

            # Usando Selenium Manager nativo (Sem webdriver-manager!)
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(TIMEOUT_PAGINA)

            try:
                driver.execute_cdp_cmd("Network.enable", {})
                driver.execute_cdp_cmd("Network.setBlockedURLs", {
                    "urls": ["*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot", "*.mp4", "*.webm", "*.mp3", "*.wav", "*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*google-analytics.com*", "*facebook.com/tr*", "*hotjar.com*", "*clarity.ms*", "*doubleclick.net*", "*cdn.jsdelivr.net/npm/@mailbiz*", "*tracker.mailbiz*", "*myperfit.com*", "*danube.com/bundle*", "*pubapi.myperfit*", "*perfit.com*", "*app.rdstation.com.br*", "*wisepops*", "*sleeknote*", "*privy.com*", "*optinmonster*"]
                })
            except Exception: pass

            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
            return driver
        except Exception as e:
            ultimo_erro = e
            if tentativa < tentativas - 1: time.sleep(2 + tentativa * 2)
    raise ultimo_erro if ultimo_erro else Exception("Falha ao configurar driver")

def fechar_driver(driver):
    try: driver.quit()
    except Exception: pass

def detectar_status_pagina(driver, url_alvo):
    try:
        logs = driver.get_log("performance")
        url_alvo_norm = url_alvo.rstrip("/").split("#")[0].split("?")[0]
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method") != "Network.responseReceived": continue
                params = msg.get("params", {})
                response = params.get("response", {})
                url_resp = (response.get("url") or "").rstrip("/").split("#")[0].split("?")[0]
                resource_type = params.get("type", "")
                status = response.get("status")
                if resource_type == "Document" and url_resp == url_alvo_norm:
                    if status and status >= 400: return f"Erro HTTP {status}"
            except Exception: continue
    except Exception: pass

    try:
        info = driver.execute_script("""
            var titulo = (document.title || '').toLowerCase();
            var h1 = '';
            var h1El = document.querySelector('h1');
            if (h1El) h1 = (h1El.innerText || h1El.textContent || '').toLowerCase();
            var bodyTexto = (document.body ? document.body.innerText || '' : '').toLowerCase();
            return {
                titulo: titulo, h1: h1, tamanho_body: bodyTexto.length,
                tem_404_titulo: titulo.indexOf('404') !== -1, tem_404_h1: h1.indexOf('404') !== -1,
                tem_nao_encontrado: titulo.indexOf('não encontrad') !== -1 || titulo.indexOf('nao encontrad') !== -1 || titulo.indexOf('not found') !== -1 || h1.indexOf('não encontrad') !== -1 || h1.indexOf('nao encontrad') !== -1 || h1.indexOf('not found') !== -1,
                tem_produto_indisponivel: titulo.indexOf('produto não disponível') !== -1 || titulo.indexOf('produto nao disponivel') !== -1 || titulo.indexOf('produto indisponível') !== -1 || titulo.indexOf('produto indisponivel') !== -1,
                tem_pagina_erro: titulo.indexOf('página de erro') !== -1 || titulo.indexOf('pagina de erro') !== -1 || titulo.indexOf('error page') !== -1
            };
        """)
        if info:
            if info.get("tem_404_titulo") or info.get("tem_404_h1"): return "Erro HTTP 404 (detectado por conteúdo)"
            if info.get("tem_nao_encontrado"): return "Página não encontrada (404)"
            if info.get("tem_produto_indisponivel"): return "Produto não disponível"
            if info.get("tem_pagina_erro"): return "Página de erro genérica"
            if info.get("tamanho_body", 0) < 200: return "Página vazia ou erro de carregamento"
    except Exception: pass
    return None

def carregar_pagina(driver, url):
    try: driver.get(url)
    except TimeoutException:
        try: driver.execute_script("window.stop();")
        except Exception: pass
    try:
        WebDriverWait(driver, TIMEOUT_DOM_PRONTO).until(lambda d: d.execute_script("return document.readyState") in ("interactive", "complete"))
    except TimeoutException: pass
    try:
        html = driver.execute_script("return document.body ? document.body.innerHTML.length : 0;")
        url_atual = driver.current_url or ""
        return html > 500 and url_atual.startswith("http")
    except Exception: return False

SCRIPT_LIMPEZA = """
    try {
        document.querySelectorAll('[data-mbz-popup-shell], [data-mbz-popup-overlay], [data-mbz-init-wrapper], [data-mbz-leave-wrapper], [data-mbz-button-popup-root], .mbz-popup-overlay, .p-layer, .p-layer.p-opened, .p-optin, [class*="p-layer"], [class*="p-opened"]').forEach(function(el) { try { el.style.display = 'none'; el.style.visibility = 'hidden'; el.style.pointerEvents = 'none'; if (el.parentNode) el.parentNode.removeChild(el); } catch(e) {} });
        document.body.classList.remove('mbz-popup-opened', 'p-opened', 'p-layer-opened');
        document.documentElement.classList.remove('p-opened', 'p-layer-opened');
    } catch(e) {}
    try {
        var palavrasCaptura = ['desconto', 'cupom', 'newsletter', 'cadastre', 'cadastr', 'assine', 'assinar', 'exclusivo', 'promoção', 'promocao', 'oferta', 'ganhe', 'e-mail', 'newsletter', 'inscrev', 'primeira compra', '10%', '15%', '20%', '5%', 'off'];
        var forms = document.querySelectorAll('form');
        forms.forEach(function(f) {
            try {
                var emailInput = f.querySelector('input[type="email"], input[name*="email" i], input[placeholder*="email" i], input[placeholder*="e-mail" i]');
                if (!emailInput) return;
                var txt = (f.textContent || '').toLowerCase();
                if (txt.length > 2000) return;
                var temPalavraChave = false;
                for (var i = 0; i < palavrasCaptura.length; i++) { if (txt.indexOf(palavrasCaptura[i]) !== -1) { temPalavraChave = true; break; } }
                if (!temPalavraChave) return;
                var container = f;
                for (var j = 0; j < 6 && container; j++) {
                    var style = window.getComputedStyle(container);
                    var rect = container.getBoundingClientRect();
                    if ((style.position === 'fixed' || style.position === 'absolute') && rect.width > 250 && rect.height > 200) { container.style.display = 'none'; container.style.visibility = 'hidden'; container.style.pointerEvents = 'none'; if (container.parentNode) container.parentNode.removeChild(container); return; }
                    container = container.parentElement;
                }
                f.style.display = 'none'; f.style.pointerEvents = 'none';
            } catch(e) {}
        });
    } catch(e) {}
    var btnsFechar = document.querySelectorAll('[aria-label*="fechar" i], [aria-label*="close" i], [class*="close" i]:not([class*="closet"]), [class*="dismiss" i], .modal-close, .popup-close, .js-modal-close, #adopt-accept-all-button, [id*="cookie" i] button, [class*="cookie" i] button, [data-mbz-popup-close-btn], #p-close, .p-close');
    btnsFechar.forEach(function(b) { try { if (b.offsetParent !== null) b.click(); } catch(e) {} });
    var seletores = ['.js-notification', '.newsletter', '.modal-overlay', '.js-modal-close', '[class*="popup" i]', '[class*="Popup"]', '.fancybox-overlay', '.fancybox-container', '[id*="chat" i]', '[class*="cookie" i]', '[class*="Cookie"]', '.modal', '.modal-backdrop', '#newsletter-modal', 'iframe[src*="chat"]', 'iframe[title*="chat" i]', '.adopt-ui-app', '[class*="cupom" i]', '[class*="coupon" i]', '[class*="newsletter" i]', '[class*="lead-capture" i]', '[class*="exit-intent" i]', '[role="dialog"]', '[role="alertdialog"]', '.js-popup', '.popup-newsletter', '.octane-spotlight', '.octane-modal', '.p-layer', '.p-optin'];
    seletores.forEach(function(sel) { try { document.querySelectorAll(sel).forEach(function(el) { el.style.display = 'none'; el.style.visibility = 'hidden'; el.style.pointerEvents = 'none'; if (el.parentNode) el.parentNode.removeChild(el); }); } catch(e) {} });
    document.querySelectorAll('div, section, aside').forEach(function(el) { try { var style = window.getComputedStyle(el); var zi = parseInt(style.zIndex) || 0; if ((style.position === 'fixed' || style.position === 'absolute') && zi > 50) { var rect = el.getBoundingClientRect(); if (rect.width > window.innerWidth * 0.3 && rect.height > 150) { if (rect.top > window.innerHeight * 0.15) { el.style.display = 'none'; el.style.pointerEvents = 'none'; } } } } catch(e) {} });
    document.body.style.overflow = 'auto'; document.documentElement.style.overflow = 'auto'; document.body.style.position = 'static'; document.body.classList.remove('modal-open', 'no-scroll', 'overflow-hidden');
"""

def limpar_obstaculos(driver):
    try: driver.execute_script(SCRIPT_LIMPEZA)
    except Exception: pass

def prescroll_agressivo(driver):
    try:
        driver.execute_script("""
            var alturaTotal = document.body.scrollHeight;
            var alturaViewport = window.innerHeight;
            var passos = Math.min(20, Math.ceil(alturaTotal / (alturaViewport * 0.7)));
            for (var i = 0; i <= passos; i++) { window.scrollTo(0, i * alturaViewport * 0.7); }
            window.scrollTo(0, 0);
        """)
        time.sleep(0.8)
    except Exception: pass

def aguardar_calculadora_no_dom(driver, timeout=TIMEOUT_CALCULADORA):
    script_check = """
        var indicadores = ['input.js-shipping-input', 'input[name="zipcode"]', '.js-accordion-toggle', '.js-accordion-private-toggle', '[data-component="shipping-calculator"]', '.js-shipping-calculator', '.shipping-calculator', '#js-est-cep', '#js-est-date', 'label[for*="shipping" i]', 'label[for*="frete" i]', 'label[for*="cep" i]'];
        for (var i = 0; i < indicadores.length; i++) { if (document.querySelector(indicadores[i])) return true; }
        var textos = ['meios de envio', 'frete e prazo', 'calcular frete', 'calcular o frete', 'informacoes de frete', 'informações de frete', 'calcule o prazo', 'calcule o prazo de entrega', 'entregas para o cep', 'alterar cep', 'alterar', 'shipping methods', 'shipping options', 'shipping calculator', 'delivery methods', 'calculate shipping', 'estimate shipping'];
        var todos = document.querySelectorAll('span, a, div, button, h2, h3, h4, h5, label');
        for (var j = 0; j < todos.length; j++) { var t = (todos[j].textContent || '').toLowerCase(); for (var k = 0; k < textos.length; k++) { if (t.includes(textos[k]) && t.length < 80) return true; } }
        return false;
    """
    try:
        WebDriverWait(driver, timeout).until(lambda d: d.execute_script(script_check))
        return True
    except TimeoutException: return False

SCRIPT_CLIQUE_MULTIPLOS_EVENTOS = """
    var el = arguments[0];
    var rect = el.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;
    var eventos_mouse = ['mouseover', 'mouseenter', 'mousedown', 'mouseup', 'click'];
    eventos_mouse.forEach(function(tipo) { try { var ev = new MouseEvent(tipo, { view: window, bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }); el.dispatchEvent(ev); } catch(e) {} });
    var eventos_touch = ['touchstart', 'touchend'];
    eventos_touch.forEach(function(tipo) { try { var ev = new Event(tipo, { bubbles: true, cancelable: true }); el.dispatchEvent(ev); } catch(e) {} });
    try { el.click(); } catch(e) {}
"""

def clicar_robusto(driver, elemento):
    try:
        driver.execute_script(SCRIPT_CLIQUE_MULTIPLOS_EVENTOS, elemento)
        return True
    except Exception: return False

def forcar_input_cep_visivel(driver):
    try:
        driver.execute_script("""
            document.querySelectorAll('.js-shipping-calculator-form, .shipping-calculator-form').forEach(function(el) { if (el.classList) { el.classList.remove('transition-up', 'transition-up-active', 'transition-up-leave', 'p-absolute'); } el.style.position = 'static'; el.style.transform = 'none'; el.style.display = 'block'; el.style.visibility = 'visible'; el.style.opacity = '1'; el.style.height = 'auto'; el.style.maxHeight = 'none'; el.style.width = 'auto'; });
            document.querySelectorAll('.js-shipping-calculator-with-zipcode').forEach(function(el) { el.style.display = 'none'; });
            var contentSelectors = ['.js-accordion-private-content', '.js-accordion-content', '.js-shipping-calculator-form', '.js-shipping-calculator-content', '[class*="shipping-calculator-content" i]', '[class*="accordion-content" i]'];
            contentSelectors.forEach(function(sel) { document.querySelectorAll(sel).forEach(function(el) { el.style.display = 'block'; el.style.visibility = 'visible'; el.style.maxHeight = 'none'; el.style.height = 'auto'; el.style.overflow = 'visible'; el.style.opacity = '1'; if (el.classList) { el.classList.remove('collapse', 'collapsed', 'd-none', 'hidden'); el.classList.add('show'); } }); });
            document.querySelectorAll('a.js-accordion-toggle, a.js-accordion-private-toggle').forEach(function(a) { var inactives = a.querySelectorAll('.js-accordion-toggle-inactive, .js-accordion-private-toggle-inactive'); var actives = a.querySelectorAll('.js-accordion-toggle-active, .js-accordion-private-toggle-active'); inactives.forEach(function(el) { el.style.display = 'none'; }); actives.forEach(function(el) { el.style.display = 'inline'; }); if (a.hasAttribute('aria-expanded')) a.setAttribute('aria-expanded', 'true'); });
            var inputs = document.querySelectorAll('input');
            inputs.forEach(function(inp) { try { var attrs = ((inp.name || '') + ' ' + (inp.id || '') + ' ' + (inp.placeholder || '') + ' ' + (inp.getAttribute('aria-label') || '')).toLowerCase(); var cls = (inp.className || '').toString().toLowerCase(); if (attrs.indexOf('cep') !== -1 || attrs.indexOf('zip') !== -1 || attrs.indexOf('postal') !== -1 || cls.indexOf('shipping') !== -1) { var pai = inp; for (var i = 0; i < 12 && pai; i++) { pai.style.visibility = 'visible'; pai.style.opacity = '1'; pai.style.maxHeight = 'none'; pai.style.height = 'auto'; pai.style.overflow = 'visible'; pai.style.pointerEvents = 'auto'; if (window.getComputedStyle(pai).display === 'none') { pai.style.display = 'block'; } pai.removeAttribute('hidden'); if (pai.hasAttribute('aria-hidden')) pai.setAttribute('aria-hidden', 'false'); if (pai.classList) { pai.classList.remove('collapse', 'collapsed', 'd-none', 'hidden'); pai.classList.add('show'); } pai = pai.parentElement; } } } catch(e) {} });
        """)
    except Exception: pass

def clicar_accordion_envios_nuvemshop(driver):
    try:
        clicou = driver.execute_script("""
            function clicarELiberar(el) { try { el.scrollIntoView({block: 'center'}); var rect = el.getBoundingClientRect(); var cx = rect.left + rect.width / 2; var cy = rect.top + rect.height / 2; ['mouseover', 'mouseenter', 'mousedown', 'mouseup', 'click'].forEach(function(tipo) { try { var ev = new MouseEvent(tipo, { view: window, bubbles: true, cancelable: true, clientX: cx, clientY: cy, button: 0 }); el.dispatchEvent(ev); } catch(e) {} }); try { el.click(); } catch(e) {} if (el.hasAttribute && el.hasAttribute('aria-expanded')) el.setAttribute('aria-expanded', 'true'); if (el.classList) { el.classList.remove('collapsed', 'collapse'); el.classList.add('show', 'expanded'); } var inactive = el.querySelector ? (el.querySelector('.js-accordion-toggle-inactive') || el.querySelector('.js-accordion-private-toggle-inactive')) : null; var active = el.querySelector ? (el.querySelector('.js-accordion-toggle-active') || el.querySelector('.js-accordion-private-toggle-active')) : null; if (inactive) inactive.style.display = 'none'; if (active) active.style.display = 'inline'; var proximo = el.nextElementSibling; for (var k = 0; k < 5 && proximo; k++) { var temShipping = proximo.querySelector && (proximo.querySelector('.js-shipping-input') || proximo.querySelector('input[name="zipcode"]') || proximo.querySelector('input[name*="cep" i]') || proximo.querySelector('input[name*="postal" i]')); var classes = (proximo.className || '').toString().toLowerCase(); if (temShipping || classes.indexOf('accordion') !== -1 || classes.indexOf('collapse') !== -1 || classes.indexOf('shipping') !== -1) { proximo.style.display = 'block'; proximo.style.visibility = 'visible'; proximo.style.maxHeight = 'none'; proximo.style.height = 'auto'; proximo.style.overflow = 'visible'; if (proximo.classList) { proximo.classList.remove('collapse', 'collapsed', 'd-none'); proximo.classList.add('show'); } break; } proximo = proximo.nextElementSibling; } if (el.tagName === 'SUMMARY' && el.parentElement && el.parentElement.tagName === 'DETAILS') { el.parentElement.open = true; } return true; } catch(e) { return false; } }
            var seletoresAccordion = ['.js-accordion-toggle', 'a[class*="accordion-toggle" i]', 'a.js-accordion-private-toggle', 'button[class*="accordion" i]', 'button[class*="toggle" i]', '[class*="shipping-toggle" i]', '[class*="toggle-shipping" i]', '[class*="shipping-collapse" i]', '[data-toggle="collapse"]', '[data-bs-toggle="collapse"]', '[role="button"][aria-expanded="false"]', 'summary'];
            for (var s = 0; s < seletoresAccordion.length; s++) { var elementos = document.querySelectorAll(seletoresAccordion[s]); for (var i = 0; i < elementos.length; i++) { var el = elementos[i]; if (el.offsetParent === null) continue; var txt = (el.textContent || '').toLowerCase(); if (txt.length > 200) continue; if (txt.indexOf('envio') !== -1 || txt.indexOf('frete') !== -1 || txt.indexOf('shipping') !== -1 || txt.indexOf('delivery') !== -1 || txt.indexOf('prazo') !== -1) { if (clicarELiberar(el)) return 'accordion:' + seletoresAccordion[s]; } } }
            var candidatos = document.querySelectorAll('a, button, [role="button"], div, span, h2, h3, h4, h5');
            for (var i = 0; i < candidatos.length; i++) { var el = candidatos[i]; if (el.offsetParent === null) continue; var txtTotal = (el.textContent || '').trim().toLowerCase(); if (txtTotal.length > 50) continue; if (txtTotal === 'meios de envio' || txtTotal === 'frete e prazo' || txtTotal === 'informações de frete' || txtTotal === 'informacoes de frete' || txtTotal === 'calcule o prazo' || txtTotal === 'calcule o prazo de entrega' || txtTotal === 'shipping methods' || txtTotal === 'calcular frete') { var style = window.getComputedStyle(el); var clicavel = el.tagName === 'A' || el.tagName === 'BUTTON' || el.getAttribute('role') === 'button' || style.cursor === 'pointer'; if (!clicavel) { var pai = el.parentElement; if (pai && (pai.tagName === 'A' || pai.tagName === 'BUTTON' || pai.getAttribute('role') === 'button' || window.getComputedStyle(pai).cursor === 'pointer')) { el = pai; clicavel = true; } } if (clicavel) { if (clicarELiberar(el)) return 'texto_exato:' + txtTotal; } } }
            var collapseds = document.querySelectorAll('[aria-expanded="false"]');
            for (var i = 0; i < collapseds.length; i++) { var el = collapseds[i]; if (el.offsetParent === null) continue; var txt = (el.textContent || '').toLowerCase(); if (txt.length < 200 && (txt.indexOf('envio') !== -1 || txt.indexOf('frete') !== -1 || txt.indexOf('shipping') !== -1 || txt.indexOf('prazo') !== -1)) { if (clicarELiberar(el)) return 'aria-expanded'; } }
            return false;
        """)
        if clicou: time.sleep(2)
        return bool(clicou)
    except Exception: return False

def localizar_campo_cep_qualquer(driver):
    seletores = ["input.js-shipping-input", "input.shipping-zipcode", "input[name='zipcode']", "input[name='postal_code']", "#js-est-cep", "input[id*='cep' i]", "input[placeholder*='cep' i]", "input[aria-label*='cep' i]"]
    for sel in seletores:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elementos:
                try:
                    if el.is_enabled(): return el
                except Exception: continue
        except Exception: continue
    return None

def tentar_calculo_atacando_input_diretamente(driver, cep):
    try:
        input_oculto = localizar_campo_cep_qualquer(driver)
        if input_oculto is None: return False
        driver.execute_script("""
            var el = arguments[0]; el.style.display = 'inline-block'; el.style.visibility = 'visible'; el.style.opacity = '1'; el.style.pointerEvents = 'auto'; el.removeAttribute('hidden'); el.removeAttribute('disabled');
            var pai = el.parentElement; for (var i = 0; i < 12 && pai; i++) { pai.style.visibility = 'visible'; pai.style.opacity = '1'; pai.style.maxHeight = 'none'; pai.style.height = 'auto'; pai.style.overflow = 'visible'; pai.style.pointerEvents = 'auto'; if (window.getComputedStyle(pai).display === 'none') { pai.style.display = 'block'; } pai.removeAttribute('hidden'); if (pai.hasAttribute('aria-hidden')) pai.setAttribute('aria-hidden', 'false'); if (pai.classList) { pai.classList.remove('collapse', 'collapsed', 'd-none', 'hidden'); pai.classList.add('show'); if (pai.hasAttribute('aria-expanded')) pai.setAttribute('aria-expanded', 'true'); } pai = pai.parentElement; }
            var accordions = document.querySelectorAll('a.js-accordion-toggle, a.js-accordion-private-toggle'); accordions.forEach(function(a) { var inactive = a.querySelector('.js-accordion-toggle-inactive') || a.querySelector('.js-accordion-private-toggle-inactive'); var active = a.querySelector('.js-accordion-toggle-active') || a.querySelector('.js-accordion-private-toggle-active'); if (inactive) inactive.style.display = 'none'; if (active) active.style.display = 'inline'; a.setAttribute('aria-expanded', 'true'); });
            el.scrollIntoView({block: 'center'});
        """, input_oculto)
        time.sleep(0.6)
        driver.execute_script("""
            var input = arguments[0]; var valor = arguments[1]; input.focus(); input.value = ''; var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; if (setter) { setter.call(input, valor); } else { input.value = valor; } input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
        """, input_oculto, cep)
        time.sleep(0.5)
        disparou = driver.execute_script("""
            var input = arguments[0]; var atual = input; for (var i = 0; i < 6; i++) { if (!atual.parentElement) break; atual = atual.parentElement; var botoes = atual.querySelectorAll('button, input[type="submit"], input[type="button"], a[role="button"], a.btn, .js-calculate-shipping, [aria-label="Calcular frete"], [aria-label*="alcular"]'); for (var j = 0; j < botoes.length; j++) { var b = botoes[j]; var t = ((b.innerText || b.value || '') + '').toLowerCase().trim(); if (t.indexOf('comprar') !== -1 || t.indexOf('adicionar') !== -1 || t.indexOf('cadastr') !== -1 || t.indexOf('fechar') !== -1 || t.indexOf('cancel') !== -1) continue; if (t.indexOf('calcular') !== -1 || t === 'ok' || t.indexOf('buscar') !== -1 || t.indexOf('aplicar') !== -1 || (b.classList && b.classList.contains('js-calculate-shipping')) || (b.getAttribute && b.getAttribute('aria-label') && b.getAttribute('aria-label').toLowerCase().indexOf('alcular') !== -1)) { b.style.display = 'inline-block'; b.style.visibility = 'visible'; try { b.disabled = false; } catch(e) {} try { b.click(); } catch(e) {} return 'botao'; } } }
            var form = input.closest('form'); if (form) { try { form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); return 'form_submit'; } catch(e) {} }
            try { input.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter', keyCode: 13, which: 13 })); input.dispatchEvent(new KeyboardEvent('keypress', { bubbles: true, key: 'Enter', keyCode: 13, which: 13 })); input.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter', keyCode: 13, which: 13 })); return 'enter'; } catch(e) {}
            return null;
        """, input_oculto)
        return disparou is not None
    except Exception: return False

def forcar_abrir_calculadora(driver):
    termos_prioritarios = ["calcule o prazo de entrega", "calcule o prazo", "meios de envio", "frete e prazo", "informacoes de frete", "informações de frete", "calcular frete", "calcular o frete", "alterar cep", "alterar"]
    for termo in termos_prioritarios:
        try:
            xpath = "//*[self::a or self::button or self::span or self::div or self::h2 or self::h3 or self::h4 or self::h5 or self::label][contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÂÊÔÃÕÇ', 'abcdefghijklmnopqrstuvwxyzáéíóúâêôãõç'), '" + termo + "')]"
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.3)
                    if not el.is_displayed(): continue
                    txt = (el.text or "").strip().lower()
                    if termo == "alterar" and "cep" not in txt:
                        contexto = driver.execute_script("""var el = arguments[0]; for (var i = 0; i < 5; i++) { if (!el.parentElement) break; el = el.parentElement; var t = (el.textContent || '').toLowerCase(); if (t.indexOf('cep') !== -1 || t.indexOf('entrega') !== -1 || t.indexOf('frete') !== -1) return true; } return false;""", el)
                        if not contexto: continue
                    if len(txt) > 100: continue
                    clicar_robusto(driver, el)
                    time.sleep(1.5)
                except Exception: continue
        except Exception: continue
    forcar_input_cep_visivel(driver)

def aguardar_input_cep_aparecer(driver, timeout=TIMEOUT_INPUT_CEP):
    seletores = ["input.js-shipping-input", "input.shipping-zipcode", "input[name='zipcode']", "input[name='postal_code']", "#zipcode-input", "#js-est-cep", ".js-shipping-input", "input[id*='cep' i]", "input[name*='cep' i]", "input[placeholder*='cep' i]", "input[aria-label*='cep' i]", "input[type='tel'][maxlength='9']", "input[type='tel'][maxlength='8']"]
    def buscar_input_com_scroll():
        for sel in seletores:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elementos:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", el)
                        time.sleep(0.1)
                        if el.is_displayed() and el.is_enabled(): return el
                    except StaleElementReferenceException: continue
            except Exception: continue
        return None
    inicio = time.time()
    while time.time() - inicio < timeout:
        campo = buscar_input_com_scroll()
        if campo: return campo
        forcar_input_cep_visivel(driver)
        time.sleep(0.5)
        campo = buscar_input_com_scroll()
        if campo: return campo
        time.sleep(0.4)
    return None

def abrir_accordion_envio(driver):
    seletores_accordion = [".js-accordion-toggle", ".js-accordion-private-toggle", ".js-toggle-shipping", ".js-shipping-calculator-toggle", ".accordion-shipping", "[data-component='shipping-calculator'] button", "[data-component='shipping-calculator'] [aria-expanded='false']", "[aria-expanded='false'][class*='shipping' i]", "[aria-expanded='false'][class*='envio' i]"]
    for sel in seletores_accordion:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try: driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el); time.sleep(0.2)
                except Exception: pass
                if not el.is_displayed(): continue
                try: texto = driver.execute_script("return (arguments[0].textContent || '').toLowerCase();", el)
                except Exception: texto = (el.text or "").lower()
                if ("frete" in texto or "envio" in texto or "prazo" in texto or "calcular" in texto or "informa" in texto or "shipping" in texto or "delivery" in texto or "calculate" in texto or sel != ".js-accordion-toggle"):
                    clicar_robusto(driver, el); time.sleep(0.8); return True
        except Exception: continue

    try:
        seletor_labels = ("label[for*='shipping' i], label[for*='frete' i], label[for*='cep' i], label[for*='zip' i], label[for*='envio' i], label[for*='postal' i], label[for*='delivery' i]")
        for label in driver.find_elements(By.CSS_SELECTOR, seletor_labels):
            try: driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label); time.sleep(0.2)
            except Exception: pass
            if not label.is_displayed(): continue
            texto = (label.text or "").lower()
            if any(t in texto for t in ["frete", "envio", "cep", "prazo", "informa", "shipping", "delivery", "zip", "postal"]):
                for_id = label.get_attribute("for")
                script_ativar = "var label = arguments[0]; var forId = arguments[1]; try { label.click(); } catch(e) {} if (forId) { var input = document.getElementById(forId); if (input) { try { if (input.type === 'checkbox' || input.type === 'radio') { input.checked = true; } input.dispatchEvent(new Event('change', { bubbles: true })); input.dispatchEvent(new Event('click', { bubbles: true })); } catch(e) {} } }"
                driver.execute_script(script_ativar, label, for_id)
                time.sleep(0.8)
                return True
    except Exception: pass

    try:
        for det in driver.find_elements(By.CSS_SELECTOR, "details"):
            try:
                if not det.is_displayed(): continue
                texto = (det.text or "").lower()
                if any(t in texto for t in ["frete", "envio", "prazo", "calcular", "shipping", "delivery", "calculate"]):
                    driver.execute_script("arguments[0].open = true;", det); time.sleep(0.5); return True
            except Exception: continue
    except Exception: pass

    termos = ["informacoes de frete", "informações de frete", "frete e prazo", "meios de envio", "calcular frete", "calcular o frete", "calcule o prazo", "calcule o prazo de entrega", "calcule o prazo e valores", "entregas para o cep", "alterar cep", "shipping methods", "shipping options", "shipping calculator", "delivery methods", "calculate shipping", "estimate shipping"]
    for termo in termos:
        try:
            xpath = "//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÂÊÔÃÕÇ', 'abcdefghijklmnopqrstuvwxyzáéíóúâêôãõç'), '" + termo + "')]"
            for el in driver.find_elements(By.XPATH, xpath):
                try: driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el); time.sleep(0.2)
                except Exception: pass
                if not el.is_displayed(): continue
                clicar_robusto(driver, el); time.sleep(0.8); return True
        except Exception: continue
    return False

def scroll_ate_calculadora(driver):
    seletores_ancora = ["input.js-shipping-input", "input[name='zipcode']", "#js-est-cep", "[data-component='shipping-calculator']", ".js-shipping-calculator", ".shipping-calculator", "#shipping-calculator", "label[for*='shipping' i]", "label[for*='frete' i]", ".js-accordion-toggle", ".js-accordion-private-toggle", ".js-product-buy", ".js-buy-button", "button.js-add-to-cart-button", "form.js-product-form"]
    for sel in seletores_ancora:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elementos:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", el)
                    time.sleep(0.4)
                    if el.is_displayed(): return True
                except Exception: continue
        except Exception: continue
    return False

def scroll_pagina_inteira_procurando(driver):
    try:
        altura = driver.execute_script("return document.body.scrollHeight;")
        for pos in range(0, altura, 500):
            driver.execute_script(f"window.scrollTo(0, {pos});")
            time.sleep(0.25)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.3)
    except Exception: pass

def localizar_campo_cep(driver):
    seletores = ["input.js-shipping-input", "input.shipping-zipcode", "input[name='zipcode']", "input[name='postal_code']", "#zipcode-input", "#js-est-cep", ".js-shipping-input", "input[id*='cep' i]", "input[name*='cep' i]", "input[placeholder*='cep' i]", "input[aria-label*='cep' i]", "input[type='tel'][maxlength='9']", "input[type='tel'][maxlength='8']"]
    for sel in seletores:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.15)
                    if el.is_displayed() and el.is_enabled(): return el
                except StaleElementReferenceException: continue
        except Exception: continue
    return None

def capturar_estimativa_prazo(driver):
    try:
        return driver.execute_script("""
            var ids = ['js-est-date', 'js-shipping-estimate', 'js-estimate-date', 'estimate-date'];
            for (var i = 0; i < ids.length; i++) { var el = document.getElementById(ids[i]); if (el && el.offsetParent !== null) { var txt = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' '); if (txt && txt.length > 5 && txt.length < 200) { return txt; } } }
            var todos = document.querySelectorAll('div, span, p');
            for (var i = 0; i < todos.length; i++) { if (todos[i].offsetParent === null) continue; var t = (todos[i].innerText || '').trim().replace(/\\s+/g, ' '); var tl = t.toLowerCase(); if (t.length < 200 && t.length > 10) { if (tl.indexOf('chega entre') !== -1 || (tl.indexOf('chega ') === 0 && (tl.indexOf('de jun') !== -1 || tl.indexOf('de jul') !== -1 || tl.indexOf('de ago') !== -1 || tl.indexOf('de set') !== -1 || tl.indexOf('de out') !== -1 || tl.indexOf('de nov') !== -1 || tl.indexOf('de dez') !== -1 || tl.indexOf('de jan') !== -1 || tl.indexOf('de fev') !== -1 || tl.indexOf('de mar') !== -1 || tl.indexOf('de abr') !== -1 || tl.indexOf('de mai') !== -1))) { return t; } } }
            return null;
        """)
    except Exception: return None

def _fingerprint_frete(txt):
    if not txt: return None
    t = txt.lower()
    t_norm = (t.replace("á", "a").replace("ã", "a").replace("â", "a").replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o").replace("ô", "o").replace("õ", "o").replace("ú", "u").replace("ç", "c"))
    preco_match = re.search(r"r\$\s*([\d.]+,\d{2}|[\d]+,\d{2}|\d+)", t)
    if preco_match: preco_key = preco_match.group(1).replace(".", "")
    elif "gratis" in t_norm or "free" in t_norm: preco_key = "gratis"
    else: return None
    modalidades = ["correios", "sedex", "pac", "jadlog", "loggi", "mandae", "mandaê", "azul cargo", "total express", "mercado envios", "motoboy", "transportadora", "retirada", "loja", "fixo", "expressa", "expresso", "economico", "econômico", "econômica", "economica", "rapido", "rápido", "normal", "standard", "premium", "package", ".com", ".package", "shipping", "delivery", "ground", "priority", "express", "nuvem envio", "nuvemshop"]
    modalidade_encontrada = ""
    for m in modalidades:
        if m in t_norm: modalidade_encontrada = m; break
    dias_match = re.search(r"(\d+)\s*dia", t_norm)
    dias = dias_match.group(1) if dias_match else ""
    return f"{preco_key}|{modalidade_encontrada}|{dias}"

def _deduplicar_fretes(opcoes):
    melhor_por_fp = {}; sem_fingerprint = []
    for txt in opcoes:
        if not txt or not txt.strip(): continue
        txt = txt.strip()
        fp = _fingerprint_frete(txt)
        if fp is None: sem_fingerprint.append(txt); continue
        if fp not in melhor_por_fp or len(txt) > len(melhor_por_fp[fp]): melhor_por_fp[fp] = txt
    resultado = list(melhor_por_fp.values())
    textos_existentes_lower = [r.lower() for r in resultado]
    for item in sem_fingerprint:
        item_lower = item.lower()
        ja_coberto = False
        for existente in textos_existentes_lower:
            if item_lower in existente or existente in item_lower: ja_coberto = True; break
        if not ja_coberto: resultado.append(item)
    return resultado

def expandir_todas_opcoes(driver, max_iteracoes=10):
    termos = ["ver mais opções de envio", "ver mais opcoes de envio", "ver mais opções", "ver mais opcoes", "ver mais", "ver todas", "mostrar todas", "mais formas de envio", "mostrar mais", "ver outras", "outras opcoes", "outras opções", "expandir", "carregar mais", "ver outros", "see more", "show more", "view more", "more options", "more shipping", "other options", "load more", "expand", "see all", "show all"]
    seletores_diretos = [".js-shipping-see-more", ".js-show-more-shipping-options", "[class*='shipping-see-more']", "[class*='more-shipping']"]
    def contar_itens_frete():
        try:
            return driver.execute_script("var count = 0; document.querySelectorAll('.js-shipping-list-item, .shipping-option, [class*=\"shipping-item\"]').forEach(function(el) { count++; }); if (count === 0) { document.querySelectorAll('*').forEach(function(el) { var t = (el.textContent || ''); if (t.indexOf('R$') !== -1 && el.children.length === 0) count++; }); } return count;")
        except Exception: return 0
    contagem_anterior = contar_itens_frete()
    for iteracao in range(max_iteracoes):
        clicou_algo = False
        for sel in seletores_diretos:
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    try:
                        if not el.is_displayed(): continue
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el); time.sleep(0.2)
                        clicar_robusto(driver, el); clicou_algo = True; time.sleep(1.5); break
                    except StaleElementReferenceException: continue
                if clicou_algo: break
            except Exception: continue
        if not clicou_algo:
            for termo in termos:
                try:
                    xpath = "//*[self::button or self::a or self::span or self::div or self::p][contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÂÊÔÃÕÇ', 'abcdefghijklmnopqrstuvwxyzáéíóúâêôãõç'), '" + termo + "')]"
                    for el in driver.find_elements(By.XPATH, xpath):
                        try:
                            if not el.is_displayed(): continue
                            txt = (el.text or "").strip()
                            if len(txt) > 80 or len(txt) < 3: continue
                            contexto = driver.execute_script("var el = arguments[0]; for (var i = 0; i < 5; i++) { if (!el.parentElement) break; el = el.parentElement; var t = (el.textContent || '').toLowerCase(); if (t.indexOf('frete') !== -1 || t.indexOf('envio') !== -1 || t.indexOf('cep') !== -1 || t.indexOf('correios') !== -1 || t.indexOf('sedex') !== -1 || t.indexOf('chega') !== -1 || t.indexOf('shipping') !== -1 || t.indexOf('delivery') !== -1 || t.indexOf('arrives') !== -1 || t.indexOf('zip') !== -1 || t.indexOf('r$') !== -1) { return true; } } return false;", el)
                            if not contexto: continue
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el); time.sleep(0.2)
                            clicar_robusto(driver, el); clicou_algo = True; time.sleep(1.5); break
                        except StaleElementReferenceException: continue
                    if clicou_algo: break
                except Exception: continue
        if not clicou_algo: break
        nova_contagem = contar_itens_frete()
        if nova_contagem <= contagem_anterior and iteracao > 1: break
        contagem_anterior = nova_contagem

def capturar_lista_fretes(driver, ja_expandiu=False):
    if not ja_expandiu: expandir_todas_opcoes(driver)
    opcoes = []
    try:
        itens_estruturados = driver.execute_script("""
            var resultados = [];
            var itens = document.querySelectorAll('.js-shipping-list-item, .shipping-option, li.radio-button-item, [class*="shipping-item"]');
            itens.forEach(function(item) {
                try {
                    var nome = item.querySelector('[data-component="option.name"], .shipping-option-name');
                    var prazo = item.querySelector('[data-component="option.date"]');
                    var preco = item.querySelector('[data-component="option.price"]');
                    if (nome || preco) {
                        var partes = [];
                        if (nome) partes.push(nome.innerText.trim().replace(/\\s+/g, ' '));
                        if (prazo) partes.push(prazo.innerText.trim().replace(/\\s+/g, ' '));
                        if (preco) partes.push(preco.innerText.trim().replace(/\\s+/g, ' '));
                        var texto = partes.filter(function(p) { return p.length > 0; }).join(' - ');
                        if (texto && (texto.indexOf('R$') !== -1 || texto.toLowerCase().indexOf('grá') !== -1 || texto.toLowerCase().indexOf('gra') !== -1 || texto.toLowerCase().indexOf('free') !== -1)) { resultados.push(texto); return; }
                    }
                    var textoCompleto = (item.innerText || item.textContent || '').trim();
                    if (!textoCompleto) return;
                    var linhas = textoCompleto.split('\\n').map(function(l) { return l.trim().replace(/\\s+/g, ' '); }).filter(function(l) { return l.length > 0 && l.length < 200; });
                    if (linhas.length === 0) return;
                    var textoFinal; if (linhas.length === 1) { textoFinal = linhas[0]; } else { textoFinal = linhas.join(' - '); }
                    if (textoFinal.length < 250 && (textoFinal.indexOf('R$') !== -1 || textoFinal.toLowerCase().indexOf('grá') !== -1 || textoFinal.toLowerCase().indexOf('gra') !== -1 || textoFinal.toLowerCase().indexOf('free') !== -1)) { resultados.push(textoFinal); }
                } catch(e) {}
            });
            return resultados;
        """) or []
        for linha in itens_estruturados:
            if linha and linha.strip(): opcoes.append(linha.strip())
    except Exception: pass

    seletores_itens = [".shipping-option", ".js-shipping-method", "li.radio-button-item", "[class*='shippingOptionContent']", ".list-group-item", ".shipping-item", ".js-shipping-list li", "table.table-shipping tbody tr", "[class*='shipping'] li", "[class*='shipping'] tr", ".js-shipping-list-item"]
    for sel in seletores_itens:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    txt = driver.execute_script("return arguments[0].innerText || arguments[0].textContent || '';", el)
                    txt = (txt or "").strip().replace("\n", " - ").replace("\r", "")
                    txt = re.sub(r'\s+-\s+-\s+', ' - ', txt)
                    txt = re.sub(r'\s+', ' ', txt)
                except StaleElementReferenceException: continue
                if parece_frete(txt) and len(txt) < 250: opcoes.append(txt)
        except Exception: continue

    if not opcoes:
        try:
            elementos = driver.find_elements(By.XPATH, "//*[contains(text(), 'R$') or contains(text(), 'Grátis') or contains(text(), 'GRÁTIS') or contains(text(), 'gratis') or contains(text(), 'GRATIS')]")
            for el in elementos:
                try:
                    txt = el.text.strip().replace("\n", " - ")
                    if len(txt) < 120 and parece_frete(txt): opcoes.append(txt)
                except StaleElementReferenceException: continue
        except Exception: pass

    if not opcoes:
        estimativa = capturar_estimativa_prazo(driver)
        if estimativa: opcoes.append(f"Estimativa de prazo: {estimativa}")

    return _deduplicar_fretes(opcoes)

def aguardar_calculo_terminar(driver, timeout=15):
    try:
        WebDriverWait(driver, timeout).until_not(lambda d: d.execute_script("""
            var spinner = document.querySelector('.js-shipping-calculator-spinner');
            if (spinner) { var style = window.getComputedStyle(spinner); if (style.display !== 'none' && spinner.offsetParent !== null) return true; }
            var spinners = document.querySelectorAll('.spinner, [class*="loading" i]');
            for (var i = 0; i < spinners.length; i++) { if (spinners[i].offsetParent !== null) { var style = window.getComputedStyle(spinners[i]); if (style.display !== 'none' && style.visibility !== 'hidden') { var rect = spinners[i].getBoundingClientRect(); if (rect.width > 0 && rect.height > 0) return true; } } }
            var todos = document.querySelectorAll('span, p, div, a');
            for (var i = 0; i < todos.length; i++) { var t = (todos[i].textContent || '').toLowerCase(); if (todos[i].offsetParent !== null && t.indexOf('calculando') !== -1 && t.length < 80) { return true; } }
            return false;
        """))
        return True
    except TimeoutException: return False

def preencher_cep(driver, cep, max_retries=3):
    for tentativa in range(max_retries):
        try:
            campo = localizar_campo_cep(driver)
            if campo is None: return False
            try: campo.click()
            except Exception: driver.execute_script("arguments[0].focus();", campo)
            campo = localizar_campo_cep(driver) or campo
            try: campo.send_keys(Keys.CONTROL + "a"); campo.send_keys(Keys.BACKSPACE); campo.clear()
            except Exception: driver.execute_script("arguments[0].value = '';", campo)
            time.sleep(0.2)
            campo = localizar_campo_cep(driver) or campo
            try:
                for char in cep: campo.send_keys(char); time.sleep(0.15)
            except StaleElementReferenceException:
                campo = localizar_campo_cep(driver)
                if campo is None: raise
                script_react = "var input = arguments[0]; var valor = arguments[1]; var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; input.value = valor; if (setter) { setter.call(input, valor); } input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('keyup', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));"
                driver.execute_script(script_react, campo, cep)
            except Exception:
                campo = localizar_campo_cep(driver) or campo
                script_react = "var input = arguments[0]; var valor = arguments[1]; var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; input.value = valor; if (setter) { setter.call(input, valor); } input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('keyup', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));"
                driver.execute_script(script_react, campo, cep)
            try:
                campo = localizar_campo_cep(driver) or campo
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true })); arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", campo)
            except Exception: pass
            return True
        except StaleElementReferenceException:
            if tentativa < max_retries - 1: time.sleep(0.4); continue
            return False
        except Exception:
            if tentativa < max_retries - 1: time.sleep(0.4); continue
            return False
    return False

def clicar_botao_proximo_ao_input(driver, campo):
    try:
        botao = driver.execute_script("""
            var input = arguments[0]; var atual = input; for (var i = 0; i < 6; i++) { if (!atual.parentElement) break; atual = atual.parentElement; var botoes = atual.querySelectorAll('button, input[type="submit"], input[type="button"], a[role="button"], .js-calculate-shipping, [aria-label="Calcular frete"], [aria-label*="alcular"]'); for (var j = 0; j < botoes.length; j++) { var b = botoes[j]; if (b.offsetParent === null) continue; var t = ((b.innerText || b.value || '') + '').toLowerCase().trim(); if (t.indexOf('comprar') !== -1 || t.indexOf('adicionar') !== -1 || t.indexOf('login') !== -1 || t.indexOf('cadastr') !== -1 || t.indexOf('fechar') !== -1 || t.indexOf('cancel') !== -1 || t.indexOf('voltar') !== -1) continue; var temSvg = b.querySelector('svg') !== null; var ehSubmit = b.getAttribute('type') === 'submit'; if (t.length < 30 || temSvg || ehSubmit) { return b; } } } return null;
        """, campo)
        if botao:
            try: driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao); time.sleep(0.2)
            except Exception: pass
            clicar_robusto(driver, botao); return True
    except Exception: pass
    return False

def clicar_calcular(driver):
    seletores_botao = [".js-calculate-shipping", ".js-shipping-calculator-btn", "[data-component='shipping-calculator'] button[type='submit']", "button.shipping-calculator-button", "form.js-shipping-calculator-form button[type='submit']", ".shipping-calculator-form button", "button.js-shipping-calculator-btn svg", "[aria-label='Calcular frete']", "[aria-label*='alcular']"]
    for sel in seletores_botao:
        try:
            for b in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", b); time.sleep(0.15)
                    if b.is_displayed(): clicar_robusto(driver, b); return True
                except StaleElementReferenceException: continue
        except Exception: continue
    try:
        xpath = ("//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'calcular') or contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'calculate') or normalize-space(translate(text(),'OK','ok'))='ok' or contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'buscar') or contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'ver opç') or contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'ver opc')] | //input[@type='submit' and (contains(translate(@value,'CALCULAR','calcular'),'calcular') or contains(translate(@value,'CALCULATE','calculate'),'calculate') or normalize-space(translate(@value,'OK','ok'))='ok')] | //div[contains(@class, 'js-calculate-shipping')] | //span[contains(translate(normalize-space(text()),'CALCULAR','calcular'), 'calcular') and not(contains(translate(normalize-space(text()),'CALCULAR','calcular'), 'calculando'))] | //a[contains(translate(normalize-space(text()),'CALCULAR','calcular'), 'calcular') or normalize-space(translate(text(),'OK','ok'))='ok']")
        for b in driver.find_elements(By.XPATH, xpath):
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", b); time.sleep(0.15)
                if b.is_displayed():
                    contexto = driver.execute_script("var el = arguments[0]; for (var i = 0; i < 6; i++) { if (!el.parentElement) break; el = el.parentElement; var t = (el.textContent || '').toLowerCase(); if (t.indexOf('cep') !== -1 || t.indexOf('frete') !== -1 || t.indexOf('envio') !== -1 || t.indexOf('shipping') !== -1 || t.indexOf('zip') !== -1 || t.indexOf('postal') !== -1 || t.indexOf('entrega') !== -1 || t.indexOf('prazo') !== -1) { return true; } } return false;", b)
                    if not contexto: continue
                    clicar_robusto(driver, b); return True
            except StaleElementReferenceException: continue
    except Exception: pass
    try:
        campo = localizar_campo_cep(driver)
        if campo:
            if clicar_botao_proximo_ao_input(driver, campo): return True
    except Exception: pass
    try:
        campo = localizar_campo_cep(driver)
        if campo: campo.send_keys(Keys.ENTER); return True
    except Exception: pass
    return False

def verificar_frete(driver, url_produto, cep_alvo, eh_primeiro_cep=False):
    if pd.isna(url_produto) or "http" not in str(url_produto): return ["URL Inválida"], False
    sleep_inicial = 4 if eh_primeiro_cep else 2
    try:
        carregou = carregar_pagina(driver, url_produto)
        if not carregou:
            erro_status = detectar_status_pagina(driver, url_produto)
            if erro_status: return [erro_status], False
            return ["Página não carregou"], False
        erro_status = detectar_status_pagina(driver, url_produto)
        if erro_status: return [erro_status], False

        time.sleep(sleep_inicial)
        prescroll_agressivo(driver)
        limpar_obstaculos(driver)
        time.sleep(0.5)

        aguardar_calculadora_no_dom(driver, timeout=TIMEOUT_CALCULADORA)
        time.sleep(1.5)
        limpar_obstaculos(driver)
        time.sleep(1)
        limpar_obstaculos(driver)

        scroll_ate_calculadora(driver)
        limpar_obstaculos(driver)
        forcar_abrir_calculadora(driver)
        time.sleep(2)
        limpar_obstaculos(driver)
        clicar_accordion_envios_nuvemshop(driver)
        time.sleep(1.5)
        limpar_obstaculos(driver)
        forcar_input_cep_visivel(driver)
        time.sleep(0.5)

        timeout_input = TIMEOUT_INPUT_CEP if not eh_primeiro_cep else TIMEOUT_INPUT_CEP + 5
        campo_cep = aguardar_input_cep_aparecer(driver, timeout=timeout_input)

        if not campo_cep:
            for tentativa in range(6):
                limpar_obstaculos(driver)
                campo_cep = localizar_campo_cep(driver)
                if campo_cep: break
                clicar_accordion_envios_nuvemshop(driver)
                time.sleep(1)
                forcar_input_cep_visivel(driver)
                time.sleep(0.5)
                campo_cep = localizar_campo_cep(driver)
                if campo_cep: break
                abriu = abrir_accordion_envio(driver)
                if abriu:
                    limpar_obstaculos(driver)
                    forcar_input_cep_visivel(driver)
                    time.sleep(1)
                    campo_cep = localizar_campo_cep(driver)
                    if campo_cep: break
                if tentativa == 2:
                    limpar_obstaculos(driver)
                    forcar_abrir_calculadora(driver)
                    time.sleep(2)
                    campo_cep = aguardar_input_cep_aparecer(driver, timeout=5)
                    if campo_cep: break
                if tentativa == 3:
                    scroll_pagina_inteira_procurando(driver)
                    scroll_ate_calculadora(driver)
                elif tentativa >= 4:
                    scroll_ate_calculadora(driver)
                time.sleep(1)

        if not campo_cep:
            if tentar_calculo_atacando_input_diretamente(driver, cep_alvo):
                time.sleep(2); limpar_obstaculos(driver); aguardar_calculo_terminar(driver, timeout=15)
                resultados_ataque = []
                inicio_ataque = time.time()
                while time.time() - inicio_ataque < JANELA_CAPTURA_FRETE:
                    elapsed = time.time() - inicio_ataque
                    if elapsed < 1.5: time.sleep(0.5); continue
                    try: resultados_ataque = capturar_lista_fretes(driver, ja_expandiu=True)
                    except StaleElementReferenceException: time.sleep(0.5); continue
                    if resultados_ataque: break
                    if elapsed > 3: limpar_obstaculos(driver)
                    time.sleep(0.5)
                if resultados_ataque: return resultados_ataque, True
            estimativa = capturar_estimativa_prazo(driver)
            if estimativa: return [f"Estimativa de prazo: {estimativa}"], True
            return ["Campo de frete não localizado"], False

        try: driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", campo_cep)
        except StaleElementReferenceException:
            campo_cep = localizar_campo_cep(driver)
            if campo_cep: driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", campo_cep)
        time.sleep(0.5)
        limpar_obstaculos(driver)

        if not preencher_cep(driver, cep_alvo): return ["Falha ao preencher o CEP"], True

        time.sleep(0.5)
        clicar_calcular(driver)
        time.sleep(0.5)
        limpar_obstaculos(driver)
        time.sleep(0.5)
        aguardar_calculo_terminar(driver, timeout=15)
        limpar_obstaculos(driver)

        janela = JANELA_CAPTURA_FRETE if not eh_primeiro_cep else JANELA_CAPTURA_FRETE + 5
        primeiros_resultados = []
        inicio = time.time()
        while time.time() - inicio < janela:
            elapsed = time.time() - inicio
            if elapsed < 1.5: time.sleep(0.5); continue
            try: primeiros_resultados = capturar_lista_fretes(driver, ja_expandiu=True)
            except StaleElementReferenceException: time.sleep(0.5); continue
            if primeiros_resultados: break
            if elapsed > 3: limpar_obstaculos(driver)
            time.sleep(0.5)

        if not primeiros_resultados: return ["Frete não localizado"], True

        time.sleep(1)
        try: resultados_finais = capturar_lista_fretes(driver, ja_expandiu=False)
        except StaleElementReferenceException:
            time.sleep(0.5)
            try: resultados_finais = capturar_lista_fretes(driver, ja_expandiu=False)
            except Exception: resultados_finais = primeiros_resultados

        if not resultados_finais: resultados_finais = primeiros_resultados
        elif len(resultados_finais) < len(primeiros_resultados):
            todos = primeiros_resultados + resultados_finais
            resultados_finais = _deduplicar_fretes(todos)

        return resultados_finais, True

    except Exception as e: return [f"Erro: {str(e)[:80]}"], False


def _eh_erro_pagina(resultados):
    if not resultados: return False
    r = resultados[0].lower() if resultados else ""
    return ("erro http" in r or "não encontrad" in r or "nao encontrad" in r or "não disponível" in r or "nao disponivel" in r or "indisponível" in r or "indisponivel" in r or "página vazia" in r or "pagina vazia" in r or "página de erro" in r or "pagina de erro" in r)


# ============================================================
# 5. PIPELINE PRINCIPAL E MULTI-THREADING
# ============================================================
def processar_produto(row_dict, idx, total_produtos, driver):
    nome = row_dict.get(COLUNA_NOME, "") or "Sem Nome"
    urls_candidatas = []
    
    if pd.notna(row_dict.get(COLUNA_URL)) and "http" in str(row_dict.get(COLUNA_URL)):
        urls_candidatas.append(str(row_dict[COLUNA_URL]))
        
    for col_b in COLUNAS_BACKUP:
        if col_b in row_dict and pd.notna(row_dict.get(col_b)) and "http" in str(row_dict.get(col_b)):
            urls_candidatas.append(str(row_dict[col_b]))

    if not urls_candidatas: return "Sem URL válida", []

    linhas_resultado = []
    for url_index, url_atual in enumerate(urls_candidatas):
        tipo_url = "Principal" if url_index == 0 else f"Backup {url_index}"
        print(f"\n🔍 [{idx+1}/{total_produtos}] {nome} | Testando {tipo_url}: {url_atual}")

        resultados_por_cep = {}
        falhou_url_atual = False

        for cep_idx, cep in enumerate(LISTA_CEPS):
            try:
                resultados, achou = verificar_frete(driver, url_atual, cep, (cep_idx == 0))
            except Exception as e:
                resultados, achou = [f"Erro inesperado: {str(e)[:50]}"], False

            if _eh_erro_pagina(resultados) or not achou or resultados == ["Frete não localizado"]:
                print(f"   ⚠️ URL {tipo_url} falhou no CEP {cep}. Motivo: {resultados[0]}")
                falhou_url_atual = True
                break # Sai deste CEP e pula pra próxima URL Backup

            resultados_por_cep[cep_idx] = {"resultados": resultados, "cep": cep}

        # Se não falhou nenhum CEP, Sucesso!
        if not falhou_url_atual and len(resultados_por_cep) == len(LISTA_CEPS):
            print(f"   ✅ Sucesso com a URL {tipo_url}!")
            for c_idx in sorted(resultados_por_cep.keys()):
                for frete in resultados_por_cep[c_idx]["resultados"]:
                    linha_formatada = padronizar_resultados(row_dict, resultados_por_cep[c_idx]["cep"], frete)
                    linhas_resultado.append(linha_formatada)
            return "Sucesso", linhas_resultado
            
    print(f"   ❌ Todas as URLs falharam para {nome}.")
    return "Erro: Todas as URLs falharam", []

def worker_task(tarefa):
    idx = tarefa['idx']
    total_produtos = tarefa['total']
    row_dict = tarefa['row']
    
    driver = configurar_driver()
    try:
        status, dados_formatados = processar_produto(row_dict, idx, total_produtos, driver)
        return {'orig_row_index': tarefa['orig_row_index'], 'status': status, 'dados_formatados': dados_formatados}
    except Exception as e:
        return {'orig_row_index': tarefa['orig_row_index'], 'status': f"Erro Crítico: {str(e)[:30]}", 'dados_formatados': []}
    finally:
        fechar_driver(driver)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk", type=int, default=1)
    parser.add_argument("--total-chunks", type=int, default=1)
    args = parser.parse_args()

    print("🔌 Conectando ao Google Sheets...")
    client = conectar_google_sheets()
    
    planilha_entrada = client.open_by_key(ID_PLANILHA_ENTRADA).worksheet(ABA_ENTRADA)
    planilha_saida = client.open_by_key(ID_PLANILHA_SAIDA).worksheet(ABA_SAIDA)

    dados_entrada = planilha_entrada.get_all_records()
    df_orig = pd.DataFrame(dados_entrada)
    
    total_linhas = len(df_orig)
    tamanho_lote = math.ceil(total_linhas / args.total_chunks)
    linha_inicial = (args.chunk - 1) * tamanho_lote
    linha_final = linha_inicial + tamanho_lote
    
    df_processar = df_orig.iloc[linha_inicial:linha_final].copy()
    print(f"🖥️ Máquina {args.chunk}/{args.total_chunks} - Processando da linha {linha_inicial} à {linha_final}")

    tarefas = []
    for i, row in df_processar.iterrows():
        tarefas.append({
            'idx': i, 'total': total_linhas, 'row': row.to_dict(),
            'orig_row_index': i + 2 # Google Sheets index (Header é 1)
        })

    resultados_finais_saida = []
    atualizacoes_status = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(worker_task, t): t for t in tarefas}
        
        for future in as_completed(futures):
            resultado = future.result()
            
            # A Coluna F (Status)
            atualizacoes_status.append({
                'range': f'F{resultado["orig_row_index"]}',
                'values': [[resultado['status']]]
            })
            
            if resultado['dados_formatados']:
                resultados_finais_saida.extend(resultado['dados_formatados'])

    print("\n💾 Salvando resultados nas Planilhas...")
    if atualizacoes_status:
        planilha_entrada.batch_update(atualizacoes_status)
        print(f"   ✓ Coluna de Status (F) atualizada na Entrada.")

    if resultados_finais_saida:
        planilha_saida.append_rows(resultados_finais_saida, value_input_option='USER_ENTERED')
        print(f"   ✓ {len(resultados_finais_saida)} linhas adicionadas na aba Resultados (Sem substituir fórmulas)!")
    
    print("\n✅ Máquina concluída com sucesso!")

if __name__ == "__main__":
    main()
