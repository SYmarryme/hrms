import { createApp, h, ref } from 'vue';

createApp({
  setup() {
    const result = ref('NOT_RUN');
    async function check() {
      try {
        if (location.protocol !== 'https:') throw new Error('必须从 CloudStudio HTTPS 公网入口打开');
        const probeId = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
        const cookieName = 'hrms_t004_probe_' + probeId;
        const scoped = (path: string) => path + '?probe_id=' + probeId;
        const get = async (path: string) => {
          const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', redirect: 'error' });
          if (!response.ok || response.redirected || response.url !== new URL(path, location.origin).href) throw new Error('同源 API 或最终请求路径不符，禁止重定向');
          return response.json();
        };
        const health = await get('/api/v1/poc/health');
        await get(scoped('/api/v1/poc/cookie'));
        const inside = await get(scoped('/api/v1/poc/cookie-check'));
        const outside = await get(scoped('/api/v1/poc-outside/cookie-check'));
        const pathsVerified = inside.observed_path === '/api/v1/poc/cookie-check' && outside.observed_path === '/api/v1/poc-outside/cookie-check';
        const frame = document.createElement('iframe');
        frame.hidden = true;
        frame.src = scoped('/api/v1/poc/browser-cookie');
        let hidden = false;
        try {
          await new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Cookie path document timeout')), 15000);
            frame.onload = () => { clearTimeout(timeout); resolve(); };
            frame.onerror = () => { clearTimeout(timeout); reject(new Error('Cookie path document failed')); };
            document.body.append(frame);
          });
          const context = frame.contentDocument;
          if (!context || context.location.href !== new URL(frame.src, location.origin).href || !context.body.hasAttribute('data-t004-cookie-context') || context.body.dataset.cookieReceived !== 'true') {
            throw new Error('未加载收到诊断 Cookie 的同源路径文档');
          }
          hidden = !context.cookie.split(';').some(value => value.trim().startsWith(cookieName + '='));
        } finally {
          frame.remove();
        }
        const passed = health.fixture === 'hrms-t004' && health.status === 'ok' && pathsVerified && inside.received === true
          && inside.cookie_name_count === 1 && outside.received === false && outside.cookie_name_present === false && outside.cookie_name_count === 0 && hidden;
        result.value = JSON.stringify({ browser_result: passed ? 'PASS' : 'FAIL', commit: health.commit,
          https: true, same_origin: true, cookie_received: inside.received,
          cookie_outside_path: outside.cookie_name_present, cookie_hidden_from_js_inside_path: hidden,
          request_paths_verified: pathsVerified, cookie_scope: 'unique-per-run',
          cookie_inside_name_count: inside.cookie_name_count, cookie_outside_name_count: outside.cookie_name_count,
          legacy_cookie_outside_path: outside.legacy_cookie_present }, null, 2);
      } catch (error) {
        result.value = 'FAIL: ' + (error instanceof Error ? error.message : 'request failed');
      }
    }
    return () => h('main', { style: 'font:16px system-ui;max-width:760px;margin:48px auto;padding:20px' }, [
      h('h1', 'HRMS T-004 健康检查'),
      h('p', '临时技术验证夹具，无员工数据、登录或业务功能。'),
      h('button', { onClick: check, type: 'button' }, '运行浏览器同源与 Cookie 检查'),
      h('pre', { 'aria-live': 'polite', style: 'white-space:pre-wrap' }, result.value),
      h('p', '本页不能证明 8000 端口未曝光或工作空间重启后数据仍在，这两项需独立留证。'),
    ]);
  },
}).mount('#app');
