"""
processa_dirf_odontoart_xls.py
-------------------------------
Mesmo fluxo de 'processa_dirf_odontoart.py', porém lê a fonte de dados
da planilha Excel (Odontoart 2025.xls) em vez do PDF.

Regras críticas (documentadas em DOCUMENTACAO_DIRF.md):
  - Encoding SEMPRE cp1252 + newline='' para preservar \\r\\n original.
  - NUNCA recriar estrutura DIRF — apenas substituição cirúrgica de TPSE.
  - TPSE grava o titular; DTPSE grava cada dependente logo abaixo.

Lógica da planilha:
  - O arquivo .xls é um HTML disfarçado; usamos pandas.read_html().
  - Cada linha = 1 mês de competência. Valor anual = soma dos 12 meses.
  - A coluna "Responsável" / CPF do titular identifica o grupo.
  - Parentesco "TITULAR" => linha TPSE; demais => linhas DTPSE.
"""

import pandas as pd
import re


# ---------------------------------------------------------------------------
# Mapeamento de parentesco (texto planilha → código DIRF)
# ---------------------------------------------------------------------------
MAPA_PARENTESCO = {
    'CONJUGE':   '03',
    'COMPANHEIRO': '03',
    'FILHO':     '04',
    'FILHA':     '04',
    'ENTEADO':   '06',
    'ENTEADA':   '06',
    'PAI':       '08',
    'MAE':       '08',
    'MÃE':       '08',
    'AGREGADO':  '10',
}


def get_parentesco_code(txt_relacao: str) -> str:
    txt = txt_relacao.upper()
    for k, v in MAPA_PARENTESCO.items():
        if k in txt:
            return v
    return '10'  # Outro


def limpar_cpf(cpf: str) -> str:
    """Remove pontos e traços, retorna apenas dígitos."""
    return re.sub(r'[.\-]', '', str(cpf)).strip()


# ---------------------------------------------------------------------------
# 1. Extração dos dados da planilha
# ---------------------------------------------------------------------------
def extrair_dados_xls(xls_path: str) -> dict:
    """
    Retorna dicionário keyed pelo CPF do titular (somente dígitos):
    {
        '00000000000': {
            'nome': 'NOME DO TITULAR',
            'titular_valor': 178800,          # centavos (valor anual * 100)
            'dependentes': [
                {
                    'cpf':        '11111111111',
                    'nome':       'NOME DEP',
                    'parentesco': 'CONJUGE/COMPANHEIRO',
                    'valor':       89400
                },
                ...
            ]
        },
        ...
    }
    """
    # O .xls é um HTML exportado — pandas lê as tabelas HTML embutidas
    tables = pd.read_html(xls_path, encoding='latin1')

    # Tabela 1 contém os dados (tabela 0 é o cabeçalho do relatório)
    df = tables[1].copy()

    # Colunas esperadas: Cód, Responsável, CPF, Usuário, Data Nascimento, Parentesco, Valor
    df.columns = ['cod', 'responsavel', 'cpf', 'usuario', 'dt_nasc', 'parentesco', 'valor']

    # Limpa CPFs e normaliza
    df['cpf'] = df['cpf'].astype(str).apply(limpar_cpf)
    df['responsavel'] = df['responsavel'].astype(str).str.strip()
    df['usuario'] = df['usuario'].astype(str).str.strip()
    df['parentesco'] = df['parentesco'].astype(str).str.strip()
    df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)

    dados = {}

    # Identifica o CPF do titular de cada grupo (cod único por responsável)
    # Para cada 'cod', o titular é a linha com parentesco == TITULAR
    for cod, grupo in df.groupby('cod'):
        titulares = grupo[grupo['parentesco'].str.upper().str.contains('TITULAR')]
        if titulares.empty:
            continue

        # Nome e CPF do titular (primeira ocorrência)
        nome_titular = titulares.iloc[0]['responsavel']
        cpf_titular  = limpar_cpf(titulares.iloc[0]['cpf'])

        # Valor anual do titular = soma dos 12 meses, armazenado em centavos
        # CRÍTICO: mesmo formato do script PDF — ex: R$17.880,00 -> 1788000
        # O PGD espera esse valor inteiro sem vírgula (centavos sem separador)
        valor_titular = int(round(titulares['valor'].sum() * 100))

        if cpf_titular not in dados:
            dados[cpf_titular] = {
                'nome': nome_titular,
                'titular_valor': valor_titular,
                'dependentes': []
            }

        # Dependentes: todas as linhas que NÃO são TITULAR
        deps = grupo[~grupo['parentesco'].str.upper().str.contains('TITULAR')]
        dependentes_processados = {}

        for _, row in deps.iterrows():
            cpf_dep = limpar_cpf(row['cpf'])
            if cpf_dep == cpf_titular:
                continue  # segurança: ignora se CPF dep == titular

            if cpf_dep not in dependentes_processados:
                dependentes_processados[cpf_dep] = {
                    'cpf':        cpf_dep,
                    'nome':       row['usuario'],
                    'parentesco': row['parentesco'],
                    'valor':      0
                }
            # Acumula em centavos — mesmo padrão do script PDF
            dependentes_processados[cpf_dep]['valor'] += int(round(row['valor'] * 100))

        dados[cpf_titular]['dependentes'] = list(dependentes_processados.values())

    return dados


