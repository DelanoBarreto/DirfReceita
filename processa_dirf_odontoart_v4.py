
import pandas as pd
import re

# ---------------------------------------------------------------------------
# Mapeamento e Auxiliares
# ---------------------------------------------------------------------------
MAPA_PARENTESCO = {
    'CONJUGE': '03', 'COMPANHEIRO': '03', 'FILHO': '04', 'FILHA': '04',
    'ENTEADO': '06', 'ENTEADA': '06', 'PAI': '08', 'MAE': '08', 'MÃE': '08', 
    'NETO': '10', 'NETA': '10', 'OUTROS': '10', 'AGREGADO': '10'
}

def get_parentesco_code(txt_relacao: str) -> str:
    txt = str(txt_relacao).upper()
    for k, v in MAPA_PARENTESCO.items():
        if k in txt: return v
    return '10'

def limpar_cpf(cpf: str) -> str:
    if not cpf or str(cpf).lower() == 'nan': return ""
    c = re.sub(r'[.\-]', '', str(cpf)).strip()
    match = re.search(r'\d{11}', c)
    if match: return match.group(0)
    c = re.sub(r'\D', '', c)
    if not c: return ""
    return c[:11].zfill(11)

def validar_cpf(cpf: str) -> bool:
    """Validação matemática de dígito verificador de CPF."""
    if not cpf or len(cpf) != 11 or cpf == cpf[0] * 11: return False
    for i in range(9, 11):
        s = sum(int(cpf[num]) * ((i + 1) - num) for num in range(i))
        r = (s * 10) % 11
        if r == 10: r = 0
        if r != int(cpf[i]): return False
    return True

def formatar_data_dirf(data_str: str) -> str:
    if not data_str or data_str.lower() == 'nan': return ""
    limpo = re.sub(r'\D', '', data_str)
    if len(limpo) == 8:
        if '/' in data_str or (not '-' in data_str and int(limpo[:2]) <= 31 and int(limpo[4:]) > 1900):
            return limpo[4:] + limpo[2:4] + limpo[:2]
        return limpo
    return limpo

# ---------------------------------------------------------------------------
# 1. Extração da planilha Odontoart
# ---------------------------------------------------------------------------
def extrair_dados_odontoart(xlsx_path: str) -> dict:
    df = pd.read_excel(xlsx_path)
    df.columns = [c.strip() for c in df.columns]
    
    df['cpf_clean'] = df['CPF'].astype(str).apply(limpar_cpf)
    df['Responsável'] = df['Responsável'].astype(str).str.strip()
    df['Usuário'] = df['Usuário'].astype(str).str.strip()
    df['Parentesco'] = df['Parentesco'].astype(str).str.strip().str.upper()
    df['Cód'] = df['Cód'].astype(str).str.strip()
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
    df['Data Nascimento'] = df['Data Nascimento'].astype(str).str.strip()

    dados = {}
    for cod, grupo in df.groupby('Cód'):
        titulares = grupo[grupo['Parentesco'] == 'TITULAR']
        if titulares.empty: continue
        row_tit = titulares.iloc[0]
        cpf_tit = row_tit['cpf_clean']
        if not cpf_tit: continue
        
        if cpf_tit not in dados:
            dados[cpf_tit] = {'nome': row_tit['Usuário'], 'titular_valor': 0, 'dependentes': {}}
        dados[cpf_tit]['titular_valor'] += int(round(row_tit['Valor'] * 100))

        deps = grupo[grupo['Parentesco'] != 'TITULAR']
        for _, dep_row in deps.iterrows():
            cpf_dep = dep_row['cpf_clean']
            if cpf_dep == cpf_tit: continue
            key_dep = cpf_dep if cpf_dep else dep_row['Usuário']
            if key_dep not in dados[cpf_tit]['dependentes']:
                dados[cpf_tit]['dependentes'][key_dep] = {
                    'cpf': cpf_dep, 'nome': dep_row['Usuário'], 
                    'parentesco': dep_row['Parentesco'], 'valor': 0, 
                    'dtnasc': formatar_data_dirf(dep_row['Data Nascimento'])
                }
            dados[cpf_tit]['dependentes'][key_dep]['valor'] += int(round(dep_row['Valor'] * 100))

    for cpf in dados:
        lista_deps = list(dados[cpf]['dependentes'].values())
        dados[cpf]['dependentes'] = sorted(lista_deps, key=lambda x: (x['cpf'], x['dtnasc']))
    return dados

# ---------------------------------------------------------------------------
# 2. Processamento Binário Sanitizado
# ---------------------------------------------------------------------------
def processar_dirf_odontoart(txt_entrada, txt_saida, dados_plano):
    cnpj_odontoart = b"03187913000157"
    cpfs_com_cadastro = set()
    with open(txt_entrada, 'rb') as f:
        for linha in f:
            if linha.startswith(b'BPFDEC|'):
                cpfs_com_cadastro.add(linha.split(b'|')[1].decode('cp1252').strip())

    with open(txt_entrada, 'rb') as fin, open(txt_saida, 'wb') as fout:
        linhas = fin.readlines()
        i = 0
        infpas_vistos = set()
        while i < len(linhas):
            linha = linhas[i]
            if linha.startswith(b'BPFDEC|'):
                infpas_vistos = set()
                fout.write(linha)
                i += 1
                continue
            if linha.startswith(b'INFPA|'):
                cpf_infpa = linha.split(b'|')[1].decode('cp1252').strip()
                if cpf_infpa in infpas_vistos:
                    i += 1
                    if i < len(linhas) and linhas[i].startswith(b'RTPA|'): i += 1
                    continue
                else:
                    infpas_vistos.add(cpf_infpa)
                    fout.write(linha)
                    i += 1
                    continue

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
                
                if cnpj_atual == cnpj_odontoart:
                    fout.write(bloco_opse_head)
                    todos_cpfs = set(registros_saude.keys()) | (set(dados_plano.keys()) & cpfs_com_cadastro)
                    for cpf in sorted(todos_cpfs):
                        if cpf in dados_plano:
                            info = dados_plano[cpf]
                            fout.write(f"TPSE|{cpf}|{info['nome']}|{info['titular_valor']}|\r\n".encode('cp1252'))
                            for dep in info['dependentes']:
                                cod_par = get_parentesco_code(dep['parentesco'])
                                # Lógica de resgate: Se CPF inválido e tem data, limpa CPF
                                cpf_out = dep['cpf']
                                dtnasc = dep['dtnasc']
                                if not validar_cpf(cpf_out) and dtnasc:
                                    cpf_out = ""
                                elif dep['cpf']: # Se tem CPF mas ele é válido, data fica vazia
                                    dtnasc = ""
                                fout.write(f"DTPSE|{cpf_out}|{dtnasc}|{dep['nome']}|{cod_par}|{dep['valor']}|\r\n".encode('cp1252'))
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
    XLSX_PATH = 'Base/Odontoart 2025Atual.xlsx'
    TXT_IN    = 'Importação/2026_processado_saude_odonto.txt'
    TXT_OUT   = 'Importação/2026_HAPVIDA_ODONTOART.txt'
    dados = extrair_dados_odontoart(XLSX_PATH)
    processar_dirf_odontoart(TXT_IN, TXT_OUT, dados)
    print(f"\nConcluído! Arquivo Odontoart com Validador: {TXT_OUT}")
