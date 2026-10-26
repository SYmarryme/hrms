<script setup lang="ts">
import { useRoute } from 'vue-router';
import AppShell from './components/AppShell.vue';
const route=useRoute();
</script>
<template><router-view v-if="route.path==='/login'"/><AppShell v-else/></template>
