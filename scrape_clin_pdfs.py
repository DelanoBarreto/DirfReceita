
import os
import re
from pypdf import PdfReader
import pandas as pd

def limpar_cpf(cpf: str) -> str:
    """Função ÚNICA e ESTREITA para CPF: Garante 11 dígitos numéricos exatos."""
    if not cpf or str(cpf).lower() == 'nan': return ""
    # Remove pontos e traços, mantém espaços temporariamente
    c = re.sub(r'[.\-]', '', str(cpf)).strip()
    # Busca a primeira sequência de 11 dígitos
    match = re.search(r'\d{11}', c)
    if match: return match.group(0)
    # Se não achar, limpa tudo que não é número e pega os 11 primeiros
    c = re.sub(r'\D', '', c)
    if not c: return ""
    return c[:11].zfill(11)

def extract_data_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Nome do titular no cabeçalho (Backup)
    tit_match = re.search(r"Associado\(a\): (.*?), CPF: ([\d.\-]+)", text)
    nome_tit_header = tit_match.group(1).strip() if tit_match else ""
    cpf_tit_header = limpar_cpf(tit_match.group(2)) if tit_match else ""
    
    text_useful = re.split(r'VALOR TOTAL BASE', text)[0]
    person_blocks = re.split(r'\n(?=.*? \[.*?\] - [A-Z]+)', text_useful)
    
    extracted = []
    for block in person_blocks:
        match = re.search(r'([A-Z\s\n]+) \[(.*?)\] - ([A-Z]+)', block)
        if not match: continue
        
        name = match.group(1).strip().replace('\n', ' ')
        info_bracket = match.group(2).strip()
        p_type = match.group(3).strip()
        
        cpf_p = ""
        dob_p = ""
        
        if "/" in info_bracket:
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', info_bracket)
            if date_match: dob_p = date_match.group(1)
            cpf_match = re.search(r'(\d[\d.\- ]{10,15})', info_bracket.replace(dob_p if dob_p else "", ""))
            if cpf_match: cpf_p = limpar_cpf(cpf_match.group(1))
        else:
            cpf_p = limpar_cpf(info_bracket)
            
        # Se for titular e o nome capturado for curto/vazio, usa o do cabeçalho
        if p_type == 'TITULAR' and len(name) < 3:
            name = nome_tit_header
            
        val_matches = re.findall(r'(\d+,\d{2})', block)
        if not val_matches: continue
        
        extracted.append({
            'titular_cpf': cpf_tit_header,
            'nome': name,
            'cpf': cpf_p,
            'dtnasc': dob_p,
            'parentesco': p_type,
            'valor': float(val_matches[-1].replace(',', '.'))
        })
    return extracted

def main():
    pdf_dir = 'Base/CLIN -Plano Odontologico/'
    all_data = []
    for file in os.listdir(pdf_dir):
        if file.lower().endswith('.pdf'):
            path = os.path.join(pdf_dir, file)
            try:
                data = extract_data_from_pdf(path)
                all_data.extend(data)
            except Exception: pass
                
    df = pd.DataFrame(all_data)
    df = df[df['nome'].str.len() > 2] # Remove lixo sem nome
    df.to_csv('Base/clin_consolidado.csv', index=False, encoding='utf-8')
    print(f"Extração concluída! {len(df)} registros.")

if __name__ == '__main__':
    main()
