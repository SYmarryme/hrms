<script setup lang="ts">
defineProps<{path:string}>();
const shapes:Record<string,string[]>={
 '/':['M3 10 12 3l9 7','M5 9v12h5v-7h4v7h5V9'],
 '/departments':['M9 3h6v5H9zM3 16h6v5H3zM15 16h6v5h-6z','M12 8v4M6 16v-4h12v4'],
 '/positions':['M4 7h16v14H4z','M8 7V3h8v4M4 12h16M10 12v3h4v-3'],
 '/employees':['M8 8a4 4 0 1 0 8 0 4 4 0 0 0-8 0','M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2'],
 '/employee-files':['M4 3h10l6 6v12H4z','M14 3v6h6M8 14h8M8 18h6'],
 '/attendance':['M5 5h14v16H5zM8 2v6M16 2v6M5 10h14','m9 15 2 2 4-4'],
 '/leaves':['M6 3h12v18H6zM9 7h6M9 11h6M9 15h3'],
 '/approvals':['M4 3h16v18H4z','m8 12 3 3 5-6'],
 '/salaries':['M12 3C2 3 2 9 12 9s10-6 0-6','M4 6v6c0 4 16 4 16 0V6M4 12v6c0 4 16 4 16 0v-6'],
 '/dashboard':['M4 3v18h17M8 17v-5M13 17V7M18 17v-8'],
 '/users':['M5 8a3 3 0 1 0 6 0 3 3 0 0 0-6 0M2 21v-2a6 6 0 0 1 12 0v2','M17 4v6M14 7h6M17 14v7M14 17h6'],
};
</script>
<template><svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-for="(d,index) in shapes[path]||shapes['/']" :key="index" :d="d"/></svg></template>
