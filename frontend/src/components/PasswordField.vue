<script setup lang="ts">
import {ref} from 'vue';
const props=withDefaults(defineProps<{modelValue:string;id:string;label:string;placeholder:string;current?:boolean;disabled?:boolean}>(),{current:false,disabled:false});
const emit=defineEmits<{'update:modelValue':[value:string]}>();const shown=ref(false);
</script>
<template><div class="password-row"><label :for="id">{{label}}：</label><div class="password-field-control"><input :id="id" :value="modelValue" :type="shown?'text':'password'" :placeholder="placeholder" required maxlength="128" :autocomplete="current?'current-password':'new-password'" :disabled="disabled" @input="emit('update:modelValue',($event.target as HTMLInputElement).value)"><button type="button" :disabled="disabled" :aria-label="(shown?'隐藏':'显示')+label" :aria-pressed="shown" @click="shown=!shown"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path v-if="!shown" d="m3 3 18 18"/></svg></button></div></div></template>
