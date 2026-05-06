# Documentação de Integração: DIRF 2026 & Plano de Saúde (Odontoart)

Este documento descreve o fluxo de trabalho, os problemas encontrados e a solução arquitetada para automatizar a individualização de valores de planos de saúde no arquivo de importação da DIRF (`2026.txt`).

## 1. O Problema de Negócio
O usuário possui um arquivo da DIRF (`2026.txt`) perfeitamente validado pela Receita Federal, contendo as informações da folha de pagamento de mais de 1000 funcionários. O arquivo também já continha o bloco de saúde (`PSE`, `OPSE`), porém os valores dos planos de saúde (Titular + Dependentes) estavam **consolidados (somados) no registro do titular (`TPSE`)**, e não havia registros de dependentes (`DTPSE`).
A Receita Federal exige que o valor seja **individualizado** por CPF (Titular e Dependente separados).

Os dados individualizados estavam disponíveis apenas em um relatório em PDF da operadora ("odontoart 2025.pdf").

## 2. Descobertas e Falhas (Lições Aprendidas)
Durante o desenvolvimento, algumas abordagens falharam e ensinaram regras estritas sobre o parser da DIRF:

*   **Injeção de Blocos `PSE` por Funcionário (FALHA):** A primeira tentativa inseriu blocos `PSE` logo após o bloco `BPFDEC` de cada funcionário. Isso quebrou o importador (10.000+ erros) porque o registro `PSE` é estruturalmente um irmão de `IDREC` ou filho de `DECPJ` – ele deve existir **apenas uma vez** listando todos os funcionários juntos, e não espalhado pelo arquivo.
*   **Problemas de Encoding e Finais de Linha:** O simples ato de ler o arquivo em `utf-8` ou `latin-1` e salvá-lo corrompeu o arquivo gerando rejeição maciça de registros. O arquivo original usava codificação `cp1252` (ANSI) e quebras de linha padrão Windows (`\r\n`). Qualquer desvio invalida a importação.
*   **Tamanho de Campos `TPSE` e `DTPSE`:** Ao contrário de rendimentos normais que usam 13 posições, os valores de saúde em `TPSE` e `DTPSE` aceitam tamanho variável ou um preenchimento específico. Mas o mais seguro foi descobrir que, como o arquivo já tinha a estrutura pronta, bastava reaproveitar o valor sem zerofill forçado, ou simplesmente usar o valor inteiro.
*   **Quebra de Página no PDF:** A extração do PDF com `pdfplumber` falhava ao ler dependentes porque o nome estava na página 1 e os valores na página 2. A solução foi concatenar todo o texto de todas as páginas em uma única string gigante antes de aplicar o Regex.

## 3. A Solução Definitiva (Script `processa_dirf_odontoart.py`)
A estratégia final abandonou a tentativa de "recriar" a estrutura DIRF e focou em uma **substituição cirúrgica (in-place)**.

### Fluxo de Extração (PDF)
1.  Junta o texto completo do PDF.
2.  Usa Regex (`Associado\(a\)`) para identificar o Titular e o CPF.
3.  Usa Regex para identificar Dependentes e seus graus de parentesco.
4.  Identifica os valores mensais e, crucialmente, capta a última linha de valor financeiro (`^\d+,\d{2}$`) associando-a à pessoa ativa no contexto do loop.

### Fluxo de Injeção (TXT)
1.  Abre o `2026.txt` garantindo `encoding='cp1252'` e `newline=''` para **não tocar nos finais de linha (`\r\n`)**.
2.  Itera linha a linha.
3.  Se a linha não for um `TPSE`, copia exatamente como está para o novo arquivo (preservação 100%).
4.  Se a linha for `TPSE`:
    *   Verifica o CPF. Se estiver no dicionário raspado do PDF:
        *   Descarta a linha `TPSE` consolidada original.
        *   Escreve a nova linha `TPSE` com o valor exclusivo do Titular.
        *   Escreve imediatamente abaixo as linhas `DTPSE` (traduzindo "CONJUGE" para "03", "FILHO" para "04", etc.) com os valores exclusivos dos dependentes.
    *   Se o CPF não estiver no PDF, apenas copia o `TPSE` original sem modificações.

## 4. Como Continuar o Trabalho
Para a próxima IA ou desenvolvedor:
*   O script atual está com uma trava de segurança na linha 85 (`keys_teste = list(dados.keys())[:3]`) que limita a execução a apenas 3 funcionários.
*   **Próximo Passo:** Assim que o usuário validar que a importação do PGD (Programa Gerador da DIRF) aceitou os 3 registros perfeitamente, basta **remover a limitação do slice `[:3]`** no dicionário e rodar o script novamente para processar todos os 191 titulares em poucos segundos.
*   **Atenção:** Nunca modifique a leitura/escrita do arquivo removendo o `encoding='cp1252'` ou o `newline=''`. Se o fizer, o PGD da Receita Federal rejeitará o arquivo com milhares de erros "O registro precisa estar associado a um registro do tipo IDREC".
