import {invalidateBusiness} from './data-sync';
import {passwordNotice} from './password-notice';
// Module-private memory only. Never export a token getter or persist this state.
let token: string | null = null;
let onExpired: () => void = () => {};
let onPasswordRequired:()=>void=()=>{};

export interface Profile {
  id: string; username: string; status: string; employee_id: string | null; roles: string[];
  session: { id: string; created_at: string; expires_at: string };
  must_change_password?:boolean;
  employee_name?: string | null; employee_no?: string | null; employment_valid?: boolean;
}
export interface DepartmentRecord {
  id: string; code: string; name: string; parent_id: string | null; status: 'ACTIVE' | 'DISABLED'; version_no: number;
  created_at: string; updated_at: string;
}
export interface Department extends DepartmentRecord {
  direct_employee_count: number; subtree_employee_count: number;
  parent_name?: string | null;
}
export interface DepartmentPage { items: Department[]; total: number; page: number; page_size: number }
export interface DepartmentInput { code: string; name: string; parent_id: string | null; status: 'ACTIVE' | 'DISABLED' }
export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) { super(message); this.status = status; this.code = code; }
}
export const hasSession = () => token !== null;
export function setExpiredHandler(handler: () => void) { onExpired = handler; }
export function setPasswordRequiredHandler(handler:()=>void){onPasswordRequired=handler;}
export function discardSession(){ token=null;onExpired(); }

export type CoursePath = `/positions${string}` | `/employees${string}` | `/attendance${string}` | `/leaves${string}` | `/salaries${string}` | `/dashboard${string}` | `/users${string}`;
type ApiPath = '/auth/login' | '/auth/me' | '/auth/logout' | '/auth/password' | `/departments${string}` | CoursePath;
async function request(path: ApiPath, init: RequestInit = {}, etag?: string, binary = false, probe = false) {
  const attached = path === '/auth/login' ? null : token;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (init.body) headers['Content-Type'] = typeof init.body === 'string' ? 'application/json' : 'application/octet-stream';
  if (attached) headers.Authorization = 'Bearer ' + attached;
  if (etag) headers['If-Match'] = etag;
  if(probe&&path==='/auth/me')headers['X-HRMS-Session-Probe']='1';
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, { ...init, headers, credentials: 'omit', cache: 'no-store',
      redirect: 'error', signal: AbortSignal.timeout(15000) });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '服务暂不可用，请检查连接后重试');
  }
  if(attached && token!==attached)throw new ApiError(401,'AUTHENTICATION_REQUIRED','会话已变化，请重新登录');
  if (response.status === 204) {invalidateBusiness(path,init.method||'GET');return { data: undefined, etag: null };}
  if (!response.ok) {
    if (response.status === 401 && attached && token === attached) { token = null; onExpired(); }
    // Only known constant user messages; never include response bodies/requests in errors.
    let message = response.status === 401 ? '账号或密码错误，或会话已失效' : response.status === 403 ? '当前请求没有访问权限' :
      response.status === 429 ? '尝试过于频繁，请稍后重试' : response.status === 412 ? '记录已被其他操作修改，请重新读取详情后编辑' :
      response.status === 428 ? '请先重新打开详情，再进行修改' : response.status === 409 ? '编号重复或存在层级、在职归属等业务冲突，请核对后重试' :
      response.status === 422 ? '输入或查询参数不正确，请核对字段与长度' : response.status === 404 ? '记录不存在，请刷新列表' : '操作未完成，请稍后重试';
    let passwordRequired=false;
    // Only explicitly approved messages; arbitrary gateway/server text is never reflected.
    try{const payload:unknown=await response.json();if(payload&&typeof payload==='object'&&'error' in payload){const error=payload.error;
      if(error&&typeof error==='object'&&'code' in error&&error.code==='PASSWORD_CHANGE_REQUIRED'&&response.status===403)passwordRequired=true;
      if(error&&typeof error==='object'&&'message' in error&&typeof error.message==='string'){
        const { businessError }=await import('./error-messages');message=businessError(error.message)||message;
      }}}catch{/* Keep the safe status fallback for non-JSON gateways. */}
    if(passwordRequired&&attached&&token===attached){message='请先修改临时密码';onPasswordRequired();}
    const code = passwordRequired?'PASSWORD_CHANGE_REQUIRED':response.status === 401 ? 'AUTHENTICATION_REQUIRED' : response.status === 403 ? 'AUTHORIZATION_DENIED' :
      response.status === 429 ? 'RATE_LIMITED' : response.status === 412 ? 'VERSION_MISMATCH' : 'REQUEST_FAILED';
    throw new ApiError(response.status, code, message);
  }
  if (binary) return { data: await response.blob(), etag: response.headers.get('ETag') };
  let payload: any;
  try { payload = await response.json(); }
  catch { throw new ApiError(response.status, 'INVALID_RESPONSE', '服务响应格式不正确'); }
  invalidateBusiness(path,init.method||'GET');
  return { data: payload.data, etag: response.headers.get('ETag') };
}

export async function courseRequest<T>(path: CoursePath, init: RequestInit = {}, etag?: string): Promise<T> {
  return (await request(path, init, etag)).data as T;
}
export async function employeeFile(path: `/employees/${'template' | 'export'}?${string}`): Promise<Blob> {
  return (await request(path, {}, undefined, true)).data as Blob;
}

export async function login(username: string, password: string): Promise<void> {
  token = null;
  const { data } = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
  if (data?.token_type !== 'Bearer' || typeof data?.access_token !== 'string' || data.access_token.length < 32) {
    throw new ApiError(0, 'INVALID_RESPONSE', '登录响应不可用');
  }
  token = data.access_token;
}
export async function me(probe=false): Promise<Profile> { return (await request('/auth/me',{},undefined,false,probe)).data; }
export async function logout(): Promise<void> {
  try { await request('/auth/logout', { method: 'POST' }); }
  finally { discardSession(); }
}

export async function listDepartments(q = '', page = 1, pageSize = 20): Promise<DepartmentPage> {
  const query = new URLSearchParams({ q, page: String(page), page_size: String(pageSize) });
  return (await request(`/departments?${query.toString()}`)).data;
}
export async function getDepartment(id: string): Promise<{ item: DepartmentRecord; etag: string }> {
  const result = await request(`/departments/${encodeURIComponent(id)}`);
  if (!result.etag || !/^"v[1-9]\d*"$/.test(result.etag)) throw new ApiError(0, 'INVALID_RESPONSE', '暂时无法编辑此部门，请刷新后重试');
  return { item: result.data, etag: result.etag };
}
export async function createDepartment(input: DepartmentInput): Promise<DepartmentRecord> {
  return (await request('/departments', { method: 'POST', body: JSON.stringify(input) })).data;
}
export async function updateDepartment(id: string, input: DepartmentInput, etag: string): Promise<DepartmentRecord> {
  return (await request(`/departments/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(input) }, etag)).data;
}

export async function changeOwnPassword(current_password:string,new_password:string,confirm_password:string):Promise<void>{
  await request('/auth/password',{method:'POST',body:JSON.stringify({current_password,new_password,confirm_password})});
  passwordNotice.value='密码已修改，请使用新密码重新登录。';
  discardSession();
}
