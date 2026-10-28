import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, createDepartment, getDepartment, listDepartments, me, updateDepartment } from './api';
import { useDepartmentPage } from './department-page';

vi.mock('./api', async original => ({ ...(await original<typeof import('./api')>()),
  createDepartment: vi.fn(), getDepartment: vi.fn(), listDepartments: vi.fn(), me: vi.fn(), updateDepartment: vi.fn() }));
const item = { id: 'synthetic-department', code: 'D01', name: 'Synthetic', parent_id: null, status: 'ACTIVE' as const,
  version_no: 1, created_at: '', updated_at: '', direct_employee_count: 0, subtree_employee_count: 0 };

describe('department page operations', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(listDepartments).mockResolvedValue({ items: [item], total: 1, page: 1, page_size: 20 });
    vi.mocked(me).mockResolvedValue({ id: 'hr', username: 'synthetic', status: 'ACTIVE', employee_id: 'employee', roles: ['HR'],
      session: { id: 'session', created_at: '', expires_at: '' } });
    vi.mocked(getDepartment).mockResolvedValue({ item, etag: '"v1"' });
  });
  it('loads profile, list, search and pagination with feedback', async () => {
    const page = useDepartmentPage();
    await page.initialize();
    expect(page.canManage.value).toBe(true);
    expect(page.state.items).toHaveLength(1);
    page.state.q = 'Alpha'; await page.search();
    expect(listDepartments).toHaveBeenLastCalledWith('Alpha', 1, 20);
    await page.go(2);
    expect(listDepartments).toHaveBeenLastCalledWith('Alpha', 2, 20);
  });
  it('creates and reloads real data using the shared API', async () => {
    const page = useDepartmentPage(); await page.initialize(); await page.beginCreate();
    page.state.form.code = 'NEW'; page.state.form.name = 'New';
    vi.mocked(createDepartment).mockResolvedValue({ ...item, code: 'NEW' });
    await page.save();
    expect(createDepartment).toHaveBeenCalledWith({ code: 'NEW', name: 'New', parent_id: null, status: 'ACTIVE' });
    expect(page.state.notice).toContain('新增');
    expect(page.state.mode).toBeNull();
  });
  it('gets detail ETag before editing and preserves edits after stale-version rejection', async () => {
    const page = useDepartmentPage(); await page.initialize(); await page.open(item.id, true);
    page.state.form.name = 'Edited';
    vi.mocked(updateDepartment).mockRejectedValue(new ApiError(412, 'VERSION_MISMATCH', '请重新读取详情'));
    await page.save();
    expect(updateDepartment).toHaveBeenCalledWith(item.id, expect.objectContaining({ name: 'Edited' }), '"v1"');
    expect(page.state.error).toContain('重新读取');
    expect(page.state.form.name).toBe('Edited');
    expect(page.state.mode).toBe('edit');
  });
  it('does not offer editing to ADMIN alone', async () => {
    vi.mocked(me).mockResolvedValue({ id: 'admin', username: 'synthetic', status: 'ACTIVE', employee_id: null, roles: ['ADMIN'],
      session: { id: 'session', created_at: '', expires_at: '' } });
    const page = useDepartmentPage(); await page.initialize(); await page.beginCreate();
    expect(page.canManage.value).toBe(false);
    expect(page.state.mode).toBeNull();
    expect(createDepartment).not.toHaveBeenCalled();
  });
  it('shows empty and failed load states and recovers on retry', async () => {
    const page = useDepartmentPage();
    vi.mocked(listDepartments).mockRejectedValueOnce(new ApiError(0, 'NETWORK_ERROR', '连接失败'));
    await page.initialize(); expect(page.state.error).toBe('连接失败'); expect(page.state.loading).toBe(false);
    vi.mocked(listDepartments).mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20 });
    await page.load(); expect(page.state.items).toEqual([]); expect(page.state.error).toBe('');
  });
  it('submits explicit disable status through version-controlled update', async () => {
    const page = useDepartmentPage(); await page.initialize(); await page.open(item.id, true);
    page.state.form.status = 'DISABLED';
    vi.mocked(updateDepartment).mockResolvedValue({ ...item, status: 'DISABLED', version_no: 2 });
    await page.save();
    expect(updateDepartment).toHaveBeenCalledWith(item.id, expect.objectContaining({ status: 'DISABLED' }), '"v1"');
  });
});

const parentSample={id:'child',code:'C',name:'Child',parent_id:null,status:'ACTIVE' as 'ACTIVE'|'DISABLED',version_no:1,created_at:'',updated_at:'',direct_employee_count:0,subtree_employee_count:0};
it('recomputes disabled-parent warnings when the user corrects the child status',async()=>{vi.mocked(me).mockResolvedValue({id:'hr',username:'synthetic',status:'ACTIVE',employee_id:'employee',roles:['HR'],session:{id:'s',created_at:'',expires_at:''}});vi.mocked(listDepartments).mockResolvedValue({items:[parentSample],total:1,page:1,page_size:20});const page=useDepartmentPage();await page.initialize();await page.beginCreate();page.state.form.parent_id='parent';vi.mocked(getDepartment).mockResolvedValue({item:{...parentSample,id:'parent',status:'DISABLED'},etag:'"v1"'});await page.parents();expect(page.parentWarning.value).toContain('停用');page.state.form.status='DISABLED';expect(page.parentWarning.value).toBe('');});
it('an older parent check cannot replace a more recent selected parent',async()=>{vi.mocked(me).mockResolvedValue({id:'hr',username:'synthetic',status:'ACTIVE',employee_id:'employee',roles:['HR'],session:{id:'s',created_at:'',expires_at:''}});vi.mocked(listDepartments).mockResolvedValue({items:[parentSample],total:1,page:1,page_size:20});const page=useDepartmentPage();await page.initialize();let resolve!:(value:{item:typeof parentSample;etag:string})=>void;const slow=new Promise<{item:typeof parentSample;etag:string}>(yes=>resolve=yes);vi.mocked(getDepartment).mockImplementation(id=>id==='old'?slow:Promise.resolve({item:{...parentSample,id:'new'},etag:'"v1"'}));page.state.form.parent_id='old';const first=page.parents();page.state.form.parent_id='new';await page.parents();resolve({item:{...parentSample,id:'old',status:'DISABLED'},etag:'"v1"'});await first;expect(page.state.parentCurrent?.id).toBe('new');expect(page.parentWarning.value).toBe('');});
it('an obsolete profile recheck cannot start a new department query',async()=>{vi.mocked(listDepartments).mockClear();let resolve!:(value:Awaited<ReturnType<typeof me>>)=>void;vi.mocked(me).mockReturnValueOnce(new Promise(yes=>resolve=yes));const page=useDepartmentPage();let current=true;const pending=page.initialize(true,()=>current);current=false;resolve({id:'hr',username:'synthetic',status:'ACTIVE',employee_id:'employee',roles:['HR'],session:{id:'s',created_at:'',expires_at:''}});await pending;expect(listDepartments).not.toHaveBeenCalled();});
