from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "indie_games.csv"

N_TOP_TAGS = 60
K_DEFAULT = 10
UMBRAL_PCT_POSITIVE = 70.0


def cargar_datos(path=DATA_PATH):
    df = pd.read_csv(path)
    df["tags"] = df["tags"].fillna("")
    return df


def top_tags_mas_frecuentes(df, n=N_TOP_TAGS):
    contador = {}
    for tags_str in df["tags"]:
        for tag in tags_str.split("|"):
            tag = tag.strip()
            if tag:
                contador[tag] = contador.get(tag, 0) + 1
    tags_ordenados = sorted(contador.items(), key=lambda kv: -kv[1])
    return [t for t, _ in tags_ordenados[:n]]


def construir_matriz_features(df, top_tags, scaler=None):
    onehot = np.zeros((len(df), len(top_tags)), dtype=float)
    for i, tags_str in enumerate(df["tags"]):
        tags_del_juego = set(t.strip() for t in tags_str.split("|"))
        for j, tag in enumerate(top_tags):
            if tag in tags_del_juego:
                onehot[i, j] = 1.0

    n_lang = df["n_languages"].to_numpy(dtype=float).reshape(-1, 1)
    if scaler is None:
        scaler = StandardScaler()
        n_lang_escalado = scaler.fit_transform(n_lang)
    else:
        n_lang_escalado = scaler.transform(n_lang)

    X = np.hstack([onehot, n_lang_escalado])
    return X, scaler


def vectorizar_juego_nuevo(tags, n_languages, top_tags, scaler):
    tags_usuario = set(t.strip() for t in tags)
    onehot = np.array([[1.0 if t in tags_usuario else 0.0 for t in top_tags]])
    n_lang = np.array([[float(n_languages)]])
    n_lang_escalado = scaler.transform(n_lang)
    return np.hstack([onehot, n_lang_escalado])


class ModeloPixelRadar:
    def __init__(self, df=None, n_top_tags=N_TOP_TAGS, k=K_DEFAULT, metric="cosine"):
        self.df = df if df is not None else cargar_datos()
        self.top_tags = top_tags_mas_frecuentes(self.df, n_top_tags)
        self.X, self.scaler = construir_matriz_features(self.df, self.top_tags)
        self.k = k
        self.metric = metric
        self.knn = NearestNeighbors(n_neighbors=k, metric=metric)
        self.knn.fit(self.X)

    def vecinos_de_vector(self, vector, k=None):
        k = k or self.k
        distancias, indices = self.knn.kneighbors(vector, n_neighbors=k)
        similitud = 1 - distancias[0]
        return indices[0], similitud

    def vecinos_de_juego_nuevo(self, tags, n_languages, k=None):
        vector = vectorizar_juego_nuevo(tags, n_languages, self.top_tags, self.scaler)
        return self.vecinos_de_vector(vector, k=k)


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


_modelo_cacheado = None


def _obtener_modelo():
    global _modelo_cacheado
    if _modelo_cacheado is None:
        _modelo_cacheado = ModeloPixelRadar()
    return _modelo_cacheado


def recomendar(tags, n_languages, k=K_DEFAULT, modelo=None):
    modelo = modelo or _obtener_modelo()
    indices, similitud = modelo.vecinos_de_juego_nuevo(tags, n_languages, k=k)
    tabla_vecinos = armar_tabla_vecinos(modelo.df, indices, similitud)
    tabla_vecinos = clasificar_exitosos(tabla_vecinos)

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

    return {
        "input": {"tags": list(tags), "n_languages": n_languages},
        "neighbors": neighbors,
        "benchmark": construir_benchmark(tabla_vecinos),
    }


if __name__ == "__main__":
    import json

    ejemplo = recomendar(tags=["Pixel Graphics", "Platformer", "Difficult"], n_languages=3)
    print(json.dumps(ejemplo, indent=2, ensure_ascii=False))
