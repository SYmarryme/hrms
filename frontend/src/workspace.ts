import { reactive } from 'vue';
import { me, discardSession, ApiError,type Profile } from './api';
import { pages, canAccess } from './policy';
export const workspace=reactive({profile:null as Profile|null,epoch:0,cover:false,connectionError:'',collapsed:false,tabs:[] as {path:string;label:string;dirty:boolean;dirtyScopes:string[]}[]});
let generation=0;
let pending:Promise<boolean>|null=null;
export function resetWorkspace(){generation++;pending=null;workspace.profile=null;workspace.tabs=[];workspace.cover=true;workspace.connectionError='';workspace.epoch++;}
export function openTab(path:string){const page=pages.find(p=>p.path===path);if(page&&canAccess(path,workspace.profile)&&!workspace.tabs.some(t=>t.path===path))workspace.tabs.push({path,label:page.label,dirty:false,dirtyScopes:[]});}
export function markDirty(path:string,dirty:boolean,scope='editor'){const tab=workspace.tabs.find(t=>t.path===path);if(tab){if(dirty&&!tab.dirtyScopes.includes(scope))tab.dirtyScopes.push(scope);if(!dirty)tab.dirtyScopes=tab.dirtyScopes.filter(s=>s!==scope);tab.dirty=tab.dirtyScopes.length>0;}}
export function closeTab(path:string,confirm:()=>boolean){const tab=workspace.tabs.find(t=>t.path===path);if(!tab||path==='/'||tab.dirty&&!confirm())return false;workspace.tabs=workspace.tabs.filter(t=>t.path!==path);return true;}
export async function verifySession(cover=true):Promise<boolean>{
  if(cover)workspace.cover=true;
  if(pending)return pending;
  const mine=generation;
  const task=(async()=>{try{
    const profile=await me(!cover);if(mine!==generation)return false;
    const before=workspace.profile;
    if(before&&JSON.stringify([before.id,before.employee_id,before.roles,before.employment_valid])!==JSON.stringify([profile.id,profile.employee_id,profile.roles,profile.employment_valid])){
      workspace.epoch++;workspace.tabs=[];
    }
    workspace.profile=profile;workspace.connectionError='';openTab('/');return true;
  }catch(error){if(mine===generation){if(error instanceof ApiError&&error.status===401){resetWorkspace();discardSession();}
    else{workspace.connectionError='暂时无法核验权限，内容已遮挡；未保存内容仍保留，请重试。';workspace.cover=true;}}return false;}
  finally{if(mine===generation){workspace.cover=!!workspace.connectionError;pending=null;}}})();
  pending=task;return task;
}
