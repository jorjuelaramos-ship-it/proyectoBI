import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_data():
    clientes = pd.read_csv(DATA_DIR / "clientes_andina.csv", parse_dates=["fecha_alta"])
    productos = pd.read_csv(DATA_DIR / "productos_andina.csv")
    ventas = pd.read_csv(
        DATA_DIR / "ventas_andina.csv",
        parse_dates=["fecha"],
    )
    inventario = pd.read_csv(DATA_DIR / "inventario_andina.csv", parse_dates=["fecha_corte"])
    importaciones = pd.read_csv(DATA_DIR / "importaciones_andina.csv", parse_dates=["fecha_orden", "fecha_llegada"])
    cartera = pd.read_csv(DATA_DIR / "cartera_andina.csv", parse_dates=["fecha_factura", "fecha_vencimiento"])

    # Limpieza básica
    clientes = clientes.drop_duplicates(subset=["cliente_id"]).dropna(subset=["cliente_id"])
    productos = productos.drop_duplicates(subset=["producto_id"]).dropna(subset=["producto_id"])
    ventas = ventas.dropna(subset=["venta_id", "fecha", "cliente_id", "producto_id"])
    cartera = cartera.dropna(subset=["documento_id", "cliente_id", "fecha_factura"])

    # Asegurar tipos
    ventas["cliente_id"] = ventas["cliente_id"].astype(int)
    ventas["producto_id"] = ventas["producto_id"].astype(int)

    # Enriquecimiento para análisis principal
    ventas_ext = (
        ventas
        .merge(clientes[["cliente_id", "nombre_cliente", "segmento", "region", "ciudad"]], on="cliente_id", how="left", suffixes=("", "_cli"))
        .merge(productos[["producto_id", "sku", "categoria", "subcategoria", "marca", "descripcion"]], on="producto_id", how="left")
    )

    # Campos derivados
    ventas_ext["anio"] = ventas_ext["fecha"].dt.year
    ventas_ext["mes"] = ventas_ext["fecha"].dt.to_period("M").astype(str)

    return {
        "clientes": clientes,
        "productos": productos,
        "ventas": ventas,
        "ventas_ext": ventas_ext,
        "inventario": inventario,
        "importaciones": importaciones,
        "cartera": cartera,
    }


