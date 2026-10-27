import { ref,computed,getCurrentInstance,onActivated,onDeactivated,onScopeDispose } from 'vue';
export function useScopedRefresh(refresh:()=>Promise<void>){
 const instance=getCurrentInstance(),heldHeight=ref(0);
 // Include child margins in the measured page box instead of collapsing outside it.
 const scopeStyle=computed(()=>({display:'flow-root',minHeight:heldHeight.value?heldHeight.value+'px':undefined}));
 const scopeLocked=ref(false),scopeFailure=ref('');let first=true,active=true,pending:Promise<void>|null=null;
 async function retryScope(){if(pending)return pending;const root=instance?.vnode.el;if(root instanceof HTMLElement)heldHeight.value=root.getBoundingClientRect().height;scopeLocked.value=true;scopeFailure.value='';pending=(async()=>{try{await refresh();scopeLocked.value=false;heldHeight.value=0;}catch{scopeFailure.value='暂时无法加载此页面，请重试。';}finally{pending=null;}})();return pending;}
 function focus(){if(active&&!document.hidden)void retryScope();}
 window.addEventListener('focus',focus);
 document.addEventListener('visibilitychange',focus);
 onScopeDispose(()=>{window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus);});
 onDeactivated(()=>{active=false;scopeLocked.value=true;});onActivated(()=>{active=true;if(first){first=false;return;}void retryScope();});
 return {scopeLocked,scopeFailure,retryScope,scopeStyle};
}
