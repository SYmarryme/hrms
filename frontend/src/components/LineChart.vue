<script setup lang="ts">
import {computed,ref,useId} from 'vue';
import EmptyState from './EmptyState.vue';
import {orderedTrend,numericTicks,moneyLabel,type MonthPoint} from '../chart-data';
const props=defineProps<{items:MonthPoint[]}>(),active=ref<number|null>(null),gradientId=useId();
const data=computed(()=>{try{return {rows:orderedTrend(props.items),error:''};}catch{return {rows:[],error:'工资统计数据不完整，请重新查询。'};}});
const ticks=computed(()=>numericTicks(Math.max(0,...data.value.rows.map(row=>Number(row.amount))))),max=computed(()=>ticks.value.at(-1)||1);
const points=computed(()=>data.value.rows.map((row,i)=>({...row,x:55+(data.value.rows.length===1?205:i/(data.value.rows.length-1)*410),y:195-Number(row.amount)/max.value*165})));
const path=computed(()=>points.value.map((p,i)=>`${i?'L':'M'}${p.x},${p.y}`).join(' ')),area=computed(()=>points.value.length?`${path.value} L${points.value.at(-1)!.x},195 L${points.value[0].x},195 Z`:'');
const tickLabel=(value:number)=>new Intl.NumberFormat('zh-CN',{notation:value>=10000?'compact':'standard',maximumFractionDigits:2}).format(value);
</script>
<template><figure class="chart-frame"><p v-if="data.error" class="error" role="alert">{{data.error}}</p><EmptyState v-else-if="!points.length" text="暂无应发工资统计" compact/><template v-else><div class="chart-scroll line-scroll"><svg viewBox="0 0 480 240" role="group" aria-label="近六个月应发总额折线图"><defs><linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#1464f4" stop-opacity="0.17"/><stop offset="1" stop-color="#1464f4" stop-opacity="0.02"/></linearGradient></defs>
 <g v-for="tick in ticks" :key="tick"><line x1="55" x2="465" :y1="195-tick/max*165" :y2="195-tick/max*165" class="chart-grid-line"/><text x="46" :y="199-tick/max*165" text-anchor="end" class="chart-tick">{{tickLabel(tick)}}</text></g><text x="8" y="16" class="chart-tick">元</text><path :d="area" :fill="`url(#${gradientId})`"/><path :d="path" fill="none" stroke="#1464f4" stroke-width="2.5"/>
 <g v-for="(row,index) in points" :key="row.month" tabindex="0" role="img" :aria-label="`${row.month}：${moneyLabel(row.amount)}元`" @focus="active=index" @blur="active=null" @mouseenter="active=index" @mouseleave="active=null"><title>{{row.month}}：{{moneyLabel(row.amount)}}元</title><line :x1="row.x" :x2="row.x" y1="30" y2="195" class="chart-grid-line chart-vertical"/><circle :cx="row.x" :cy="row.y" r="4" fill="white" stroke="#1464f4" stroke-width="2"/><text :x="row.x" y="222" :text-anchor="index===0?'start':index===points.length-1?'end':'middle'" class="chart-tick">{{row.month}}</text></g>
 </svg></div><figcaption class="chart-readout" aria-live="polite">{{active!==null&&points[active]?`${points[active].month}：${moneyLabel(points[active].amount)} 元`:'鼠标悬停或使用键盘查看每月金额'}}</figcaption></template></figure></template>
