<script setup lang="ts">
import {usePageActivity} from '../page-activity';
const listLoaded=ref(false);
const pageActive=usePageActivity();
import Modal from '../components/Modal.vue';
import EmptyState from '../components/EmptyState.vue';
import Pagination from '../components/Pagination.vue';
import {confirmOperation} from '../modal';

import { isHR } from '../policy';
import { markDirty } from '../workspace';
import { useFeedback } from '../feedback';
import { enabledLabel } from '../presentation';
import { ref, computed } from 'vue';
import {useScopedRefresh} from '../scoped-refresh';
import {useLatestRead,useOperationRead,collectPages} from '../data-sync';
import { me, listDepartments, type Department } from '../api';
import { courseApi, tag, errorText, type Position, type Page } from '../course-api';
const items = ref<Position[]>([]), departments = ref<Department[]>([]), q = ref(''), filter = ref(''), grade = ref(''), status = ref('');
const pageSize=ref(20);
const page = ref(1), total = ref(0), busy = ref(false), loading = ref(false), error = ref(''), notice = ref(''), canWrite = ref(false);
const selected = ref<Position | null>(null), open = ref(false),detail=ref<Position|null>(null);
const empty = () => ({ department_id: '', code: '', name: '', grade_code: '', status: 'ACTIVE' });
const form = ref(empty());
const depName = (id: string) => departments.value.find(d => d.id === id)?.name || '部门信息未加载';
const listRead=useLatestRead(),optionsRead=useLatestRead(),operate=useOperationRead(busy,error),detailTarget=ref<string|null>(null);
const selectionWarning=computed(()=>open.value&&form.value.department_id&&!departments.value.some(d=>d.id===form.value.department_id&&d.status==='ACTIVE')?'原选择的部门已停用或不可用，请重新选择。':'');
async function load(strict=false){
 const query=new URLSearchParams({q:q.value,page:String(page.value),page_size:String(pageSize.value),...(filter.value?{department_id:filter.value}:{}),...(grade.value?{grade_code:grade.value}:{}),...(status.value?{status:status.value}:{})});
 try{await listRead.run(query.toString(),()=>courseApi<Page<Position>>(`/positions?${query}`),{start:()=>{loading.value=true;error.value='';},success:data=>{items.value=data.items;total.value=data.total;listLoaded.value=true;},failure:e=>{error.value=errorText(e);},finish:()=>{loading.value=false;}});}catch(e){if(strict===true)throw e;}
}
async function options(){await optionsRead.run('options',async()=>{const [profile,rows]=await Promise.all([me(),collectPages(page=>listDepartments('',page,100))]);return {profile,rows};},{success:data=>{canWrite.value=isHR(data.profile);departments.value=data.rows;}});}
async function edit(item?:Position){if(busy.value)return;await operate('edit:'+String(item?.id||'new'),async()=>{await options();return item?await courseApi<Position>(`/positions/${encodeURIComponent(item.id)}`):null;},latest=>{selected.value=latest;form.value=latest?{department_id:latest.department_id,code:latest.code,name:latest.name,grade_code:latest.grade_code,status:latest.status}:empty();open.value=true;});}
async function save() {if(busy.value)return;if(selectionWarning.value){error.value=selectionWarning.value;return;} busy.value = true; error.value = ''; notice.value='';try {
  if (selected.value) await courseApi(`/positions/${encodeURIComponent(selected.value.id)}`, 'PATCH', form.value, tag(selected.value));
  else await courseApi('/positions', 'POST', form.value);
  markDirty('/positions',false);notice.value = '职位已保存'; open.value = false; await load();
} catch(e) { error.value = errorText(e); } finally { busy.value = false; } }
async function toggle(row:Position){const target=row.status==='ACTIVE'?'DISABLED':'ACTIVE';await confirmOperation({title:row.status==='ACTIVE'?'停用职位':'恢复职位',message:`确认${row.status==='ACTIVE'?'停用':'恢复'}职位“${row.name}”？使用中的职位不能停用。`,danger:row.status==='ACTIVE'},async()=>{busy.value=true;error.value='';notice.value='';try{const latest=await courseApi<Position>(`/positions/${encodeURIComponent(row.id)}`);await courseApi(`/positions/${encodeURIComponent(row.id)}`,'PATCH',{department_id:latest.department_id,code:latest.code,name:latest.name,grade_code:latest.grade_code,status:target},tag(latest));notice.value=target==='DISABLED'?'职位已停用':'职位已恢复';await load();}finally{busy.value=false;}});}
async function showDetail(row:Position){if(busy.value)return;detailTarget.value=row.id;await operate('detail:'+row.id,async()=>{await options();return courseApi<Position>(`/positions/${encodeURIComponent(row.id)}`);},fresh=>{detail.value=fresh;},()=>{detailTarget.value=null;});}
const {scopeLocked,scopeFailure,retryScope,scopeStyle}=useScopedRefresh(async current=>{await Promise.all([options(),load(true)]);if(!current())return;const target=detailTarget.value;if(target){const fresh=await courseApi<Position>(`/positions/${encodeURIComponent(target)}`);if(current()&&detailTarget.value===target)detail.value=fresh;}},['positions','departments']);
useFeedback(notice,error,'/positions');
</script>
<template><div :style="scopeStyle" class="business-page"><p v-if="scopeLocked" class="verification" role="status">{{scopeFailure||'加载中…'}}<button v-if="scopeFailure" @click="retryScope">重试</button></p><main v-show="!scopeLocked">
  <div class="section-heading"><h1>职位管理</h1><button v-if="canWrite" :disabled="busy" @click="edit()">新增职位</button></div>
  <p v-if="busy&&!open&&!detail" role="status">正在读取操作所需数据…</p><p v-if="error" class="error feedback" role="alert">{{error}}</p><p v-if="notice" class="success feedback" role="status">{{notice}}</p>
  <section class="card"><form class="search-row" @submit.prevent="page=1;load()"><label>名称 / 编码<input v-model="q" maxlength="128"></label><label>部门<select aria-label="部门" v-model="filter"><option value="">全部</option><option v-for="d in departments" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>职级<input v-model="grade" maxlength="64"></label><label>筛选状态<select aria-label="筛选状态" v-model="status"><option value="">全部</option><option value="ACTIVE">启用</option><option value="DISABLED">停用</option></select></label><button :disabled="loading">查询</button></form>
  <p v-if="!scopeLocked&&(loading||!listLoaded&&!error)" role="status">加载中…</p><EmptyState v-else-if="listLoaded&&!error&&!items.length" text="暂无职位数据"/>
  <div v-else-if="listLoaded&&!error" class="table-scroll"><table><thead><tr><th>编码 / 名称</th><th>职级</th><th>部门</th><th>状态</th><th>在职人数</th><th>操作</th></tr></thead><tbody><tr v-for="row in items" :key="row.id"><td>{{row.code}} · {{row.name}}</td><td>{{row.grade_code}}</td><td>{{depName(row.department_id)}}</td><td><span :class="['status-badge',row.status==='ACTIVE'?'active':'disabled']">{{enabledLabel(row.status)}}</span></td><td>{{row.employee_count}}</td><td><button class="text-button" :disabled="busy" @click="showDetail(row)">详情</button><button v-if="canWrite" class="text-button" :disabled="busy" @click="edit(row).catch(e=>error=errorText(e))">编辑</button><button v-if="canWrite" class="text-button" :disabled="busy||open" @click="toggle(row)">{{row.status==='ACTIVE'?'停用':'恢复'}}</button></td></tr></tbody></table></div>
  <Pagination :page="page" :page-size="pageSize" :total="total" :busy="loading" @page="page=$event;load()" @size="pageSize=$event;page=1;load()"/></section>
  <Modal :return-focus="operate.opener.value" v-if="open" :title="selected?'编辑职位':'新增职位'" :busy="busy" :error="error" :concealed="scopeLocked" @retry="retryScope" @close="open=false"><form @submit.prevent="save"><fieldset :disabled="busy"><p v-if="selectionWarning" class="error" role="alert">{{selectionWarning}}</p><div class="form-columns"><label>编码<input v-model="form.code" required maxlength="64"></label><label>名称<input v-model="form.name" required maxlength="128"></label><label>职级<input v-model="form.grade_code" required maxlength="64"></label><label>所属部门<select aria-label="所属部门" v-model="form.department_id" required><option disabled value="">请选择</option><option v-if="selectionWarning" disabled :value="form.department_id">原选择已不可用，请重新选择</option><option v-for="d in departments.filter(x=>x.status==='ACTIVE')" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>职位状态<select aria-label="职位状态" v-model="form.status"><option value="ACTIVE">启用</option><option value="DISABLED">停用</option></select></label></div><p class="muted">使用中的职位不能停用或换部门。</p><div class="form-actions"><button>保存职位</button><button type="button" class="secondary" data-modal-cancel>取消</button></div></fieldset></form></Modal>
<Modal :return-focus="operate.opener.value" v-if="detail" title="职位详情" :track-changes="false" :concealed="scopeLocked" @retry="retryScope" @close="detail=null;detailTarget=null"><dl><dt>编码 / 名称</dt><dd>{{detail.code}} · {{detail.name}}</dd><dt>职级</dt><dd>{{detail.grade_code}}</dd><dt>部门</dt><dd>{{depName(detail.department_id)}}</dd><dt>状态</dt><dd>{{enabledLabel(detail.status)}}</dd></dl></Modal></main></div></template>
