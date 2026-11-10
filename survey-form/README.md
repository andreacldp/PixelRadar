# PixelRadar — Encuesta de validación

Formulario de validación para estudios indie, construido con Next.js (App Router) +
TypeScript + Tailwind. Mobile-first, sin base de datos: cada respuesta se envía a un
Google Sheet a través de un Google Apps Script publicado como web app.

El diseño (colores, tipografías, tono, motivo visual de peces/sonar) está basado en
`PixelRadar IdeasWeb.pdf`. El PDF no trae una guía de estilo con valores HEX ni nombres
de fuente exactos (son capturas de pantalla de ideas de interfaz), así que los valores
en `src/app/globals.css` y las fuentes en `src/app/layout.tsx` son una reconstrucción
visual fiel a esas capturas, no una extracción literal. Ver la sección "Placeholders y
decisiones de diseño" al final.

## Correr en local

```bash
npm install
cp .env.example .env.local   # y pega ahí la URL del Apps Script (te la publica Google al desplegarlo)
npm run dev
```

Abre `http://localhost:3000`.

El código del Apps Script que recibe las respuestas y las escribe en el Sheet está en
[`apps-script/Code.gs`](apps-script/Code.gs). Los pasos para crear el Sheet y publicar
ese script (y obtener la URL para `SHEETS_WEBHOOK_URL`) no están en este README — se
hicieron/explicaron por fuera, puntualmente, al montar este proyecto.

## 1. Variable de entorno

Local (`.env.local`, no se sube a git):

```
SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/AKfycb.../exec
```

En Vercel: Project Settings > Environment Variables > agrega `SHEETS_WEBHOOK_URL` con el
mismo valor, para los entornos de Production y Preview.

La variable **no** lleva el prefijo `NEXT_PUBLIC_` a propósito: solo se usa dentro de la
ruta de API (`src/app/api/submit/route.ts`), nunca llega al navegador.

## 2. Desplegar en Vercel

1. Sube este repo (o esta carpeta) a GitHub/GitLab/Bitbucket.
2. En [vercel.com/new](https://vercel.com/new), importa el repositorio.
3. Si `survey-form/` vive dentro de un repo más grande (como en este caso, junto al
   proyecto de Python de PixelRadar), en **Root Directory** selecciona `survey-form`.
4. Agrega la variable de entorno `SHEETS_WEBHOOK_URL` (paso 1) antes de desplegar, o
   después desde Project Settings y vuelve a desplegar.
5. Deploy. Vercel detecta Next.js automáticamente, no hace falta configurar nada más.

## Cómo está armado

- `src/app/page.tsx` renderiza `<SurveyForm />`, el orquestador cliente de todo el flujo
  (bienvenida → 5 pasos de preguntas → agradecimiento).
- `src/lib/schema.ts` define con Zod las opciones de cada pregunta y las reglas de
  validación; se usa tanto en el cliente (para no dejar avanzar de paso con datos
  inválidos) como en el servidor (`src/app/api/submit/route.ts`), como defensa real.
- `src/app/api/submit/route.ts`:
  - revisa el campo honeypot oculto (`company_website`): si viene lleno, responde éxito
    falso y no reenvía nada (para no delatarle al bot que fue detectado).
  - aplica un límite simple de envíos por IP en memoria (`src/lib/rateLimit.ts`). Es
    "best effort": en serverless cada instancia tiene su propio contador y se reinicia
    entre cold starts, no es una garantía dura contra abuso.
  - valida con el mismo schema de Zod.
  - reenvía el payload (sin IP ni ningún dato de dispositivo) al Apps Script.
- La encuesta es anónima: no se guarda la IP en el Sheet, solo se usa de forma efímera
  en memoria para el límite de envíos.

## Placeholders y decisiones de diseño

Cosas que dejé como aproximación o pendientes de que el equipo las reemplace por el
asset real:

- **Logo** (`src/components/Logo.tsx`, `src/app/icon.svg`): reconstruí el ícono de
  sonar/radar (círculos concéntricos + punto central con gradiente rosa→verde menta) a
  partir de lo que se ve en las capturas del PDF. No es el archivo de logo oficial —
  si existe un SVG real de la marca, reemplaza este componente y `app/icon.svg`.
- **`public/og-image.png`**: no existe todavía. La metadata en `src/app/layout.tsx` ya
  apunta a `/og-image.png` (1200×630 recomendado) para que al compartir el link se vea
  una imagen de vista previa; falta generar y agregar ese archivo.
- **Colores** (`src/app/globals.css`): reconstruidos visualmente del PDF (fondo casi
  negro, texto gris apagado, acentos rosa/magenta y verde-menta, azul terciario). El
  PDF no trae valores HEX exactos de marca.
- **Tipografías** (`src/app/layout.tsx`): Space Grotesk (headlines), Inter (cuerpo/UI) y
  JetBrains Mono (etiquetas tipo "SONDEO · ROGUELIKE · PIXEL ART" y la barra de
  progreso), elegidas por similitud visual con las capturas del PDF, vía `next/font`
  (se auto-hospedan en el build, no hacen requests a Google en producción). Si la marca
  tiene tipografías con licencia propia, cámbialas aquí.
- **Dominio** (`metadataBase` en `src/app/layout.tsx`): usa un dominio de ejemplo
  (`pixelradar-survey.vercel.app`); actualízalo con la URL real una vez desplegado.
- **Decoración de peces** (`src/components/FishDots.tsx`): es un ícono simple tipo pez
  hecho a mano, discreto, no una recreación pixel-exacta de las visualizaciones del PDF
  (esas usan miles de puntos/números animados, que haría pesada la página).
