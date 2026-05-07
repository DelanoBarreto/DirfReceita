
import pandas as pd
import re

def limpar_cpf(cpf: str) -> str:
    if not cpf or str(cpf).lower() == 'nan': return ""
    c = re.sub(r'\D', '', str(cpf))
    return c.zfill(11)[-11:]

def extrair_dados_importados(txt_path):
    importados = set()
    try:
        with open(txt_path, 'rb') as f:
            for linha in f:
                if linha.startswith(b'TPSE|') or linha.startswith(b'DTPSE|'):
                    partes = linha.split(b'|')
                    if len(partes) > 1:
                        cpf = partes[1].decode('cp1252', errors='ignore').strip()
                        if cpf: importados.add(cpf)
                    if len(partes) > 3:
                        nome = partes[3].decode('cp1252', errors='ignore').strip()
                        if nome: importados.add(nome)
    except: pass
    return importados

def gerar_relatorio():
    txt_final = 'Importação/2026_FINAL_COMPLETO.txt'
    importados = extrair_dados_importados(txt_final)
    
    relatorio = []
    relatorio.append("=== RELATÓRIO DE AUDITORIA COMPLETO - DIRF 2026 ===")
    relatorio.append("Este relatório contém a lista INTEGRAL de beneficiários não importados.")
    relatorio.append("MOTIVO: O titular do plano não possui cadastro de rendimentos (BPFDEC) na DIRF.")
    relatorio.append("="*85 + "\n")

    # 1. Analisar HAPVIDA
    relatorio.append("--- PLANO HAPVIDA (SAÚDE) - LISTA COMPLETA DE AUSENTES ---")
    try:
        df_hap = pd.read_excel('Base/SAUDE E ODONTO ATUALIZADO.xlsx', sheet_name='SAUDE CONF. JAN A DEZEMBRO')
        col_nome = 'BENEFICIRIO' if 'BENEFICIRIO' in df_hap.columns else df_hap.columns[0]
        col_cpf = 'cpf' if 'cpf' in df_hap.columns else df_hap.columns[3]
        
        nao_importados_hap = []
        for _, row in df_hap.iterrows():
            nome = str(row[col_nome]).strip()
            cpf = limpar_cpf(row[col_cpf])
            if cpf not in importados and nome not in importados:
                nao_importados_hap.append(f"- {nome} (CPF: {cpf})")
        
        relatorio.append(f"Total na planilha Hapvida: {len(df_hap)}")
        relatorio.append(f"Total de Ausentes: {len(nao_importados_hap)}")
        relatorio.extend(sorted(nao_importados_hap))
    except Exception as e:
        relatorio.append(f"Aviso ao analisar HAPVIDA: {e}")
    relatorio.append("\n" + "-"*60)

    # 2. Analisar ODONTOART
    relatorio.append("--- PLANO ODONTOART - LISTA COMPLETA DE AUSENTES ---")
    try:
        df_odonto = pd.read_excel('Base/Odontoart 2025Atual.xlsx')
        nao_importados_odonto = []
        for _, row in df_odonto.iterrows():
            nome = str(row['Usuário']).strip()
            cpf = limpar_cpf(row['CPF'])
            if cpf not in importados and nome not in importados:
                nao_importados_odonto.append(f"- {nome} (CPF: {cpf})")
        
        relatorio.append(f"Total na planilha Odontoart: {len(df_odonto)}")
        relatorio.append(f"Total de Ausentes: {len(nao_importados_odonto)}")
        relatorio.extend(sorted(nao_importados_odonto))
    except Exception as e:
        relatorio.append(f"Erro ao analisar ODONTOART: {e}")
    relatorio.append("\n" + "-"*60)

    # 3. Analisar CLIN
    relatorio.append("--- PLANO CLIN (ODONTO) - LISTA COMPLETA DE AUSENTES ---")
    try:
        df_clin = pd.read_csv('Base/clin_consolidado.csv')
        nao_importados_clin = []
        for _, row in df_clin.iterrows():
            nome = str(row['nome']).strip()
            cpf = limpar_cpf(row['cpf'])
            if cpf not in importados and nome not in importados:
                nao_importados_clin.append(f"- {nome} (CPF: {cpf})")
        
        relatorio.append(f"Total extraído dos PDFs Clin: {len(df_clin)}")
        relatorio.append(f"Total de Ausentes: {len(nao_importados_clin)}")
        relatorio.extend(sorted(nao_importados_clin))
    except Exception as e:
        relatorio.append(f"Erro ao analisar CLIN: {e}")

    # 4. RESUMO DE ERROS CRÍTICOS
    relatorio.append("\n" + "="*85)
    relatorio.append("!!! PENDÊNCIAS QUE EXIGEM CORREÇÃO MANUAL NO PGD (PLANO CLIN) !!!")
    relatorio.append("Estes registros estão no arquivo mas darão erro até você informar a DATA DE NASCIMENTO:")
    pendencias = [
        "1. ANDREZA DOS SANTOS BARROSO (Titular: JOSE DIEGO CONDE DA SILVA SOUZA)",
        "2. CARLOS ALBERTO LEAL DE SOUZA FILHO (Titular: FRANCISCO SERGIO DE ARAUJO FIRMINO)",
        "3. HILDEBERTO MOTA TORRES JUNIOR (Titular: GLEICIANE DE MENEZES LUCAS TORRES)",
        "4. AILTON PIRES ALVES NETO (Titular: MILENA MARA DE ALMEIDA ROCHA)"
    ]
    for p in pendencias:
        relatorio.append(p)
    relatorio.append("="*85)

    with open('Doc/RELATORIO_COMPLETO_NAO_IMPORTADOS.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(relatorio))

if __name__ == '__main__':
    gerar_relatorio()
