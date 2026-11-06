from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from knn_model import _obtener_modelo, recomendar

app = FastAPI(title="PixelRadar - prueba de modelo")


class RecommendRequest(BaseModel):
    tags: list[str]
    n_languages: int = 1
    k: int = 20


@app.get("/api/tags")
def api_tags():
    modelo = _obtener_modelo()
    return {"tags": sorted(modelo.top_tags)}


@app.post("/api/recommend")
def api_recommend(req: RecommendRequest):
    return recomendar(tags=req.tags, n_languages=req.n_languages, k=req.k)


INDEX_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>PixelRadar - prueba de modelo</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  h1 { margin-bottom: 0; }
  .subtitle { color: #666; margin-top: 0.2rem; }
  fieldset { border: 1px solid #ccc; border-radius: 8px; margin-bottom: 1rem; }
  legend { font-weight: bold; }
  #tags-box { max-height: 220px; overflow-y: auto; border: 1px solid #ddd; padding: 0.5rem; border-radius: 6px; }
  .tag-chip { display: inline-block; margin: 2px; }
  label.tag-label { font-size: 0.85rem; }
  .row { display: flex; gap: 1rem; align-items: center; margin: 0.5rem 0; }
  button { background: #2b6cb0; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; font-size: 1rem; }
  button:hover { background: #2554a0; }
  #resultado { margin-top: 1.5rem; }
  .card { background: #f7f7f9; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #ddd; }
  .precio-grande { font-size: 1.6rem; font-weight: bold; color: #2b6cb0; }
  .muted { color: #777; font-size: 0.85rem; }
  .error { color: #b00020; }
</style>
</head>
<body>

<h1>PixelRadar</h1>
<p class="subtitle">Describi tu juego y mira que precio y mes de lanzamiento usaron juegos indie parecidos.</p>

<fieldset>
  <legend>Tags del juego</legend>
  <div id="tags-box">Cargando tags...</div>
</fieldset>

<div class="row">
  <label>Numero de idiomas: <input type="number" id="n_languages" value="3" min="0" style="width:4rem"></label>
  <label>K (cantidad de vecinos): <input type="number" id="k" value="20" min="1" max="200" style="width:4rem"></label>
  <button onclick="recomendar()">Buscar juegos parecidos</button>
</div>

<div id="resultado"></div>

<script>
async function cargarTags() {
  const res = await fetch("/api/tags");
  const data = await res.json();
  const box = document.getElementById("tags-box");
  box.innerHTML = "";
  data.tags.forEach(tag => {
    const span = document.createElement("span");
    span.className = "tag-chip";
    span.innerHTML = `<label class="tag-label"><input type="checkbox" value="${tag}"> ${tag}</label>`;
    box.appendChild(span);
  });
}

const MESES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

async function recomendar() {
  const tags = Array.from(document.querySelectorAll("#tags-box input:checked")).map(el => el.value);
  const n_languages = parseInt(document.getElementById("n_languages").value) || 0;
  const k = parseInt(document.getElementById("k").value) || 20;
  const resultadoDiv = document.getElementById("resultado");

  if (tags.length === 0) {
    resultadoDiv.innerHTML = '<p class="error">Elegi al menos un tag.</p>';
    return;
  }

  resultadoDiv.innerHTML = "<p>Buscando...</p>";

  const res = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tags, n_languages, k }),
  });

  if (!res.ok) {
    resultadoDiv.innerHTML = '<p class="error">Error al consultar el modelo.</p>';
    return;
  }

  const data = await res.json();
  const b = data.benchmark;

  let precioHtml;
  if (b.price_median !== null) {
    precioHtml = `
      <div class="precio-grande">$${b.price_median.toFixed(2)}</div>
      <div class="muted">Rango tipico (P25-P75): $${b.price_p25.toFixed(2)} - $${b.price_p75.toFixed(2)}</div>
    `;
  } else {
    precioHtml = '<p class="muted">No hubo suficientes vecinos exitosos de pago para sugerir un precio.</p>';
  }

  const mesesHtml = b.top_months.map(m => `${MESES[m.month]} (${m.count} juegos)`).join(", ");

  const filasVecinos = data.neighbors.map(n => `
    <tr>
      <td>${n.name}</td>
      <td>${(n.similarity * 100).toFixed(1)}%</td>
      <td>$${n.price.toFixed(2)}</td>
      <td>${n.release_month ? MESES[n.release_month] : "-"}</td>
      <td>${n.pct_positive}%</td>
    </tr>
  `).join("");

  resultadoDiv.innerHTML = `
    <div class="card">
      <h3>Precio sugerido</h3>
      ${precioHtml}
    </div>
    <div class="card">
      <h3>Mejores meses para lanzar</h3>
      <p>${mesesHtml || "sin datos"}</p>
    </div>
    <div class="card">
      <h3>Detalle: ${data.neighbors.length} juegos mas parecidos</h3>
      <p class="muted">Similitud promedio: ${(b.mean_similarity * 100).toFixed(1)}% |
         ${b.n_successful} considerados "exitosos" |
         ${b.pct_free_neighbors.toFixed(0)}% son gratis</p>
      <table>
        <tr><th>Juego</th><th>Similitud</th><th>Precio</th><th>Mes lanz.</th><th>% positivas</th></tr>
        ${filasVecinos}
      </table>
    </div>
  `;
}

cargarTags();
</script>

</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML
