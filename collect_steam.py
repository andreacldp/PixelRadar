"""
collect_steam.py
-----------------
Recolecta un dataset de juegos indie de Steam combinando dos fuentes:
  1. SteamSpy (https://steamspy.com/api.php)
     - request=tag&tag=Indie   -> lista completa de juegos con tag "Indie"
                                   (trae owners, reviews, precio actual)
     - request=appdetails      -> detalle por juego (tags con votos, idiomas, genero)
  2. Steam Store (https://store.steampowered.com/api/appdetails)
     - fecha de lanzamiento (SteamSpy no la trae)

DISENO:
- Para evitar el sesgo hacia "exitos" (bajar solo los juegos con mas owners),
  se hace un MUESTREO ESTRATIFICADO por owners_mid en 3 grupos: bajo, medio, alto.
  Se toma una cantidad IGUAL de cada estrato (no proporcional), para que el
  estrato "alto" (el mas chico, ~2.4% del total) no quede casi sin representacion.
- Se filtra por un minimo de resenas totales (MIN_REVIEWS) porque con pocas
  resenas el pct_positive es puro ruido (ej. 1 de 1 resena = 100%).
- El script es RESUMIBLE: guarda cache de la lista completa (lenta, ~22s) y
  de la muestra elegida (para no re-samplear distinto si se reinicia), y escribe
  el CSV final fila por fila, así que si se interrumpe (Ctrl+C) o se cae la
  conexion, al volver a correrlo continua donde se quedo sin perder progreso
  ni duplicar llamadas a las APIs.
- Respeta limites de velocidad: ~1 req/seg en SteamSpy, ~1 cada 1.5s en Steam
  Store, con reintentos (backoff) si hay error de red o código 429/5xx.
"""

import csv
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# En Windows la consola (y la redireccion a archivo) suele usar cp1252, que no
# soporta varios caracteres que aparecen en nombres de juegos (comillas
# tipograficas, acentos raros, etc). Forzamos UTF-8 para no tronar al imprimir.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# CONFIGURACION (ajusta aqui, no en medio del codigo)
# ============================================================

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "data" / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TAG_LIST_CACHE = CACHE_DIR / "tag_list_indie.json"      # cache de la lista completa (52k+ juegos)
SAMPLE_CACHE = CACHE_DIR / "sample_appids.csv"           # cache de la muestra estratificada elegida
OUTPUT_CSV = BASE_DIR / "indie_games.csv"                # resultado final
DROPPED_LOG = BASE_DIR / "data" / "dropped_games.csv"    # juegos que se descartaron, con la razon

N_POR_ESTRATO = 100          # 100 x 3 estratos = 300 juegos totales
MIN_REVIEWS = 10             # minimo de (positive + negative) para incluir un juego
RANDOM_SEED = 42             # para que el muestreo sea reproducible

# limites de los 3 estratos, segun owners_mid (promedio del rango que da SteamSpy)
ESTRATO_BAJO_MAX = 50_000        # owners_mid < 50,000      -> "bajo"
ESTRATO_MEDIO_MAX = 500_000      # 50,000 <= owners_mid < 500,000 -> "medio"
                                  # owners_mid >= 500,000    -> "alto"

STEAMSPY_DELAY = 1.1          # segundos entre llamadas a SteamSpy (limite ~1 req/seg)
STORE_DELAY = 1.5             # segundos entre llamadas a Steam Store (mas estricto)
MAX_RETRIES = 3
TIMEOUT = 30

HEADERS = {"User-Agent": "PixelRadar-research-script/1.0 (uso academico, no comercial)"}


# ============================================================
# FUNCIONES DE RED (con reintentos y backoff)
# ============================================================

