<script setup lang="ts">
import { ref,onMounted } from 'vue';
import { courseApi,errorText } from '../course-api';
interface Dashboard {employee_count:number;hired_this_month:number;terminated_this_month:number;departments:{id:string;name:string;count:number}[];grades:{name:string;count:number}[];leave_types:{name:string;count:number}[];attendance:Record<string,number>;salary_trend?:{month:string;amount:string}[]}
const result=ref<Dashboard|null>(null),month=ref(new Date().toISOString().slice(0,7)),busy=ref(false),error=ref('');
const labels:Record<string,string>={expected_days:'应出勤天数',complete_days:'完整打卡',late_days:'迟到',early_days:'早退',missing_days:'漏卡',ANNUAL:'年假',SICK:'病假',PERSONAL:'事假',OTHER:'其他'};
async function load(){busy.value=true;error.value='';try{result.value=await courseApi<Dashboard>(`/dashboard?month=${encodeURIComponent(month.value)}`);}catch(e){error.value=errorText(e);}finally{busy.value=false;}}
const width=(count:number,counts:number[])=>`${Math.max(...counts,1)?count/Math.max(...counts,1)*100:0}%`;
onMounted(load);
</script>
<template><div class="workspace"><header><span class="brand">HRMS</span><span>数据看板</span><router-link class="back-link" to="/">返回主页</router-link></header><main><h1>数据看板</h1><p class="muted">统计来自 SQLite 业务记录，并受当前角色和部门范围限制。员工与主管不返回公司薪资汇总。</p><form class="search-row" @submit.prevent="load"><label>统计月份<input v-model="month" type="month" required></label><button :disabled="busy">查询</button></form><p v-if="error" class="error feedback" role="alert">{{error}}</p><p v-if="busy" role="status">统计加载中…</p>
<template v-if="result"><div class="stat-grid"><section><span>当前在职人数</span><strong>{{result.employee_count}}</strong></section><section><span>本月入职</span><strong>{{result.hired_this_month}}</strong></section><section><span>本月离职</span><strong>{{result.terminated_this_month}}</strong></section></div>
<div class="chart-grid"><section class="card"><h2>部门人数</h2><p v-if="!result.departments.length" class="muted">暂无授权范围内的在职人员。</p><div v-for="row in result.departments" :key="row.id" class="bar-row"><span>{{row.name}}</span><div class="bar-track"><i :style="{width:width(row.count,result.departments.map(r=>r.count))}"></i></div><b>{{row.count}}</b></div></section>
<section class="card"><h2>职级比例</h2><p v-if="!result.grades.length" class="muted">暂无职级数据。</p><div v-for="row in result.grades" :key="row.name" class="bar-row"><span>{{row.name}}</span><div class="bar-track"><i :style="{width:result.employee_count?row.count/result.employee_count*100+'%':'0%'}"></i></div><b>{{row.count}} 人</b></div></section>
<section class="card"><h2>月度出勤</h2><dl><template v-for="(value,key) in result.attendance" :key="key"><dt>{{labels[key]}}</dt><dd>{{value}} 天</dd></template></dl></section>
<section class="card"><h2>批准请假类型</h2><p v-if="!result.leave_types.length" class="muted">该月暂无批准请假。</p><div v-for="row in result.leave_types" :key="row.name" class="bar-row"><span>{{labels[row.name]}}</span><div class="bar-track"><i :style="{width:width(row.count,result.leave_types.map(r=>r.count))}"></i></div><b>{{row.count}} 单</b></div></section></div>
<section v-if="result.salary_trend" class="card"><h2>近六个月应发总额（仅 HR）</h2><div v-for="row in result.salary_trend" :key="row.month" class="bar-row"><span>{{row.month}}</span><div class="bar-track"><i :style="{width:width(Number(row.amount),result.salary_trend.map(r=>Number(r.amount)))}"></i></div><b class="money">{{row.amount}} 元</b></div><p class="muted">金额由服务端以整数分聚合；图形比例仅用于显示。</p></section>
</template></main></div></template>
