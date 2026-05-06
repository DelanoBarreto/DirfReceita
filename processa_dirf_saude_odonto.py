"""
processa_dirf_saude_odonto.py
------------------------------
Mesmo fluxo dos scripts anteriores, porém lê a fonte de dados
de 'SAUDE E ODONTO ATUALIZADO.xlsx' (aba DadosCompleto).

Diferenças em relação ao script Odontoart XLS:
  - Valores já são TOTAIS ANUAIS em reais (não mensais). Não há soma de 12 meses.
  - Agrupamento pelo COD completo (ex: '1-S', '7-O') para ligar titular -> dependentes.
  - TPBEN pode ser: TITULAR, CONJUGE, FILHO(A), OUTROS, ENTEADO, PAI/MAE.

Regras críticas (DOCUMENTACAO_DIRF.md):
  - Encoding SEMPRE cp1252 + newline='' para preservar \\r\\n original.
  - Substituição cirúrgica: apenas TPSE encontrados na planilha são substituídos.
  - Valor gravado em centavos: R$6.515,00 → 651500.
"""

import pandas as pd
import re


# ---------------------------------------------------------------------------
# Mapeamento de parentesco (DadosCompleto → código DIRF)
# ---------------------------------------------------------------------------
MAPA_PARENTESCO = {
    'CONJUGE':    '03',
    'COMPANHEIRO': '03',
    'FILHO':      '04',
    'FILHA':      '04',
    'ENTEADO':    '06',
    'ENTEADA':    '06',
    'PAI':        '08',
    'MAE':        '08',
    'MÃE':        '08',
    'OUTROS':     '10',
}


def get_parentesco_code(txt_relacao: str) -> str:
    txt = txt_relacao.upper()
    for k, v in MAPA_PARENTESCO.items():
        if k in txt:
            return v
    return '10'  # Outros/não mapeado


def limpar_cpf(cpf: str) -> str:
    """Remove pontos, traços e espaços — retorna apenas dígitos."""
    return re.sub(r'[.\-\s]', '', str(cpf)).strip()


# ---------------------------------------------------------------------------
# 1. Extração da planilha (aba DadosCompleto)
# ---------------------------------------------------------------------------
def extrair_dados_xlsx(xlsx_path: str) -> dict:
    """
    Retorna dicionário keyed pelo CPF do titular (somente dígitos):
    {
        '00000000000': {
            'nome': 'NOME DO TITULAR',
            'titular_valor': 651500,       # centavos (TotalGeral * 100)
            'dependentes': [
                {
                    'cpf':        '11111111111',
                    'nome':       'NOME DEP',
                    'parentesco': 'CONJUGE',
                    'valor':       651500
                },
                ...
            ]
        },
        ...
    }
    """
    df = pd.read_excel(xlsx_path, sheet_name='DadosCompleto')
    # Colunas: COD, NOME, DTNASC, TPBEN, CPF, TotalGeral

    df['cpf_clean']  = df['CPF'].astype(str).apply(limpar_cpf)
    df['NOME']       = df['NOME'].astype(str).str.strip()
    df['TPBEN']      = df['TPBEN'].astype(str).str.strip().str.upper()
    df['COD']        = df['COD'].astype(str).str.strip()
    df['TotalGeral'] = pd.to_numeric(df['TotalGeral'], errors='coerce').fillna(0)

    dados = {}

    # Agrupa pelo COD completo (ex: '1-S', '7-O') — cada COD = 1 família num plano
    for cod, grupo in df.groupby('COD'):
        titulares = grupo[grupo['TPBEN'] == 'TITULAR']
        if titulares.empty:
            continue

        row_tit    = titulares.iloc[0]
        cpf_tit    = row_tit['cpf_clean']
        nome_tit   = row_tit['NOME']
        # Valor anual já em reais → converte para centavos (padrão do PGD)
        valor_tit  = int(round(row_tit['TotalGeral'] * 100))

        if cpf_tit not in dados:
            dados[cpf_tit] = {
                'nome': nome_tit,
                'titular_valor': 0,
                'dependentes': {}
            }

        dados[cpf_tit]['titular_valor'] += valor_tit

        # Dependentes deste COD
        deps = grupo[grupo['TPBEN'] != 'TITULAR']
        for _, dep_row in deps.iterrows():
            cpf_dep      = dep_row['cpf_clean']
            nome_dep     = dep_row['NOME']
            parentesco   = dep_row['TPBEN']
            valor_dep    = int(round(dep_row['TotalGeral'] * 100))

            if cpf_dep == cpf_tit:
                continue  # segurança

            if cpf_dep not in dados[cpf_tit]['dependentes']:
                dados[cpf_tit]['dependentes'][cpf_dep] = {
                    'cpf':        cpf_dep,
                    'nome':       nome_dep,
                    'parentesco': parentesco,
                    'valor':      0
                }
            dados[cpf_tit]['dependentes'][cpf_dep]['valor'] += valor_dep

    # Converte dicionário de dependentes para lista
    for cpf in dados:
        dados[cpf]['dependentes'] = list(dados[cpf]['dependentes'].values())

    return dados