def get_con_reintentos(url, params, timeout=TIMEOUT, max_retries=MAX_RETRIES):
    """
    Hace un GET con reintentos automaticos (backoff exponencial) si falla
    por timeout, error de conexion, o codigo 429/5xx.
    Devuelve el JSON ya parseado, o None si fallan todos los intentos.
    """
    for intento in range(1, max_retries + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                espera = 5 * intento
                print(f"    [429 - demasiadas peticiones] esperando {espera}s...")
                time.sleep(espera)
                continue
            if r.status_code >= 500:
                print(f"    [error {r.status_code}] reintentando...")
                time.sleep(3 * intento)
                continue
            # otros codigos (404, etc.) no tiene caso reintentar
            return None
        except requests.exceptions.RequestException as e:
            print(f"    [error de red: {e}] reintento {intento}/{max_retries}")
            time.sleep(3 * intento)
    return None


# ============================================================
# PASO 1: lista completa de juegos con tag "Indie" (via SteamSpy)
# ============================================================

def obtener_lista_indie():
    """
    Pide la lista completa de juegos tag=Indie a SteamSpy. Esta llamada
    es lenta (~20s) pero trae TODO en una sola peticion (no hay paginacion
    real: se probo page=0 y page=1 y devuelven exactamente lo mismo).
    Se cachea en disco para no repetirla si se vuelve a correr el script.
    """
    if TAG_LIST_CACHE.exists():
        print(f"Usando cache de la lista indie: {TAG_LIST_CACHE}")
        with open(TAG_LIST_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)

    print("Descargando lista completa de juegos tag=Indie desde SteamSpy...")
    print("(esta llamada tarda ~20 segundos, es normal)")
    data = get_con_reintentos(
        "https://steamspy.com/api.php",
        {"request": "tag", "tag": "Indie", "page": 0},
    )
    if data is None:
        raise RuntimeError("No se pudo descargar la lista de SteamSpy tras varios intentos.")

    juegos = list(data.values())
    with open(TAG_LIST_CACHE, "w", encoding="utf-8") as f:
        json.dump(juegos, f)
    print(f"Lista descargada y cacheada: {len(juegos)} juegos.")
    return juegos


def owners_a_mid(owners_str):
    """Convierte 'X .. Y' (texto de SteamSpy) al punto medio numerico."""
    try:
        lo, hi = owners_str.replace(",", "").split(" .. ")
        return (int(lo) + int(hi)) / 2
    except (ValueError, AttributeError):
        return None


def asignar_estrato(owners_mid):
    if owners_mid is None:
        return None
    if owners_mid < ESTRATO_BAJO_MAX:
        return "bajo"
    if owners_mid < ESTRATO_MEDIO_MAX:
        return "medio"
    return "alto"


# ============================================================
# PASO 2: muestreo estratificado (cantidad IGUAL por estrato)
# ============================================================

def construir_muestra(juegos):
    """
    Filtra por numero minimo de resenas y arma la muestra estratificada.
    Se cachea la muestra elegida (lista de appids) para que si el script
    se interrumpe y se vuelve a correr, siga con los MISMOS juegos y no
    elija una muestra distinta cada vez.
    """
    if SAMPLE_CACHE.exists():
        print(f"Usando muestra ya elegida (cache): {SAMPLE_CACHE}")
        with open(SAMPLE_CACHE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [(int(row["appid"]), row["name"], row["estrato"]) for row in reader]

    random.seed(RANDOM_SEED)

    candidatos_por_estrato = {"bajo": [], "medio": [], "alto": []}
    for j in juegos:
        total_resenas = j["positive"] + j["negative"]
        if total_resenas < MIN_REVIEWS:
            continue
        mid = owners_a_mid(j["owners"])
        estrato = asignar_estrato(mid)
        if estrato is None:
            continue
        candidatos_por_estrato[estrato].append((j["appid"], j["name"], estrato))

    print("Candidatos disponibles tras filtro de calidad (>= %d resenas):" % MIN_REVIEWS)
    for estrato, lista in candidatos_por_estrato.items():
        print(f"  {estrato}: {len(lista)} disponibles")

    muestra = []
    for estrato, lista in candidatos_por_estrato.items():
        n = min(N_POR_ESTRATO, len(lista))
        if n < N_POR_ESTRATO:
            print(f"  AVISO: estrato '{estrato}' solo tiene {n} juegos disponibles "
                  f"(se pidieron {N_POR_ESTRATO}).")
        muestra.extend(random.sample(lista, n))

    random.shuffle(muestra)  # para que al recolectar no queden agrupados por estrato

    with open(SAMPLE_CACHE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["appid", "name", "estrato"])
        writer.writerows(muestra)

    print(f"Muestra estratificada construida: {len(muestra)} juegos en total.")
    return muestra


# ============================================================
# PASO 3: detalle por juego (SteamSpy appdetails + Steam Store)
# ============================================================

def parsear_fecha(fecha_texto):
    """
    Steam Store devuelve fechas como 'Sep 17, 2020'. Si el juego no tiene
    fecha valida (ej. 'Coming soon', string vacio, formato raro), devuelve
    (None, None, None) y se deja como nulo en el CSV.
    """
    if not fecha_texto:
        return None, None, None
    try:
        dt = datetime.strptime(fecha_texto, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d"), dt.month, dt.year
    except ValueError:
        return None, None, None


def obtener_detalle_juego(appid, nombre, estrato):
    """
    Combina SteamSpy appdetails + Steam Store appdetails para un solo juego.
    Devuelve un dict con la fila lista para el CSV, o None si el juego
    debe descartarse (y en ese caso registra la razon en DROPPED_LOG).
    """
    # --- SteamSpy appdetails ---
    ss = get_con_reintentos(
        "https://steamspy.com/api.php",
        {"request": "appdetails", "appid": appid},
    )
    time.sleep(STEAMSPY_DELAY)

    if ss is None or not ss.get("name"):
        return None, "steamspy_sin_datos"

    positive = ss.get("positive", 0)
    negative = ss.get("negative", 0)
    n_reviews = positive + negative
    if n_reviews == 0:
        return None, "sin_resenas_en_detalle"

    owners_mid = owners_a_mid(ss.get("owners", ""))
    if owners_mid is None:
        return None, "owners_invalido"

    try:
        price_usd = int(ss.get("price", 0)) / 100
    except (ValueError, TypeError):
        price_usd = None

    languages_str = ss.get("languages", "") or ""
    n_languages = len([x for x in languages_str.split(",") if x.strip()]) if languages_str else 0

    tags_dict = ss.get("tags", {})
    if isinstance(tags_dict, list):  # SteamSpy devuelve [] si no hay tags, no {}
        tags_dict = {}
    tags_ordenados = sorted(tags_dict.items(), key=lambda kv: -kv[1])
    tags_str = "|".join(t[0] for t in tags_ordenados)

    genre_str = ss.get("genre", "") or ""
    primary_genre = genre_str.split(",")[0].strip() if genre_str else None

    # --- Steam Store appdetails (solo para fecha de lanzamiento) ---
    store = get_con_reintentos(
        "https://store.steampowered.com/api/appdetails",
        {"appids": appid, "cc": "us", "l": "en"},
    )
    time.sleep(STORE_DELAY)

    release_date, release_month, release_year = None, None, None
    if store and store.get(str(appid), {}).get("success"):
        info = store[str(appid)]["data"]
        fecha_info = info.get("release_date", {})
        if not fecha_info.get("coming_soon", False):
            release_date, release_month, release_year = parsear_fecha(fecha_info.get("date"))
        # si Steam Store no nos dio genero (raro), usamos el de SteamSpy ya guardado arriba
    else:
        # el juego pudo haber sido removido de la tienda; igual lo conservamos
        # porque SteamSpy si tiene sus datos, solo quedara sin fecha
        pass

    fila = {
        "appid": appid,
        "name": ss.get("name", nombre),
        "price_usd": price_usd,
        "owners_mid": owners_mid,
        "owners_range": ss.get("owners", ""),
        "owners_stratum": estrato,
        "positive": positive,
        "negative": negative,
        "n_reviews": n_reviews,
        "pct_positive": round(100 * positive / n_reviews, 2),
        "n_languages": n_languages,
        "tags": tags_str,
        "primary_genre": primary_genre,
        "release_date": release_date,
        "release_month": release_month,
        "release_year": release_year,
    }
    return fila, None


# ============================================================
# PASO 4: orquestacion principal (con resume automatico)
# ============================================================

COLUMNAS = [
    "appid", "name", "price_usd", "owners_mid", "owners_range", "owners_stratum",
    "positive", "negative", "n_reviews", "pct_positive", "n_languages", "tags",
    "primary_genre", "release_date", "release_month", "release_year",
]


def cargar_appids_ya_procesados():
    """Lee el CSV final (si existe) y los descartados, para no re-pedir lo ya hecho."""
    procesados = set()
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                procesados.add(int(row["appid"]))
    if DROPPED_LOG.exists():
        with open(DROPPED_LOG, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                procesados.add(int(row["appid"]))
    return procesados


def main():
    juegos = obtener_lista_indie()
    muestra = construir_muestra(juegos)

    ya_procesados = cargar_appids_ya_procesados()
    pendientes = [(aid, name, estr) for aid, name, estr in muestra if aid not in ya_procesados]

    print(f"\nTotal en la muestra: {len(muestra)} | ya procesados: {len(ya_procesados)} | "
          f"pendientes: {len(pendientes)}")

    output_existe = OUTPUT_CSV.exists()
    dropped_existe = DROPPED_LOG.exists()

    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f_out, \
         open(DROPPED_LOG, "a", newline="", encoding="utf-8") as f_drop:

        writer_out = csv.DictWriter(f_out, fieldnames=COLUMNAS)
        writer_drop = csv.writer(f_drop)
        if not output_existe:
            writer_out.writeheader()
        if not dropped_existe:
            writer_drop.writerow(["appid", "name", "razon"])

        ok_count, drop_count = 0, 0
        t_inicio = time.time()

        try:
            for i, (appid, nombre, estrato) in enumerate(pendientes, start=1):
                fila, razon = obtener_detalle_juego(appid, nombre, estrato)
                if fila is not None:
                    writer_out.writerow(fila)
                    f_out.flush()
                    ok_count += 1
                    print(f"[{i}/{len(pendientes)}] OK  {nombre} (appid {appid})")
                else:
                    writer_drop.writerow([appid, nombre, razon])
                    f_drop.flush()
                    drop_count += 1
                    print(f"[{i}/{len(pendientes)}] DROP {nombre} (appid {appid}) -> {razon}")
        except KeyboardInterrupt:
            print("\nInterrumpido por el usuario. Todo lo recolectado hasta ahora quedo "
                  "guardado en el CSV. Vuelve a correr el script para continuar donde se quedo.")

    transcurrido = time.time() - t_inicio
    print(f"\nListo. {ok_count} juegos agregados, {drop_count} descartados en esta corrida. "
          f"Tiempo: {transcurrido/60:.1f} min.")
    print(f"Resultado final en: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
