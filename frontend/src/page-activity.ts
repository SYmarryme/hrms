import {ref,provide,onActivated,onDeactivated,onBeforeUnmount,type InjectionKey,type Ref} from 'vue';
import {useRoute} from 'vue-router';
export const pageActivityKey:InjectionKey<{active:Ref<boolean>;path:string}>=Symbol('business-page-activity');
export function usePageActivity(){const active=ref(true),path=useRoute().path;provide(pageActivityKey,{active,path});onActivated(()=>{active.value=true;});onDeactivated(()=>{active.value=false;});onBeforeUnmount(()=>{active.value=false;});return active;}
