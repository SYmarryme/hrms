import { onScopeDispose, watch, type Ref } from 'vue';
export function useFeedback(notice:Ref<string>,error:Ref<string>,path:string){
  let timer:ReturnType<typeof setTimeout>|undefined;
  watch(notice,value=>{if(!value)return;error.value='';clearTimeout(timer);timer=setTimeout(()=>{notice.value='';},5000);});
  watch(error,value=>{if(value){notice.value='';clearTimeout(timer);}});
  onScopeDispose(()=>clearTimeout(timer));
}
