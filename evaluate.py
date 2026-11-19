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
    tags_estilo_presentes,
    construir_matriz_features,
    vectorizar_juego_nuevo,
    armar_tabla_vecinos,
    clasificar_exitosos,
    construir_benchmark,
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIN_JUEGOS_MISMO_GENERO = 3


def construir_matriz_booleana(df, top_tags, tags_estilo, usar_estilo=True, usar_idiomas=True, umbral_idiomas=None):
    onehot = np.zeros((len(df), len(top_tags)), dtype=float)
    for i, tags_str in enumerate(df["tags"]):
        tags_del_juego = set(t.strip() for t in tags_str.split("|"))
        for j, tag in enumerate(top_tags):
            if tag in tags_del_juego:
                onehot[i, j] = 1.0
    bloques = [onehot]

    if usar_estilo and len(tags_estilo) > 0:
        onehot_estilo = np.zeros((len(df), len(tags_estilo)), dtype=float)
        for i, tags_str in enumerate(df["tags"]):
            tags_del_juego = set(t.strip() for t in tags_str.split("|"))
            for j, tag in enumerate(tags_estilo):
                if tag in tags_del_juego:
                    onehot_estilo[i, j] = 1.0
        bloques.append(onehot_estilo)

    if usar_idiomas:
        n_lang = df["n_languages"].to_numpy(dtype=float)
        if umbral_idiomas is None:
            umbral_idiomas = float(np.median(n_lang))
        n_lang_bin = (n_lang > umbral_idiomas).astype(float).reshape(-1, 1)
        bloques.append(n_lang_bin)

    X = np.hstack(bloques)
    return X, {"umbral_idiomas": umbral_idiomas}


def vectorizar_booleano(tags, n_languages, top_tags, tags_estilo, extras, usar_estilo=True, usar_idiomas=True):
    tags_usuario = set(t.strip() for t in tags)
    bloques = [np.array([[1.0 if t in tags_usuario else 0.0 for t in top_tags]])]

    if usar_estilo and len(tags_estilo) > 0:
        bloques.append(np.array([[1.0 if t in tags_usuario else 0.0 for t in tags_estilo]]))

    if usar_idiomas:
        bloques.append(np.array([[1.0 if float(n_languages) > extras["umbral_idiomas"] else 0.0]]))

    return np.hstack(bloques)


def calcular_baselines_loo(df):
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
            baseline_genero = baseline_global

        moda_mes_global = train["release_month"].dropna().mode()
        baseline_mes_global = int(moda_mes_global.iloc[0]) if len(moda_mes_global) else None

        mismo_genero_todos = train[train["primary_genre"] == genero]
        moda_mes_genero = mismo_genero_todos["release_month"].dropna().mode()
        baseline_mes_genero = int(moda_mes_genero.iloc[0]) if len(moda_mes_genero) else baseline_mes_global

        resultados[df.loc[i, "appid"]] = {
            "real_price": df.loc[i, "price_usd"],
            "real_month": df.loc[i, "release_month"],
            "primary_genre": genero,
            "baseline_global": baseline_global,
            "baseline_genero": baseline_genero,
            "baseline_mes_global": baseline_mes_global,
            "baseline_mes_genero": baseline_mes_genero,
        }
    return resultados


