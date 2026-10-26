<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { me, listDepartments, type Department } from '../api';
import { courseApi, tag, errorText, type Position, type Page } from '../course-api';
const items = ref<Position[]>([]), departments = ref<Department[]>([]), q = ref(''), filter = ref(''), grade = ref(''), status = ref('');
const page = ref(1), total = ref(0), busy = ref(false), loading = ref(false), error = ref(''), notice = ref(''), canWrite = ref(false);
const selected = ref<Position | null>(null), open = ref(false);
const empty = () => ({ department_id: '', code: '', name: '', grade_code: '', status: 'ACTIVE' });
const form = ref(empty());
const depName = (id: string) => departments.value.find(d => d.id === id)?.name || id;
async function load() { loading.value = true; error.value = ''; try {
  const query = new URLSearchParams({ q:q.value, page:String(page.value), page_size:'20', ...(filter.value ? {department_id:filter.value}:{}), ...(grade.value?{grade_code:grade.value}:{}), ...(status.value?{status:status.value}:{}) });
  const result = await courseApi<Page<Position>>(`/positions?${query}`); items.value = result.items; total.value = result.total;
} catch(e) { error.value = errorText(e); } finally { loading.value = false; } }
async function edit(item?: Position) { error.value = ''; selected.value = item ? await courseApi<Position>(`/positions/${encodeURIComponent(item.id)}`) : null;
  form.value = selected.value ? { department_id:selected.value.department_id, code:selected.value.code, name:selected.value.name, grade_code:selected.value.grade_code, status:selected.value.status } : empty(); open.value = true; }
async function save() { busy.value = true; error.value = ''; try {
  if (selected.value) await courseApi(`/positions/${encodeURIComponent(selected.value.id)}`, 'PATCH', form.value, tag(selected.value));
  else await courseApi('/positions', 'POST', form.value);
  notice.value = '职位已保存'; open.value = false; await load();
} catch(e) { error.value = errorText(e); } finally { busy.value = false; } }
onMounted(async () => { try { canWrite.value = (await me()).roles.includes('HR'); let p=1; for (;;) {const result = await listDepartments('',p,100); departments.value.push(...result.items); if (departments.value.length>=result.total) break;p++;} await load(); } catch(e) { error.value=errorText(e); } });
</script>
<template><div class="workspace"><header><span class="brand">HRMS</span><span>职位管理</span><router-link class="back-link" to="/">返回主页</router-link></header><main>
  <div class="section-heading"><h1>职位管理</h1><button v-if="canWrite" @click="edit()">新增职位</button></div>
  <p v-if="error" class="error feedback" role="alert">{{error}}</p><p v-if="notice" class="success feedback" role="status">{{notice}}</p>
  <section class="card"><form class="search-row" @submit.prevent="page=1;load()"><label>名称 / 编码<input v-model="q" maxlength="128"></label><label>部门<select aria-label="部门" v-model="filter"><option value="">全部</option><option v-for="d in departments" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>职级<input v-model="grade" maxlength="64"></label><label>筛选状态<select aria-label="筛选状态" v-model="status"><option value="">全部</option><option>ACTIVE</option><option>DISABLED</option></select></label><button :disabled="loading">查询</button></form>
  <p v-if="loading" role="status">加载中…</p><p v-else-if="!items.length" class="muted">暂无职位，请由 HR 新增。</p>
  <div v-else class="table-scroll"><table><thead><tr><th>编码 / 名称</th><th>职级</th><th>部门</th><th>状态</th><th>在职人数</th><th>操作</th></tr></thead><tbody><tr v-for="row in items" :key="row.id"><td>{{row.code}} · {{row.name}}</td><td>{{row.grade_code}}</td><td>{{depName(row.department_id)}}</td><td>{{row.status}}</td><td>{{row.employee_count}}</td><td><button v-if="canWrite" class="text-button" @click="edit(row).catch(e=>error=errorText(e))">编辑 / 启停</button></td></tr></tbody></table></div>
  <nav class="pagination"><span>共 {{total}} 条 · 第 {{page}} 页</span><button :disabled="page<=1||loading" @click="page--;load()">上一页</button><button :disabled="page*20>=total||loading" @click="page++;load()">下一页</button></nav></section>
  <section v-if="open" class="card"><h2>{{selected?'编辑':'新增'}}职位</h2><form @submit.prevent="save"><fieldset :disabled="busy"><div class="form-columns"><label>编码<input v-model="form.code" required maxlength="64"></label><label>名称<input v-model="form.name" required maxlength="128"></label><label>职级<input v-model="form.grade_code" required maxlength="64"></label><label>所属部门<select aria-label="所属部门" v-model="form.department_id" required><option disabled value="">请选择</option><option v-for="d in departments.filter(x=>x.status==='ACTIVE')" :key="d.id" :value="d.id">{{d.name}}</option></select></label><label>职位状态<select aria-label="职位状态" v-model="form.status"><option>ACTIVE</option><option>DISABLED</option></select></label></div><p class="muted">使用中的职位不能停用或换部门。</p><div class="form-actions"><button>保存职位</button><button type="button" class="secondary" @click="open=false">取消</button></div></fieldset></form></section>
</main></div></template>
