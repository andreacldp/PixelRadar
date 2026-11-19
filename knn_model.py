import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "indie_games.csv"
EVENTS_PATH = BASE_DIR / "events.json"

N_TOP_TAGS = 60
K_DEFAULT = 20
UMBRAL_PCT_POSITIVE = 70.0
COMISION_STEAM_DEFAULT = 0.30

COLUMNAS_NUEVAS_OPCIONALES = [
    "median_forever", "average_forever",
    "price_mx_initial", "price_mx_final", "price_mx_discount_percent",
    "has_demo", "release_weekday", "release_week",
]

TAGS_ESTILO_CANDIDATOS = [
    "Pixel Graphics", "2D", "3D", "Retro", "Colorful", "Stylized", "Realistic", "Anime",
    "Isometric", "Hand-drawn", "Cartoony", "Minimalist", "Dark", "Side Scroller", "Surreal",
    "Top-Down", "Third Person", "First-Person",
]

LIMITES_TEXT = [
    "Este reporte es benchmarking (como fijaron precio y fecha juegos parecidos), no una prediccion "
    "de ventas: ningun precio o mes 'garantiza' resultados.",
    "El dataset viene de SteamSpy y la Steam Store API, con muestreo estratificado por owners; Steam "
    "no es todo el mercado de videojuegos y SteamSpy estima los owners, no los mide exacto.",
    "Las relaciones que se muestran (precio vs reseñas, mes vs owners, etc.) son correlaciones "
    "descriptivas entre los vecinos de esta consulta, no relaciones de causa-efecto.",
    "La muestra de entrevistas/encuesta que motivo estas mejoras es chica y autoseleccionada (11 "
    "respuestas, mayoria Mexico): sirve para orientar que mostrar, no para generalizar estadisticamente.",
]


def nota_impuestos_comisiones(comision):
    return (
        f"Steam se queda con una comision sobre cada venta (aqui se uso un {comision * 100:.0f}% de "
        "referencia, pero en la realidad Steam tiene tramos que bajan segun los ingresos del juego). "
        "Dependiendo del pais tambien puede aplicar IVA u otros impuestos sobre la venta. Esto NO es "
        "asesoria fiscal ni legal: confirma las reglas vigentes con Steamworks y con un contador antes "
        "de fijar el precio final."
    )


def cargar_datos(path=DATA_PATH):
    df = pd.read_csv(path)
    df["tags"] = df["tags"].fillna("")

    for col in COLUMNAS_NUEVAS_OPCIONALES:
        if col not in df.columns:
            df[col] = np.nan

    if df["release_weekday"].isna().all() or df["release_week"].isna().all():
        fechas = pd.to_datetime(df["release_date"], errors="coerce")
        df["release_weekday"] = fechas.dt.weekday
        df["release_week"] = fechas.dt.isocalendar().week.astype(float)

    return df


def contar_tags(df):
    contador = {}
    for tags_str in df["tags"]:
        for tag in tags_str.split("|"):
            tag = tag.strip()
            if tag:
                contador[tag] = contador.get(tag, 0) + 1
    return contador


def top_tags_mas_frecuentes(df, n=N_TOP_TAGS):
    contador = contar_tags(df)
    tags_ordenados = sorted(contador.items(), key=lambda kv: -kv[1])
    return [t for t, _ in tags_ordenados[:n]]


def tags_estilo_presentes(df, candidatos=TAGS_ESTILO_CANDIDATOS):
    contador = contar_tags(df)
    presentes = [t for t in candidatos if t in contador]
    return sorted(presentes, key=lambda t: -contador[t])


def pesos_tfidf(df, lista_tags):
    contador = contar_tags(df)
    n_juegos = len(df)
    return np.array([np.log(n_juegos / contador[t]) for t in lista_tags])


