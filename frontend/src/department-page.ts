import {useLatestRead,useOperationRead} from './data-sync';
import { computed, reactive, ref,toRef } from 'vue';
import { markDirty } from './workspace';
import {confirmOperation} from './modal';
import { ApiError, createDepartment, getDepartment, listDepartments, me, updateDepartment,
  type Department, type DepartmentRecord, type DepartmentInput, type Profile } from './api';

const emptyForm = (): DepartmentInput => ({ code: '', name: '', parent_id: null, status: 'ACTIVE' });
const safeError = (error: unknown) => error instanceof ApiError ? error.message : '操作未完成，请重试';

export function useDepartmentPage() {
  const profile = ref<Profile | null>(null);
  const canManage = computed(() => !!profile.value?.roles.includes('HR') && !!profile.value.employee_id && profile.value.employment_valid!==false);
  const state = reactive({ items: [] as Department[], q: '', page: 1, pageSize: 20, total: 0,
    loaded:false, loading: false, busy: false, error: '', notice: '', mode: null as 'new' | 'edit' | 'detail' | null,
    detail: null as DepartmentRecord | null, summary: null as Department | null, etag: '', form: emptyForm(),
    parentOptions: [] as Department[], parentQ: '', parentPage: 1, parentTotal: 0, parentLoading: false, parentError: '', parentCurrent:null as DepartmentRecord|null });
  const parentWarning=computed(()=>state.parentError||(state.form.status==='ACTIVE'&&state.form.parent_id&&((state.parentCurrent?.id===state.form.parent_id&&state.parentCurrent.status==='DISABLED')||state.parentOptions.some(row=>row.id===state.form.parent_id&&row.status==='DISABLED'))?'原选择的上级部门已停用，请重新选择或核对部门状态。':''));
  const listRead=useLatestRead(),parentRead=useLatestRead(),operate=useOperationRead(toRef(state,'busy'),toRef(state,'error'));
  async function load(strict=false){const q=state.q.trim(),page=state.page,size=state.pageSize;try{await listRead.run(JSON.stringify([q,page,size]),()=>listDepartments(q,page,size),{start:()=>{state.loading=true;state.error='';},success:result=>{state.items=result.items;state.total=result.total;state.loaded=true;},failure:error=>{state.items=[];state.total=0;state.error=safeError(error);},finish:()=>{state.loading=false;}});}catch(e){if(strict===true)throw e;}}
  async function initialize(strict=false,current:()=>boolean=()=>true){try{const fresh=await me();if(!current())return;profile.value=fresh;await load(true);if(!current())return;if(state.mode==='new'||state.mode==='edit')await parents(state.parentPage,true);const target=state.detail;if(current()&&state.mode==='detail'&&target){const fresh=await getDepartment(target.id);if(current()&&state.detail?.id===target.id){state.detail=fresh.item;state.summary=state.items.find(row=>row.id===fresh.item.id)||null;}}}catch(error){if(!current())return;state.error=safeError(error);state.loading=false;if(strict===true)throw error;}}
  async function search() { state.page = 1; state.notice = ''; await load(); }
  async function go(page: number) { state.page = Math.max(1, page); await load(); }
  async function parents(page=1,strict=false){const q=state.parentQ.trim(),parent=state.form.parent_id;try{await parentRead.run(JSON.stringify([q,page,parent]),async()=>{const [result,current]=await Promise.all([listDepartments(q,page,20),parent?getDepartment(parent):Promise.resolve(null)]);return {result,current};},{start:()=>{state.parentLoading=true;state.parentError='';},success:({result,current})=>{state.parentPage=page;state.parentOptions=result.items;state.parentTotal=result.total;state.parentCurrent=current?.item||null;},failure:error=>{state.error=safeError(error);state.parentError='暂时无法确认上级部门，请重新读取后操作。';},finish:()=>{state.parentLoading=false;}});}catch(error){if(strict===true)throw error;}}
  async function beginCreate(){if(!canManage.value||state.busy)return;await operate('create',async()=>{const profile=await me();const parents=await listDepartments('',1,20);return {profile,parents};},fresh=>{profile.value=fresh.profile;if(!canManage.value)return;state.notice='';state.form=emptyForm();state.parentQ='';state.parentPage=1;state.parentOptions=fresh.parents.items;state.parentTotal=fresh.parents.total;state.parentError='';state.parentCurrent=null;state.mode='new';state.detail=null;state.summary=null;state.etag='';});}
  async function open(id:string,edit=false){if(state.busy||(edit&&!canManage.value))return;await operate('open:'+id+':'+edit,async()=>{const [result,currentProfile,parents]=await Promise.all([getDepartment(id),me(),edit?listDepartments('',1,20):Promise.resolve(null)]);const current=result.item.parent_id?await getDepartment(result.item.parent_id):null;return {result,currentProfile,parents,current};},({result,currentProfile,parents,current})=>{profile.value=currentProfile;if(edit&&!canManage.value)return;state.notice='';state.detail=result.item;state.etag=result.etag;state.mode=edit?'edit':'detail';state.summary=state.items.find(item=>item.id===id)||null;state.form={code:result.item.code,name:result.item.name,parent_id:result.item.parent_id,status:result.item.status};state.parentCurrent=current?.item||null;state.parentError='';if(parents){state.parentQ='';state.parentPage=1;state.parentOptions=parents.items;state.parentTotal=parents.total;}});}
  async function save() {
    if (!canManage.value || state.busy || !['new', 'edit'].includes(state.mode || '')) return;
    if(state.parentLoading||parentWarning.value){state.error=parentWarning.value||'正在读取上级部门，请稍候';return;}
    const input: DepartmentInput = { ...state.form, code: state.form.code.trim(), name: state.form.name.trim() };
    if (!input.code || !input.name) { state.error = '部门编号和名称不能为空'; return; }
    state.busy = true; state.error = ''; state.notice = '';
    try {
      if (state.mode === 'new') { await createDepartment(input); state.notice = '部门新增成功'; }
      else { await updateDepartment(state.detail!.id, input, state.etag); state.notice = '部门更新成功'; }
      markDirty('/departments',false);state.mode = null; state.detail = null; state.summary = null; await load();
    } catch (error) { state.error = safeError(error); }
    finally { state.busy = false; }
  }
  function close() { if (!state.busy) { state.mode = null; state.detail = null; state.summary = null; } }
  async function toggle(item:Department){
    if(!canManage.value||state.busy)return;
    const status=item.status==='ACTIVE'?'DISABLED':'ACTIVE';
    await confirmOperation({title:status==='DISABLED'?'停用部门':'恢复部门',message:`确认${status==='DISABLED'?'停用':'恢复'}部门“${item.name}”？请先处理在职人员、下级部门及相关授权。`,danger:status==='DISABLED'},async()=>{
      state.busy=true;state.error='';state.notice='';
      try{const latest=await getDepartment(item.id);await updateDepartment(item.id,{code:latest.item.code,name:latest.item.name,parent_id:latest.item.parent_id,status},latest.etag);
        state.notice=status==='DISABLED'?'部门已停用':'部门已恢复';await load();
      }finally{state.busy=false;}
    });
  }
  return { state, canManage,parentWarning,opener:operate.opener, initialize, load, search, go, parents, beginCreate, open, save, close, toggle };
}
