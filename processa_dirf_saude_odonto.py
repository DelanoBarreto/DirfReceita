
import pandas as pd
import re

# ---------------------------------------------------------------------------
# Mapeamento e Auxiliares
# ---------------------------------------------------------------------------
MAPA_PARENTESCO = {
    'CONJUGE': '03', 'COMPANHEIRO': '03', 'FILHO': '04', 'FILHA': '04',
    'ENTEADO': '06', 'ENTEADA': '06', 'PAI': '08', 'MAE': '08', 'MÃE': '08', 'OUTROS': '10',
}

def get_parentesco_code(txt_relacao: str) -> str:
    txt = str(txt_relacao).upper()
    for k, v in MAPA_PARENTESCO.items():
        if k in txt: return v
    return '10'

def limpar_cpf(cpf: str) -> str:
    # Remove pontos, traços e espaços
    c = re.sub(r'[.\-\s]', '', str(cpf)).strip()
    if not c or c.lower() == 'nan' or c == '0': return ""
    # Remove parte decimal se houver (.0)
    c = c.split('.')[0]
    # Garante 11 dígitos (P0: Resolve erro de tamanho inválido)
    return c.zfill(11)

# ---------------------------------------------------------------------------
# 1. Extração da planilha
# ---------------------------------------------------------------------------
def extrair_dados_xlsx(xlsx_path: str) -> dict:
    df = pd.read_excel(xlsx_path, sheet_name='DadosCompleto')
    df['cpf_clean']  = df['CPF'].astype(str).apply(limpar_cpf)
    df['NOME']       = df['NOME'].astype(str).str.strip()
    df['TPBEN']      = df['TPBEN'].astype(str).str.strip().str.upper()
    df['COD']        = df['COD'].astype(str).str.strip()
    df['TotalGeral'] = pd.to_numeric(df['TotalGeral'], errors='coerce').fillna(0)
    df['DTNASC']     = df['DTNASC'].astype(str).str.strip().replace('nan', '')

    dados = {}
    for cod, grupo in df.groupby('COD'):
        titulares = grupo[grupo['TPBEN'] == 'TITULAR']
        if titulares.empty: continue
        row_tit = titulares.iloc[0]
        cpf_tit = row_tit['cpf_clean']
        if cpf_tit not in dados:
            dados[cpf_tit] = {'nome': row_tit['NOME'], 'titular_valor': 0, 'dependentes': {}}
        dados[cpf_tit]['titular_valor'] += int(round(row_tit['TotalGeral'] * 100))
        deps = grupo[grupo['TPBEN'] != 'TITULAR']
        for _, dep_row in deps.iterrows():
            cpf_dep = dep_row['cpf_clean']
            if cpf_dep == cpf_tit: continue
            key_dep = cpf_dep if cpf_dep else dep_row['NOME']
            if key_dep not in dados[cpf_tit]['dependentes']:
                dados[cpf_tit]['dependentes'][key_dep] = {
                    'cpf': cpf_dep, 'nome': dep_row['NOME'], 
                    'parentesco': dep_row['TPBEN'], 'valor': 0, 'dtnasc': dep_row['DTNASC']
                }
            dados[cpf_tit]['dependentes'][key_dep]['valor'] += int(round(dep_row['TotalGeral'] * 100))

    for cpf in dados:
        lista_deps = list(dados[cpf]['dependentes'].values())
        dados[cpf]['dependentes'] = sorted(lista_deps, key=lambda x: (x['cpf'], x['dtnasc']))
    return dados

