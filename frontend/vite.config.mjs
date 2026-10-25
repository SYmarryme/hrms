import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const origin = new URL(process.env.HRMS_PUBLIC_ORIGIN || 'http://127.0.0.1:3000');
if (origin.username || origin.password || origin.search || origin.hash || origin.pathname !== '/' ||
    (origin.protocol !== 'https:' && !(origin.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(origin.hostname)))) {
  throw new Error('Use an HTTPS public origin or a loopback development origin');
}
export default defineConfig({
  root, envDir: false, envPrefix: [], publicDir: false, plugins: [vue()],
  server: {
    host: '0.0.0.0', port: 3000, strictPort: true, allowedHosts: [origin.hostname], cors: false,
    fs: { strict: true, allow: [root], deny: ['.env', '.env.*', '*.{pem,key,p12,pfx}', '**/.git/**'] },
    proxy: { '/api/': { target: 'http://127.0.0.1:8000', changeOrigin: true, xfwd: false, ws: false,
      configure(proxy) {
        proxy.on('proxyReq', outgoing => {
          for (const key of ['forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-forwarded-port', 'x-real-ip']) outgoing.removeHeader(key);
        });
      } } },
  },
  build: { outDir: 'dist', sourcemap: false },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
