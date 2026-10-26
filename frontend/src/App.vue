<script setup lang="ts">
import { useRoute } from 'vue-router';
import AppShell from './components/AppShell.vue';
import ConfirmationHost from './components/ConfirmationHost.vue';
const route=useRoute();
</script>
<template><router-view v-if="route.path==='/login'"/><AppShell v-else/><ConfirmationHost/></template>
