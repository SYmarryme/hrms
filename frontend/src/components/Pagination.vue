<script setup lang="ts">
withDefaults(defineProps<{page:number;pageSize:number;total:number;busy?:boolean;label?:string}>(),{busy:false,label:'分页'});
const emit=defineEmits<{page:[value:number];size:[value:number]}>();
</script>
<template><nav class="pagination" :aria-label="label"><span>共 {{total}} 条 · 第 {{page}} 页</span><label>每页条数<select aria-label="每页条数" :value="pageSize" :disabled="busy" @change="emit('size',Number(($event.target as HTMLSelectElement).value))"><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select></label><button class="secondary" :disabled="busy||page<=1" @click="emit('page',page-1)">上一页</button><button class="secondary" :disabled="busy||page*pageSize>=total" @click="emit('page',page+1)">下一页</button></nav></template>
