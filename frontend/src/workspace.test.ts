import { beforeEach, expect, it, vi } from 'vitest';
import { visiblePages, canAccess } from './policy';
import { formatBeijing, stateLabel } from './presentation';
import { workspace, resetWorkspace, requirePasswordChange, openTab, closeTab, markDirty } from './workspace';
import type { Profile } from './api';
import { me,ApiError } from './api';
import { verifySession } from './workspace';
vi.mock('./api',async original=>({...await original<typeof import('./api')>(),me:vi.fn(),discardSession:vi.fn()}));

const profile=(roles:string[]):Profile=>({id:'fictional',username:'fixture',employee_id:roles.includes('ADMIN')&&roles.length===1?null:'employee',status:'ACTIVE',roles,session:{id:'session',created_at:'2026-10-26T00:00:00Z',expires_at:'2026-11-25T00:00:00Z'}});
beforeEach(resetWorkspace);
it('shows self service to employees without HR or system management',()=>{
  const paths=visiblePages(profile(['EMPLOYEE'])).map(p=>p.path);
  expect(paths).toEqual(['/', '/attendance','/leaves','/salaries','/dashboard']);
  expect(canAccess('/employees',profile(['EMPLOYEE']))).toBe(false);
});
it('does not give MANAGER HR writes or ADMIN salary access; unions actual roles',()=>{
  expect(visiblePages(profile(['MANAGER'])).map(p=>p.path)).toContain('/approvals');
  expect(canAccess('/employee-files',profile(['MANAGER']))).toBe(false);
  expect(canAccess('/salaries',profile(['ADMIN']))).toBe(false);
  expect(canAccess('/users',profile(['HR']))).toBe(false);
  expect(canAccess('/users',profile(['HR','ADMIN']))).toBe(true);
  expect(canAccess('/salaries',profile(['HR','ADMIN']))).toBe(true);
});
it('opens one tab per exact page and confirms dirty close',()=>{
  workspace.profile=profile(['HR']);openTab('/');openTab('/departments');openTab('/departments');
  expect(workspace.tabs.map(t=>t.path)).toEqual(['/','/departments']);
  markDirty('/departments',true);expect(closeTab('/departments',()=>false)).toBe(false);
  expect(closeTab('/departments',()=>true)).toBe(true);expect(workspace.tabs.map(t=>t.path)).toEqual(['/']);
});
it('clears tabs and sensitive component generation on session reset',()=>{
  workspace.profile=profile(['HR']);openTab('/salaries');const before=workspace.epoch;
  resetWorkspace();expect(workspace.profile).toBeNull();expect(workspace.tabs).toEqual([]);expect(workspace.epoch).toBeGreaterThan(before);
});
it('formats UTC contract exactly once to Beijing and localizes statuses',()=>{
  expect(formatBeijing('2026-10-26T07:35:51Z')).toBe('2026-10-26 15:35:51');
  expect(formatBeijing('2026-10-26T15:35:51+08:00')).toBe('2026-10-26 15:35:51');
  expect(formatBeijing('2026-10-26T07:35:51')).toBe('2026-10-26 15:35:51');
  expect(formatBeijing('unknown')).toBe('—');expect(stateLabel('TERMINATED')).toBe('已离职');
});
it('keeps drafts concealed but intact during transient permission probe failures',async()=>{
 workspace.profile=profile(['HR']);openTab('/attendance');markDirty('/attendance',true,'rule');const before=workspace.epoch;
 vi.mocked(me).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','连接失败'));
 expect(await verifySession(false)).toBe(false);expect(workspace.profile).not.toBeNull();expect(workspace.epoch).toBe(before);expect(workspace.cover).toBe(true);
 expect(workspace.tabs.find(t=>t.path==='/attendance')?.dirty).toBe(true);
 vi.mocked(me).mockResolvedValueOnce(profile(['HR']));expect(await verifySession(false)).toBe(true);expect(workspace.cover).toBe(false);
});
it('only clears the form that actually saved, keeping independent drafts dirty',()=>{
 workspace.profile=profile(['HR']);openTab('/attendance');markDirty('/attendance',true,'rule');markDirty('/attendance',false,'punch');
 expect(closeTab('/attendance',()=>false)).toBe(false);markDirty('/attendance',false,'rule');expect(closeTab('/attendance',()=>false)).toBe(true);
});

it('removes legacy employee-files entries and preserves one employee tab',async()=>{
 workspace.profile=profile(['HR']);openTab('/employees');workspace.tabs.push({path:'/employee-files',label:'员工文件',dirty:false,dirtyScopes:[]});vi.mocked(me).mockResolvedValueOnce(profile(['HR']));await verifySession(false);
 expect(workspace.tabs.some(t=>t.path==='/employee-files')).toBe(false);expect(visiblePages(profile(['HR'])).some(p=>p.path==='/employee-files')).toBe(false);
 openTab('/employee-files');expect(workspace.tabs.filter(t=>t.path==='/employees')).toHaveLength(1);
});

it('settings is a utility tab, never a home shortcut or business navigation item',()=>{
 workspace.profile=profile(['ADMIN']);openTab('/');openTab('/settings');
 expect(workspace.tabs.map(t=>t.path)).toEqual(['/','/settings']);
 expect(visiblePages(workspace.profile).some(p=>p.path==='/settings')).toBe(false);
 expect(canAccess('/settings',workspace.profile)).toBe(true);
});
it('password restriction destroys sensitive tab generations and suppresses every business menu',()=>{
 workspace.profile=profile(['HR']);openTab('/salaries');const before=workspace.epoch;requirePasswordChange();
 expect(workspace.tabs).toEqual([]);expect(workspace.epoch).toBeGreaterThan(before);
 expect(visiblePages(workspace.profile)).toEqual([]);expect(canAccess('/salaries',workspace.profile)).toBe(false);
});
