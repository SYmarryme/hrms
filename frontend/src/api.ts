// Module-private memory only. Never export a token getter or persist this state.
let token: string | null = null;
let onExpired: () => void = () => {};

export interface Profile {
  id: string; username: string; status: string; employee_id: string | null; roles: string[];
  session: { id: string; created_at: string; expires_at: string };
}
export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) { super(message); this.status = status; this.code = code; }
}
export const hasSession = () => token !== null;
export function setExpiredHandler(handler: () => void) { onExpired = handler; }

async function request(path: '/auth/login' | '/auth/me' | '/auth/logout', init: RequestInit = {}) {
  const attached = path === '/auth/login' ? null : token;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (init.body) headers['Content-Type'] = 'application/json';
  if (attached) headers.Authorization = 'Bearer ' + attached;
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, { ...init, headers, credentials: 'omit', cache: 'no-store',
      redirect: 'error', signal: AbortSignal.timeout(15000) });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '服务暂不可用，请检查连接后重试');
  }
  if (response.status === 204) return undefined;
  if (!response.ok) {
    if (response.status === 401 && attached && token === attached) { token = null; onExpired(); }
    // Only known constant user messages; never include response bodies/requests in errors.
    const message = response.status === 401 ? '账号或密码错误，或会话已失效' : response.status === 403 ? '当前请求没有访问权限' :
      response.status === 429 ? '尝试过于频繁，请稍后重试' : '操作未完成，请稍后重试';
    const code = response.status === 401 ? 'AUTHENTICATION_REQUIRED' : response.status === 403 ? 'AUTHORIZATION_DENIED' :
      response.status === 429 ? 'RATE_LIMITED' : 'REQUEST_FAILED';
    throw new ApiError(response.status, code, message);
  }
  let payload: any;
  try { payload = await response.json(); }
  catch { throw new ApiError(response.status, 'INVALID_RESPONSE', '服务响应格式不正确'); }
  return payload.data;
}

export async function login(username: string, password: string): Promise<void> {
  token = null;
  const data = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
  if (data?.token_type !== 'Bearer' || typeof data?.access_token !== 'string' || data.access_token.length < 32) {
    throw new ApiError(0, 'INVALID_RESPONSE', '登录响应不可用');
  }
  token = data.access_token;
}
export async function me(): Promise<Profile> { return await request('/auth/me'); }
export async function logout(): Promise<void> {
  try { await request('/auth/logout', { method: 'POST' }); }
  finally { token = null; onExpired(); }
}