def evaluar_knn_loo(df, k, metric, usar_tfidf=True, usar_estilo=True, usar_idiomas=True):
    predicciones = {}
    n = len(df)

    for i in range(n):
        appid = df.loc[i, "appid"]
        train_df = df.drop(index=i).reset_index(drop=True)
        top_tags_train = top_tags_mas_frecuentes(train_df, n=N_TOP_TAGS)
        tags_estilo_train = tags_estilo_presentes(train_df) if usar_estilo else []

        tags_juego = df.loc[i, "tags"].split("|") if df.loc[i, "tags"] else []
        n_lang_juego = df.loc[i, "n_languages"]

        if metric == "cosine":
            X_train, extras = construir_matriz_features(
                train_df, top_tags_train, tags_estilo_train,
                usar_tfidf=usar_tfidf, usar_estilo=usar_estilo, usar_idiomas=usar_idiomas, usar_duracion=False,
            )
            vector_test = vectorizar_juego_nuevo(
                tags_juego, n_lang_juego, top_tags_train, tags_estilo_train, extras,
                usar_tfidf=usar_tfidf, usar_estilo=usar_estilo, usar_idiomas=usar_idiomas, usar_duracion=False,
            )
            knn = NearestNeighbors(n_neighbors=k, metric="cosine").fit(X_train)
            distancias, indices = knn.kneighbors(vector_test, n_neighbors=k)
        elif metric == "jaccard":
            X_train, extras = construir_matriz_booleana(
                train_df, top_tags_train, tags_estilo_train, usar_estilo=usar_estilo, usar_idiomas=usar_idiomas,
            )
            vector_test = vectorizar_booleano(
                tags_juego, n_lang_juego, top_tags_train, tags_estilo_train, extras,
                usar_estilo=usar_estilo, usar_idiomas=usar_idiomas,
            )
            knn = NearestNeighbors(n_neighbors=k, metric="jaccard").fit(X_train.astype(bool))
            distancias, indices = knn.kneighbors(vector_test.astype(bool), n_neighbors=k)
        else:
            raise ValueError(f"metrica no soportada: {metric}")

        similitud = 1 - distancias[0]
        tabla_vecinos = armar_tabla_vecinos(train_df, indices[0], similitud)
        tabla_vecinos = clasificar_exitosos(tabla_vecinos)
        benchmark = construir_benchmark(tabla_vecinos)

        predicciones[appid] = {
            "price_median": benchmark["price_median"],
            "top3_meses": [m["month"] for m in benchmark["top_months"][:3]],
        }

    return predicciones


def calcular_mae_y_mediana(reales, predicciones):
    errores = np.abs(np.array(reales, dtype=float) - np.array(predicciones, dtype=float))
    return float(errores.mean()), float(np.median(errores))


def calcular_smape(reales, predicciones):
    reales = np.array(reales, dtype=float)
    predicciones = np.array(predicciones, dtype=float)
    denominador = (np.abs(reales) + np.abs(predicciones)) / 2
    errores_pct = np.abs(reales - predicciones) / denominador
    return float(errores_pct.mean() * 100)


def resumen_error(reales, predicciones):
    if len(reales) == 0:
        return None, None, None
    mae, mediana = calcular_mae_y_mediana(reales, predicciones)
    smape = calcular_smape(reales, predicciones)
    return round(mae, 2), round(mediana, 2), round(smape, 2)


def reportar_combinacion(baselines, predicciones_knn, etiqueta):
    filas_precio = []
    hits_mes = []

    for appid, pred in predicciones_knn.items():
        base = baselines[appid]

        if base["real_price"] > 0 and pred["price_median"] is not None:
            filas_precio.append({
                "real": base["real_price"], "knn": pred["price_median"],
                "baseline_global": base["baseline_global"], "baseline_genero": base["baseline_genero"],
            })

        if pd.notna(base["real_month"]):
            real_month = int(base["real_month"])
            hits_mes.append({
                "knn": real_month in pred["top3_meses"],
                "baseline_global": real_month == base["baseline_mes_global"],
                "baseline_genero": real_month == base["baseline_mes_genero"],
            })

    tabla_precio = pd.DataFrame(filas_precio)
    tabla_mes = pd.DataFrame(hits_mes)
    n_evaluados_precio = len(tabla_precio)
    n_evaluados_mes = len(tabla_mes)

    mae_knn, med_knn, smape_knn = resumen_error(tabla_precio["real"], tabla_precio["knn"]) if n_evaluados_precio else (None, None, None)
    mae_glob, med_glob, smape_glob = resumen_error(tabla_precio["real"], tabla_precio["baseline_global"]) if n_evaluados_precio else (None, None, None)
    mae_gen, med_gen, smape_gen = resumen_error(tabla_precio["real"], tabla_precio["baseline_genero"]) if n_evaluados_precio else (None, None, None)

    acierto_knn_mes = round(100 * tabla_mes["knn"].mean(), 1) if n_evaluados_mes else None
    acierto_base_mes_glob = round(100 * tabla_mes["baseline_global"].mean(), 1) if n_evaluados_mes else None
    acierto_base_mes_gen = round(100 * tabla_mes["baseline_genero"].mean(), 1) if n_evaluados_mes else None

    print(f"\n=== {etiqueta} ===")
    print(f"Precio - evaluados: {n_evaluados_precio} | MAE KNN: {mae_knn} | MAE global: {mae_glob} | MAE genero: {mae_gen} | sMAPE KNN: {smape_knn}")
    print(f"Mes (top-3 KNN vs 1 sola moda en baseline) - evaluados: {n_evaluados_mes} | "
          f"acierto KNN: {acierto_knn_mes}% | acierto baseline global: {acierto_base_mes_glob}% | "
          f"acierto baseline genero: {acierto_base_mes_gen}%")

    if mae_knn is not None and mae_knn > min(mae_glob, mae_gen):
        print("  AVISO: en esta combinacion el KNN NO le gana a los baselines de precio.")

    return {
        "etiqueta": etiqueta,
        "n_evaluados_precio": n_evaluados_precio, "mae_knn": mae_knn, "med_knn": med_knn, "smape_knn": smape_knn,
        "mae_baseline_global": mae_glob, "mae_baseline_genero": mae_gen,
        "n_evaluados_mes": n_evaluados_mes, "acierto_knn_top3_mes": acierto_knn_mes,
        "acierto_baseline_mes_global": acierto_base_mes_glob, "acierto_baseline_mes_genero": acierto_base_mes_gen,
    }


