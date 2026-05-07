
import pandas as pd
import re

def limpar_cpf(cpf):
    return re.sub(r'[.\-\s]', '', str(cpf)).strip()

def auditoria_dirf(xlsx_path, txt_path):
    # 1. Carregar CPFs da Planilha
    print(f"Lendo planilha {xlsx_path}...")
    df = pd.read_excel(xlsx_path, sheet_name='DadosCompleto')
    df['cpf_clean'] = df['CPF'].astype(str).apply(limpar_cpf)
    cpfs_planilha = set(df[df['TPBEN'] == 'TITULAR']['cpf_clean'].unique())
    print(f"Total de Titulares na Planilha: {len(cpfs_planilha)}")

    # 2. Carregar CPFs do TXT original
    print(f"Analisando arquivo {txt_path}...")
    cpfs_no_arquivo = set()
    cpfs_com_saude = set()
    
    with open(txt_path, 'r', encoding='cp1252') as f:
        for linha in f:
            if linha.startswith('BPFDEC|'):
                cpfs_no_arquivo.add(linha.split('|')[1].strip())
            if linha.startswith('TPSE|'):
                cpfs_com_saude.add(linha.split('|')[1].strip())

    print(f"Total de Funcionários (BPFDEC) no arquivo: {len(cpfs_no_arquivo)}")
    print(f"Total de Titulares com Saúde (TPSE) no arquivo: {len(cpfs_com_saude)}")

    # 3. Cruzamento de Dados
    fora_do_arquivo = cpfs_planilha - cpfs_no_arquivo
    no_arquivo_sem_saude = (cpfs_planilha & cpfs_no_arquivo) - cpfs_com_saude
    processados_ok = cpfs_planilha & cpfs_com_saude

    print("\n" + "="*50)
    print("RESULTADO DA AUDITORIA")
    print("="*50)
    print(f"1. CPFs que NEM EXISTEM no arquivo TXT: {len(fora_do_arquivo)}")
    print(f"2. CPFs no arquivo mas SEM LINHA DE SAÚDE (TPSE): {len(no_arquivo_sem_saude)}")
    print(f"3. CPFs que foram processados corretamente: {len(processados_ok)}")
    print("="*50)

    if fora_do_arquivo:
        print("\nExemplos de CPFs que NÃO existem no arquivo (Top 5):")
        for c in list(fora_do_arquivo)[:5]:
            nome = df[df['cpf_clean'] == c]['NOME'].iloc[0]
            print(f"  - {c} ({nome})")

    if no_arquivo_sem_saude:
        print("\nExemplos de CPFs no arquivo mas SEM linha TPSE (Top 5):")
        for c in list(no_arquivo_sem_saude)[:5]:
            nome = df[df['cpf_clean'] == c]['NOME'].iloc[0]
            print(f"  - {c} ({nome})")

if __name__ == '__main__':
    auditoria_dirf('Base/SAUDE E ODONTO ATUALIZADO.xlsx', 'Importação/2026.txt')
