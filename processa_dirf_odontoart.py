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

def processar_dirf(txt_entrada: str, txt_saida: str, dados_plano: dict, limit_records=50):
    mapa_parentesco = {'CONJUGE': '03', 'FILHO(A)': '04', 'FILHO': '04', 'ENTEADO(A)': '06', 'PAI': '08', 'MAE': '08', 'AGREGADO': '10'}
    
    def get_parentesco_code(txt_relacao):
        txt_relacao = txt_relacao.upper()
        for k, v in mapa_parentesco.items():
            if k in txt_relacao: return v
        return '10'

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
                    continue 

                if cpf_titular in dados_plano:
                    info = dados_plano[cpf_titular]
                    val_tit = int(info['titular_valor'])
                    fout.write(f"TPSE|{cpf_titular}|{info['nome']}|{val_tit}|\r\n")
                    for dep in info['dependentes']:
                        cod_par = get_parentesco_code(dep['parentesco'])
                        val_dep = int(dep['valor'])
                        fout.write(f"DTPSE|{dep['cpf']}||{dep['nome']}|{cod_par}|{val_dep}|\r\n")
                    continue
                else:
                    fout.write(linha)
                    continue

            if linha.startswith('DTPSE|'):
                continue 

            if linha.startswith('FIMDIRF|'):
                fout.write(linha)
                break

            if not manter_bloco_atual:
                continue

            fout.write(linha)

if __name__ == '__main__':
    dados = extrair_dados_pdf('Base/odontoart 2025.pdf')
    # Validando com 5 funcionários
    keys_teste = list(dados.keys())[:5]
    dados_teste = {k: dados[k] for k in keys_teste}
    
    processar_dirf('Importação/2026.txt', 'Importação/2026_processado.txt', dados_teste)
    print("Sucesso! Arquivo gerado com a mesma estrutura original, apenas individualizando os valores do plano de saúde dos testes.")
