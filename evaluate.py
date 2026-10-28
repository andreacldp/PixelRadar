"""
evaluate.py
-----------
Valida el modelo KNN de PixelRadar con leave-one-out (LOO):

Para cada juego del dataset, lo "escondemos", le preguntamos al modelo
"¿que precio le sugerirías a este juego basandote en sus vecinos?" usando
SOLO los otros 299 juegos, y comparamos esa sugerencia contra el precio
real del juego. Se compara contra dos baselines simples:
  - mediana global de precio (sin usar ningun vecino, solo "el precio
    tipico de un indie" en el resto del dataset)
  - mediana de precio POR GENERO (un poco mas informado que el global)

Si el KNN no le gana ni siquiera a la mediana global, el modelo no esta
aportando nada sobre simplemente adivinar "el precio tipico".

Tambien se prueba K = 5, 10, 20 y distancia coseno vs Jaccard, para ver
si alguna combinacion es claramente mejor.

NOTA sobre Jaccard: esta distancia esta hecha para vectores BINARIOS
(presencia/ausencia), no para numeros continuos. Como el feature de
n_languages esta escalado (continuo) en el modelo de produccion, para
la comparacion con Jaccard se usa una version binaria de ese feature
(1 si el juego tiene mas idiomas que la mediana del dataset, 0 si no).
Esto es solo para esta comparacion experimental; el modelo de produccion
(knn_model.py) sigue usando el feature escalado con distancia coseno.
"""

