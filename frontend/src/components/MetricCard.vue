<script setup lang="ts">
withDefaults(defineProps<{label:string;value:number;icon?:string;tone?:string}>(),{icon:'people',tone:'blue'});
const paths:Record<string,string>={people:'M8 8a4 4 0 1 0 8 0 4 4 0 0 0-8 0M4 22v-3a8 8 0 0 1 16 0v3',plus:'M12 5v14M5 12h14',minus:'M5 12h14',calendar:'M4 5h16v17H4zM8 2v6M16 2v6M4 10h16',clock:'M12 7v6l4 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',check:'m6 12 4 4 8-9',cross:'m6 6 12 12M18 6 6 18'};
</script>
<template><section :class="['metric-card',tone]"><span class="metric-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[icon]||paths.people"/></svg></span><div><span class="metric-label">{{label}}</span><strong>{{value}}</strong></div></section></template>
