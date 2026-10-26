<script setup lang="ts">
import { computed } from 'vue';
import { workspace } from '../workspace';
import { visiblePages } from '../policy';
import { formatBeijing,rolesText } from '../presentation';
const profile=computed(()=>workspace.profile);
const entries=computed(()=>visiblePages(profile.value).filter(p=>p.path!=='/'));
</script>
<template><div class="business-page"><main><div class="section-heading"><div><h1>系统主页</h1><p class="muted">欢迎使用 HRMS，当前工作区按你的实际授权开放。</p></div></div>
<section v-if="profile" class="card welcome-panel"><div><p class="welcome-label">工作台</p><h2>你好，{{profile.employee_name||profile.username}}</h2><p>你的账号已通过服务端会话验证。</p></div><dl><dt>账号</dt><dd>{{profile.username}}</dd><dt>账号状态</dt><dd>{{profile.status==='ACTIVE'?'正常':'停用'}}</dd><dt>当前角色</dt><dd>{{rolesText(profile.roles)||'尚未分配有效角色'}}</dd><dt>固定到期时间（北京时间）</dt><dd>{{formatBeijing(profile.session.expires_at)}}</dd></dl></section>
<section class="card"><h2>业务入口</h2><p class="muted">进入已授权的功能页面；切换顶部标签可保留当前筛选和未提交内容。</p><div class="module-links"><router-link v-for="entry in entries" :key="entry.path" :to="entry.path">{{entry.label}}</router-link></div><p v-if="!entries.length" class="muted">暂无可用业务权限，请联系管理员。</p></section>
</main></div></template>
