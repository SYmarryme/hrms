import {getCurrentInstance,onDeactivated,onScopeDispose,type Ref,shallowRef} from 'vue';
export type DataResource='departments'|'positions'|'employees'|'attendance'|'leaves'|'salaries'|'users'|'identity'|'dashboard';
let readRevision=0;
const listeners=new Set<(resources:ReadonlySet<DataResource>)=>void>();
const impacts:Record<string,DataResource[]>={departments:['departments','positions','employees','users','dashboard'],positions:['positions','employees','dashboard'],employees:['employees','departments','positions','users','attendance','leaves','salaries','dashboard','identity'],attendance:['attendance','dashboard'],leaves:['leaves','attendance','dashboard'],salaries:['salaries','dashboard'],users:['users','identity']};
export function invalidateBusiness(path:string,method:string){
 if(['GET','HEAD','OPTIONS'].includes(method.toUpperCase()))return;
 const url=new URL(path,'http://local.invalid');
 if(url.pathname==='/employees/import'&&url.searchParams.get('mode')!=='commit')return;
 const resources=impacts[url.pathname.split('/')[1]];if(!resources)return;
 readRevision++;const changed=new Set(resources);for(const listener of listeners)listener(changed);
}
export function advanceReadRevision(){readRevision++;}
export function onDataInvalidated(listener:(resources:ReadonlySet<DataResource>)=>void){listeners.add(listener);return ()=>{listeners.delete(listener);};}
interface Handlers<T>{start?:()=>void;success:(value:T)=>void;failure?:(error:unknown)=>void;finish?:()=>void}
/** In-flight coalescing only: no response cache, and only the latest issued read may update UI. */
export function createLatestRead(){
 let generation=0,pending:{key:string;revision:number;finish:()=>void;promise:Promise<void>}|null=null;
 function cancel(){generation++;const previous=pending;pending=null;previous?.finish();}
 function run<T>(key:string,read:()=>Promise<T>,handlers:Handlers<T>):Promise<void>{
  if(pending?.key===key&&pending.revision===readRevision)return pending.promise;
  const mine=++generation;handlers.start?.();
  const promise=(async()=>{try{const value=await read();if(mine===generation)handlers.success(value);}
   catch(error){if(mine===generation){handlers.failure?.(error);throw error;}}
   finally{if(mine===generation){handlers.finish?.();pending=null;}}})();
  pending={key,revision:readRevision,finish:()=>handlers.finish?.(),promise};return promise;
 }
 return {run,cancel};
}
export function useLatestRead(){const task=createLatestRead();if(getCurrentInstance()){onDeactivated(task.cancel);onScopeDispose(task.cancel);}return task;}
export async function collectPages<T>(fetchPage:(page:number)=>Promise<{items:T[];total:number}>):Promise<T[]>{
 const items:T[]=[];for(let page=1;;page++){const result=await fetchPage(page);items.push(...result.items);if(items.length>=result.total||!result.items.length)return items;}
}

/** Operation results own the activation that initiated them; cancelled opens cannot reappear later. */
export function useOperationRead(busy:Ref<boolean>,error:Ref<string>){
 const task=useLatestRead(),opener=shallowRef<HTMLElement|null>(null);
 async function operate<T>(key:string,read:()=>Promise<T>,commit:(value:T)=>void,failed?:()=>void){
  if(typeof document!=='undefined'&&document.activeElement instanceof HTMLElement)opener.value=document.activeElement;
  const revision=readRevision;try{await task.run(key,read,{start:()=>{busy.value=true;error.value='';},success:value=>{if(revision===readRevision)commit(value);},failure:failure=>{if(revision!==readRevision)return;error.value=failure instanceof Error?failure.message:'暂时无法读取最新数据，请重试。';failed?.();},finish:()=>{busy.value=false;}});}catch{/* The safe failure remains visible, never as a successful operation. */}
 }
 return Object.assign(operate,{opener});
}
