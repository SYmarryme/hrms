<script setup lang="ts">
import { computed } from 'vue';
import { workspace } from '../workspace';
import { visiblePages } from '../policy';
import { formatBeijing,rolesText } from '../presentation';
const profile=computed(()=>workspace.profile);
const entries=computed(()=>visiblePages(profile.value).filter(p=>p.path!=='/'));
</script>
<template><div class="business-page"><main><div class="section-heading"><div><h1>系统主页</h1><p class="muted">欢迎使用 HRMS，请从导航进入业务页面。</p></div></div>
<section v-if="profile" class="card welcome-panel"><div><p class="welcome-label">工作台</p><h2>你好，{{profile.employee_name||profile.username}}</h2><p>欢迎回来。</p></div><dl><dt>账号</dt><dd>{{profile.username}}</dd><dt>账号状态</dt><dd>{{profile.status==='ACTIVE'?'正常':'停用'}}</dd><dt>当前角色</dt><dd>{{rolesText(profile.roles)||'尚未分配有效角色'}}</dd><dt>登录有效期至</dt><dd>{{formatBeijing(profile.session.expires_at)}}</dd></dl></section>
<section class="card"><h2>业务入口</h2><p class="muted">从业务入口开始工作，切换标签可保留当前操作。</p><div class="module-links"><router-link v-for="entry in entries" :key="entry.path" :to="entry.path">{{entry.label}}</router-link></div><p v-if="!entries.length" class="muted">暂无可用业务权限，请联系管理员。</p></section>
</main></div></template>
