import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const origin = new URL(process.env.T004_PUBLIC_ORIGIN || '');
if (origin.protocol !== 'https:' || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/') {
  throw new Error('T004_PUBLIC_ORIGIN must be a bare HTTPS origin without credentials');
}
const root = fileURLToPath(new URL('.', import.meta.url));
// Only whitelisted scalar observations are retained; NEVER log request headers.
const ingress = new WeakMap();
const describeRequest = (request) => {
  const url = new URL(request.url || '/', 'http://t004.invalid');
  const id = url.searchParams.get('probe_id') || '';
  if (!/^[0-9a-f]{32}$/.test(id)) return null;
  const name = 'hrms_t004_probe_' + id;
  return { path: url.pathname, name, count: countName(request.headers.cookie, name) };
};
function countName(header, name) {
  const headers = Array.isArray(header) ? header : [header || ''];
  return headers.flatMap(value => String(value).split(';')).filter(part => part.split('=', 1)[0].trim() === name).length;
}
function describeSetCookie(headers, name) {
  for (const header of Array.isArray(headers) ? headers : [headers || '']) {
    const parts = header.split(';');
    if (parts[0].split('=', 1)[0].trim() !== name) continue;
    const attrs = new Map(parts.slice(1).map(part => {
      const at = part.indexOf('=');
      return at < 0 ? [part.trim().toLowerCase(), ''] : [part.slice(0, at).trim().toLowerCase(), part.slice(at + 1).trim()];
    }));
    return { name, path: attrs.get('path') || '', secure: attrs.has('secure'), httpOnly: attrs.has('httponly'),
      sameSite: (attrs.get('samesite') || '').toLowerCase(), domain_present: attrs.has('domain') };
  }
  return null;
}
export default defineConfig({
  root, envDir: false, envPrefix: [], publicDir: false,
  cacheDir: '.vite-cache',
  plugins: [{ name: 't004-safe-boundary-observations', configureServer(server) {
    server.middlewares.use((request, _response, next) => {
      const observed = describeRequest(request);
      if (observed) ingress.set(request, observed);
      next();
    });
  } }],
  server: {
    host: '0.0.0.0', port: 3000, strictPort: true, hmr: false,
    allowedHosts: [origin.hostname], cors: false,
    fs: { strict: true, allow: [root], deny: ['.env', '.env.*', '*.{crt,pem,key,p12,pfx,cer,der}', '.npmrc', '.yarnrc.yml', '**/.git/**'] },
    proxy: {
      '/api/': {
        target: 'http://127.0.0.1:8000', changeOrigin: true, xfwd: false, ws: false,
        configure(proxy) {
          proxy.on('proxyReq', (outgoing, request) => {
            for (const name of ['forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-forwarded-port', 'x-real-ip']) {
              outgoing.removeHeader(name);
            }
            outgoing.setHeader('x-forwarded-proto', 'https');
            outgoing.setHeader('x-forwarded-host', origin.host);
            outgoing.setHeader('x-forwarded-port', origin.port || '443');
            for (const key of ['x-t004-vite-in-path', 'x-t004-vite-out-path', 'x-t004-vite-in-count', 'x-t004-vite-out-count']) outgoing.removeHeader(key);
            const observed = ingress.get(request);
            if (observed) {
              outgoing.setHeader('x-t004-vite-in-path', observed.path);
              outgoing.setHeader('x-t004-vite-in-count', String(observed.count));
              outgoing.setHeader('x-t004-vite-out-path', new URL(outgoing.path, 'http://t004.invalid').pathname);
              outgoing.setHeader('x-t004-vite-out-count', String(countName(outgoing.getHeader('cookie'), observed.name)));
            }
          });
          proxy.on('proxyRes', (response, request) => {
            const observed = ingress.get(request);
            if (observed) {
              const attrs = describeSetCookie(response.headers['set-cookie'], observed.name);
              // Add sanitized metadata only. Original Set-Cookie is NEVER rewritten.
              response.headers['x-t004-vite-set-cookie'] = JSON.stringify(attrs);
            }
          });
        },
      },
    },
  },
});
