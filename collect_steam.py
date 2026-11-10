import csv
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "data" / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TAG_LIST_CACHE = CACHE_DIR / "tag_list_indie.json"
SAMPLE_CACHE = CACHE_DIR / "sample_appids.csv"
OUTPUT_CSV = BASE_DIR / "indie_games.csv"
DROPPED_LOG = BASE_DIR / "data" / "dropped_games.csv"

N_POR_ESTRATO = 500
MIN_REVIEWS = 10
RANDOM_SEED = 42

ESTRATO_BAJO_MAX = 50_000
ESTRATO_MEDIO_MAX = 500_000

STEAMSPY_DELAY = 1.1
STORE_DELAY = 1.5
MAX_RETRIES = 3
TIMEOUT = 30

HEADERS = {"User-Agent": "PixelRadar-research-script/1.0 (uso academico, no comercial)"}


def get_con_reintentos(url, params, timeout=TIMEOUT, max_retries=MAX_RETRIES):
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
            return None
        except requests.exceptions.RequestException as e:
            print(f"    [error de red: {e}] reintento {intento}/{max_retries}")
            time.sleep(3 * intento)
    return None


def obtener_lista_indie():
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


def contar_ya_tengo_por_estrato():
    """Cuenta cuantos juegos ya hay en el CSV de salida para cada estrato,
    para no pasarnos de la cuota si el script se corre mas de una vez
    (por ejemplo tras cambiar N_POR_ESTRATO)."""
    conteo = {"bajo": 0, "medio": 0, "alto": 0}
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                estrato = row.get("owners_stratum")
                if estrato in conteo:
                    conteo[estrato] += 1
    return conteo


def construir_muestra(juegos, ya_procesados, ya_tengo_por_estrato):
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
        if j["appid"] in ya_procesados:
            continue
        mid = owners_a_mid(j["owners"])
        estrato = asignar_estrato(mid)
        if estrato is None:
            continue
        candidatos_por_estrato[estrato].append((j["appid"], j["name"], estrato))

    print("Candidatos nuevos disponibles tras filtro de calidad (>= %d resenas):" % MIN_REVIEWS)
    for estrato, lista in candidatos_por_estrato.items():
        print(f"  {estrato}: {len(lista)} disponibles (ya tengo {ya_tengo_por_estrato[estrato]} "
              f"de {N_POR_ESTRATO})")

    muestra = []
    for estrato, lista in candidatos_por_estrato.items():
        objetivo = max(0, N_POR_ESTRATO - ya_tengo_por_estrato[estrato])
        n = min(objetivo, len(lista))
        if n < objetivo:
            print(f"  AVISO: estrato '{estrato}' solo tiene {n} juegos nuevos disponibles "
                  f"(se necesitaban {objetivo} para llegar a la cuota).")
        muestra.extend(random.sample(lista, n))

    random.shuffle(muestra)

    with open(SAMPLE_CACHE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["appid", "name", "estrato"])
        writer.writerows(muestra)

    print(f"Muestra estratificada construida: {len(muestra)} juegos nuevos en total.")
    return muestra


def parsear_fecha(fecha_texto):
    if not fecha_texto:
        return None, None, None
    try:
        dt = datetime.strptime(fecha_texto, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d"), dt.month, dt.year
    except ValueError:
        return None, None, None


def obtener_detalle_juego(appid, nombre, estrato):
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
    if isinstance(tags_dict, list):
        tags_dict = {}
    tags_ordenados = sorted(tags_dict.items(), key=lambda kv: -kv[1])
    tags_str = "|".join(t[0] for t in tags_ordenados)

    genre_str = ss.get("genre", "") or ""
    primary_genre = genre_str.split(",")[0].strip() if genre_str else None

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
    else:
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


COLUMNAS = [
    "appid", "name", "price_usd", "owners_mid", "owners_range", "owners_stratum",
    "positive", "negative", "n_reviews", "pct_positive", "n_languages", "tags",
    "primary_genre", "release_date", "release_month", "release_year",
]


def cargar_appids_ya_procesados():
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

    ya_procesados = cargar_appids_ya_procesados()
    ya_tengo_por_estrato = contar_ya_tengo_por_estrato()
    pendientes = construir_muestra(juegos, ya_procesados, ya_tengo_por_estrato)

    print(f"\nPendientes por procesar: {len(pendientes)}")

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
