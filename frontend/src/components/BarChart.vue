<script setup lang="ts">
import {computed,ref} from 'vue';
import EmptyState from './EmptyState.vue';
import {integerTicks,labelLines,type CountPoint} from '../chart-data';
const props=withDefaults(defineProps<{items:CountPoint[];title:string;unit?:string;compact?:boolean}>(),{unit:'人',compact:false});
const active=ref<number|null>(null),left=computed(()=>props.compact?68:175),width=computed(()=>props.compact?360:640),plot=computed(()=>width.value-left.value-48);
const valid=computed(()=>props.items.every(row=>Number.isSafeInteger(row.count)&&row.count>=0));
const ticks=computed(()=>integerTicks(Math.max(0,...props.items.map(row=>row.count)))),max=computed(()=>ticks.value.at(-1)||1);
const rows=computed(()=>{let y=12;return props.items.map(row=>{const lines=labelLines(row.name,props.compact?4:11),height=Math.max(props.compact?32:40,lines.length*17+10),center=y+height/2;const entry={...row,lines,y,center,height};y+=height;return entry;});});
const bottom=computed(()=>rows.value.reduce((sum,row)=>sum+row.height,12)),height=computed(()=>bottom.value+35);
</script>
<template><figure class="chart-frame"><p v-if="!valid" class="error" role="alert">统计数据暂不可用，请重新查询。</p><EmptyState v-else-if="!items.length" :text="'暂无'+title+'数据'" compact/><template v-else><div :class="['chart-scroll',{'chart-compact':compact}]"><svg :viewBox="`0 0 ${width} ${height}`" role="group" :aria-label="title+'，横轴为'+unit">
 <g v-for="tick in ticks" :key="tick"><line :x1="left+tick/max*plot" :x2="left+tick/max*plot" y1="8" :y2="bottom" class="chart-grid-line"/><text :x="left+tick/max*plot" :y="bottom+21" text-anchor="middle" class="chart-tick">{{tick}}</text></g>
 <line :x1="left" :x2="left+plot" :y1="bottom" :y2="bottom" class="chart-axis"/>
 <g v-for="(row,index) in rows" :key="row.id||row.name" tabindex="0" role="img" :aria-label="`${row.name}：${row.count}${unit}`" @focus="active=index" @blur="active=null" @mouseenter="active=index" @mouseleave="active=null"><title>{{row.name}}：{{row.count}}{{unit}}</title><text :x="left-12" :y="row.center-(row.lines.length-1)*8.5+4" text-anchor="end" class="chart-label"><tspan v-for="(line,i) in row.lines" :key="i" :x="left-12" :dy="i?17:0">{{line}}</tspan></text><rect :x="left" :y="row.center-9" :width="plot" height="18" rx="3" class="chart-bar-track"/><rect :x="left" :y="row.center-9" :width="row.count/max*plot" height="18" rx="3" class="chart-bar"/><text :x="left+row.count/max*plot+8" :y="row.center+4" class="chart-value">{{row.count}}</text></g>
 </svg></div><figcaption class="chart-readout" aria-live="polite">{{active!==null&&items[active]?`${items[active].name}：${items[active].count}${unit}`:`单位：${unit}`}}</figcaption></template></figure></template>