# ---------------------------------------------------------------------------
# 2. Processamento v4.1 (Deduplicação de RTPA + Padding de CPF)
# ---------------------------------------------------------------------------
def processar_dirf_v4_1(txt_entrada, txt_saida, dados_hapvida):
    cnpj_hapvida = b"63554067000198"
    
    print("  - Fazendo leitura prévia de cadastros...")
    cpfs_com_cadastro = set()
    with open(txt_entrada, 'rb') as f:
        for linha in f:
            if linha.startswith(b'BPFDEC|'):
                cpfs_com_cadastro.add(linha.split(b'|')[1].decode('cp1252').strip())

    print("  - Processando e Sanitizando arquivo...")
    with open(txt_entrada, 'rb') as fin, open(txt_saida, 'wb') as fout:
        linhas = fin.readlines()
        i = 0
        
        # Estado para deduplicação de INFPA dentro de BPFDEC
        infpas_vistos = set()
        
        while i < len(linhas):
            linha = linhas[i]
            
            # Resetamos a lista de INFPA ao entrar em um novo funcionário
            if linha.startswith(b'BPFDEC|'):
                infpas_vistos = set()
                fout.write(linha)
                i += 1
                continue

            # DEDUPLICAÇÃO DE RENDIMENTOS (Resolve erro RTPA único)
            if linha.startswith(b'INFPA|'):
                cpf_infpa = linha.split(b'|')[1].decode('cp1252').strip()
                if cpf_infpa in infpas_vistos:
                    # Pula este bloco INFPA e o próximo RTPA
                    i += 1
                    if i < len(linhas) and linhas[i].startswith(b'RTPA|'):
                        i += 1
                    continue
                else:
                    infpas_vistos.add(cpf_infpa)
                    fout.write(linha)
                    i += 1
                    continue

            # BLOCO DE SAÚDE
            if linha.startswith(b'OPSE|'):
                partes = linha.split(b'|')
                cnpj_atual = partes[1].strip()
                
                bloco_opse_head = linha
                registros_saude = {} 
                i += 1
                while i < len(linhas) and not (linhas[i].startswith(b'OPSE|') or linhas[i].startswith(b'FIMDIRF|')):
                    l = linhas[i]
                    if l.startswith(b'TPSE|'):
                        cpf = l.split(b'|')[1].decode('cp1252').strip()
                        registros_saude[cpf] = {'original_tpse': l, 'original_dtpses': []}
                        current_cpf = cpf
                    elif l.startswith(b'DTPSE|') and 'current_cpf' in locals():
                        registros_saude[current_cpf]['original_dtpses'].append(l)
                    i += 1
                
                if cnpj_atual == cnpj_hapvida:
                    fout.write(bloco_opse_head)
                    todos_cpfs = set(registros_saude.keys()) | (set(dados_hapvida.keys()) & cpfs_com_cadastro)
                    for cpf in sorted(todos_cpfs):
                        if cpf in dados_hapvida:
                            info = dados_hapvida[cpf]
                            fout.write(f"TPSE|{cpf}|{info['nome']}|{info['titular_valor']}|\r\n".encode('cp1252'))
                            for dep in info['dependentes']:
                                cod_par = get_parentesco_code(dep['parentesco'])
                                dtnasc = "" if dep['cpf'] else dep['dtnasc']
                                fout.write(f"DTPSE|{dep['cpf']}|{dtnasc}|{dep['nome']}|{cod_par}|{dep['valor']}|\r\n".encode('cp1252'))
                        else:
                            item = registros_saude[cpf]
                            fout.write(item['original_tpse'])
                            for d in item['original_dtpses']: fout.write(d)
                else:
                    fout.write(bloco_opse_head)
                    for cpf in sorted(registros_saude.keys()):
                        item = registros_saude[cpf]
                        fout.write(item['original_tpse'])
                        for d in item['original_dtpses']: fout.write(d)
                continue

            fout.write(linha)
            i += 1

if __name__ == '__main__':
    XLSX_PATH = 'Base/SAUDE E ODONTO ATUALIZADO.xlsx'
    TXT_IN    = 'Importação/2026.txt'
    TXT_OUT   = 'Importação/2026_processado_saude_odonto.txt'

    print("Iniciando sanitização profunda...")
    dados = extrair_dados_xlsx(XLSX_PATH)
    processar_dirf_v4_1(TXT_IN, TXT_OUT, dados)
    print("\nConcluído! CPFs corrigidos e blocos duplicados removidos.")
