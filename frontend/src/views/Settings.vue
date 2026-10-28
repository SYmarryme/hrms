<script setup lang="ts">
import {useScopedRefresh} from '../scoped-refresh';
import {verifySession} from '../workspace';
import {computed,ref,onDeactivated} from 'vue';
import PasswordChangeForm from '../components/PasswordChangeForm.vue';
import {workspace,markDirty} from '../workspace';
import {rolesText} from '../presentation';
const section=ref<'profile'|'security'>('profile'),profile=computed(()=>workspace.profile);
function cleared(){markDirty('/settings',false,'password');}
onDeactivated(()=>{cleared();section.value='profile';});
const {scopeLocked,scopeFailure,retryScope,scopeStyle}=useScopedRefresh(async()=>{if(!await verifySession(false))throw new Error('暂时无法确认账号信息');},['identity']);
</script>
<template><div :style="scopeStyle" class="business-page settings-page"><p v-if="scopeLocked" class="verification" role="status">{{scopeFailure||'加载中…'}}<button v-if="scopeFailure" @click="retryScope">重试</button></p><main v-show="!scopeLocked"><h1>个人设置</h1><p class="muted">查看个人账户信息，管理账号安全。</p><section class="card settings-card"><nav aria-label="个人设置分类"><button :class="{active:section==='profile'}" :aria-current="section==='profile'?'page':undefined" @click="section='profile'">个人信息</button><button :class="{active:section==='security'}" :aria-current="section==='security'?'page':undefined" @click="section='security'">账号安全</button></nav><div class="settings-panel"><template v-if="section==='profile'"><h2>个人信息</h2><p class="muted">以下信息来自当前登录账号和已绑定的员工档案。</p><dl v-if="profile" class="personal-fields"><dt>用户名</dt><dd>{{profile.username}}</dd><dt>当前角色</dt><dd>{{rolesText(profile.roles)||'未分配角色'}}</dd><dt>账号状态</dt><dd>{{profile.status==='ACTIVE'?'正常':'停用'}}</dd><dt>绑定员工</dt><dd>{{profile.employee_name||'未绑定员工'}}</dd><template v-if="profile.employee_no"><dt>员工工号</dt><dd>{{profile.employee_no}}</dd></template></dl><p class="settings-hint">需要修改密码？请点击左侧“账号安全”。</p></template><template v-else><h2>账号安全</h2><p class="muted">修改您的登录密码。修改成功后，需要使用新密码重新登录。</p><h3>修改密码</h3><PasswordChangeForm @cleared="cleared" @cancel="section='profile'"/></template></div></section></main></div></template>
