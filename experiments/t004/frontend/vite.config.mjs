import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const origin = new URL(process.env.T004_PUBLIC_ORIGIN || '');
if (origin.protocol !== 'https:' || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/') {
  throw new Error('T004_PUBLIC_ORIGIN must be a bare HTTPS origin without credentials');
}
const root = fileURLToPath(new URL('.', import.meta.url));
export default defineConfig({
  root, envDir: false, envPrefix: [], publicDir: false,
  cacheDir: '.vite-cache',
  server: {
    host: '0.0.0.0', port: 3000, strictPort: true, hmr: false,
    allowedHosts: [origin.hostname], cors: false,
    fs: { strict: true, allow: [root], deny: ['.env', '.env.*', '*.{crt,pem,key,p12,pfx,cer,der}', '.npmrc', '.yarnrc.yml', '**/.git/**'] },
    proxy: {
      '/api/': {
        target: 'http://127.0.0.1:8000', changeOrigin: true, xfwd: false, ws: false,
        configure(proxy) {
          proxy.on('proxyReq', (outgoing) => {
            for (const name of ['forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-forwarded-port', 'x-real-ip']) {
              outgoing.removeHeader(name);
            }
            outgoing.setHeader('x-forwarded-proto', 'https');
            outgoing.setHeader('x-forwarded-host', origin.host);
            outgoing.setHeader('x-forwarded-port', origin.port || '443');
          });
        },
      },
    },
  },
});