def construir_bloque_tags(df, top_tags, usar_tfidf=True, idf=None):
    onehot = np.zeros((len(df), len(top_tags)), dtype=float)
    for i, tags_str in enumerate(df["tags"]):
        tags_del_juego = set(t.strip() for t in tags_str.split("|"))
        for j, tag in enumerate(top_tags):
            if tag in tags_del_juego:
                onehot[i, j] = 1.0

    if not usar_tfidf:
        return onehot, None

    if idf is None:
        idf = pesos_tfidf(df, top_tags)
    return onehot * idf, idf


def construir_bloque_estilo(df, tags_estilo):
    onehot = np.zeros((len(df), len(tags_estilo)), dtype=float)
    for i, tags_str in enumerate(df["tags"]):
        tags_del_juego = set(t.strip() for t in tags_str.split("|"))
        for j, tag in enumerate(tags_estilo):
            if tag in tags_del_juego:
                onehot[i, j] = 1.0
    return onehot


def construir_bloque_idiomas(df, scaler=None):
    n_lang = df["n_languages"].to_numpy(dtype=float).reshape(-1, 1)
    if scaler is None:
        scaler = StandardScaler()
        n_lang_escalado = scaler.fit_transform(n_lang)
    else:
        n_lang_escalado = scaler.transform(n_lang)
    return n_lang_escalado, scaler


def construir_bloque_duracion(df, scaler=None):
    valores = df["median_forever"].to_numpy(dtype=float)
    if np.isnan(valores).all():
        return np.zeros((len(df), 1)), None, 0.0

    fallback = float(np.nanmedian(valores))
    valores = np.where(np.isnan(valores), fallback, valores).reshape(-1, 1)

    if scaler is None:
        scaler = StandardScaler()
        valores_escalados = scaler.fit_transform(valores)
    else:
        valores_escalados = scaler.transform(valores)
    return valores_escalados, scaler, fallback


def construir_matriz_features(
    df, top_tags, tags_estilo,
    scaler_idiomas=None, idf_tags=None, scaler_duracion=None, fallback_duracion=None,
    usar_tfidf=True, usar_estilo=True, usar_idiomas=True, usar_duracion=False,
    w_tags=1.0, w_estilo=0.5, w_lang=0.5, w_duracion=0.3,
):
    bloques = []

    bloque_tags, idf_tags = construir_bloque_tags(df, top_tags, usar_tfidf=usar_tfidf, idf=idf_tags)
    bloques.append(bloque_tags * w_tags)

    if usar_estilo and len(tags_estilo) > 0:
        bloques.append(construir_bloque_estilo(df, tags_estilo) * w_estilo)

    if usar_idiomas:
        bloque_lang, scaler_idiomas = construir_bloque_idiomas(df, scaler_idiomas)
        bloques.append(bloque_lang * w_lang)

    if usar_duracion:
        bloque_dur, scaler_duracion, fallback_duracion = construir_bloque_duracion(df, scaler_duracion)
        bloques.append(bloque_dur * w_duracion)

    X = np.hstack(bloques)
    extras = {
        "idf_tags": idf_tags,
        "scaler_idiomas": scaler_idiomas,
        "scaler_duracion": scaler_duracion,
        "fallback_duracion": fallback_duracion,
    }
    return X, extras


