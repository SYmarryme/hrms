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
import { ref, onMounted } from 'vue';
import { me, listDepartments, type Department } from '../api';
import { courseApi, tag, errorText, type Position, type Page } from '../course-api';
const items = ref<Position[]>([]), departments = ref<Department[]>([]), q = ref(''), filter = ref(''), grade = ref(''), status = ref('');
const pageSize=ref(20);
const page = ref(1), total = ref(0), busy = ref(false), loading = ref(false), error = ref(''), notice = ref(''), canWrite = ref(false);
const selected = ref<Position | null>(null), open = ref(false),detail=ref<Position|null>(null);
const empty = () => ({ department_id: '', code: '', name: '', grade_code: '', status: 'ACTIVE' });
const form = ref(empty());
const depName = (id: string) => departments.value.find(d => d.id === id)?.name || '部门信息未加载';
async function load() { loading.value = true; error.value = ''; try {
  const query = new URLSearchParams({ q:q.value, page:String(page.value), page_size:String(pageSize.value), ...(filter.value ? {department_id:filter.value}:{}), ...(grade.value?{grade_code:grade.value}:{}), ...(status.value?{status:status.value}:{}) });
  const result = await courseApi<Page<Position>>(`/positions?${query}`); items.value = result.items; total.value = result.total;listLoaded.value=true;
} catch(e) { error.value = errorText(e); } finally { loading.value = false; } }
async function edit(item?: Position) { error.value = ''; selected.value = item ? await courseApi<Position>(`/positions/${encodeURIComponent(item.id)}`) : null;
  form.value = selected.value ? { department_id:selected.value.department_id, code:selected.value.code, name:selected.value.name, grade_code:selected.value.grade_code, status:selected.value.status } : empty(); open.value = true; }
async function save() {if(busy.value)return; busy.value = true; error.value = ''; notice.value='';try {
  if (selected.value) await courseApi(`/positions/${encodeURIComponent(selected.value.id)}`, 'PATCH', form.value, tag(selected.value));
  else await courseApi('/positions', 'POST', form.value);
  markDirty('/positions',false);notice.value = '职位已保存'; open.value = false; await load();
} catch(e) { error.value = errorText(e); } finally { busy.value = false; } }
async function toggle(row:Position){await confirmOperation({title:row.status==='ACTIVE'?'停用职位':'恢复职位',message:`确认${row.status==='ACTIVE'?'停用':'恢复'}职位“${row.name}”？使用中的职位不能停用。`,danger:row.status==='ACTIVE'},async()=>{busy.value=true;error.value='';notice.value='';try{const latest=await courseApi<Position>(`/positions/${encodeURIComponent(row.id)}`);await courseApi(`/positions/${encodeURIComponent(row.id)}`,'PATCH',{department_id:latest.department_id,code:latest.code,name:latest.name,grade_code:latest.grade_code,status:latest.status==='ACTIVE'?'DISABLED':'ACTIVE'},tag(latest));notice.value=latest.status==='ACTIVE'?'职位已停用':'职位已恢复';await load();}finally{busy.value=false;}});}
onMounted(async () => { try { canWrite.value = isHR(await me()); let p=1; for (;;) {const result = await listDepartments('',p,100); departments.value.push(...result.items); if (departments.value.length>=result.total) break;p++;} await load(); } catch(e) { error.value=errorText(e); } });
async function showDetail(row:Position){error.value='';try{detail.value=await courseApi<Position>(`/positions/${encodeURIComponent(row.id)}`);}catch(e){error.value=errorText(e);}}
useFeedback(notice,error,'/positions');
</script>
<template><div class="business-page"><main>
  <div class="section-heading"><h1>职位管理</h1><button v-if="canWrite" @click="edit()">新增职位</button></div>
  <p v-if="error" class="error feedback" role="alert">{{error}}</p><p v-if="notice" class="success feedback" role="status">{{notice}}</p>
  <section class="card"><form class="search-row" @submit.prevent="page=1;load()"><label>名称 / 编码<input v-model="q" maxlength="128"></label><label>部门<select aria-label="部门" v-model="filter"><option value="">全部</option><option v-for="d in departments" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>职级<input v-model="grade" maxlength="64"></label><label>筛选状态<select aria-label="筛选状态" v-model="status"><option value="">全部</option><option value="ACTIVE">启用</option><option value="DISABLED">停用</option></select></label><button :disabled="loading">查询</button></form>
  <p v-if="loading||!listLoaded&&!error" role="status">加载中…</p><EmptyState v-else-if="listLoaded&&!error&&!items.length" text="暂无职位数据"/>
  <div v-else-if="listLoaded&&!error" class="table-scroll"><table><thead><tr><th>编码 / 名称</th><th>职级</th><th>部门</th><th>状态</th><th>在职人数</th><th>操作</th></tr></thead><tbody><tr v-for="row in items" :key="row.id"><td>{{row.code}} · {{row.name}}</td><td>{{row.grade_code}}</td><td>{{depName(row.department_id)}}</td><td><span :class="['status-badge',row.status==='ACTIVE'?'active':'disabled']">{{enabledLabel(row.status)}}</span></td><td>{{row.employee_count}}</td><td><button class="text-button" @click="showDetail(row)">详情</button><button v-if="canWrite" class="text-button" @click="edit(row).catch(e=>error=errorText(e))">编辑</button><button v-if="canWrite" class="text-button" :disabled="busy||open" @click="toggle(row)">{{row.status==='ACTIVE'?'停用':'恢复'}}</button></td></tr></tbody></table></div>
  <Pagination :page="page" :page-size="pageSize" :total="total" :busy="loading" @page="page=$event;load()" @size="pageSize=$event;page=1;load()"/></section>
  <Modal v-if="open" :title="selected?'编辑职位':'新增职位'" :busy="busy" :error="error" @close="open=false"><form @submit.prevent="save"><fieldset :disabled="busy"><div class="form-columns"><label>编码<input v-model="form.code" required maxlength="64"></label><label>名称<input v-model="form.name" required maxlength="128"></label><label>职级<input v-model="form.grade_code" required maxlength="64"></label><label>所属部门<select aria-label="所属部门" v-model="form.department_id" required><option disabled value="">请选择</option><option v-for="d in departments.filter(x=>x.status==='ACTIVE')" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>职位状态<select aria-label="职位状态" v-model="form.status"><option value="ACTIVE">启用</option><option value="DISABLED">停用</option></select></label></div><p class="muted">使用中的职位不能停用或换部门。</p><div class="form-actions"><button>保存职位</button><button type="button" class="secondary" data-modal-cancel>取消</button></div></fieldset></form></Modal>
<Modal v-if="detail" title="职位详情" :track-changes="false" @close="detail=null"><dl><dt>编码 / 名称</dt><dd>{{detail.code}} · {{detail.name}}</dd><dt>职级</dt><dd>{{detail.grade_code}}</dd><dt>部门</dt><dd>{{depName(detail.department_id)}}</dd><dt>状态</dt><dd>{{enabledLabel(detail.status)}}</dd></dl></Modal></main></div></template>
