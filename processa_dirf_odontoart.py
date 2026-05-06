import pdfplumber
import re

def extrair_dados_pdf(pdf_path):
    dados = {}
    with pdfplumber.open(pdf_path) as pdf:
        full_text = []
        for page in pdf.pages:
            t = page.extract_text()
            if t: full_text.append(t)
            
        text = '\n'.join(full_text)
        
        # Como o texto pode ter vários titulares, vamos iterar por linhas e guardar o contexto
        cpf_titular = None
        pessoa_atual = None
        
        for linha in text.split('\n'):
            titular_match = re.search(r'Associado\(a\):\s*\d+\s*-\s*([^,]+),\s*CPF:\s*([\d\.\-]+)', linha)
            if titular_match:
                nome_titular = titular_match.group(1).strip()
                cpf_titular = titular_match.group(2).replace('.', '').replace('-', '').strip()
                if cpf_titular not in dados:
                    dados[cpf_titular] = {'nome': nome_titular, 'dependentes': [], 'titular_valor': 0}
                pessoa_atual = None # Reset
                continue
                
            pessoa_match = re.search(r'\d+\s*-\s*([^\[]+)\[([\d\.\-]+)\]\s*-\s*([A-Za-z\(\)]+)', linha)
            if pessoa_match and cpf_titular:
                nome = pessoa_match.group(1).strip()
                cpf = pessoa_match.group(2).replace('.', '').replace('-', '').strip()
                parentesco = pessoa_match.group(3).strip()
                pessoa_atual = {'nome': nome, 'cpf': cpf, 'parentesco': parentesco, 'valor': '0'}
                if 'TITULAR' not in parentesco.upper():
                    dados[cpf_titular]['dependentes'].append(pessoa_atual)
                continue
                
            valor_match = re.match(r'^([\d\.]+,\d{2})$', linha.strip())
            if valor_match and pessoa_atual and cpf_titular:
                valor = valor_match.group(1).replace('.', '').replace(',', '').strip()
                if 'TITULAR' in pessoa_atual['parentesco'].upper():
                    dados[cpf_titular]['titular_valor'] = valor
                else:
                    pessoa_atual['valor'] = valor
                pessoa_atual = None
    return dados

def processar_dirf(txt_entrada, txt_saida, dados_plano):
    mapa_parentesco = {'CONJUGE': '03', 'FILHO(A)': '04', 'FILHO': '04', 'ENTEADO(A)': '06', 'PAI': '08', 'MAE': '08', 'AGREGADO': '10'}
    
    def get_parentesco_code(txt_relacao):
        txt_relacao = txt_relacao.upper()
        for k, v in mapa_parentesco.items():
            if k in txt_relacao: return v
        return '10'

    # newline='' para manter o padrão \r\n
    with open(txt_entrada, 'r', encoding='cp1252', newline='') as fin, \
         open(txt_saida, 'w', encoding='cp1252', newline='') as fout:
        
        for linha in fin:
            if linha.startswith('TPSE|'):
                partes = linha.split('|')
                cpf_titular = partes[1].strip()
                
                if cpf_titular in dados_plano:
                    info_titular = dados_plano[cpf_titular]
                    
                    # Usa o valor sem preenchimento de zeros, igual ao arquivo original
                    val_titular = int(info_titular['titular_valor'])
                    fout.write(f"TPSE|{cpf_titular}|{info_titular['nome']}|{val_titular}|\r\n")
                    
                    for dep in info_titular['dependentes']:
                        parentesco_code = get_parentesco_code(dep['parentesco'])
                        val_dep = int(dep['valor'])
                        fout.write(f"DTPSE|{dep['cpf']}||{dep['nome']}|{parentesco_code}|{val_dep}|\r\n")
                else:
                    # Se não for um dos 3 funcionários teste, copia o original intacto
                    fout.write(linha)
            else:
                fout.write(linha)

if __name__ == '__main__':
    dados = extrair_dados_pdf('c:/Antigravity/DirfReceita/odontoart 2025.pdf')
    # Validando com 3 funcionários
    keys_teste = list(dados.keys())[:3]
    dados_teste = {k: dados[k] for k in keys_teste}
    
    processar_dirf('c:/Antigravity/DirfReceita/2026.txt', 'c:/Antigravity/DirfReceita/2026_processado.txt', dados_teste)
    print("Sucesso! Arquivo gerado com a mesma estrutura original, apenas individualizando os valores do plano de saúde dos testes.")
