import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const generated = () => crypto.randomUUID() + crypto.randomUUID();
const reply = (data: unknown, status = 200) => new Response(JSON.stringify({ data }), { status });

describe('private memory session client', () => {
  beforeEach(() => { vi.resetModules(); vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.unstubAllGlobals(); });
  it('attaches Bearer only after login, omits cookies, and resets on module reload', async () => {
    const api = await import('./api');
    const token = generated();
    vi.mocked(fetch).mockResolvedValueOnce(reply({ access_token: token, token_type: 'Bearer' }));
    await api.login('synthetic-user', generated());
    expect(api.hasSession()).toBe(true);
    vi.mocked(fetch).mockResolvedValueOnce(reply({ username: 'synthetic-user' }));
    await api.me();
    const options = vi.mocked(fetch).mock.calls[1][1];
    const safelyAttached = (options?.headers as Record<string, string>).Authorization === 'Bearer ' + token;
    expect(safelyAttached).toBe(true);
    expect(options?.credentials).toBe('omit');
    expect(options?.redirect).toBe('error');
    vi.resetModules();
    expect((await import('./api')).hasSession()).toBe(false);
  });
  it('401 clears session; 403 does not silently become successful authentication', async () => {
    const api = await import('./api');
    vi.mocked(fetch).mockResolvedValueOnce(reply({ access_token: generated(), token_type: 'Bearer' }));
    await api.login('synthetic-user', generated());
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'AUTHORIZATION_DENIED' } }), { status: 403 }));
    await expect(api.me()).rejects.toMatchObject({ status: 403 });
    expect(api.hasSession()).toBe(true);
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}', { status: 401 }));
    await expect(api.me()).rejects.toMatchObject({ status: 401 });
    expect(api.hasSession()).toBe(false);
  });
  it('failed logout clears local token without claiming server revocation', async () => {
    const api = await import('./api');
    vi.mocked(fetch).mockResolvedValueOnce(reply({ access_token: generated(), token_type: 'Bearer' }));
    await api.login('synthetic-user', generated());
    vi.mocked(fetch).mockRejectedValueOnce(new Error('controlled offline fixture'));
    await expect(api.logout()).rejects.toMatchObject({ status: 0 });
    expect(api.hasSession()).toBe(false);
  });
  it('empty or gateway-generated non-JSON401 also clears matching private state', async () => {
    const api = await import('./api');
    for (const body of ['', '<html>unauthorized</html>']) {
      vi.mocked(fetch).mockResolvedValueOnce(reply({ access_token: generated(), token_type: 'Bearer' }));
      await api.login('synthetic-user', generated());
      vi.mocked(fetch).mockResolvedValueOnce(new Response(body, { status: 401 }));
      await expect(api.me()).rejects.toMatchObject({ status: 401 });
      expect(api.hasSession()).toBe(false);
    }
  });
});


it('password success clears private session, failure retains it, and required state has its own signal', async () => {
  vi.resetModules(); vi.stubGlobal('fetch', vi.fn());
  const api=await import('./api'); const notice=await import('./password-notice');
  vi.mocked(fetch).mockResolvedValueOnce(reply({access_token:generated(),token_type:'Bearer'}));
  await api.login('synthetic-user',generated()); const required=vi.fn(); api.setPasswordRequiredHandler(required);
  vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({error:{code:'PASSWORD_CHANGE_REQUIRED'}}),{status:403}));
  await expect(api.me()).rejects.toMatchObject({status:403,code:'PASSWORD_CHANGE_REQUIRED'});
  expect(required).toHaveBeenCalledOnce(); expect(api.hasSession()).toBe(true);
  vi.mocked(fetch).mockResolvedValueOnce(new Response('{}',{status:400}));
  await expect(api.changeOwnPassword(generated(),generated(),generated())).rejects.toMatchObject({status:400});
  expect(api.hasSession()).toBe(true); expect(notice.passwordNotice.value).toBe('');
  vi.mocked(fetch).mockResolvedValueOnce(new Response(null,{status:204}));
  await api.changeOwnPassword(generated(),generated(),generated());
  expect(vi.mocked(fetch).mock.calls.at(-1)?.[0]).toBe('/api/v1/auth/password');
  expect(api.hasSession()).toBe(false); expect(notice.passwordNotice.value).toContain('重新登录');
  vi.unstubAllGlobals();
});

it('failed writes never invalidate business data, while a confirmed successful write does',async()=>{
 vi.resetModules();vi.stubGlobal('fetch',vi.fn());const api=await import('./api'),sync=await import('./data-sync');const listener=vi.fn(),stop=sync.onDataInvalidated(listener);
 try{vi.mocked(fetch).mockResolvedValueOnce(reply({access_token:generated(),token_type:'Bearer'}));await api.login('synthetic-user',generated());const input={code:'SYNTHETIC',name:'测试',parent_id:null,status:'ACTIVE' as const};
 for(const status of [400,403,409,422,500]){vi.mocked(fetch).mockResolvedValueOnce(new Response('{}',{status}));await expect(api.createDepartment(input)).rejects.toMatchObject({status});}expect(listener).not.toHaveBeenCalled();
 vi.mocked(fetch).mockResolvedValueOnce(new Response('<html>invalid</html>',{status:200}));await expect(api.createDepartment(input)).rejects.toMatchObject({code:'INVALID_RESPONSE'});expect(listener).not.toHaveBeenCalled();
 vi.mocked(fetch).mockResolvedValueOnce(reply({id:'synthetic',...input}));await api.createDepartment(input);expect(listener).toHaveBeenCalledOnce();expect([...listener.mock.calls[0][0]]).toContain('positions');
 }finally{stop();vi.unstubAllGlobals();}
});
