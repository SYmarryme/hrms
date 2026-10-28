import {ref,computed,getCurrentInstance,onMounted,onActivated,onDeactivated,onScopeDispose} from 'vue';
import {onDataInvalidated,advanceReadRevision,type DataResource} from './data-sync';
export function useScopedRefresh(refresh:(current:()=>boolean)=>Promise<void>,resources:DataResource[]=[]){
 const instance=getCurrentInstance(),heldHeight=ref(0);
 const scopeStyle=computed(()=>({display:'flow-root',minHeight:heldHeight.value?heldHeight.value+'px':undefined}));
 const scopeLocked=ref(false),scopeFailure=ref('');let first=true,active=true,pending:Promise<void>|null=null,timer:ReturnType<typeof setTimeout>|undefined,needed=0,disposed=false,cycle=0;
 async function retryScope(){
  if(disposed||!active)return;if(pending)return pending;
  const root=instance?.vnode.el;if(root instanceof HTMLElement)heldHeight.value=root.getBoundingClientRect().height;
  const mine=++cycle;scopeLocked.value=true;scopeFailure.value='';
  pending=(async()=>{try{while(mine===cycle&&active&&!disposed){const completed=needed;
   try{await refresh(()=>mine===cycle&&active&&!disposed);}catch{if(mine===cycle&&active&&completed!==needed)continue;if(mine===cycle&&!disposed)scopeFailure.value='暂时无法加载最新数据，请重试。';return;}
   if(mine!==cycle||!active||disposed)return;if(completed!==needed)continue;scopeLocked.value=false;heldHeight.value=0;return;
  }}finally{if(mine===cycle)pending=null;}})();return pending;
 }
 function schedule(changed=false){if(changed)needed++;if(!active||document.hidden||disposed||timer)return;timer=setTimeout(()=>{timer=undefined;void retryScope();},0);}
 function focus(){if(active&&!document.hidden){if(!timer)advanceReadRevision();schedule(true);}}
 const unsubscribe=onDataInvalidated(changed=>{if(resources.some(resource=>changed.has(resource)))schedule(true);});
 window.addEventListener('focus',focus);document.addEventListener('visibilitychange',focus);
 onMounted(()=>{void retryScope();});
 onActivated(()=>{active=true;if(first){first=false;return;}needed++;void retryScope();});
 onDeactivated(()=>{active=false;cycle++;pending=null;needed++;scopeLocked.value=true;clearTimeout(timer);timer=undefined;});
 onScopeDispose(()=>{disposed=true;cycle++;pending=null;unsubscribe();clearTimeout(timer);window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus);});
 return {scopeLocked,scopeFailure,retryScope,scopeStyle};
}
