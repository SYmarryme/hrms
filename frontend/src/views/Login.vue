<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ApiError, login, me, logout } from '../api';

const router = useRouter();
const username = ref('');
const password = ref('');
const passwordVisible=ref(false);
const error = ref('');
const busy = ref(false);
async function submit() {
  if (busy.value) return;
  busy.value = true; error.value = '';
  try {
    await login(username.value.trim(), password.value);
    await me(); // The server, not the route guard, decides whether this session is valid.
    await router.replace('/');
  } catch (failure) {
    error.value = failure instanceof ApiError ? failure.message : '登录未完成，请重试';
    // Release any issued token if profile validation did not complete.
    try { await logout(); } catch { /* The original safe error remains visible. */ }
  } finally { password.value = ''; busy.value = false; }
}
</script>

<template>
  <main class="login-shell">
    <section class="login-intro"><span class="brand">HRMS</span><h1>企业员工管理系统</h1>
      <p>使用管理员分配的账号，进入你的工作空间。</p><p class="muted">账号由受控管理流程建立，系统不开放注册。</p></section>
    <form class="card login-card" @submit.prevent="submit">
      <h2>登录账号</h2><p class="muted">刷新页面或打开新标签页后需要重新登录。</p>
      <label for="username">账号</label><input id="username" v-model="username" required maxlength="64" autocomplete="username" :disabled="busy">
      <label for="password">密码</label><div class="password-control"><input id="password" v-model="password" :type="passwordVisible?'text':'password'" required maxlength="128" autocomplete="current-password" :disabled="busy"><button class="password-toggle" type="button" :disabled="busy" :aria-pressed="passwordVisible" :aria-label="passwordVisible?'隐藏密码':'显示密码'" @click="passwordVisible=!passwordVisible">{{passwordVisible?'隐藏':'显示'}}</button></div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button>
    </form>
  </main>
</template>
