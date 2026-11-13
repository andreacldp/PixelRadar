<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.svg">
    <img alt="PixelRadar" src="assets/banner-dark.svg" width="100%">
  </picture>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-4E7BE0?style=flat-square&logo=python&logoColor=FFFFFF">
  <img alt="scikit-learn" src="https://img.shields.io/badge/scikit--learn-NearestNeighbors-B33A93?style=flat-square&logo=scikitlearn&logoColor=FFFFFF">
  <img alt="Estado" src="https://img.shields.io/badge/estado-research%20%2F%20prototipo-E6457A?style=flat-square">
  <img alt="Licencia" src="https://img.shields.io/badge/licencia-sin%20especificar-333333?style=flat-square">
</p>

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🐟 Qué es PixelRadar

**PixelRadar** es un proyecto de análisis de datos que responde una pregunta muy concreta para un desarrollador indie: *"si mi juego tiene estos tags en Steam, ¿a qué precio y en qué mes suelen lanzarse juegos parecidos que funcionaron bien?"*

El proyecto recolecta datos reales de juegos indie de Steam (vía SteamSpy y la Store API) y entrena un modelo de **K-Nearest Neighbors** sobre sus tags e idiomas soportados para estimar precio y mes de lanzamiento.

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🫧 Features

- **Dataset propio de juegos indie** ([`indie_games.csv`](indie_games.csv)): ~1499 juegos recolectados con muestreo estratificado por cantidad de owners (500 bajo / 500 medio / 499 alto), filtrando juegos con al menos 10 reseñas.
- **Modelo KNN** ([`knn_model.py`](knn_model.py)) sobre los 60 tags más frecuentes (one-hot) + cantidad de idiomas soportados (escalado), con distancia coseno.
- **Benchmark automático** por cada consulta:
  - 💲 precio sugerido (mediana y rango P25–P75) calculado solo con vecinos "exitosos" y de pago.
  - 📅 mejores meses de lanzamiento según la frecuencia entre los vecinos.
  - 📊 similitud promedio y porcentaje de vecinos gratuitos.
- **Clasificación de "éxito"**: un vecino se considera exitoso si su cantidad de owners está por encima de la mediana local y tiene ≥ 70% de reseñas positivas.
- **Evaluación leave-one-out** ([`evaluate.py`](evaluate.py)) comparando el KNN (coseno y jaccard, K=5/10/20) contra baselines de mediana global y mediana por género, con MAE y sMAPE.

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🌊 Resultados de evaluación

Comparación leave-one-out del KNN contra los baselines, tomada de [`data/resultados_evaluacion.csv`](data/resultados_evaluacion.csv):

| K  | Métrica | Evaluados | MAE KNN (USD) | sMAPE KNN (%) | MAE baseline global (USD) | MAE baseline género (USD) |
|----|---------|-----------|----------------|----------------|-----------------------------|------------------------------|
| 5  | coseno  | 1172      | 6.99           | 68.74          | 7.00                        | 7.09                         |
| 10 | coseno  | 1198      | 6.85           | 67.24          | 7.00                        | 7.10                         |
| 20 | coseno  | 1219      | **6.22**       | **62.95**      | 6.98                        | 7.09                         |
| 5  | jaccard | 1181      | 7.47           | 69.81          | 7.00                        | 7.12                         |
| 10 | jaccard | 1202      | 7.05           | 66.62          | 6.98                        | 7.08                         |
| 20 | jaccard | 1220      | 6.45           | 63.65          | 6.97                        | 7.09                         |

El mejor resultado observado es **K=20 con distancia coseno**, levemente por debajo de ambos baselines en error absoluto. Resultados recalculados tras corregir el sesgo de muestreo del dataset (ver sección de recolección).

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🐠 Instalación

Requisitos: **Python 3.10+**.

```bash
git clone https://github.com/andreacldp/PixelRadar.git
cd PixelRadar

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install pandas numpy scikit-learn requests
```

> El repo todavía no incluye un `requirements.txt`; la lista de arriba son las dependencias que importan `knn_model.py`, `evaluate.py` y `collect_steam.py`.

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🐟 Uso

### Correr el modelo KNN

```bash
python knn_model.py
```

Imprime un ejemplo de recomendación en JSON usando los tags `["Pixel Graphics", "Platformer", "Difficult"]`.

### Reproducir la evaluación

```bash
python evaluate.py
```

Corre la validación leave-one-out para las combinaciones de K y métrica, e imprime/guarda el resumen en `data/resultados_evaluacion.csv`.

### Regenerar o ampliar el dataset (opcional)

```bash
python collect_steam.py
```

Descarga juegos indie desde SteamSpy y la Steam Store API, con caché y reintentos (`data/.cache/`). Es un proceso largo y resumible: puede interrumpirse y vuelve a correr desde donde quedó usando `indie_games.csv` y `data/dropped_games.csv` como registro de lo ya procesado.

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🫧 Estructura del proyecto

```
PixelRadar/
├── knn_model.py                # Modelo KNN: features, entrenamiento, benchmark de vecinos
├── evaluate.py                 # Evaluación leave-one-out (KNN vs baselines) -> MAE / sMAPE
├── collect_steam.py            # Recolección del dataset desde SteamSpy + Steam Store API
├── indie_games.csv             # Dataset de juegos indie (~1499 filas, estratificado por owners)
├── data/
│   ├── dropped_games.csv       # Juegos descartados durante la recolección, con motivo
│   ├── resultados_evaluacion.csv  # Salida de evaluate.py
│   └── .cache/                 # Caché de SteamSpy y de la muestra elegida (para resumir la corrida)
└── assets/                     # Banner, paleta y separadores del README
```

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🌊 Tecnologías

- **Python** — lenguaje principal.
- **scikit-learn** — `NearestNeighbors` (KNN) y `StandardScaler`.
- **pandas** / **NumPy** — manipulación de datos y features.
- **Requests** — consumo de las APIs de SteamSpy y Steam Store.

<img src="assets/divider.svg" width="100%" height="24" alt="">

## 🐠 Créditos y licencia

Datos obtenidos de la [API de SteamSpy](https://steamspy.com/api.php) y de la [Steam Store API](https://store.steampowered.com/api/appdetails), usados con fines de investigación/educativos.

Este repositorio todavía no define una licencia. Si pensás abrirlo públicamente, agregá un archivo `LICENSE` (por ejemplo MIT) para dejar claro cómo se puede usar el código y el dataset.

<p align="center"><sub>Hecho con 🐟 y Python — <a href="https://github.com/andreacldp/PixelRadar">andreacldp/PixelRadar</a></sub></p>
