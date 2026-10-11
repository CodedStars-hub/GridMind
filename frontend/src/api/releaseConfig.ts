// Production has no Vite development proxy. Require an explicit secure API origin/path.
export function productionApiBase(value: string | undefined): string {
  if (!value) throw new Error('Production build requires VITE_API_BASE_URL pointing to the reviewed HTTPS backend.');
  let url: URL;
  try { url = new URL(value); } catch { throw new Error('Production VITE_API_BASE_URL must be an absolute HTTPS URL; /api is development-only.'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) throw new Error('Production VITE_API_BASE_URL must be HTTPS without credentials, query or fragment.');
  return value;
}