def vectorizar_juego_nuevo(
    tags, n_languages, top_tags, tags_estilo, extras, horas_de_juego=None,
    usar_tfidf=True, usar_estilo=True, usar_idiomas=True, usar_duracion=False,
    w_tags=1.0, w_estilo=0.5, w_lang=0.5, w_duracion=0.3,
):
    tags_usuario = set(t.strip() for t in tags)
    bloques = []

    onehot_tags = np.array([[1.0 if t in tags_usuario else 0.0 for t in top_tags]])
    if usar_tfidf and extras.get("idf_tags") is not None:
        onehot_tags = onehot_tags * extras["idf_tags"]
    bloques.append(onehot_tags * w_tags)

    if usar_estilo and len(tags_estilo) > 0:
        onehot_estilo = np.array([[1.0 if t in tags_usuario else 0.0 for t in tags_estilo]])
        bloques.append(onehot_estilo * w_estilo)

    if usar_idiomas:
        n_lang = np.array([[float(n_languages)]])
        n_lang_escalado = extras["scaler_idiomas"].transform(n_lang)
        bloques.append(n_lang_escalado * w_lang)

    if usar_duracion:
        minutos = (
            float(horas_de_juego) * 60 if horas_de_juego is not None else extras["fallback_duracion"]
        )
        if extras.get("scaler_duracion") is not None:
            dur_escalada = extras["scaler_duracion"].transform(np.array([[minutos]]))
        else:
            dur_escalada = np.array([[0.0]])
        bloques.append(dur_escalada * w_duracion)

    return np.hstack(bloques)


class ModeloPixelRadar:
    def __init__(
        self, df=None, n_top_tags=N_TOP_TAGS, k=K_DEFAULT, metric="cosine",
        usar_tfidf=True, usar_estilo=True, usar_idiomas=True, usar_duracion=False,
        w_tags=1.0, w_estilo=0.5, w_lang=0.5, w_duracion=0.3,
    ):
        self.df = df if df is not None else cargar_datos()
        self.top_tags = top_tags_mas_frecuentes(self.df, n_top_tags)
        self.tags_estilo = tags_estilo_presentes(self.df) if usar_estilo else []

        self.config = dict(
            usar_tfidf=usar_tfidf, usar_estilo=usar_estilo, usar_idiomas=usar_idiomas, usar_duracion=usar_duracion,
            w_tags=w_tags, w_estilo=w_estilo, w_lang=w_lang, w_duracion=w_duracion,
        )
        self.X, self.extras = construir_matriz_features(self.df, self.top_tags, self.tags_estilo, **self.config)

        self.k = k
        self.metric = metric
        self.knn = NearestNeighbors(n_neighbors=k, metric=metric)
        self.knn.fit(self.X)

    def vecinos_de_vector(self, vector, k=None):
        k = k or self.k
        distancias, indices = self.knn.kneighbors(vector, n_neighbors=k)
        similitud = 1 - distancias[0]
        return indices[0], similitud

    def vecinos_de_juego_nuevo(self, tags, n_languages, horas_de_juego=None, k=None):
        vector = vectorizar_juego_nuevo(
            tags, n_languages, self.top_tags, self.tags_estilo, self.extras,
            horas_de_juego=horas_de_juego, **self.config,
        )
        return self.vecinos_de_vector(vector, k=k)


def filtrar_candidatos(
    df, price_min=None, price_max=None, n_languages_min=None, has_demo=None,
    year_min=None, duracion_min=None, duracion_max=None,
):
    mask = pd.Series(True, index=df.index)
    if price_min is not None:
        mask &= df["price_usd"] >= price_min
    if price_max is not None:
        mask &= df["price_usd"] <= price_max
    if n_languages_min is not None:
        mask &= df["n_languages"] >= n_languages_min
    if has_demo is not None:
        mask &= df["has_demo"] == has_demo
    if year_min is not None:
        mask &= df["release_year"] >= year_min
    if duracion_min is not None:
        mask &= df["median_forever"] >= duracion_min
    if duracion_max is not None:
        mask &= df["median_forever"] <= duracion_max
    return df[mask]


def armar_tabla_vecinos(df, indices, similitud):
    tabla = df.iloc[indices].copy()
    tabla["similarity"] = similitud
    return tabla


def clasificar_exitosos(tabla_vecinos):
    mediana_owners_local = tabla_vecinos["owners_mid"].median()
    es_exitoso = (
        (tabla_vecinos["owners_mid"] >= mediana_owners_local)
        & (tabla_vecinos["pct_positive"] >= UMBRAL_PCT_POSITIVE)
    )
    return tabla_vecinos.assign(exitoso=es_exitoso)


