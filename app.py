import io
import re
import os
import pdfplumber
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="PDF → Excel (Produtos)", page_icon="📄", layout="centered")

st.title("📄→📊 Extrator de Produtos (PDF → Excel)")
st.caption("Lê PDFs tipo 'Curva ABC' (Lince) e gera Excel com colunas: nome do produto, setor, mês, semana, quantidade e valor.")

# ---------- Utilidades ----------
NUM_TOKEN = r"[0-9\.\,]+"

def br_to_float(txt: str):
    if txt is None: 
        return None
    t = txt.strip()
    # tenta formato BR: 1.234,56
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
        try:
            return float(t)
        except:
            pass
    # fallback: formato EN: 1,234.56 ou 1234.56
    t2 = t.replace(",", "")
    try:
        return float(t2)
    except:
        return None

def guess_setor(text: str, filename: str) -> str:
    # tenta ler após "Departamento:"
    m = re.search(r"Departamento:\s*([\s\S]{0,40})", text, flags=re.IGNORECASE)
    if m:
        # pega próxima linha com palavra em maiúsculas/sem espaços longos
        tail = text[m.end():].splitlines()
        for ln in tail[:5]:
            t = ln.strip()
            if 2 <= len(t) <= 20 and t.isupper():
                return t
    # tenta pela dica do nome do arquivo
    base = os.path.basename(filename or "")
    base_up = base.upper()
    for chave in ["FRIOS", "AÇOUGUE", "PADARIA", "HORTIFRUTI", "BEBIDAS", "MERCEARIA"]:
        if chave in base_up:
            # Se tiver número junto (ex.: FRIOS3), mantém
            start = base_up.find(chave)
            end = min(len(base_up), start + len(chave) + 2)
            return re.sub(r"[^A-Z0-9]", "", base_up[start:end])
    return "N/D"

def parse_lince_lines(text: str):
    """
    Extrai (nome, quantidade, valor) de linhas de produto no relatório Curva ABC (Lince).
    Heurística:
      [NOME PRODUTO] [preço_unit] [quantidade] [valor] ...
    Onde 'quantidade' pode ter 3 casas e 'valor' tem 2 casas, ambos em BR.
    Também há código e código de barras no fim da linha (ignoramos).
    """
    produtos = []

    # Normaliza espaços múltiplos
    lines = [re.sub(r"\s{2,}", " ", ln).strip() for ln in text.splitlines()]
    # Remove cabeçalhos/rodapés muito óbvios
    lixo = (
        "Curva ABC", "Período", "CST", "ECF", "Situação Tributária",
        "Classif.", "Codigo", "Barras", "Total do Departamento",
        "Total Geral", "www.grupotecnoweb.com.br"
    )

    for ln in lines:
        if not ln or any(k in ln for k in lixo):
            continue

        # Muitos itens terminam com um EAN (13 dígitos). Remova o final com EAN e/ou código curto antes
        ln_clean = re.sub(r"\b\d{8,13}\b$", "", ln).strip()  # tira EAN
        # tira "código interno" (geralmente 6-8 dígitos) se vier logo antes
        ln_clean = re.sub(r"\b\d{4,8}\b\s*$", "", ln_clean).strip()

        # Agora buscamos um padrão: ... <preco_unit> <quantidade> <valor> ...
        # Permitimos números BR/EN para robustez.
        patt = re.compile(
            rf"^(?P<nome>.+?)\s+(?P<preco>{NUM_TOKEN})\s+(?P<qtd>{NUM_TOKEN})\s+(?P<valor>{NUM_TOKEN})(\s+.+)?$"
        )
        m = patt.match(ln_clean)
        if not m:
            continue

        nome = m.group("nome").strip()
        preco = br_to_float(m.group("preco"))
        qtd   = br_to_float(m.group("qtd"))
        val   = br_to_float(m.group("valor"))

        # Filtros de sanidade:
        # - preço > 0
        # - valor >= 0
        # - quantidade >= 0
        # - nome em maiúsculas típico de item
        if preco is None or preco <= 0:
            continue
        if val is None or val < 0:
            continue
        if qtd is None or qtd < 0:
            continue
        # Alguns nomes tem muito ruído; exigimos pelo menos 3 letras
        if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", nome):
            continue

        produtos.append({
            "nome": nome,
            "preco_unit": preco,
            "quantidade": qtd,
            "valor": val
        })

    # Pode haver duplicatas (mesmo nome em linhas distintas). Consolidamos por nome somando qtd/valor.
    df = pd.DataFrame(produtos)
    if df.empty:
        return df

    df = (
        df.groupby("nome", as_index=False)
          .agg({"preco_unit":"mean", "quantidade":"sum", "valor":"sum"})
          .sort_values("valor", ascending=False)
          .reset_index(drop=True)
    )
    return df

# ---------- UI ----------
uploaded = st.file_uploader("Envie o PDF (formato 'Curva ABC' do Lince)", type=["pdf"])

default_mes = datetime.today().strftime("%m/%Y")
mes = st.text_input("Mês (ex.: 08/2025)", value=default_mes, help="Use MM/AAAA")
semana = st.text_input("Semana (ex.: 1ª semana de ago/2025)", value="", help="Descreva como deseja que apareça no Excel")

if uploaded:
    with pdfplumber.open(uploaded) as pdf:
        all_text = ""
        for page in pdf.pages:
            all_text += page.extract_text(x_tolerance=1, y_tolerance=1) or ""
            all_text += "\n"

    setor_guess = guess_setor(all_text, uploaded.name)
    setor = st.text_input("Setor", value=setor_guess)

    df_items = parse_lince_lines(all_text)

    if df_items.empty:
        st.error("Não consegui identificar linhas de produto neste PDF. Verifique se é o relatório 'Curva ABC' padrão do Lince.")
        st.code(all_text[:2000])
        st.stop()

    st.subheader("Produtos detectados")
    st.dataframe(df_items[["nome", "quantidade", "valor"]], use_container_width=True)

    # Multi-seleção de produtos
    nomes = df_items["nome"].tolist()
    selecionados = st.multiselect("Selecione os produtos que entrarão no Excel", options=nomes, default=nomes[: min(10, len(nomes))])

    if st.button("Gerar Excel"):
        if not selecionados:
            st.warning("Selecione ao menos um produto.")
            st.stop()

        df_sel = df_items[df_items["nome"].isin(selecionados)].copy()
        # Monta a planilha final:
        out = pd.DataFrame({
            "nome do produto": df_sel["nome"],
            "setor": setor,
            "mês": mes,
            "semana": semana,
            "quantidade": df_sel["quantidade"].round(3),
            "valor": df_sel["valor"].round(2),
        })

        # Ordena por valor desc
        out = out.sort_values("valor", ascending=False).reset_index(drop=True)

        # Entrega como Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            out.to_excel(writer, index=False, sheet_name="Produtos")
        st.success("Excel gerado com sucesso!")
        st.download_button(
            label="⬇️ Baixar Excel",
            data=buffer.getvalue(),
            file_name=f"produtos_{mes.replace('/', '-')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

else:
    st.info("Envie um PDF para começar.")
