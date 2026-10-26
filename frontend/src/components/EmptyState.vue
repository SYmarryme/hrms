<script setup lang="ts">
withDefaults(defineProps<{text:string;hint?:string;compact?:boolean}>(),{hint:'请调整查询条件后重试。',compact:false});
</script>
<template><div :class="['empty-state',{compact}]" role="status"><svg aria-hidden="true" viewBox="0 0 80 70" fill="none"><path d="M17 29 25 15h30l8 14v26H17Z"/><path d="M17 30h15l4 7h9l4-7h14M32 7l-3-5m12 5V1m10 6 3-5"/><path d="M20 55h40"/></svg><p>{{text}}</p><small v-if="hint">{{hint}}</small></div></template>
