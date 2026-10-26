import { beforeEach, expect, it, vi } from 'vitest';
import { courseApi, downloadEmployees, importEmployees } from './course-api';
import { login } from './api';

beforeEach(() => vi.restoreAllMocks());
it('all course API requests stay on the same origin with private memory credentials', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ data: { access_token: crypto.randomUUID(), token_type: 'Bearer' } }), { status: 200 }));
  await login('fictional', crypto.randomUUID());
  fetcher.mockResolvedValue(new Response(JSON.stringify({ data: { items: [], total: 0 } }), { status: 200 }));
  await courseApi('/positions?q=x');
  expect(fetcher.mock.lastCall?.[0]).toBe('/api/v1/positions?q=x');
  expect(fetcher.mock.lastCall?.[1]).toMatchObject({ credentials: 'omit', redirect: 'error' });
  expect(fetcher.mock.lastCall?.[1]?.headers).toHaveProperty('Authorization');
});
it('binary uploads and downloads reuse the authenticated same-origin boundary', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ data: { valid: false, errors: [{ row: 2 }] } }), { status: 200 }));
  await importEmployees(new Blob(['csv']), 'csv', 'preflight');
  expect(fetcher.mock.lastCall?.[0]).toBe('/api/v1/employees/import?format=csv&mode=preflight');
  fetcher.mockResolvedValue(new Response('file', { status: 200 }));
  expect(await (await downloadEmployees('csv', false, 'a&b')).text()).toBe('file');
  expect(fetcher.mock.lastCall?.[0]).toBe('/api/v1/employees/export?format=csv&q=a%26b');
});
it('rejects oversized files before reading or uploading them', async () => {
  const fetcher=vi.spyOn(globalThis,'fetch');
  await expect(importEmployees(new Blob(['x'.repeat(2*1024*1024+1)]),'csv','preflight')).rejects.toMatchObject({status:413});
  expect(fetcher).not.toHaveBeenCalled();
});
it('reports a generic record conflict for non-department edits', async () => {
  vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('{}',{status:412}));
  await expect(courseApi('/salaries','PUT',{amount:'1.00'})).rejects.toMatchObject({message:'记录已被其他操作修改，请重新读取详情后编辑'});
});
it('preserves row, field and actionable reasons from import preflight', async () => {
  const issue={row:3,field:'所属职位',code:'POSITION_DEPARTMENT_MISMATCH',message:'所属职位不属于所选部门，请核对职位所属部门编号'};
  vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({data:{valid:false,errors:[issue],imported:0}}),{status:200}));
  const result=await importEmployees(new Blob(['csv']),'csv','preflight');
  expect(result.valid).toBe(false);expect(result.errors).toEqual([issue]);expect(result.imported).toBe(0);
});