# ---------------------------------------------------------------------------
# 2. Injeção no arquivo DIRF (substituição cirúrgica — igual ao script PDF)
# ---------------------------------------------------------------------------
def processar_dirf(txt_entrada: str, txt_saida: str, dados_plano: dict, limit_records=50):
    """
    Lê o TXT da DIRF linha a linha.
    - Mantém apenas os 50 primeiros funcionários + os funcionários que estão em dados_plano.
    - Substitui cirurgicamente o TPSE e insere os DTPSE corretos.
    CRÍTICO: encoding=cp1252 e newline='' para não corromper \\r\\n.
    """
    cpfs_mantidos = set()
    bpfdec_lidos = 0
    manter_bloco_atual = True

    with open(txt_entrada, 'r', encoding='cp1252', newline='') as fin, \
         open(txt_saida,   'w', encoding='cp1252', newline='') as fout:

        for linha in fin:
            if linha.startswith('BPFDEC|'):
                partes = linha.split('|')
                cpf = partes[1].strip()
                
                if cpf in dados_plano or bpfdec_lidos < limit_records:
                    manter_bloco_atual = True
                    cpfs_mantidos.add(cpf)
                    if cpf not in dados_plano:
                        bpfdec_lidos += 1
                else:
                    manter_bloco_atual = False
            
            if linha.startswith('PSE|'):
                manter_bloco_atual = True
                
            if linha.startswith('TPSE|'):
                partes = linha.split('|')
                cpf_titular = partes[1].strip()
                
                if cpf_titular not in cpfs_mantidos:
                    continue # Pula TPSE de quem não foi incluído

                if cpf_titular in dados_plano:
                    info = dados_plano[cpf_titular]
                    fout.write(f"TPSE|{cpf_titular}|{info['nome']}|{info['titular_valor']}|\r\n")
                    for dep in info['dependentes']:
                        cod_par = get_parentesco_code(dep['parentesco'])
                        fout.write(f"DTPSE|{dep['cpf']}||{dep['nome']}|{cod_par}|{dep['valor']}|\r\n")
                    continue
                else:
                    fout.write(linha)
                    continue

            if linha.startswith('DTPSE|'):
                continue # Original não tinha

            if linha.startswith('FIMDIRF|'):
                fout.write(linha)
                break

            if not manter_bloco_atual:
                continue

            fout.write(linha)


# ---------------------------------------------------------------------------
# 3. Ponto de entrada — TRAVA DE SEGURANÇA: apenas os 3 primeiros titulares
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    XLS_PATH = 'Base/Odontoart 2025.xls'
    TXT_ENTRADA = 'Importação/2026.txt'
    TXT_SAIDA   = 'Importação/2026_processado_xls.txt'

    print("Extraindo dados da planilha Excel...")
    dados = extrair_dados_xls(XLS_PATH)
    print(f"Total de titulares encontrados na planilha: {len(dados)}")

    # =====================================================================
    # TRAVA DE SEGURANÇA — remover [:3] após validar no PGD
    # =====================================================================
    keys_teste = list(dados.keys())[:5]
    dados_teste = {k: dados[k] for k in keys_teste}

    print(f"\n--- {len(keys_teste)} titulares que serão processados neste teste ---")
    for cpf, info in dados_teste.items():
        val_reais = info['titular_valor'] / 100
        print(f"  CPF: {cpf} | Nome: {info['nome']} | Anual Titular: R$ {val_reais:,.2f} | Gravado como: {info['titular_valor']}")
        for dep in info['dependentes']:
            dep_reais = dep['valor'] / 100
            print(f"      Dep: {dep['nome']} | {dep['parentesco']} | R$ {dep_reais:,.2f} | Gravado como: {dep['valor']}")
    print("------------------------------------------------------\n")

    processar_dirf(TXT_ENTRADA, TXT_SAIDA, dados_teste)
    print(f"Sucesso! Arquivo gerado em: {TXT_SAIDA}")
    print("Valide a importação no PGD e, se aprovado, remova o slice [:3] na linha marcada.")