def construir_benchmark(tabla_vecinos):
    exitosos = tabla_vecinos[tabla_vecinos["exitoso"]]
    exitosos_pagados = exitosos[exitosos["price_usd"] > 0]

    if len(exitosos_pagados) > 0:
        price_p25 = float(exitosos_pagados["price_usd"].quantile(0.25))
        price_median = float(exitosos_pagados["price_usd"].median())
        price_p75 = float(exitosos_pagados["price_usd"].quantile(0.75))
    else:
        price_p25 = price_median = price_p75 = None

    meses = (
        tabla_vecinos["release_month"]
        .dropna()
        .astype(int)
        .value_counts()
        .sort_values(ascending=False)
    )
    top_months = [{"month": int(m), "count": int(c)} for m, c in meses.items()]

    return {
        "price_p25": price_p25,
        "price_median": price_median,
        "price_p75": price_p75,
        "top_months": top_months,
        "mean_similarity": float(tabla_vecinos["similarity"].mean()),
        "n_successful": int(exitosos.shape[0]),
        "pct_free_neighbors": float((tabla_vecinos["price_usd"] == 0).mean() * 100),
    }


def calcular_precio_rangos(tabla_vecinos, comision=COMISION_STEAM_DEFAULT):
    exitosos = tabla_vecinos[tabla_vecinos["exitoso"]]

    pagados_usd = exitosos[exitosos["price_usd"] > 0]
    usd = None
    if len(pagados_usd) > 0:
        usd = {
            "p25": round(float(pagados_usd["price_usd"].quantile(0.25)), 2),
            "mediana": round(float(pagados_usd["price_usd"].median()), 2),
            "p75": round(float(pagados_usd["price_usd"].quantile(0.75)), 2),
        }
        usd["neto_estimado_mediana"] = round(usd["mediana"] * (1 - comision), 2)

    mxn = None
    if "price_mx_final" in exitosos.columns:
        pagados_mxn = exitosos[exitosos["price_mx_final"].notna() & (exitosos["price_mx_final"] > 0)]
        if len(pagados_mxn) > 0:
            mxn = {
                "p25": round(float(pagados_mxn["price_mx_final"].quantile(0.25)), 2),
                "mediana": round(float(pagados_mxn["price_mx_final"].median()), 2),
                "p75": round(float(pagados_mxn["price_mx_final"].quantile(0.75)), 2),
            }
            mxn["neto_estimado_mediana"] = round(mxn["mediana"] * (1 - comision), 2)

    return {
        "usd": usd,
        "mxn": mxn,
        "mxn_nota": None if mxn else "todavia no hay precios reales en MXN (falta correr el backfill de collect_steam.py)",
        "comision_usada": comision,
        "nota_impuestos_comisiones": nota_impuestos_comisiones(comision),
    }


def calcular_precio_por_nivel_reviews(tabla_vecinos, n_niveles=3):
    pagados = tabla_vecinos[tabla_vecinos["price_usd"] > 0].copy()
    if len(pagados) < n_niveles:
        return {"disponible": False, "nota": "muy pocos vecinos de pago para separar por nivel de reseñas"}

    try:
        pagados["nivel_reviews"] = pd.qcut(
            pagados["n_reviews"], q=n_niveles, labels=["bajo", "medio", "alto"], duplicates="drop"
        )
    except ValueError:
        return {"disponible": False, "nota": "no se pudieron formar niveles de reseñas (valores muy repetidos)"}

    por_nivel = pagados.groupby("nivel_reviews", observed=True)["price_usd"].median().round(2)

    correlacion = round(float(pagados["price_usd"].corr(pagados["pct_positive"])), 3)

    return {
        "disponible": True,
        "precio_mediano_por_nivel_reviews": {str(k): v for k, v in por_nivel.items()},
        "correlacion_precio_vs_pct_positivo": correlacion,
        "nota": "correlacion descriptiva entre los vecinos de esta consulta, no implica causalidad",
    }


