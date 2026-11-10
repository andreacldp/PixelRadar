type Bucket = { count: number; windowStart: number };

const WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 5;

// Limitador en memoria: suficiente como freno simple contra envíos repetidos.
// En un entorno serverless cada instancia tiene su propio mapa y se reinicia
// entre cold starts, así que esto es "best effort", no una garantía dura.
const buckets = new Map<string, Bucket>();

export function isRateLimited(key: string): boolean {
  const now = Date.now();
  const bucket = buckets.get(key);

  if (!bucket || now - bucket.windowStart > WINDOW_MS) {
    buckets.set(key, { count: 1, windowStart: now });
    return false;
  }

  bucket.count += 1;
  return bucket.count > MAX_REQUESTS_PER_WINDOW;
}
