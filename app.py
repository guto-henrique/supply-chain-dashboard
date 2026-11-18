from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Painel Supply Chain",
    page_icon="📦",
    layout="wide",
)

PALETTE = ["#E8505B", "#F0932B", "#6AB187", "#4A90D9", "#9B59B6"]
GREEN, RED = "#5DAA68", "#E8505B"

CSS = """
<style>
.stApp { background-color: #EEF1F5; }
.block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 1400px; }
header[data-testid="stHeader"] { background: transparent; }
h1.dash-title { font-size: 1.6rem; font-weight: 500; color: #222; margin: 0 0 .5rem 0; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF; border: none !important; border-radius: 10px;
    box-shadow: 0 1px 3px rgba(16, 24, 40, .06);
}
.card-title { font-size: .85rem; color: #555; margin-bottom: .2rem; }
.kpi { text-align: center; padding: .3rem 0 .4rem 0; }
.kpi .value { font-size: 2.4rem; font-weight: 700; color: #2B2B2B; line-height: 1.1; }
.kpi .delta { font-size: .9rem; margin-top: .15rem; }
.kpi .note { font-size: .7rem; color: #888; margin-top: .5rem; }
div[data-testid="stMultiSelect"] label p, div[data-testid="stSelectbox"] label p { font-size: .75rem; color: #777; }
</style>
"""


@st.cache_data
def load_data() -> pd.DataFrame:
    base_dir = Path(__file__).resolve().parent
    default_path = base_dir / "data" / "supply_chain_data.csv"

    if default_path.exists():
        return pd.read_csv(default_path)

    csv_files = sorted((base_dir / "data").glob("*.csv"))
    if csv_files:
        return pd.read_csv(csv_files[0])

    raise FileNotFoundError(
        "Arquivo de dados não encontrado em data/supply_chain_data.csv. "
        "Adicione o CSV na pasta data."
    )


def style_fig(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color="#555"),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5, title=None),
    )
    fig.update_xaxes(showgrid=False, title=None)
    fig.update_yaxes(gridcolor="#EAEAEA", title=None, zeroline=False)
    return fig


def kpi_card(title: str, value: str, current: float, reference: float, higher_is_better: bool = True) -> None:
    diff = (current - reference) / reference * 100 if reference else 0
    good = (diff >= 0) == higher_is_better
    arrow = "↑" if diff >= 0 else "↓"
    color = GREEN if good else RED
    with st.container(border=True):
        st.markdown(
            f"""<div class="card-title">{title}</div>
            <div class="kpi"><div class="value">{value}</div>
            <div class="delta" style="color:{color}">{arrow} {abs(diff):.1f}%</div>
            <div class="note">vs média geral</div></div>""",
            unsafe_allow_html=True,
        )


def chart_card(title: str, fig: go.Figure) -> None:
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<h1 class="dash-title">Painel Supply Chain</h1>', unsafe_allow_html=True)

    try:
        df = load_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    product_options = sorted(df["Product type"].dropna().unique().tolist())
    carrier_options = sorted(df["Shipping carriers"].dropna().unique().tolist())

    f1, f2, _ = st.columns([2, 2, 3])
    selected_products = f1.multiselect("Tipo de produto", product_options, default=product_options)
    selected_carriers = f2.multiselect("Transportadora", carrier_options, default=carrier_options)

    fdf = df[df["Product type"].isin(selected_products) & df["Shipping carriers"].isin(selected_carriers)]
    if fdf.empty:
        st.warning("Nenhum dado encontrado com os filtros selecionados.")
        st.stop()

    # --- Figuras ---
    receita = fdf.groupby("Product type", as_index=False)["Revenue generated"].sum()
    fig_pie = px.pie(receita, names="Product type", values="Revenue generated",
                     color_discrete_sequence=PALETTE)
    fig_pie.update_traces(textinfo="percent", marker=dict(line=dict(color="#fff", width=2)))
    fig_pie = style_fig(fig_pie)

    frete = fdf.groupby(["Shipping carriers", "Product type"], as_index=False)["Shipping costs"].mean()
    fig_bar = px.bar(frete, x="Shipping carriers", y="Shipping costs", color="Product type",
                     barmode="stack", color_discrete_sequence=PALETTE)
    fig_bar.update_traces(width=0.55)
    fig_bar = style_fig(fig_bar)

    area_df = fdf.reset_index(drop=True).copy()
    area_df["Item"] = area_df.index + 1
    fig_area = go.Figure()
    for col, color, name in [
        ("Revenue generated", "#F0932B", "Receita"),
        ("Manufacturing costs", "#6AB187", "Custo de fabricação (x20)"),
    ]:
        y = area_df[col] * (20 if col == "Manufacturing costs" else 1)
        y = y.rolling(5, min_periods=1, center=True).mean()
        fig_area.add_trace(go.Scatter(
            x=area_df["Item"], y=y, name=name, mode="lines", fill="tozeroy",
            line=dict(color=color, width=2, shape="spline"),
        ))
    fig_area = style_fig(fig_area, height=330)

    # --- Layout ---
    left, mid, right = st.columns([1, 2, 2])
    with left:
        kpi_card("Receita total", f"${fdf['Revenue generated'].sum()/1000:,.1f}k",
                 fdf["Revenue generated"].mean(), df["Revenue generated"].mean())
        kpi_card("Estoque médio", f"{fdf['Stock levels'].mean():.0f}",
                 fdf["Stock levels"].mean(), df["Stock levels"].mean())
    with mid:
        chart_card("Receita por tipo de produto", fig_pie)
    with right:
        chart_card("Custo médio de frete por transportadora", fig_bar)

    left2, wide = st.columns([1, 4])
    with left2:
        kpi_card("Taxa de defeitos", f"{fdf['Defect rates'].mean():.2f}%",
                 fdf["Defect rates"].mean(), df["Defect rates"].mean(), higher_is_better=False)
        aprov = (fdf["Inspection results"] == "Pass").mean() * 100
        aprov_ref = (df["Inspection results"] == "Pass").mean() * 100
        kpi_card("Aprovação em inspeção", f"{aprov:.0f}%", aprov, aprov_ref)
    with wide:
        chart_card("Receita x custo de fabricação por item", fig_area)


if __name__ == "__main__":
    main()
