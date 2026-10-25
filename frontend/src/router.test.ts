import { describe, expect, it, vi } from 'vitest';
import { createMemoryHistory } from 'vue-router';
import { hasSession } from './api';
import { makeRouter } from './router';

vi.mock('./api', async original => ({ ...(await original<typeof import('./api')>()), hasSession: vi.fn(), setExpiredHandler: vi.fn() }));

describe('protected route navigation', () => {
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
});