def calcular_descuentos(tabla_vecinos):
    col = "price_mx_discount_percent"
    if col not in tabla_vecinos.columns or tabla_vecinos[col].isna().all():
        return {"disponible": False, "nota": "todavia no hay datos de descuentos (falta correr el backfill)"}

    exitosos = tabla_vecinos[tabla_vecinos["exitoso"]]
    con_dato = exitosos[exitosos[col].notna()]
    if len(con_dato) == 0:
        return {"disponible": False, "nota": "ningun vecino exitoso tiene dato de descuento todavia"}

    con_descuento = con_dato[con_dato[col] > 0]
    return {
        "disponible": True,
        "pct_vecinos_exitosos_con_descuento": round(100 * len(con_descuento) / len(con_dato), 1),
        "descuento_tipico_pct": round(float(con_descuento[col].median()), 1) if len(con_descuento) > 0 else None,
    }


def calcular_estacionalidad(tabla_vecinos):
    con_mes = tabla_vecinos.dropna(subset=["release_month"]).copy()
    if len(con_mes) == 0:
        return {"disponible": False, "nota": "ningun vecino tiene fecha de lanzamiento registrada"}

    con_mes["release_month"] = con_mes["release_month"].astype(int)
    por_mes = (
        con_mes.groupby("release_month")
        .agg(n_juegos=("name", "count"), owners_mid_promedio=("owners_mid", "mean"))
        .reset_index()
        .sort_values("n_juegos", ascending=False)
    )
    meses = [
        {"month": int(r.release_month), "n_juegos": int(r.n_juegos), "owners_mid_promedio": round(float(r.owners_mid_promedio), 0)}
        for r in por_mes.itertuples()
    ]

    dias = {"disponible": False}
    con_dia = tabla_vecinos.dropna(subset=["release_weekday"])
    if len(con_dia) > 0:
        por_dia = con_dia.groupby("release_weekday")["name"].count().sort_values(ascending=False)
        nombres_dia = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
        dias = {
            "disponible": True,
            "por_dia": [
                {"weekday": int(d), "nombre": nombres_dia[int(d)], "n_juegos": int(c)}
                for d, c in por_dia.items()
            ],
        }

    return {"disponible": True, "por_mes": meses, "por_dia_semana": dias}


def calcular_congestion_semanal(tabla_vecinos):
    con_semana = tabla_vecinos.dropna(subset=["release_week"])
    if len(con_semana) == 0:
        return {"disponible": False, "nota": "ningun vecino tiene semana de lanzamiento registrada"}

    por_semana = con_semana.groupby(con_semana["release_week"].astype(int))["name"].count().sort_values(ascending=False)
    semanas_top = [{"week": int(w), "n_juegos": int(c)} for w, c in por_semana.items() if c > 1][:5]

    return {
        "disponible": True,
        "semanas_mas_congestionadas": semanas_top,
        "nota": "basado solo en los vecinos similares de esta consulta, no en todo el dataset",
    }


def cargar_eventos(path=EVENTS_PATH):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        categorias = json.load(f)

    eventos = []
    for clave, lista in categorias.items():
        if clave.startswith("_") or not isinstance(lista, list):
            continue
        eventos.extend(lista)
    return eventos


def eventos_cercanos(eventos, meses_sugeridos):
    meses_sugeridos = set(meses_sugeridos)
    cercanos = []
    for ev in eventos:
        inicio = ev.get("start") or ""
        if not inicio:
            continue
        fecha_inicio = pd.to_datetime(inicio, errors="coerce")
        if pd.isna(fecha_inicio):
            continue
        if fecha_inicio.month in meses_sugeridos:
            cercanos.append({"name": ev.get("name"), "type": ev.get("type"), "start": ev.get("start"), "end": ev.get("end")})
    return cercanos


