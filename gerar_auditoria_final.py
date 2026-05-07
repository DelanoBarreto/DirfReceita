
import pandas as pd
import re

def limpar_cpf(cpf: str) -> str:
    if not cpf or str(cpf).lower() == 'nan': return ""
    c = re.sub(r'\D', '', str(cpf))
    return c.zfill(11)[-11:]

def extrair_cpfs_importados(txt_path):
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
    importados = extrair_cpfs_importados(txt_final)
    
    relatorio = []
    relatorio.append("=== RELATÓRIO DE AUDITORIA FINAL - DIRF 2026 ===")
    relatorio.append(f"Arquivo Analisado: {txt_final}")
    relatorio.append("="*50 + "\n")

    # 1. Analisar CLIN
    relatorio.append("--- PLANO CLIN (ODONTO) ---")
    try:
        df_clin = pd.read_csv('Base/clin_consolidado.csv')
        total_clin = len(df_clin)
        nao_importados_clin = []
        for _, row in df_clin.iterrows():
            nome = str(row['nome']).strip()
            cpf = limpar_cpf(row['cpf'])
            if cpf not in importados and nome not in importados:
                nao_importados_clin.append(f"- {nome} (Titular CPF: {row['titular_cpf']})")
        
        relatorio.append(f"Total no PDF: {total_clin}")
        relatorio.append(f"Não Importados (Sem cadastro na DIRF): {len(nao_importados_clin)}")
        if nao_importados_clin:
            relatorio.append("Lista de Ausentes (CLIN):")
            relatorio.extend(nao_importados_clin[:100])
    except Exception as e:
        relatorio.append(f"Erro ao analisar CLIN: {e}")
    
    relatorio.append("\n" + "-"*30)

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
                nao_importados_odonto.append(f"- {nome} (Responsável: {row['Responsável']})")
        
        relatorio.append(f"Total na Planilha: {total_odonto}")
        relatorio.append(f"Não Importados (Sem cadastro na DIRF): {len(nao_importados_odonto)}")
        if nao_importados_odonto:
            relatorio.append("Lista de Ausentes (ODONTOART):")
            relatorio.extend(nao_importados_odonto[:100])
    except Exception as e:
        relatorio.append(f"Erro ao analisar ODONTOART: {e}")

    # 3. ERROS CRÍTICOS
    relatorio.append("\n" + "="*50)
    relatorio.append("!!! ERROS CRÍTICOS QUE EXIGEM CORREÇÃO NO PGD !!!")
    relatorio.append("Estes nomes estão no arquivo mas o PGD dará erro até você preencher a data de nascimento:")
    
    pendencias = [
        "ANDREZA DOS SANTOS BARROSO (Titular: JOSE DIEGO CONDE DA SILVA SOUZA)",
        "CARLOS ALBERTO LEAL DE SOUZA FILHO (Titular: FRANCISCO SERGIO DE ARAUJO FIRMINO)",
        "HILDEBERTO MOTA TORRES JUNIOR (Titular: GLEICIANE DE MENEZES LUCAS TORRES)",
        "AILTON PIRES ALVES NETO (Titular: MILENA MARA DE ALMEIDA ROCHA)"
    ]
    for p in pendencias:
        relatorio.append(f"[ERRO] {p}")

    with open('Doc/RELATORIO_CONSOLIDADO_DIRF_2026.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(relatorio))

if __name__ == '__main__':
    gerar_relatorio()