# ---------------------------------------------------------------------------
# 2. Injeção no arquivo DIRF (substituição cirúrgica — igual aos scripts anteriores)
# ---------------------------------------------------------------------------
def processar_dirf(txt_entrada: str, txt_saida: str, dados_plano: dict):
    """
    Lê o TXT da DIRF linha a linha.
    - Linhas que NÃO são TPSE: copia intactas.
    - Linhas TPSE cujo CPF está em dados_plano: substitui com valor individual
      do titular + DTPSE de cada dependente logo abaixo.
    - Linhas TPSE cujo CPF NÃO está no dicionário: copia intactas.

    CRÍTICO: encoding=cp1252 e newline='' para não corromper \\r\\n.
    """
    with open(txt_entrada, 'r', encoding='cp1252', newline='') as fin, \
         open(txt_saida,   'w', encoding='cp1252', newline='') as fout:

        for linha in fin:
            if not linha.startswith('TPSE|'):
                fout.write(linha)
                continue

            partes      = linha.split('|')
            cpf_titular = partes[1].strip()

            if cpf_titular not in dados_plano:
                # CPF não encontrado na planilha — mantém original
                fout.write(linha)
                continue

            info = dados_plano[cpf_titular]

            # TPSE do titular (valor anual em centavos)
            fout.write(f"TPSE|{cpf_titular}|{info['nome']}|{info['titular_valor']}|\r\n")

            # DTPSE para cada dependente
            for dep in info['dependentes']:
                cod_par = get_parentesco_code(dep['parentesco'])
                fout.write(f"DTPSE|{dep['cpf']}||{dep['nome']}|{cod_par}|{dep['valor']}|\r\n")


# ---------------------------------------------------------------------------
# 3. Ponto de entrada — TRAVA DE SEGURANÇA: apenas os 3 primeiros titulares
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    XLSX_PATH   = 'c:/Antigravity/DirfReceita/SAUDE E ODONTO ATUALIZADO.xlsx'
    TXT_ENTRADA = 'c:/Antigravity/DirfReceita/2026.txt'
    TXT_SAIDA   = 'c:/Antigravity/DirfReceita/2026_processado_saude_odonto.txt'

    print("Extraindo dados de 'SAUDE E ODONTO ATUALIZADO.xlsx'...")
    dados = extrair_dados_xlsx(XLSX_PATH)
    print(f"Total de titulares encontrados: {len(dados)}")

    # =====================================================================
    # TRAVA DE SEGURANÇA — remover [:3] após validar no PGD
    # =====================================================================
    keys_teste  = list(dados.keys())[:3]
    dados_teste = {k: dados[k] for k in keys_teste}

    print("\n--- 3 titulares que serão processados neste teste ---")
    for cpf, info in dados_teste.items():
        val_reais = info['titular_valor'] / 100
        print(f"  CPF: {cpf} | {info['nome']} | Anual: R$ {val_reais:,.2f} | Gravado: {info['titular_valor']}")
        for dep in info['dependentes']:
            dep_reais = dep['valor'] / 100
            print(f"      Dep: {dep['nome']} | {dep['parentesco']} | R$ {dep_reais:,.2f} | Gravado: {dep['valor']}")
    print("------------------------------------------------------\n")

    processar_dirf(TXT_ENTRADA, TXT_SAIDA, dados_teste)

    # Verificação rápida do output
    tpse_count, dtpse_count = 0, 0
    with open(TXT_SAIDA, 'r', encoding='cp1252', newline='') as f:
        for linha in f:
            if linha.startswith('TPSE|'):  tpse_count += 1
            if linha.startswith('DTPSE|'): dtpse_count += 1

    print(f"Arquivo gerado: {TXT_SAIDA}")
    print(f"  TPSE  no arquivo: {tpse_count}")
    print(f"  DTPSE no arquivo: {dtpse_count}")
    print("Valide no PGD e, se aprovado, remova o slice [:3] para processar todos.")
