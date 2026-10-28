import { reactive } from 'vue';
import { me, discardSession, ApiError,type Profile } from './api';
import { allPages, canAccess } from './policy';
export const workspace=reactive({profile:null as Profile|null,epoch:0,cover:false,connectionError:'',collapsed:false,tabs:[] as {path:string;label:string;dirty:boolean;dirtyScopes:string[]}[]});
let generation=0;
let pending:Promise<boolean>|null=null;
export function resetWorkspace(){generation++;pending=null;workspace.profile=null;workspace.tabs=[];workspace.cover=true;workspace.connectionError='';workspace.epoch++;}
export function openTab(path:string){if(path==='/employee-files')path='/employees';const page=allPages.find(p=>p.path===path);if(page&&canAccess(path,workspace.profile)&&!workspace.tabs.some(t=>t.path===path))workspace.tabs.push({path,label:page.label,dirty:false,dirtyScopes:[]});}
export function markDirty(path:string,dirty:boolean,scope='editor'){const tab=workspace.tabs.find(t=>t.path===path);if(tab){if(dirty&&!tab.dirtyScopes.includes(scope))tab.dirtyScopes.push(scope);if(!dirty)tab.dirtyScopes=tab.dirtyScopes.filter(s=>s!==scope);tab.dirty=tab.dirtyScopes.length>0;}}
export function closeTab(path:string,confirm:()=>boolean){const tab=workspace.tabs.find(t=>t.path===path);if(!tab||path==='/'||tab.dirty&&!confirm())return false;workspace.tabs=workspace.tabs.filter(t=>t.path!==path);return true;}
export async function verifySession(cover=true):Promise<boolean>{
  if(cover)workspace.cover=true;
  if(pending)return pending;
  const mine=generation;
  const task=(async()=>{try{
    const profile=await me(!cover);if(mine!==generation)return false;
    const before=workspace.profile;
    if(before&&JSON.stringify([before.id,before.employee_id,before.roles,before.employment_valid,!!before.must_change_password])!==JSON.stringify([profile.id,profile.employee_id,profile.roles,profile.employment_valid,!!profile.must_change_password])){
      workspace.epoch++;workspace.tabs=[];
    }
    workspace.profile=profile;workspace.connectionError='';if(workspace.tabs.some(t=>t.path==='/employee-files')){workspace.tabs=workspace.tabs.filter(t=>t.path!=='/employee-files');openTab('/employees');}if(!profile.must_change_password)openTab('/');return true;
  }catch(error){if(mine===generation){if(error instanceof ApiError&&error.status===401){resetWorkspace();discardSession();}
    else{workspace.connectionError='暂时无法确认登录状态，请检查网络后重试。未保存的内容已保留。';workspace.cover=true;}}return false;}
  finally{if(mine===generation){workspace.cover=!!workspace.connectionError;pending=null;}}})();
  pending=task;return task;
}

export function requirePasswordChange(){workspace.epoch++;workspace.tabs=[];workspace.cover=true;if(workspace.profile)workspace.profile={...workspace.profile,must_change_password:true};}