import sys
import time

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from knn_model import (
    DATA_PATH,
    N_TOP_TAGS,
    cargar_datos,
    top_tags_mas_frecuentes,
    construir_matriz_features,
    vectorizar_juego_nuevo,
    armar_tabla_vecinos,
    clasificar_exitosos,
    construir_benchmark,
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIN_JUEGOS_MISMO_GENERO = 3  # si hay menos que esto, el baseline de genero usa el global


# ============================================================
# Features para la variante JACCARD (solo para esta evaluacion)
# ============================================================

def construir_features_binario(df, top_tags, umbral=None):
    """Igual que construir_matriz_features, pero n_languages queda BINARIO (0/1)."""
    onehot = np.zeros((len(df), len(top_tags)), dtype=float)
    for i, tags_str in enumerate(df["tags"]):
        tags_del_juego = set(t.strip() for t in tags_str.split("|"))
        for j, tag in enumerate(top_tags):
            if tag in tags_del_juego:
                onehot[i, j] = 1.0

    n_lang = df["n_languages"].to_numpy(dtype=float)
    if umbral is None:
        umbral = float(np.median(n_lang))
    n_lang_bin = (n_lang > umbral).astype(float).reshape(-1, 1)

    X = np.hstack([onehot, n_lang_bin])
    return X, umbral


def vectorizar_binario(tags, n_languages, top_tags, umbral):
    tags_usuario = set(t.strip() for t in tags)
    onehot = np.array([[1.0 if t in tags_usuario else 0.0 for t in top_tags]])
    n_lang_bin = np.array([[1.0 if float(n_languages) > umbral else 0.0]])
    return np.hstack([onehot, n_lang_bin])


# ============================================================
# Baselines (no usan KNN, se calculan una sola vez)
# ============================================================

def calcular_baselines_loo(df):
    """
    Para cada juego i, calcula los dos baselines usando los OTROS 299 juegos
    (nunca usando el precio real del propio juego i, para que sea honesto).
    """
    resultados = {}
    for i in range(len(df)):
        train = df.drop(index=i)
        train_pagados = train[train["price_usd"] > 0]

        baseline_global = train_pagados["price_usd"].median()

        genero = df.loc[i, "primary_genre"]
        mismo_genero = train_pagados[train_pagados["primary_genre"] == genero]
        if len(mismo_genero) >= MIN_JUEGOS_MISMO_GENERO:
            baseline_genero = mismo_genero["price_usd"].median()
        else:
            baseline_genero = baseline_global  # fallback: no hay suficientes del mismo genero

        resultados[df.loc[i, "appid"]] = {
            "real_price": df.loc[i, "price_usd"],
            "primary_genre": genero,
            "baseline_global": baseline_global,
            "baseline_genero": baseline_genero,
            "n_mismo_genero_disponibles": len(mismo_genero),
        }
    return resultados


# ============================================================
# LOO para una combinacion (k, metrica)
# ============================================================

def evaluar_knn_loo(df, k, metric):
    """
    Corre leave-one-out completo para una combinacion de k y metrica.
    Devuelve un dict {appid: precio_sugerido_o_None}.
    metric: 'cosine' (usa n_languages escalado) o 'jaccard' (usa n_languages binario).
    """
    predicciones = {}
    n = len(df)

    for i in range(n):
        appid = df.loc[i, "appid"]
        train_df = df.drop(index=i).reset_index(drop=True)
        top_tags_train = top_tags_mas_frecuentes(train_df, n=N_TOP_TAGS)

        tags_juego = df.loc[i, "tags"].split("|") if df.loc[i, "tags"] else []
        n_lang_juego = df.loc[i, "n_languages"]

        if metric == "cosine":
            X_train, scaler = construir_matriz_features(train_df, top_tags_train)
            vector_test = vectorizar_juego_nuevo(tags_juego, n_lang_juego, top_tags_train, scaler)
            knn = NearestNeighbors(n_neighbors=k, metric="cosine").fit(X_train)
            distancias, indices = knn.kneighbors(vector_test, n_neighbors=k)
        elif metric == "jaccard":
            X_train, umbral = construir_features_binario(train_df, top_tags_train)
            vector_test = vectorizar_binario(tags_juego, n_lang_juego, top_tags_train, umbral)
            knn = NearestNeighbors(n_neighbors=k, metric="jaccard").fit(X_train.astype(bool))
            distancias, indices = knn.kneighbors(vector_test.astype(bool), n_neighbors=k)
        else:
            raise ValueError(f"metrica no soportada: {metric}")

        similitud = 1 - distancias[0]
        tabla_vecinos = armar_tabla_vecinos(train_df, indices[0], similitud)
        tabla_vecinos = clasificar_exitosos(tabla_vecinos)
        benchmark = construir_benchmark(tabla_vecinos)

        predicciones[appid] = benchmark["price_median"]

    return predicciones


# ============================================================
# Metricas de error
# ============================================================

def calcular_mae_y_mediana(reales, predicciones):
    errores = np.abs(np.array(reales) - np.array(predicciones))
    return float(errores.mean()), float(np.median(errores))


def calcular_smape(reales, predicciones):
    """
    sMAPE (error porcentual absoluto simetrico). A diferencia del MAPE
    normal, no se dispara a infinito cuando el valor real es chico, porque
    divide entre el PROMEDIO de real y predicho (no solo entre el real).
    Se reporta en %, 0% = perfecto, 100% = el peor caso posible con esta formula.
    Aqui siempre real>0 y pred>0 (ya se filtran antes), asi que no hay
    division entre cero.
    """
    reales = np.array(reales, dtype=float)
    predicciones = np.array(predicciones, dtype=float)
    denominador = (np.abs(reales) + np.abs(predicciones)) / 2
    errores_pct = np.abs(reales - predicciones) / denominador
    return float(errores_pct.mean() * 100)


def reportar_combinacion(df, baselines, predicciones_knn, etiqueta):
    """
    Compara KNN vs los dos baselines, SOLO en el subconjunto de juegos donde
    el KNN SI pudo dar un precio sugerido (tuvo al menos un vecino exitoso
    de pago) y donde el precio real no es gratis. Así la comparación es
    justa: los tres métodos se evalúan sobre exactamente los mismos juegos.
    """
    filas = []
    for appid, pred_knn in predicciones_knn.items():
        base = baselines[appid]
        if base["real_price"] <= 0:
            continue  # no evaluamos contra precio real $0
        if pred_knn is None:
            continue  # el KNN no tuvo vecinos exitosos de pago en este fold
        filas.append({
            "appid": appid,
            "real": base["real_price"],
            "knn": pred_knn,
            "baseline_global": base["baseline_global"],
            "baseline_genero": base["baseline_genero"],
        })

    tabla = pd.DataFrame(filas)
    n_total_pagados = (df["price_usd"] > 0).sum()
    n_evaluados = len(tabla)
    n_sin_vecino_exitoso = sum(
        1 for appid, p in predicciones_knn.items() if p is None and baselines[appid]["real_price"] > 0
    )

    mae_knn, med_knn = calcular_mae_y_mediana(tabla["real"], tabla["knn"])
    mae_glob, med_glob = calcular_mae_y_mediana(tabla["real"], tabla["baseline_global"])
    mae_gen, med_gen = calcular_mae_y_mediana(tabla["real"], tabla["baseline_genero"])

    smape_knn = calcular_smape(tabla["real"], tabla["knn"])
    smape_glob = calcular_smape(tabla["real"], tabla["baseline_global"])
    smape_gen = calcular_smape(tabla["real"], tabla["baseline_genero"])

    print(f"\n=== {etiqueta} ===")
    print(f"Juegos de pago en el dataset: {n_total_pagados} | evaluados (KNN tuvo vecino exitoso): "
          f"{n_evaluados} | sin vecino exitoso de pago: {n_sin_vecino_exitoso}")
    print(f"{'Metodo':<20}{'MAE (USD)':>12}{'Mediana err (USD)':>20}{'sMAPE (%)':>12}")
    print(f"{'KNN':<20}{mae_knn:>12.2f}{med_knn:>20.2f}{smape_knn:>12.2f}")
    print(f"{'Baseline global':<20}{mae_glob:>12.2f}{med_glob:>20.2f}{smape_glob:>12.2f}")
    print(f"{'Baseline por genero':<20}{mae_gen:>12.2f}{med_gen:>20.2f}{smape_gen:>12.2f}")

    return {
        "etiqueta": etiqueta, "n_evaluados": n_evaluados, "n_sin_vecino_exitoso": n_sin_vecino_exitoso,
        "mae_knn": mae_knn, "med_knn": med_knn, "smape_knn": smape_knn,
        "mae_baseline_global": mae_glob, "med_baseline_global": med_glob, "smape_baseline_global": smape_glob,
        "mae_baseline_genero": mae_gen, "med_baseline_genero": med_gen, "smape_baseline_genero": smape_gen,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    df = cargar_datos(DATA_PATH)

    print("Calculando baselines (mediana global y por genero, leave-one-out)...")
    baselines = calcular_baselines_loo(df)

    combinaciones = [
        (5, "cosine"), (10, "cosine"), (20, "cosine"),
        (5, "jaccard"), (10, "jaccard"), (20, "jaccard"),
    ]

    resumen = []
    for k, metric in combinaciones:
        t0 = time.time()
        print(f"\nCorriendo leave-one-out para K={k}, metrica={metric}...")
        predicciones = evaluar_knn_loo(df, k=k, metric=metric)
        etiqueta = f"K={k}, {metric}"
        resultado = reportar_combinacion(df, baselines, predicciones, etiqueta)
        resultado["k"] = k
        resultado["metric"] = metric
        resumen.append(resultado)
        print(f"  (tardo {time.time() - t0:.1f}s)")

    print("\n\n========== RESUMEN FINAL ==========")
    tabla_resumen = pd.DataFrame(resumen)[
        ["k", "metric", "n_evaluados", "mae_knn", "smape_knn",
         "mae_baseline_global", "smape_baseline_global",
         "mae_baseline_genero", "smape_baseline_genero"]
    ]
    print(tabla_resumen.to_string(index=False))

    tabla_resumen.to_csv("data/resultados_evaluacion.csv", index=False)
    print("\nGuardado en data/resultados_evaluacion.csv")


if __name__ == "__main__":
    main()