def main():
    df = cargar_datos(DATA_PATH)

    print("Calculando baselines (mediana global/genero de precio, moda global/genero de mes), leave-one-out...")
    baselines = calcular_baselines_loo(df)

    variantes = [
        {"nombre": "completo", "usar_tfidf": True, "usar_estilo": True, "usar_idiomas": True, "metricas": ["cosine", "jaccard"]},
        {"nombre": "sin_idiomas", "usar_tfidf": True, "usar_estilo": True, "usar_idiomas": False, "metricas": ["cosine", "jaccard"]},
        {"nombre": "sin_estilo", "usar_tfidf": True, "usar_estilo": False, "usar_idiomas": True, "metricas": ["cosine", "jaccard"]},
        {"nombre": "sin_tfidf", "usar_tfidf": False, "usar_estilo": True, "usar_idiomas": True, "metricas": ["cosine"]},
    ]
    ks = [5, 10, 20]

    resumen = []
    for variante in variantes:
        for metric in variante["metricas"]:
            for k in ks:
                etiqueta = f"{variante['nombre']} | K={k} | {metric}"
                print(f"\nCorriendo leave-one-out: {etiqueta}...")
                t0 = time.time()
                predicciones = evaluar_knn_loo(
                    df, k=k, metric=metric,
                    usar_tfidf=variante["usar_tfidf"], usar_estilo=variante["usar_estilo"], usar_idiomas=variante["usar_idiomas"],
                )
                resultado = reportar_combinacion(baselines, predicciones, etiqueta)
                resultado.update({"variante": variante["nombre"], "k": k, "metric": metric})
                resumen.append(resultado)
                print(f"  (tardo {time.time() - t0:.1f}s)")

    print("\n\n========== RESUMEN FINAL ==========")
    tabla_resumen = pd.DataFrame(resumen)[[
        "variante", "k", "metric", "n_evaluados_precio", "mae_knn", "smape_knn",
        "mae_baseline_global", "mae_baseline_genero",
        "n_evaluados_mes", "acierto_knn_top3_mes", "acierto_baseline_mes_global", "acierto_baseline_mes_genero",
    ]]
    print(tabla_resumen.to_string(index=False))

    tabla_resumen.to_csv("data/resultados_evaluacion_mejoras.csv", index=False)
    print("\nGuardado en data/resultados_evaluacion_mejoras.csv")

    peores = tabla_resumen[tabla_resumen["mae_knn"] > tabla_resumen[["mae_baseline_global", "mae_baseline_genero"]].min(axis=1)]
    if len(peores) > 0:
        print(f"\nAVISO: en {len(peores)} de {len(tabla_resumen)} combinaciones el KNN de precio NO le gana a los baselines.")
    else:
        print("\nEl KNN de precio le gano (o empato) a ambos baselines en todas las combinaciones.")


if __name__ == "__main__":
    main()
