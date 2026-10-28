<script setup lang="ts">
import MetricCard from '../components/MetricCard.vue';
import BarChart from '../components/BarChart.vue';
import DonutChart from '../components/DonutChart.vue';
import LineChart from '../components/LineChart.vue';
import {useLatestRead} from '../data-sync';
import {useScopedRefresh} from '../scoped-refresh';
import {ref,computed} from 'vue';
import {courseApi,errorText} from '../course-api';
import {workspace} from '../workspace';
import {isHR} from '../policy';
interface Dashboard {employee_count:number;hired_this_month:number;terminated_this_month:number;departments:{id:string;name:string;count:number}[];grades:{name:string;count:number}[];leave_types:{name:string;count:number}[];attendance:Record<string,number>;salary_trend?:{month:string;amount:string}[]}
const result=ref<Dashboard|null>(null),month=ref(new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit'}).format(new Date())),busy=ref(false),error=ref('');
const hr=computed(()=>isHR(workspace.profile));
const attendanceLabels:Record<string,string>={expected_days:'应出勤人天',complete_days:'完整打卡',late_days:'迟到',early_days:'早退',missing_days:'漏卡'};
const leaveLabels:Record<string,string>={ANNUAL:'年假',SICK:'病假',PERSONAL:'事假',OTHER:'其他'};
const leaveTypes=computed(()=>result.value?.leave_types.map(row=>({...row,name:leaveLabels[row.name]||row.name}))||[]);
const listRead=useLatestRead();
async function load(strict=false){const selectedMonth=month.value;try{await listRead.run(selectedMonth,()=>courseApi<Dashboard>(`/dashboard?month=${encodeURIComponent(selectedMonth)}`),{start:()=>{busy.value=true;error.value='';},success:fresh=>{result.value=fresh;},failure:e=>{result.value=null;error.value=errorText(e);},finish:()=>{busy.value=false;}});}catch(e){if(strict===true)throw e;}}
const {scopeLocked,scopeFailure,retryScope,scopeStyle}=useScopedRefresh(()=>load(true),['dashboard']);
</script>
<template><div :style="scopeStyle" class="business-page dashboard-page"><p v-if="scopeLocked" class="verification" role="status">{{scopeFailure||'加载中…'}}<button v-if="scopeFailure" @click="retryScope">重试</button></p><main v-show="!scopeLocked"><h1>数据看板</h1><form class="search-row dashboard-query" @submit.prevent="load()"><label>统计月份<input v-model="month" type="month" required></label><button :disabled="busy">查询</button></form><p v-if="error" class="error feedback" role="alert">{{error}}</p><p v-if="busy" role="status">统计加载中…</p>
<template v-if="result&&!error&&!busy"><div class="metric-grid dashboard-metrics"><MetricCard label="授权范围在职人数" :value="result.employee_count" icon="people"/><MetricCard label="范围内本月入职" :value="result.hired_this_month" icon="plus" tone="green"/><MetricCard label="范围内本月离职" :value="result.terminated_this_month" icon="minus" tone="red"/></div>
<div class="dashboard-charts"><section class="card"><h2 class="chart-heading"><span class="chart-heading-icon" aria-hidden="true">▥</span>部门人数</h2><BarChart :items="result.departments" title="部门人数"/></section><section class="card"><h2 class="chart-heading"><span class="chart-heading-icon" aria-hidden="true">◉</span>职级比例</h2><DonutChart :items="result.grades"/></section></div>
<div :class="['dashboard-bottom',{'with-salary':hr&&result.salary_trend}]"><section class="card"><h2 class="chart-heading"><span class="chart-heading-icon" aria-hidden="true">▦</span>{{hr?'公司月度出勤':'月度出勤'}}</h2><dl class="attendance-metrics"><template v-for="(label,key) in attendanceLabels" :key="key"><dt>{{label}}</dt><dd>{{result.attendance[key]}} <small>人天</small></dd></template></dl></section><section class="card"><h2 class="chart-heading"><span class="chart-heading-icon" aria-hidden="true">▤</span>批准请假类型</h2><BarChart :items="leaveTypes" title="批准请假类型" unit="单" compact/></section><section v-if="hr&&result.salary_trend" class="card salary-chart"><h2 class="chart-heading"><span class="chart-heading-icon" aria-hidden="true">¥</span>近六个月应发总额</h2><LineChart :items="result.salary_trend"/></section></div>
</template></main></div></template>
