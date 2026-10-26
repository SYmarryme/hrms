import { effectScope,ref,nextTick } from 'vue';
import { expect,it,vi } from 'vitest';
import { useFeedback } from './feedback';

it('removes transient success after five seconds and never overlaps an error',async()=>{
 vi.useFakeTimers();const scope=effectScope();const notice=ref(''),error=ref('');
 scope.run(()=>useFeedback(notice,error,'/attendance'));
 notice.value='已保存';await nextTick();vi.advanceTimersByTime(4999);expect(notice.value).toBe('已保存');
 vi.advanceTimersByTime(1);expect(notice.value).toBe('');
 notice.value='已保存';await nextTick();error.value='今日已打卡';await nextTick();expect(notice.value).toBe('');
 scope.stop();vi.useRealTimers();
});