def main():
    st.set_page_config(page_title="Dashboard Andina", layout="wide")
    st.title("Dashboard Comercial Andina")

    # Ajuste de estilo para que los valores de las métricas se vean más pequeños
    st.markdown(
        """
        <style>
        div[data-testid="metric-container"] > div:nth-child(2) > div {
            font-size: 20px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    data = load_data()
    ventas_ext = data["ventas_ext"]
    cartera = data["cartera"]
    inventario = data["inventario"]
    importaciones = data["importaciones"]

    # Filtros
    st.sidebar.header("Filtros")

    # Rango global de fechas según todas las tablas
    fechas_min = [
        ventas_ext["fecha"].min(),
        cartera["fecha_factura"].min(),
        inventario["fecha_corte"].min(),
        importaciones["fecha_orden"].min(),
    ]
    fechas_max = [
        ventas_ext["fecha"].max(),
        cartera["fecha_factura"].max(),
        inventario["fecha_corte"].max(),
        importaciones["fecha_orden"].max(),
    ]

    min_date = min(fechas_min)
    max_date = max(fechas_max)
    fecha_desde, fecha_hasta = st.sidebar.date_input(
        "Rango de fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    regiones = sorted(ventas_ext["region"].dropna().unique())
    regiones_opciones = ["Todos"] + regiones
    region_sel = st.sidebar.selectbox(
        "Región",
        options=regiones_opciones,
        index=0,
    )

    segmentos = sorted(ventas_ext["segmento"].dropna().unique())
    segmentos_opciones = ["Todos"] + segmentos
    segmento_sel = st.sidebar.selectbox(
        "Segmento",
        options=segmentos_opciones,
        index=0,
    )

    # Aplicar filtros
    mask = (
        (ventas_ext["fecha"] >= pd.to_datetime(fecha_desde))
        & (ventas_ext["fecha"] <= pd.to_datetime(fecha_hasta))
    )

    if region_sel != "Todos":
        mask &= ventas_ext["region"] == region_sel

    if segmento_sel != "Todos":
        mask &= ventas_ext["segmento"] == segmento_sel
    ventas_f = ventas_ext[mask].copy()

    # KPIs principales
    total_ventas = ventas_f["subtotal_cop"].sum()
    margen_total = ventas_f["margen_total_cop"].sum()
    total_unidades = ventas_f["cantidad"].sum()

    # Cartera
    cartera_vigente = cartera[cartera["estado"] == "Vigente"]["saldo_cop"].sum()
    cartera_mora = cartera[cartera["estado"] == "En mora"]["saldo_cop"].sum()

    row1_col1, row1_col2, row1_col3 = st.columns(3)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        st.image(
            "https://cdn-icons-png.flaticon.com/512/1170/1170678.png",
            width=32,
        )
        st.metric("Ventas filtradas (COP)", f"${total_ventas:,.0f}")

    with row1_col2:
        st.image(
            "https://cdn-icons-png.flaticon.com/512/929/929430.png",
            width=32,
        )
        st.metric("Margen total (COP)", f"${margen_total:,.0f}")

    with row1_col3:
        st.image(
            "https://cdn-icons-png.flaticon.com/512/5690/5690739.png",
            width=32,
        )
        st.metric("Unidades vendidas", f"{int(total_unidades):,}")

    with row2_col1:
        st.image(
            "https://cdn-icons-png.flaticon.com/512/992/992020.png",
            width=32,
        )
        st.metric("Cartera vigente (COP)", f"${cartera_vigente:,.0f}")

    with row2_col2:
        st.image(
            "https://cdn-icons-png.flaticon.com/512/992/992001.png",
            width=32,
        )
        st.metric("Cartera en mora (COP)", f"${cartera_mora:,.0f}")

    st.markdown("---")

    # Gráficos de ventas
    tab1, tab2, tab3, tab4 = st.tabs([
        "Evolución temporal",
        "Por región y segmento",
        "Top clientes / productos",
        "Inventario e importaciones",
    ])

    with tab1:
        st.subheader("Evolución de ventas y margen")
        ventas_mes = (
            ventas_f
            .groupby("mes", as_index=False)[["subtotal_cop", "margen_total_cop"]]
            .sum()
            .sort_values("mes")
        )
        fig1 = px.bar(
            ventas_mes,
            x="mes",
            y="subtotal_cop",
            title="Ventas por mes (COP)",
        )
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.line(
            ventas_mes,
            x="mes",
            y="margen_total_cop",
            title="Margen total por mes (COP)",
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.subheader("Ventas por región y segmento")
        ventas_region = (
            ventas_f
            .groupby(["region", "segmento"], as_index=False)["subtotal_cop"]
            .sum()
        )
        fig3 = px.treemap(
            ventas_region,
            path=["region", "segmento"],
            values="subtotal_cop",
            title="Contribución por región y segmento",
        )
        st.plotly_chart(fig3, use_container_width=True)

        ventas_ciudad = (
            ventas_f
            .groupby(["region", "ciudad"], as_index=False)["subtotal_cop"]
            .sum()
        )
        fig4 = px.bar(
            ventas_ciudad,
            x="ciudad",
            y="subtotal_cop",
            color="region",
            title="Ventas por ciudad",
        )
        st.plotly_chart(fig4, use_container_width=True)

    with tab3:
        st.subheader("Top clientes")
        top_clientes = (
            ventas_f
            .groupby(["cliente_id", "nombre_cliente"], as_index=False)["subtotal_cop"]
            .sum()
            .sort_values("subtotal_cop", ascending=False)
            .head(15)
        )
        fig5 = px.bar(
            top_clientes,
            x="subtotal_cop",
            y="nombre_cliente",
            orientation="h",
            title="Top 15 clientes por ventas",
        )
        st.plotly_chart(fig5, use_container_width=True)

        st.subheader("Top productos")
        top_productos = (
            ventas_f
            .groupby(["producto_id", "sku", "descripcion"], as_index=False)["subtotal_cop"]
            .sum()
            .sort_values("subtotal_cop", ascending=False)
            .head(15)
        )
        fig6 = px.bar(
            top_productos,
            x="subtotal_cop",
            y="descripcion",
            orientation="h",
            title="Top 15 productos por ventas",
        )
        st.plotly_chart(fig6, use_container_width=True)

    with tab4:
        st.subheader("Inventario por centro logístico")
        inv_resumen = (
            inventario
            .groupby(["centro_logistico"], as_index=False)["valor_inventario_cop"]
            .sum()
        )
        fig7 = px.bar(
            inv_resumen,
            x="centro_logistico",
            y="valor_inventario_cop",
            title="Valor de inventario por centro logístico",
        )
        st.plotly_chart(fig7, use_container_width=True)

        st.subheader("Costos de importaciones por país de origen")
        imp_resumen = (
            importaciones
            .groupby("pais_origen", as_index=False)["costo_mercancia_usd"]
            .sum()
        )
        fig8 = px.pie(
            imp_resumen,
            names="pais_origen",
            values="costo_mercancia_usd",
            title="Distribución de costo de mercancía por país",
        )
        st.plotly_chart(fig8, use_container_width=True)


if __name__ == "__main__":
    main()
