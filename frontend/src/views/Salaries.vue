<script setup lang="ts">
import {usePageActivity} from '../page-activity';
const listLoaded=ref(false);
const pageActive=usePageActivity();
import Modal from '../components/Modal.vue';
import EmptyState from '../components/EmptyState.vue';
import Pagination from '../components/Pagination.vue';

import { useScopedRefresh } from '../scoped-refresh';
import { isHR } from '../policy';
import { useFeedback } from '../feedback';
import { markDirty } from '../workspace';
import { formatBeijing,employeeLabel } from '../presentation';
import { ref, onMounted } from 'vue';
import { me } from '../api';
import { courseApi, all, errorText, tag, type Employee, type Page, type Salary } from '../course-api';
const editorOpen=ref(false),historyOpen=ref(false),historyBusy=ref(false),detail=ref<Salary|null>(null),pageSize=ref(20);
const month=ref(new Date().toISOString().slice(0,7)), filter=ref(''), hr=ref(false), employees=ref<Employee[]>([]), items=ref<Salary[]>([]), history=ref<{version_no:number;amount:string;recorded_at:string;actor_username?:string}[]>([]), busy=ref(false), error=ref(''), notice=ref(''), page=ref(1),total=ref(0),selected=ref<Salary|null>(null);
const form=ref({employee_id:'',month:month.value,amount:''});
const name=(row:Salary)=>employeeLabel(row,'本人');
let loadGeneration=0;
async function load(strict=false){const mine=++loadGeneration;busy.value=true;error.value='';try{const query=new URLSearchParams({page:String(page.value),page_size:String(pageSize.value),...(month.value?{month:month.value}:{}),...(filter.value?{employee_id:filter.value}:{})});const data=await courseApi<Page<Salary>>(`/salaries?${query}`);if(mine===loadGeneration){items.value=data.items;total.value=data.total;listLoaded.value=true;}}catch(e){if(mine===loadGeneration){items.value=[];total.value=0;error.value=errorText(e);}if(strict===true)throw e;}finally{if(mine===loadGeneration)busy.value=false;}}
function edit(row:Salary){error.value='';editorOpen.value=true;selected.value=row;form.value={employee_id:row.employee_id,month:row.month,amount:row.amount};history.value=[];}
async function revisions(row:Salary){history.value=[];historyOpen.value=true;historyBusy.value=true;error.value='';try{history.value=(await courseApi<{items:typeof history.value}>(`/salaries/${encodeURIComponent(row.id)}/history`)).items;}catch(e){error.value=errorText(e);}finally{historyBusy.value=false;}}
async function save(){if(busy.value)return;busy.value=true;error.value='';notice.value='';try{await courseApi('/salaries','PUT',form.value,selected.value?tag(selected.value):undefined);editorOpen.value=false;markDirty('/salaries',false,'salary');notice.value='月度应发工资已保存，修订记录已留存';selected.value=null;form.value.amount='';await load();}catch(e){error.value=errorText(e);}finally{busy.value=false;}}
onMounted(async()=>{try{hr.value=isHR(await me());if(hr.value)employees.value=await all<Employee>('/employees');await load();}catch(e){error.value=errorText(e);}});
const {scopeLocked,scopeFailure,retryScope,scopeStyle}=useScopedRefresh(()=>load(true));
useFeedback(notice,error,'/salaries');
</script>
<template><div :style="scopeStyle" class="business-page"><p v-if="scopeLocked" class="verification" role="status">{{scopeFailure||'正在加载…'}}<button v-if="scopeFailure" @click="retryScope">重试</button></p><main v-show="!scopeLocked"><div class="section-heading"><h1>{{hr?'薪资管理':'我的薪资'}}</h1><button v-if="hr" @click="selected=null;form={employee_id:'',month:month,amount:''};editorOpen=true;error=''">录入薪资</button></div><p class="muted">查看每月应发工资。</p><p v-if="error" class="error feedback" role="alert">{{error}}</p><p v-if="notice" class="success feedback" role="status">{{notice}}</p>
<section class="card"><form class="search-row" @submit.prevent="page=1;load()"><label>月份<input v-model="month" type="month"></label><label v-if="hr">员工<select aria-label="员工" v-model="filter"><option value="">全部</option><option v-for="e in employees" :key="e.id" :value="e.id">{{e.employee_no}} · {{e.full_name}}</option></select></label><button :disabled="busy">查询</button></form><p v-if="busy||!listLoaded&&!error" role="status">加载中…</p><EmptyState v-else-if="listLoaded&&!error&&!items.length" text="暂无薪资记录"/><div v-else-if="listLoaded&&!error" class="table-scroll"><table><thead><tr><th>员工</th><th>月份</th><th>应发总额（元）</th><th>操作</th></tr></thead><tbody><tr v-for="row in items" :key="row.id"><td>{{name(row)}}</td><td>{{row.month}}</td><td class="money">{{row.amount}}</td><td><button class="text-button" @click="detail=row">详情</button><button v-if="hr" class="text-button" @click="edit(row)">修订</button><button class="text-button" v-if="hr" @click="revisions(row)">历史</button></td></tr></tbody></table></div><Pagination :page="page" :page-size="pageSize" :total="total" :busy="busy" @page="page=$event;load()" @size="pageSize=$event;page=1;load()"/>
</section>
<Modal v-if="hr&&editorOpen" :title="selected?'修订月薪':'录入月薪'" scope="salary" :busy="busy" :error="error" :concealed="scopeLocked" @retry="retryScope" @close="editorOpen=false"><form data-dirty-scope="salary" @submit.prevent="save"><fieldset :disabled="busy"><div class="form-columns"><label>员工<select aria-label="员工" v-model="form.employee_id" required :disabled="!!selected"><option disabled value="">请选择</option><option v-for="e in employees" :key="e.id" :value="e.id">{{e.employee_no}} · {{e.full_name}}</option></select></label><label>月份<input v-model="form.month" type="month" required :disabled="!!selected"></label><label>应发总额（元）<input v-model="form.amount" inputmode="decimal" pattern="(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?" required placeholder="0.00" maxlength="13"></label></div><p class="muted">请输入非负金额，最多两位小数；已有记录请从列表进入“修订”。应发工资不代表实际到账金额。</p><div class="form-actions"><button>保存薪资</button><button type="button" class="secondary" data-modal-cancel>取消</button></div></fieldset></form></Modal>
<Modal v-if="hr&&historyOpen" title="薪资修订历史" :track-changes="false" :busy="historyBusy" :error="error" :concealed="scopeLocked" @retry="retryScope" @close="historyOpen=false"><p v-if="historyBusy" role="status">正在加载…</p><template v-else-if="!error"><template v-if="history.length"><h3>修订记录</h3><ul><li v-for="r in history" :key="r.version_no">第 {{r.version_no}} 次记录 · {{r.amount}} 元 · {{formatBeijing(r.recorded_at)}} · {{r.actor_username||'人事管理员'}}</li></ul></template><EmptyState v-if="!history.length" text="暂无薪资修订记录" compact/></template></Modal><Modal v-if="detail" title="薪资详情" :track-changes="false" :concealed="scopeLocked" @retry="retryScope" @close="detail=null"><dl><dt>员工</dt><dd>{{name(detail)}}</dd><dt>月份</dt><dd>{{detail.month}}</dd><dt>应发总额（元）</dt><dd>{{detail.amount}}</dd></dl></Modal></main></div></template>
