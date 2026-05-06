# Resumo do Processo de Individualização DIRF 2026

Este documento resume o progresso realizado na individualização dos valores de planos de saúde para a DIRF 2026, facilitando a continuação do trabalho em outro computador.

## 📋 Status Atual

Concluímos a criação de três ferramentas de processamento, cada uma adaptada para uma fonte de dados diferente:

| Script | Fonte de Dados | Objetivo | Status |
| :--- | :--- | :--- | :--- |
| `processa_dirf_odontoart.py` | `odontoart 2025.pdf` | Extração via Regex do PDF da Odontoart. | **Testado e Aprovado** no PGD. |
| `processa_dirf_odontoart_xls.py` | `Odontoart 2025.xls` | Processamento do Excel (HTML) da Odontoart. | **Aguardando Validação Final** (3 testes). |
| `processa_dirf_saude_odonto.py` | `SAUDE E ODONTO ATUALIZADO.xlsx` | Processamento da planilha consolidada (HAPVIDA + Outros). | **Aguardando Validação Final** (3 testes). |

## 🛠️ Regras de Ouro Aplicadas

1.  **Preservação Estrutural:** Os scripts mantêm o encoding `cp1252` e os finais de linha `\r\n` (Windows). Nunca abra ou salve os arquivos `.txt` em editores que alterem o encoding.
2.  **Formato de Valores:** Todos os scripts agora gravam valores em **centavos como inteiros** (ex: R$ 17.880,00 -> `1788000`), conforme o layout exigido pelo PGD da Receita Federal.
3.  **Individualização:** O script substitui o registro `TPSE` (titular) consolidado e insere registros `DTPSE` (dependentes) logo abaixo, mantendo a hierarquia do arquivo original.

## 🚀 Como Continuar (Próximos Passos)

1.  **Limpeza no PGD:** Ao importar os novos arquivos de teste (`2026_processado_xls.txt` ou `2026_processado_saude_odonto.txt`), use a opção **"Substituir"** ou exclua a declaração anterior no programa da Receita Federal para evitar erros de "Titular já existente".
2.  **Validação dos 3 Testes:** Verifique se os 3 primeiros registros de cada script foram importados corretamente sem avisos ou erros.
3.  **Processamento em Massa:** Assim que os testes forem validados, abra o script correspondente e remova a trava de segurança (o slice `[:3]` no final do arquivo):
    *   `keys_teste = list(dados.keys())` (Remover o `[:3]`)
4.  **Execução Final:** Rode o script novamente para gerar o arquivo com todos os titulares (191 para Odontoart ou 465 para Saúde/Hapvida).

## 📁 Arquivos no Repositório

-   `2026.txt`: Arquivo original validado.
-   `2026_processado_saude_odonto.txt`: Último arquivo gerado para testes da Hapvida/Saúde.
-   `processa_dirf_saude_odonto.py`: Script principal para a planilha consolidada.
-   `DOCUMENTACAO_DIRF.md`: Lições aprendidas e detalhes técnicos da arquitetura.

---
**Desenvolvido com Antigravity Kit**
