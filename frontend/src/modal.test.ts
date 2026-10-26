import {beforeEach,expect,it} from 'vitest';
import {confirmAction,confirmOperation,acceptConfirmation,confirmation,finishConfirmation} from './modal';
beforeEach(()=>finishConfirmation(false));
it('requires an explicit decision before resolving a confirmation',async()=>{
 const pending=confirmAction({title:'停用部门',message:'虚构确认'});expect(confirmation.current?.title).toBe('停用部门');finishConfirmation(true);expect(await pending).toBe(true);expect(confirmation.current).toBeNull();
});
it('does not overwrite an outstanding confirmation',async()=>{
 const first=confirmAction({title:'放弃未保存修改',message:'虚构确认'});expect(await confirmAction({title:'另一个动作',message:'不会执行'})).toBe(false);expect(confirmation.current?.title).toBe('放弃未保存修改');finishConfirmation(false);expect(await first).toBe(false);
});
it('cancels pending decisions during session teardown',async()=>{
 const pending=confirmAction({title:'敏感操作',message:'虚构确认'});finishConfirmation();expect(await pending).toBe(false);expect(confirmation.current).toBeNull();
});

it('keeps failed state mutations in the dialog and resolves only after a successful retry',async()=>{
 let attempts=0;const result=confirmOperation({title:'停用部门',message:'虚构状态操作'},async()=>{if(++attempts===1)throw new Error('部门仍有在职员工');});
 await acceptConfirmation();expect(confirmation.current?.title).toBe('停用部门');expect(confirmation.error).toBe('部门仍有在职员工');expect(confirmation.busy).toBe(false);
 await acceptConfirmation();expect(await result).toBe(true);expect(attempts).toBe(2);expect(confirmation.current).toBeNull();
});
it('does not execute an operation twice while confirmation is submitting',async()=>{
 let release=()=>{},calls=0;const result=confirmOperation({title:'提交',message:'虚构操作'},async()=>{calls++;await new Promise<void>(resolve=>{release=resolve;});});
 const first=acceptConfirmation();await acceptConfirmation();expect(calls).toBe(1);expect(confirmation.busy).toBe(true);release();await first;expect(await result).toBe(true);
});
it('ignores late completion from a confirmation cancelled by session teardown',async()=>{
 let release=()=>{};const old=confirmOperation({title:'旧会话',message:'虚构操作'},()=>new Promise<void>(resolve=>{release=resolve;}));const sending=acceptConfirmation();finishConfirmation(false);expect(await old).toBe(false);
 const current=confirmAction({title:'新会话',message:'虚构确认'});release();await sending;expect(confirmation.current?.title).toBe('新会话');finishConfirmation(false);expect(await current).toBe(false);
});
