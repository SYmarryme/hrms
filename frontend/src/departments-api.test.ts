import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('department shared Bearer requests', () => {
  beforeEach(() => { vi.resetModules(); vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => vi.unstubAllGlobals());
  const reply = (data: unknown, etag?: string) => new Response(JSON.stringify({ data }), { status: 200, headers: etag ? { ETag: etag } : {} });
  it('uses relative URLs, encodes search and sends only memory Bearer', async () => {
    const api = await import('./api');
    const token = crypto.randomUUID() + crypto.randomUUID();
    vi.mocked(fetch).mockResolvedValueOnce(reply({ access_token: token, token_type: 'Bearer' }));
    await api.login('synthetic', crypto.randomUUID());
    vi.mocked(fetch).mockResolvedValueOnce(reply({ items: [], total: 0 }));
    await api.listDepartments('A&B', 2, 20);
    const [url, options] = vi.mocked(fetch).mock.calls[1];
    expect(url).toBe('/api/v1/departments?q=A%26B&page=2&page_size=20');
    expect(options?.credentials).toBe('omit');
    const correctHeader = (options?.headers as Record<string, string>).Authorization === 'Bearer ' + token;
    expect(correctHeader).toBe(true);
  });
  it('reads a strong detail ETag and forwards it in PATCH', async () => {
    const api = await import('./api');
    vi.mocked(fetch).mockResolvedValueOnce(reply({ id: 'synthetic' }, '"v3"'));
    const detail = await api.getDepartment('synthetic');
    vi.mocked(fetch).mockResolvedValueOnce(reply({ version_no: 4 }, '"v4"'));
    await api.updateDepartment('synthetic', { code: 'D01', name: 'Name', parent_id: null, status: 'ACTIVE' }, detail.etag);
    expect((vi.mocked(fetch).mock.calls[1][1]?.headers as Record<string, string>)['If-Match']).toBe('"v3"');
  });
  it('does not invent an ETag from response fields', async () => {
    const api = await import('./api');
    vi.mocked(fetch).mockResolvedValueOnce(reply({ version_no: 1 }));
    await expect(api.getDepartment('synthetic')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('keeps 403 and stale edit errors as failures', async () => {
    const api = await import('./api');
    for (const status of [403, 409, 412, 422]) {
      vi.mocked(fetch).mockResolvedValueOnce(new Response('{}', { status }));
      await expect(api.createDepartment({ code: 'D01', name: 'Name', parent_id: null, status: 'ACTIVE' })).rejects.toMatchObject({ status });
    }
  });
  it.each([
    ['https://untrusted.invalid/a?b=c#d', 'https%3A%2F%2Funtrusted.invalid%2Fa%3Fb%3Dc%23d'],
    ['//untrusted.invalid/path', '%2F%2Funtrusted.invalid%2Fpath'],
    ['a/b?x=1#section%2F', 'a%2Fb%3Fx%3D1%23section%252F'],
  ])('keeps dynamic department identifiers inside the same-origin API path: %s', async (id, encoded) => {
    const api = await import('./api');
    const token = crypto.randomUUID() + crypto.randomUUID();
    vi.mocked(fetch).mockResolvedValueOnce(reply({ access_token: token, token_type: 'Bearer' }));
    await api.login('synthetic', crypto.randomUUID());
    vi.mocked(fetch).mockResolvedValueOnce(reply({ id }, '"v1"'));
    const detail = await api.getDepartment(id);
    vi.mocked(fetch).mockResolvedValueOnce(reply({ version_no: 2 }));
    await api.updateDepartment(id, { code: 'D01', name: 'Name', parent_id: null, status: 'ACTIVE' }, detail.etag);
    for (const [url, options] of vi.mocked(fetch).mock.calls.slice(1)) {
      expect(url).toBe('/api/v1/departments/' + encoded);
      expect(new URL(String(url), 'https://hrms.invalid').origin).toBe('https://hrms.invalid');
      const correctHeader = (options?.headers as Record<string, string>).Authorization === 'Bearer ' + token;
      expect(correctHeader).toBe(true);
      expect(options?.credentials).toBe('omit');
      expect(options?.redirect).toBe('error');
    }
  });
});
