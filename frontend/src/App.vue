<script setup lang="ts">
import { useRoute } from 'vue-router';
import AppShell from './components/AppShell.vue';
import ForcedPasswordChange from './components/ForcedPasswordChange.vue';
import {workspace} from './workspace';
import ConfirmationHost from './components/ConfirmationHost.vue';
const route=useRoute();
</script>
<template><router-view v-if="route.path==='/login'"/><AppShell v-else/><ForcedPasswordChange v-if="workspace.profile?.must_change_password"/><ConfirmationHost/></template>
