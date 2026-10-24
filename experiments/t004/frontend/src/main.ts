import { createApp, h, ref } from 'vue';

createApp({
  setup() {
    const result = ref('NOT_RUN');
    async function check() {
      try {
        if (location.protocol !== 'https:') throw new Error('必须从 CloudStudio HTTPS 公网入口打开');
        const get = async (path: string) => {
          const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
          if (!response.ok || new URL(response.url).origin !== location.origin) throw new Error('同源 API 失败');
          return response.json();
        };
        const health = await get('/api/v1/poc/health');
        await get('/api/v1/poc/cookie');
        const inside = await get('/api/v1/poc/cookie-check');
        const outside = await get('/api/v1/poc-outside/cookie-check');
        const frame = document.createElement('iframe');
        frame.hidden = true;
        frame.src = '/api/v1/poc/browser-cookie';
        let hidden = false;
        try {
          await new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('Cookie path document timeout')), 15000);
            frame.onload = () => { clearTimeout(timeout); resolve(); };
            frame.onerror = () => { clearTimeout(timeout); reject(new Error('Cookie path document failed')); };
            document.body.append(frame);
          });
          const context = frame.contentDocument;
          if (!context || context.location.origin !== location.origin || !context.body.hasAttribute('data-t004-cookie-context') || context.body.dataset.cookieReceived !== 'true') {
            throw new Error('未加载收到诊断 Cookie 的同源路径文档');
          }
          hidden = !context.cookie.split(';').some(value => value.trim().startsWith('hrms_t004_probe='));
        } finally {
          frame.remove();
        }
        const passed = health.fixture === 'hrms-t004' && health.status === 'ok' && inside.received === true && outside.received === false && hidden;
        result.value = JSON.stringify({ browser_result: passed ? 'PASS' : 'FAIL', commit: health.commit,
          https: true, same_origin: true, cookie_received: inside.received,
          cookie_outside_path: outside.received, cookie_hidden_from_js_inside_path: hidden }, null, 2);
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
