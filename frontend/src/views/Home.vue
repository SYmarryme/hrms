<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ApiError, me, logout, type Profile } from '../api';

const router = useRouter();
const profile = ref<Profile | null>(null);
const error = ref('');
const busy = ref(false);
async function load() {
  error.value = '';
  try { profile.value = await me(); }
  catch (failure) { error.value = failure instanceof ApiError ? failure.message : '资料加载失败'; }
}
async function signOut() {
  if (busy.value) return;
  busy.value = true;
  try { await logout(); await router.replace('/login'); }
  catch (failure) {
    // Local token is already gone. Do not claim server revocation succeeded.
    window.alert(failure instanceof ApiError && failure.status === 401 ? '会话已失效，请重新登录。' : '本地已退出，服务器撤销尚未确认；会话将受服务端期限限制。');
  } finally { busy.value = false; }
}
onMounted(load);
</script>

<template>
  <div class="workspace">
    <header><span class="brand">HRMS</span><span class="muted">员工管理系统</span><button class="secondary" :disabled="busy" @click="signOut">退出登录</button></header>
    <main><p class="eyebrow">工作空间</p><h1>系统主页</h1>
      <p v-if="!profile && !error" role="status">正在验证会话并加载当前账号…</p>
      <div v-if="error" class="card"><p class="error" role="alert">{{ error }}</p><button @click="load">重试</button></div>
      <template v-if="profile">
        <section class="card"><h2>你好，{{ profile.username }}</h2><p>你的账号已通过服务端会话验证。</p>
          <dl><dt>账号状态</dt><dd>{{ profile.status === 'ACTIVE' ? '正常' : profile.status }}</dd>
            <dt>当前有效角色</dt><dd>{{ profile.roles.join('、') || '尚未分配有效角色' }}</dd>
            <dt>会话固定到期时间（UTC）</dt><dd>{{ profile.session.expires_at }}</dd></dl></section>
        <section class="card"><h2>组织管理</h2><p>查询部门、查看层级与人数，由授权HR维护部门基础信息。</p>
          <router-link class="primary-link" to="/departments">进入部门管理</router-link>
          <div class="form-actions"><router-link class="primary-link" to="/positions">职位管理</router-link><router-link v-if="profile.roles.some(r=>['HR','MANAGER','EMPLOYEE'].includes(r))" class="primary-link" to="/employees">员工档案</router-link></div></section>
        <section v-if="profile.roles.some(r=>['HR','MANAGER','EMPLOYEE'].includes(r))" class="card"><h2>员工业务</h2><p>打卡、请假、本人薪资及授权范围的数据统计。</p><div class="module-links"><router-link to="/attendance">考勤管理</router-link><router-link to="/leaves">请假与审批</router-link><router-link to="/salaries">月度薪资</router-link><router-link to="/dashboard">数据看板</router-link></div></section>
        <section v-if="profile.roles.includes('ADMIN')" class="card"><h2>系统管理</h2><p>创建账号、绑定员工、角色授权、停用和密码重置。</p><router-link class="primary-link" to="/users">用户管理</router-link></section>
      </template>
    </main>
  </div>
</template>
