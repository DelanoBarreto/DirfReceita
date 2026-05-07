
import pandas as pd
import re

def limpar_cpf(cpf: str) -> str:
    if not cpf or str(cpf).lower() == 'nan': return ""
    c = re.sub(r'\D', '', str(cpf))
    return c.zfill(11)[-11:]

def extrair_dados_base(txt_path):
    cpfs_base = set()
    try:
        with open(txt_path, 'rb') as f:
            for linha in f:
                if linha.startswith(b'BPFDEC|'):
                    cpf = linha.split(b'|')[1].decode('cp1252', errors='ignore').strip()
                    if cpf: cpfs_base.add(cpf)
    except: pass
    return cpfs_base

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
    cpfs_base = extrair_dados_base(txt_final)
    importados = extrair_dados_importados(txt_final)
    
    relatorio = []
    relatorio.append("=== RELATÓRIO DE AUDITORIA CONSOLIDADO - DIRF 2026 ===")
    relatorio.append(f"Este relatório cruza os planos de saúde com a base de funcionários da DIRF.")
    relatorio.append("="*70 + "\n")

    # 1. Analisar HAPVIDA
    relatorio.append("--- PLANO HAPVIDA (SAÚDE) ---")
    try:
        df_hap = pd.read_excel('Base/SAUDE E ODONTO ATUALIZADO.xlsx', sheet_name='SAUDE CONF. JAN A DEZEMBRO')
        # Tentar identificar colunas de nome e CPF (ajustando para o padrão que vier)
        col_nome = [c for c in df_hap.columns if 'NOME' in str(c).upper() or 'USUÁRIO' in str(c).upper()][0]
        col_cpf = [c for c in df_hap.columns if 'CPF' in str(c).upper()][0]
        
        total_hap = len(df_hap)
        nao_importados_hap = []
        for _, row in df_hap.iterrows():
            nome = str(row[col_nome]).strip()
            cpf = limpar_cpf(row[col_cpf])
            if cpf not in importados and nome not in importados:
                nao_importados_hap.append(f"- {nome} (CPF: {cpf})")
        
        relatorio.append(f"Total na planilha Hapvida: {total_hap}")
        relatorio.append(f"Não Importados (Sem cadastro BPFDEC na DIRF): {len(nao_importados_hap)}")
        if nao_importados_hap:
            relatorio.append("Lista de Ausentes (HAPVIDA):")
            relatorio.extend(nao_importados_hap[:50])
            if len(nao_importados_hap) > 50: relatorio.append(f"... e mais {len(nao_importados_hap)-50} itens.")
    except Exception as e:
        relatorio.append(f"Aviso ao analisar HAPVIDA: {e}")
    relatorio.append("\n" + "-"*40)

    # 2. Analisar ODONTOART
    relatorio.append("--- PLANO ODONTOART ---")
    try:
        df_odonto = pd.read_excel('Base/Odontoart 2025Atual.xlsx')
        total_odonto = len(df_odonto)
        nao_importados_odonto = []
        for _, row in df_odonto.iterrows():
            nome = str(row['Usuário']).strip()
            cpf = limpar_cpf(row['CPF'])
            if cpf not in importados and nome not in importados:
                nao_importados_odonto.append(f"- {nome} (CPF: {cpf})")
        
        relatorio.append(f"Total na planilha Odontoart: {total_odonto}")
        relatorio.append(f"Não Importados (Sem cadastro BPFDEC na DIRF): {len(nao_importados_odonto)}")
        if nao_importados_odonto:
            relatorio.append("Lista de Ausentes (ODONTOART):")
            relatorio.extend(nao_importados_odonto[:50])
            if len(nao_importados_odonto) > 50: relatorio.append(f"... e mais {len(nao_importados_odonto)-50} itens.")
    except Exception as e:
        relatorio.append(f"Erro ao analisar ODONTOART: {e}")
    relatorio.append("\n" + "-"*40)

    # 3. Analisar CLIN
    relatorio.append("--- PLANO CLIN (ODONTO) ---")
    try:
        df_clin = pd.read_csv('Base/clin_consolidado.csv')
        total_clin = len(df_clin)
        nao_importados_clin = []
        for _, row in df_clin.iterrows():
            nome = str(row['nome']).strip()
            cpf = limpar_cpf(row['cpf'])
            if cpf not in importados and nome not in importados:
                nao_importados_clin.append(f"- {nome} (CPF: {cpf})")
        
        relatorio.append(f"Total extraído dos PDFs: {total_clin}")
        relatorio.append(f"Não Importados (Sem cadastro BPFDEC na DIRF): {len(nao_importados_clin)}")
        if nao_importados_clin:
            relatorio.append("Lista de Ausentes (CLIN):")
            relatorio.extend(nao_importados_clin[:50])
    except Exception as e:
        relatorio.append(f"Erro ao analisar CLIN: {e}")

    # 4. PENDÊNCIAS CRÍTICAS (PARA CORREÇÃO NO PGD)
    relatorio.append("\n" + "="*70)
    relatorio.append("!!! RESUMO DE PENDÊNCIAS PARA CORREÇÃO MANUAL NO PGD !!!")
    relatorio.append("Estes 4 dependentes estão com CPF INVÁLIDO e sem Data de Nascimento na origem.")
    relatorio.append("Eles foram importados mas darão ERRO no PGD até você preencher a data manualmente:")
    pendencias = [
        "1. ANDREZA DOS SANTOS BARROSO (Titular: JOSE DIEGO CONDE DA SILVA SOUZA)",
        "2. CARLOS ALBERTO LEAL DE SOUZA FILHO (Titular: FRANCISCO SERGIO DE ARAUJO FIRMINO)",
        "3. HILDEBERTO MOTA TORRES JUNIOR (Titular: GLEICIANE DE MENEZES LUCAS TORRES)",
        "4. AILTON PIRES ALVES NETO (Titular: MILENA MARA DE ALMEIDA ROCHA)"
    ]
    for p in pendencias:
        relatorio.append(p)

    with open('Doc/RELATORIO_FINAL_CONSOLIDADO.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(relatorio))

if __name__ == '__main__':
    gerar_relatorio()
