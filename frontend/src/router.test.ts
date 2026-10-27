import { describe, expect, it, vi,beforeEach } from 'vitest';
import { createMemoryHistory } from 'vue-router';
import { hasSession,me } from './api';
import { resetWorkspace } from './workspace';
import { makeRouter } from './router';

vi.mock('./api', async original => ({ ...(await original<typeof import('./api')>()), hasSession: vi.fn(), me:vi.fn(),setExpiredHandler: vi.fn() }));

describe('protected route navigation', () => {
  beforeEach(()=>{resetWorkspace();vi.mocked(me).mockResolvedValue({id:'fixture',username:'fixture',employee_id:null,status:'ACTIVE',roles:['ADMIN'],session:{id:'s',created_at:'',expires_at:''}});});
  it('redirects a refreshed/new tab without private state to login', async () => {
    vi.mocked(hasSession).mockReturnValue(false);
    const router = makeRouter(createMemoryHistory());
    await router.push('/');
    expect(router.currentRoute.value.path).toBe('/login');
  });
  it('allows a memory session through the guard; the page still calls server me', async () => {
    vi.mocked(hasSession).mockReturnValue(true);
    const router = makeRouter(createMemoryHistory());
    await router.push('/login');
    expect(router.currentRoute.value.path).toBe('/');
  });
  it('redirects the retired employee-files URL to the authorized employee page',async()=>{
    vi.mocked(hasSession).mockReturnValue(true);vi.mocked(me).mockResolvedValue({id:'fixture',username:'fixture',employee_id:'employee',status:'ACTIVE',roles:['HR'],session:{id:'s',created_at:'',expires_at:''}});
    const router=makeRouter(createMemoryHistory());await router.push('/employee-files');expect(router.currentRoute.value.path).toBe('/employees');
  });
});
