
import pandas as pd
import re

def limpar_cpf(cpf):
    return re.sub(r'[.\-\s]', '', str(cpf)).strip()

def gerar_relatorio_ausentes(xlsx_path, txt_path, report_path):
    # 1. Carregar CPFs da Planilha
    df = pd.read_excel(xlsx_path, sheet_name='DadosCompleto')
    df['cpf_clean'] = df['CPF'].astype(str).apply(limpar_cpf)
    titulares_planilha = df[df['TPBEN'] == 'TITULAR'][['cpf_clean', 'NOME']].drop_duplicates()
    
    # 2. Carregar CPFs do TXT original (Somente BPFDEC)
    cpfs_no_arquivo = set()
    with open(txt_path, 'r', encoding='cp1252') as f:
        for linha in f:
            if linha.startswith('BPFDEC|'):
                cpfs_no_arquivo.add(linha.split('|')[1].strip())

    # 3. Identificar os 18 ausentes
    ausentes = titulares_planilha[~titulares_planilha['cpf_clean'].isin(cpfs_no_arquivo)]

    # 4. Gravar relatório
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO DE TITULARES NA PLANILHA HAPVIDA AUSENTES NO ARQUIVO DIRF (2026.txt)\n")
        f.write("="*80 + "\n")
        f.write(f"{'CPF':<15} | {'NOME'}\n")
        f.write("-"*80 + "\n")
        for _, row in ausentes.sort_values('NOME').iterrows():
            f.write(f"{row['cpf_clean']:<15} | {row['NOME']}\n")
        f.write("-"*80 + "\n")
        f.write(f"Total: {len(ausentes)} registros.\n")
        f.write("="*80 + "\n")
        f.write("\nOBSERVAÇÃO: Estes funcionários não possuem o registro 'BPFDEC' no arquivo original.\n")
        f.write("A importação de dados de saúde para estes CPFs falhará no PGD se não for criado o cadastro deles.\n")

    print(f"Relatório gerado com sucesso em: {report_path}")
    print(ausentes[['cpf_clean', 'NOME']].to_string(index=False))

if __name__ == '__main__':
    gerar_relatorio_ausentes(
        'Base/SAUDE E ODONTO ATUALIZADO.xlsx', 
        'Importação/2026.txt', 
        'Doc/RELATORIO_AUSENTES_HAPVIDA.txt'
    )
