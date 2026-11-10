import { NextRequest, NextResponse } from 'next/server';
import { surveySchema } from '@/lib/schema';
import { isRateLimited } from '@/lib/rateLimit';

function formatMulti(values: string[], otro?: string): string {
  const parts = [...values];
  if (values.includes('otro') && otro?.trim()) {
    const idx = parts.indexOf('otro');
    parts[idx] = `otro: ${otro.trim()}`;
  }
  return parts.join('; ');
}

export async function POST(req: NextRequest) {
  const ip = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'unknown';

  if (isRateLimited(ip)) {
    return NextResponse.json({ ok: false, error: 'rate_limited' }, { status: 429 });
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid_json' }, { status: 400 });
  }

  // Honeypot: un bot que llena este campo oculto recibe una respuesta de
  // "éxito" falsa y no se reenvía nada a la hoja, sin delatar la trampa.
  if (typeof body.company_website === 'string' && body.company_website.length > 0) {
    return NextResponse.json({ ok: true });
  }

  const parsed = surveySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: 'invalid_data', issues: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const webhookUrl = process.env.SHEETS_WEBHOOK_URL;
  if (!webhookUrl) {
    console.error('SHEETS_WEBHOOK_URL no está configurada');
    return NextResponse.json({ ok: false, error: 'server_misconfigured' }, { status: 500 });
  }

  const data = parsed.data;
  // Encuesta anónima: no se envía IP ni ningún identificador de dispositivo a la hoja.
  const payload = {
    situacion: data.situacion,
    tamanoEquipo: data.tamanoEquipo,
    pais: data.pais,
    decidePrecio: formatMulti(data.decidePrecio, data.decidePrecioOtro),
    decideFecha: formatMulti(data.decideFecha, data.decideFechaOtro),
    tiempoInvestigar: data.tiempoInvestigar,
    infoTranquilidad: data.infoTranquilidad,
    usarias1a5: data.usarias1a5,
    pagarias: data.pagarias,
    contacto: data.contacto,
  };

  try {
    const res = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`sheets_webhook_status_${res.status}`);
    }
  } catch (err) {
    console.error('Error reenviando la respuesta a Google Sheets', err);
    return NextResponse.json({ ok: false, error: 'webhook_failed' }, { status: 502 });
  }

  return NextResponse.json({ ok: true });
}