def nivel_de_confianza(benchmark):
    similitud = benchmark["mean_similarity"]
    n_exitosos = benchmark["n_successful"]

    dispersion = None
    if benchmark["price_median"]:
        dispersion = (benchmark["price_p75"] - benchmark["price_p25"]) / benchmark["price_median"]

    puntos = 0
    if similitud >= 0.5:
        puntos += 1
    if n_exitosos >= 5:
        puntos += 1
    if dispersion is not None and dispersion <= 0.5:
        puntos += 1

    nivel = {0: "bajo", 1: "bajo", 2: "medio", 3: "alto"}[puntos]
    explicacion = f"similitud promedio {similitud:.0%}, {n_exitosos} vecinos exitosos considerados"
    if dispersion is not None:
        explicacion += f", dispersion de precio {dispersion:.0%} respecto a la mediana"
    else:
        explicacion += ", sin suficientes vecinos de pago para medir dispersion de precio"

    return {"nivel": nivel, "explicacion": explicacion}


_modelo_cacheado = None


def _obtener_modelo():
    global _modelo_cacheado
    if _modelo_cacheado is None:
        _modelo_cacheado = ModeloPixelRadar()
    return _modelo_cacheado


def recomendar(
    tags, n_languages, k=K_DEFAULT, modelo=None, horas_de_juego=None,
    price_min=None, price_max=None, n_languages_min=None, has_demo=None, year_min=None,
    duracion_min=None, duracion_max=None, comision=COMISION_STEAM_DEFAULT,
):
    modelo = modelo or _obtener_modelo()

    hay_filtros = any(
        v is not None for v in [price_min, price_max, n_languages_min, has_demo, year_min, duracion_min, duracion_max]
    )

    if hay_filtros:
        df_candidatos = filtrar_candidatos(
            modelo.df, price_min, price_max, n_languages_min, has_demo, year_min, duracion_min, duracion_max,
        ).reset_index(drop=True)

        if len(df_candidatos) == 0:
            return {"error": "no quedaron juegos tras aplicar los filtros, proba con filtros menos estrictos"}

        k_usado = min(k, len(df_candidatos))
        X_cand, extras_cand = construir_matriz_features(df_candidatos, modelo.top_tags, modelo.tags_estilo, **modelo.config)
        vector = vectorizar_juego_nuevo(
            tags, n_languages, modelo.top_tags, modelo.tags_estilo, extras_cand,
            horas_de_juego=horas_de_juego, **modelo.config,
        )
        knn_tmp = NearestNeighbors(n_neighbors=k_usado, metric=modelo.metric).fit(X_cand)
        distancias, indices = knn_tmp.kneighbors(vector, n_neighbors=k_usado)
        similitud = 1 - distancias[0]
        tabla_vecinos = armar_tabla_vecinos(df_candidatos, indices[0], similitud)
    else:
        indices, similitud = modelo.vecinos_de_juego_nuevo(tags, n_languages, horas_de_juego=horas_de_juego, k=k)
        tabla_vecinos = armar_tabla_vecinos(modelo.df, indices, similitud)

    tabla_vecinos = clasificar_exitosos(tabla_vecinos)
    benchmark = construir_benchmark(tabla_vecinos)

    neighbors = [
        {
            "name": row["name"],
            "similarity": round(float(row["similarity"]), 4),
            "price": float(row["price_usd"]),
            "release_month": int(row["release_month"]) if pd.notna(row["release_month"]) else None,
            "owners_mid": float(row["owners_mid"]),
            "pct_positive": float(row["pct_positive"]),
        }
        for _, row in tabla_vecinos.iterrows()
    ]

    eventos = cargar_eventos()
    meses_top3 = [m["month"] for m in benchmark["top_months"][:3]]

    return {
        "input": {
            "tags": list(tags), "n_languages": n_languages, "horas_de_juego": horas_de_juego,
            "filtros": {
                "price_min": price_min, "price_max": price_max, "n_languages_min": n_languages_min,
                "has_demo": has_demo, "year_min": year_min, "duracion_min": duracion_min, "duracion_max": duracion_max,
            },
        },
        "neighbors": neighbors,
        "benchmark": benchmark,
        "precio": calcular_precio_rangos(tabla_vecinos, comision=comision),
        "precio_por_nivel_reviews": calcular_precio_por_nivel_reviews(tabla_vecinos),
        "descuentos": calcular_descuentos(tabla_vecinos),
        "estacionalidad": calcular_estacionalidad(tabla_vecinos),
        "congestion_semanal": calcular_congestion_semanal(tabla_vecinos),
        "eventos_cercanos": eventos_cercanos(eventos, meses_top3),
        "confianza": nivel_de_confianza(benchmark),
        "limites": LIMITES_TEXT,
    }


