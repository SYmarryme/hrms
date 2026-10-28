<script setup lang="ts">
import {ref,onDeactivated,onBeforeUnmount,useId} from 'vue';
import PasswordField from './PasswordField.vue';
import {changeOwnPassword,logout} from '../api';
import {passwordNotice} from '../password-notice';
const props=withDefaults(defineProps<{forced?:boolean}>(),{forced:false});const emit=defineEmits<{cancel:[];cleared:[]}>();
const current=ref(''),password=ref(''),confirmation=ref(''),busy=ref(false),error=ref(''),id=useId();
function clear(){current.value='';password.value='';confirmation.value='';error.value='';emit('cleared');}
async function submit(){if(busy.value)return;error.value='';if(password.value.length<12||password.value.length>128){error.value='新密码须为12至128个字符。';return;}if(password.value!==confirmation.value){error.value='两次输入的新密码不一致。';return;}if(password.value===current.value){error.value='新密码不能与当前密码相同。';return;}busy.value=true;try{passwordNotice.value='';await changeOwnPassword(current.value,password.value,confirmation.value);clear();}catch(failure){passwordNotice.value='';error.value=failure instanceof Error?failure.message:'密码修改未完成，请稍后重试。';}finally{busy.value=false;}}
async function cancel(){if(busy.value)return;clear();if(props.forced){try{await logout();}catch{/* Logout always clears the in-memory session. */}}else emit('cancel');}
onDeactivated(clear);onBeforeUnmount(clear);
</script>
<template><form class="password-change-form" data-dirty-scope="password" @submit.prevent="submit"><p v-if="error" class="error feedback" role="alert">{{error}}</p><fieldset :disabled="busy"><PasswordField :id="id+'-current'" v-model="current" label="当前密码" :placeholder="forced?'请输入当前临时密码':'请输入当前密码'" current :disabled="busy"/><PasswordField :id="id+'-new'" v-model="password" label="新密码" placeholder="请输入新密码" :disabled="busy"/><PasswordField :id="id+'-confirmation'" v-model="confirmation" label="确认新密码" placeholder="请再次输入新密码" :disabled="busy"/><p class="password-rule">新密码须为12至128个字符，不能与当前密码相同。</p><p v-if="forced" class="password-restriction">首次登录须先完成密码修改，其他业务操作暂不可用。</p><div class="password-actions"><button type="button" class="secondary" :disabled="busy" @click="cancel">{{forced?'退出登录':'取消'}}</button><button type="submit" :disabled="busy">{{busy?'正在保存…':'保存新密码'}}</button></div></fieldset></form></template>
