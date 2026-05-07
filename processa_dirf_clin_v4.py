
import pandas as pd
import re

# ---------------------------------------------------------------------------
# Mapeamento e Auxiliares
# ---------------------------------------------------------------------------
MAPA_PARENTESCO = {
    'CONJUGE': '03', 'COMPANHEIRO': '03', 'FILHO': '04', 'FILHA': '04',
    'ENTEADO': '06', 'ENTEADA': '06', 'PAI': '08', 'MAE': '08', 'MÃE': '08', 
    'TITULAR': 'TITULAR'
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
# 1. Carregar dados consolidados da Clin (CSV)
# ---------------------------------------------------------------------------
def carregar_dados_clin(csv_path: str) -> dict:
    df = pd.read_csv(csv_path)
    dados = {}
    for _, row in df.iterrows():
        cpf_tit = limpar_cpf(row['titular_cpf'])
        if not cpf_tit: continue
        if cpf_tit not in dados: dados[cpf_tit] = {'dependentes': []}
        valor_centavos = int(round(float(row['valor']) * 100))
        if row['parentesco'].upper() == 'TITULAR':
            dados[cpf_tit]['nome'] = row['nome']
            dados[cpf_tit]['titular_valor'] = valor_centavos
        else:
            # Pré-sanitização para ordenação correta
            cpf_dep = limpar_cpf(row['cpf'])
            dt_dep = formatar_data_dirf(str(row['dtnasc']))
            
            # Se CPF inválido, joga pra vazio para ordenar corretamente
            if not validar_cpf(cpf_dep) and dt_dep:
                cpf_dep_final = ""
                dt_dep_final = dt_dep
            else:
                cpf_dep_final = cpf_dep
                dt_dep_final = "" if cpf_dep else dt_dep

            dados[cpf_tit]['dependentes'].append({
                'cpf': cpf_dep_final,
                'nome': row['nome'],
                'dtnasc': dt_dep_final,
                'parentesco': row['parentesco'],
                'valor': valor_centavos
            })
    
    # ORDENAÇÃO CRÍTICA PARA PGD: Vazio vem primeiro, depois por número, depois por data
    for cpf in dados:
        dados[cpf]['dependentes'] = sorted(
            dados[cpf]['dependentes'], 
            key=lambda x: (x['cpf'] == "", x['cpf'], x['dtnasc'])
        )
        # Ajuste fino: os vazios (x['cpf']=="") devem vir antes dos preenchidos.
        # No Python, True (1) vem depois de False (0), então invertemos.
        dados[cpf]['dependentes'] = sorted(
            dados[cpf]['dependentes'], 
            key=lambda x: (0 if x['cpf'] == "" else 1, x['cpf'], x['dtnasc'])
        )

    return dados

# ---------------------------------------------------------------------------
# 2. Processamento Final
# ---------------------------------------------------------------------------
def processar_dirf_clin(txt_entrada, txt_saida, dados_plano):
    cnpj_clin = b"01867792000169"
    cpfs_com_cadastro = {}
    with open(txt_entrada, 'rb') as f:
        for linha in f:
            if linha.startswith(b'BPFDEC|'):
                partes = linha.split(b'|')
                cpf = partes[1].decode('cp1252').strip()
                nome = partes[2].decode('cp1252').strip()
                cpfs_com_cadastro[cpf] = nome

    pendencias = []
    with open(txt_entrada, 'rb') as fin, open(txt_saida, 'wb') as fout:
        linhas = fin.readlines()
        i = 0
        while i < len(linhas):
            linha = linhas[i]
            if linha.startswith(b'BPFDEC|'):
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
                
                if cnpj_atual == cnpj_clin:
                    fout.write(bloco_opse_head)
                    todos_cpfs = set(registros_saude.keys()) | (set(dados_plano.keys()) & set(cpfs_com_cadastro.keys()))
                    for cpf in sorted(todos_cpfs):
                        if cpf in dados_plano:
                            info = dados_plano[cpf]
                            nome_final = info.get('nome') or cpfs_com_cadastro.get(cpf, "NOME NAO ENCONTRADO")
                            fout.write(f"TPSE|{cpf}|{nome_final}|{info.get('titular_valor', 0)}|\r\n".encode('cp1252'))
                            for dep in info['dependentes']:
                                cod_par = get_parentesco_code(dep['parentesco'])
                                if not dep['cpf'] and not dep['dtnasc']:
                                    pendencias.append(f"{dep['nome']} - Titular: {nome_final}")
                                fout.write(f"DTPSE|{dep['cpf']}|{dep['dtnasc']}|{dep['nome']}|{cod_par}|{dep['valor']}|\r\n".encode('cp1252'))
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

    if pendencias:
        with open('Doc/PENDENCIAS_MANUAIS_NECESSARIAS.txt', 'w', encoding='utf-8') as f:
            f.write("DEPENDENTES COM DADOS INSUFICIENTES (REQUER AJUSTE NO PGD)\n")
            f.write("="*70 + "\n")
            for p in pendencias: f.write(p + "\n")

if __name__ == '__main__':
    dados = carregar_dados_clin('Base/clin_consolidado.csv')
    processar_dirf_clin('Importação/2026_HAPVIDA_ODONTOART.txt', 'Importação/2026_FINAL_COMPLETO.txt', dados)
    print(f"\nConcluído! Arquivo FINAL Re-ordenado: Importação/2026_FINAL_COMPLETO.txt")
