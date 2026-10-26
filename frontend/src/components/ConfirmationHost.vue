<script setup lang="ts">
import {watch} from 'vue';
import Modal from './Modal.vue';
import {confirmation,finishConfirmation,acceptConfirmation} from '../modal';
import {workspace} from '../workspace';
watch(()=>workspace.epoch,()=>finishConfirmation(false));
</script>
<template><Modal v-if="confirmation.current" :title="confirmation.current.title" :track-changes="false" :busy="confirmation.busy" :error="confirmation.error" @close="finishConfirmation(false)">
 <p class="confirmation-message">{{confirmation.current.message}}</p>
 <template #footer><button type="button" class="secondary" :disabled="confirmation.busy" @click="finishConfirmation(false)">{{confirmation.current.cancelLabel||'取消'}}</button><button type="button" :class="{danger:confirmation.current.danger}" :disabled="confirmation.busy" @click="acceptConfirmation">{{confirmation.current.confirmLabel||'确认'}}</button></template>
</Modal></template>
