import { createApp, h, ref } from 'vue';

createApp({
  setup() {
    const result = ref('NOT_RUN');
    const bearerResult = ref('NOT_RUN');
    const bearerRunning = ref(false);
    async function checkBearer() {
      if (bearerRunning.value) return;
      bearerRunning.value = true;
      bearerResult.value = 'RUNNING';
      let token = '';
      const observations: Record<string, number | null> = { correct: null, missing: null, wrong: null };
      const https = location.protocol === 'https:';
      const edge = /\bEdg\//.test(navigator.userAgent);
      try {
        if (!https || !edge || !window.isSecureContext) throw new Error('Edge HTTPS required');
        const bytes = crypto.getRandomValues(new Uint8Array(32));
        token = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
        bytes.fill(0);
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token))),
          byte => byte.toString(16).padStart(2, '0')).join('');
        const base = '/api/v1/poc/bearer-probes';
        const send = async (path: string, init: RequestInit) => {
          const response = await fetch(path, { ...init, credentials: 'omit', cache: 'no-store',
            redirect: 'error', signal: AbortSignal.timeout(15000) });
          if (response.redirected || response.url !== new URL(path, location.origin).href) throw new Error('Unexpected response');
          return response;
        };
        const prepared = await send(base, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token_sha256: digest }) });
        if (prepared.status !== 201) throw new Error('Test setup failed');
        const context = await prepared.json();
        if (context.fixture !== 'hrms-t004-bearer' || !/^[0-9a-f]{32}$/.test(context.probe_id)
            || !/^[0-9a-f]{40}$/.test(context.commit)) throw new Error('Invalid test context');
        // A context ID is not a credential: missing/wrong Bearer must still be 401.
        const path = base + '/' + context.probe_id;
        const cases = [
          { name: 'correct', expected: 200, value: token },
          { name: 'missing', expected: 401, value: '' },
          { name: 'wrong', expected: 401, value: (token[0] === '0' ? '1' : '0') + token.slice(1) },
        ];
        let passed = true;
        for (const item of cases) {
          try {
            const headers: Record<string, string> = item.value ? { Authorization: 'Bearer ' + item.value } : {};
            const response = await send(path, { headers });
            observations[item.name] = response.status;
            const data = await response.json();
            if (response.status !== item.expected || data.fixture !== 'hrms-t004-bearer'
                || data.commit !== context.commit || data.context_active !== true
                || data.authenticated !== (item.expected === 200)) passed = false;
          } catch {
            passed = false;
          }
        }
        bearerResult.value = JSON.stringify({ bearer_result: passed ? 'PASS' : 'FAIL', https, edge,
          same_origin: true, statuses: observations, commit: context.commit }, null, 2);
      } catch {
        bearerResult.value = JSON.stringify({ bearer_result: 'FAIL', https, edge, statuses: observations,
          failure: 'test_setup_or_request_failed' }, null, 2);
      } finally {
        token = ''; // Release local references; no browser storage, console or token output.
        bearerRunning.value = false;
      }
    }
    async function check() {
      const diagnostics: Record<string, unknown> = {};
      result.value = 'RUNNING';
      try {
        if (location.protocol !== 'https:') throw new Error('必须从 CloudStudio HTTPS 公网入口打开');
        const probeId = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
        const cookieName = 'hrms_t004_probe_' + probeId;
        const scoped = (path: string) => path + '?probe_id=' + probeId;
        const safeAttrs = (attrs: any) => attrs ? ({ name: attrs.name, path: attrs.path,
          secure: attrs.secure, httpOnly: attrs.httpOnly, sameSite: attrs.sameSite,
          domain_present: attrs.domain_present }) : null;
        const strictAttrs = (attrs: any) => attrs?.name === cookieName && attrs.path === '/api/v1/poc/'
          && attrs.secure === true && attrs.httpOnly === true && attrs.sameSite === 'lax' && attrs.domain_present === false;
        const get = async (path: string) => {
          diagnostics.last_request_path = new URL(path, location.origin).pathname;
          const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', redirect: 'error' });
          if (!response.ok || response.redirected || response.url !== new URL(path, location.origin).href) throw new Error('同源 API 或最终请求路径不符，禁止重定向');
          const data = await response.json();
          data.client_boundary = { request_path: new URL(path, location.origin).pathname, response_path: new URL(response.url).pathname };
          data.vite_set_cookie = safeAttrs(JSON.parse(response.headers.get('x-t004-vite-set-cookie') || 'null'));
          return data;
        };
        const health = await get('/api/v1/poc/health');
        const issued = await get(scoped('/api/v1/poc/cookie'));
        diagnostics.issued = { ...issued.client_boundary, backend_set_cookie: safeAttrs(issued.backend_set_cookie), vite_set_cookie: issued.vite_set_cookie };
        const inside = await get(scoped('/api/v1/poc/cookie-check'));
        const outside = await get(scoped('/api/v1/poc-outside/cookie-check'));
        const boundary = (data: any) => ({ ...data.client_boundary, backend_path: data.observed_path,
          cookie_name: data.cookie_name, backend_count: data.cookie_name_count,
          proxy: data.proxy ? { ingress_path: data.proxy.ingress_path, outgoing_path: data.proxy.outgoing_path,
            ingress_count: data.proxy.ingress_count, outgoing_count: data.proxy.outgoing_count } : null });
        diagnostics.inside = boundary(inside);
        diagnostics.outside = boundary(outside);
        const pathsVerified = inside.observed_path === '/api/v1/poc/cookie-check' && outside.observed_path === '/api/v1/poc-outside/cookie-check';
        const proxyMatches = (data: any, path: string) => data.proxy?.ingress_path === path
          && data.proxy.outgoing_path === path && data.proxy.ingress_count === data.cookie_name_count
          && data.proxy.outgoing_count === data.cookie_name_count;
        const boundariesVerified = strictAttrs(issued.backend_set_cookie) && strictAttrs(issued.vite_set_cookie)
          && proxyMatches(inside, '/api/v1/poc/cookie-check') && proxyMatches(outside, '/api/v1/poc-outside/cookie-check');
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
        const passed = health.fixture === 'hrms-t004' && health.status === 'ok' && pathsVerified && boundariesVerified && inside.received === true
          && inside.cookie_name_count === 1 && outside.received === false && outside.cookie_name_present === false && outside.cookie_name_count === 0 && hidden;
        result.value = JSON.stringify({ browser_result: passed ? 'PASS' : 'FAIL', commit: health.commit,
          https: true, same_origin: true, cookie_received: inside.received,
          cookie_outside_path: outside.cookie_name_present, cookie_hidden_from_js_inside_path: hidden,
          request_paths_verified: pathsVerified, cookie_scope: 'unique-per-run',
          cookie_inside_name_count: inside.cookie_name_count, cookie_outside_name_count: outside.cookie_name_count,
          legacy_cookie_outside_path: outside.legacy_cookie_present,
          cookie_boundaries_verified: boundariesVerified, cookie_path_diagnostics: diagnostics }, null, 2);
      } catch (error) {
        result.value = JSON.stringify({ browser_result: 'FAIL', failure: 'request_or_cookie_context_failed', cookie_path_diagnostics: diagnostics }, null, 2);
      }
    }
    return () => h('main', { style: 'font:16px system-ui;max-width:760px;margin:48px auto;padding:20px' }, [
      h('h1', 'HRMS T-004 健康检查'),
      h('p', '临时技术验证夹具，无员工数据、登录或业务功能。'),
      h('button', { onClick: check, type: 'button' }, '运行浏览器同源与 Cookie 检查'),
      h('pre', { 'aria-live': 'polite', style: 'white-space:pre-wrap' }, result.value),
      h('h2', '独立 Bearer Token 兼容性测试'),
      h('p', '仅检查正确、缺失、错误三种请求的状态码，不代表正式认证或 T-004 整体验收。'),
      h('button', { onClick: checkBearer, type: 'button', disabled: bearerRunning.value }, '运行 Bearer 三项检查'),
      h('output', { id: 'bearer-result', 'aria-live': 'polite', style: 'display:block;white-space:pre-wrap;font-family:monospace' }, bearerResult.value),
      h('p', '本页不能证明 8000 端口未曝光或工作空间重启后数据仍在，这两项需独立留证。'),
    ]);
  },
}).mount('#app');
