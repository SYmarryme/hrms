import { ref,onActivated,onDeactivated,onScopeDispose } from 'vue';
export function useScopedRefresh(refresh:()=>Promise<void>){
 const scopeLocked=ref(false),scopeFailure=ref('');let first=true,active=true,pending:Promise<void>|null=null;
 async function retryScope(){if(pending)return pending;scopeLocked.value=true;scopeFailure.value='';pending=(async()=>{try{await refresh();scopeLocked.value=false;}catch{scopeFailure.value='无法核验当前数据范围，内容暂不显示，请重试。';}finally{pending=null;}})();return pending;}
 function focus(){if(active&&!document.hidden)void retryScope();}
 window.addEventListener('focus',focus);
 document.addEventListener('visibilitychange',focus);
 onScopeDispose(()=>{window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus);});
 onDeactivated(()=>{active=false;scopeLocked.value=true;});onActivated(()=>{active=true;if(first){first=false;return;}void retryScope();});
 return {scopeLocked,scopeFailure,retryScope};
}
