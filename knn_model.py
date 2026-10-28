"""
knn_model.py
------------
Modelo KNN de PixelRadar: busca juegos indie "parecidos" a la descripcion
que da el estudio (tags + numero de idiomas) y arma un benchmark de precio,
mes de lanzamiento y desempeno con esos vecinos.

IMPORTANTE - esto es benchmarking, NO prediccion causal. No le decimos al
estudio "tu juego va a vender X", le decimos "juegos parecidos a lo que
describes vendieron/se lanzaron asi".

DISENO (decisiones ya tomadas, ver notebook para el detalle):
1. La distancia solo usa CONTENIDO: tags (one-hot de los top 60 mas
   frecuentes del dataset) + numero de idiomas (escalado). NO se usa precio
   ni mes de lanzamiento en la distancia -> si entraran, los vecinos saldrian
   siempre del mismo mes/rango de precio y no podriamos comparar esas cosas.
2. Distancia coseno, K=10 (default; se puede cambiar al llamar las funciones).
3. "Vecino exitoso" = esta en la mitad superior de owners_mid DENTRO de sus
   propios K vecinos, Y tiene >= 70% de resenas positivas.
4. El benchmark de precio se calcula SOLO con vecinos exitosos Y de pago
   (price_usd > 0). Se excluyen los gratis del calculo de precio porque un
   "precio sugerido: $0" no sirve de nada: boletin el EDA mostro que 20% del
   dataset es gratis, y si los mezclamos la mediana se va para abajo sin que
   signifique nada.
5. El mes de lanzamiento (top_months) se calcula sobre TODOS los K vecinos
   (no solo los exitosos), porque con K=10 el grupo de "exitosos" puede ser
   muy chico (3-5 juegos) para sacar un patron de meses confiable.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "indie_games.csv"

N_TOP_TAGS = 60
K_DEFAULT = 10
UMBRAL_PCT_POSITIVE = 70.0  # % minimo de resenas positivas para ser "exitoso"


# ============================================================
# 1) CARGA Y PREPARACION DE FEATURES
# ============================================================

def cargar_datos(path=DATA_PATH):
    df = pd.read_csv(path)
    df["tags"] = df["tags"].fillna("")
    return df


def top_tags_mas_frecuentes(df, n=N_TOP_TAGS):
    """
    Cuenta en cuantos juegos aparece cada tag y devuelve los n mas comunes.
    Estos son las "columnas" del one-hot: cualquier tag que el usuario
    escriba y no este en esta lista simplemente no afecta la distancia.
    """
    contador = {}
    for tags_str in df["tags"]:
        for tag in tags_str.split("|"):
            tag = tag.strip()
            if tag:
                contador[tag] = contador.get(tag, 0) + 1
    tags_ordenados = sorted(contador.items(), key=lambda kv: -kv[1])
    return [t for t, _ in tags_ordenados[:n]]


def construir_matriz_features(df, top_tags, scaler=None):
    """
    Construye la matriz de features (una fila por juego):
      - 60 columnas one-hot (1 si el juego tiene ese tag, 0 si no)
      - 1 columna de n_languages ESCALADO (media 0, desviacion 1)

    Si scaler es None, se entrena uno nuevo con estos datos (se usa al
    construir el modelo). Si se pasa un scaler ya entrenado, se usa ese
    (se usa al vectorizar un juego NUEVO que el usuario describe, para no
    "aprender" de ese juego, solo transformarlo con lo que el modelo ya sabe).
    """
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
    """Convierte (tags, n_languages) de un juego NUEVO al mismo espacio de features."""
    tags_usuario = set(t.strip() for t in tags)
    onehot = np.array([[1.0 if t in tags_usuario else 0.0 for t in top_tags]])
    n_lang = np.array([[float(n_languages)]])
    n_lang_escalado = scaler.transform(n_lang)
    return np.hstack([onehot, n_lang_escalado])


# ============================================================
# 2) MODELO KNN
# ============================================================

class ModeloPixelRadar:
    """
    Envuelve el dataset + features + modelo KNN ya entrenados, para no
    tener que recargar el CSV y reconstruir todo en cada llamada a recomendar().
    """

    def __init__(self, df=None, n_top_tags=N_TOP_TAGS, k=K_DEFAULT, metric="cosine"):
        self.df = df if df is not None else cargar_datos()
        self.top_tags = top_tags_mas_frecuentes(self.df, n_top_tags)
        self.X, self.scaler = construir_matriz_features(self.df, self.top_tags)
        self.k = k
        self.metric = metric
        self.knn = NearestNeighbors(n_neighbors=k, metric=metric)
        self.knn.fit(self.X)

    def vecinos_de_vector(self, vector, k=None):
        """
        Dado un vector ya en el espacio de features, devuelve (indices, similitud)
        de sus k vecinos mas cercanos. similitud = 1 - distancia_coseno.
        """
        k = k or self.k
        distancias, indices = self.knn.kneighbors(vector, n_neighbors=k)
        similitud = 1 - distancias[0]
        return indices[0], similitud

    def vecinos_de_juego_nuevo(self, tags, n_languages, k=None):
        vector = vectorizar_juego_nuevo(tags, n_languages, self.top_tags, self.scaler)
        return self.vecinos_de_vector(vector, k=k)


# ============================================================
# 3) CLASIFICACION DE "VECINO EXITOSO" Y BENCHMARK
# ============================================================

def armar_tabla_vecinos(df, indices, similitud):
    tabla = df.iloc[indices].copy()
    tabla["similarity"] = similitud
    return tabla


def clasificar_exitosos(tabla_vecinos):
    """
    'Exitoso' = esta en la mitad superior de owners_mid DENTRO de este grupo
    de vecinos (mediana local, no global) Y tiene >= 70% de resenas positivas.
    """
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
        # no hay suficientes vecinos exitosos de pago para armar un rango
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


# ============================================================
# 4) FUNCION PUBLICA: recomendar()
# ============================================================

_modelo_cacheado = None


def _obtener_modelo():
    global _modelo_cacheado
    if _modelo_cacheado is None:
        _modelo_cacheado = ModeloPixelRadar()
    return _modelo_cacheado


def recomendar(tags, n_languages, k=K_DEFAULT, modelo=None):
    """
    Funcion principal que usara el front. Recibe lo que describe el estudio
    (lista de tags + numero de idiomas) y devuelve el JSON con vecinos y
    benchmark, en el formato acordado con el equipo de front.
    """
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
