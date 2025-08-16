# PDF → Excel (Produtos)

App em Streamlit que lê relatórios tipo **Curva ABC (Lince)** e exporta um Excel com as colunas:
`nome do produto | setor | mês | semana | quantidade | valor`

## Subir no Render
1. Faça fork/suba estes arquivos para um repositório no GitHub: `app.py`, `requirements.txt`, `Procfile`.
2. No Render: **New → Web Service** e conecte o repositório.
3. **Runtime**: Python 3.11 (ou 3.10).
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: deixe em branco (o Render vai ler o `Procfile`) ou use:
   `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`

## Uso
- Faça upload do PDF (formato Curva ABC).
- Informe **mês** e **semana** como deseja no Excel.
- Ajuste o **setor** se necessário (o app tenta adivinhar).
- Selecione múltiplos produtos e clique em **Gerar Excel**.