def render_report_md(resultado):
    if "error" in resultado:
        return f"# PixelRadar - benchmarking\n\n**Error:** {resultado['error']}\n"

    precio = resultado["precio"]
    confianza = resultado["confianza"]

    lineas = []
    lineas.append("# PixelRadar - benchmarking de precio y fecha\n")
    lineas.append(f"**Tags de entrada:** {', '.join(resultado['input']['tags'])}")
    lineas.append(f"**Nivel de confianza:** {confianza['nivel']} ({confianza['explicacion']})\n")

    lineas.append("## Precio sugerido (benchmarking, no prediccion)")
    if precio["usd"]:
        lineas.append(
            f"- USD: mediana ${precio['usd']['mediana']} (rango P25-P75: "
            f"${precio['usd']['p25']} - ${precio['usd']['p75']}), neto estimado tras comision: "
            f"${precio['usd']['neto_estimado_mediana']}"
        )
    else:
        lineas.append("- No hubo suficientes vecinos exitosos de pago para sugerir un precio en USD.")

    if precio["mxn"]:
        lineas.append(
            f"- MXN: mediana ${precio['mxn']['mediana']} (rango P25-P75: "
            f"${precio['mxn']['p25']} - ${precio['mxn']['p75']}), neto estimado tras comision: "
            f"${precio['mxn']['neto_estimado_mediana']}"
        )
    else:
        lineas.append(f"- MXN: {precio['mxn_nota']}")
    lineas.append(f"\n> {precio['nota_impuestos_comisiones']}\n")

    estacionalidad = resultado["estacionalidad"]
    lineas.append("## Estacionalidad entre juegos parecidos")
    if estacionalidad["disponible"]:
        for m in estacionalidad["por_mes"][:3]:
            lineas.append(f"- Mes {m['month']}: {m['n_juegos']} juegos parecidos lanzados ahi")
    else:
        lineas.append(f"- {estacionalidad['nota']}")

    congestion = resultado["congestion_semanal"]
    lineas.append("\n## Competencia directa (congestion semanal)")
    if congestion["disponible"] and congestion["semanas_mas_congestionadas"]:
        for s in congestion["semanas_mas_congestionadas"]:
            lineas.append(f"- Semana {s['week']} del anio: {s['n_juegos']} juegos parecidos lanzados esa semana")
    else:
        lineas.append("- No se detecto congestion relevante entre los vecinos de esta consulta.")

    eventos = resultado["eventos_cercanos"]
    lineas.append("\n## Eventos que podrian robar foco")
    if eventos:
        for ev in eventos:
            lineas.append(f"- {ev['name']} ({ev['type']}): {ev['start']} a {ev['end']}")
    else:
        lineas.append("- No hay eventos cargados en events.json para los meses sugeridos (o faltan fechas por llenar).")

    lineas.append("\n## Limites de este reporte")
    for lim in LIMITES_TEXT:
        lineas.append(f"- {lim}")

    return "\n".join(lineas)


if __name__ == "__main__":
    ejemplo = recomendar(tags=["Pixel Graphics", "Platformer", "Difficult"], n_languages=3, horas_de_juego=6)
    print(render_report_md(ejemplo))
