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
      <svg class="login-art" viewBox="0 0 420 280" fill="none" aria-hidden="true"><defs><linearGradient id="identity-blue" x1="80" y1="40" x2="290" y2="245"><stop stop-color="#bcd6ff"/><stop offset="1" stop-color="#3b78ed"/></linearGradient></defs><ellipse cx="200" cy="239" rx="156" ry="26" fill="#cfe0fc"/><ellipse cx="200" cy="234" rx="118" ry="20" fill="#f8fbff"/><rect x="101" y="30" width="220" height="165" rx="14" fill="url(#identity-blue)" transform="rotate(8 101 30)"/><rect x="78" y="65" width="220" height="151" rx="14" fill="#e1edff"/><rect x="92" y="80" width="191" height="120" rx="9" fill="white"/><circle cx="135" cy="119" r="17" fill="#5b8ff1"/><path d="M109 169v-11a26 26 0 0 1 52 0v11" fill="#5b8ff1"/><path d="M184 111h74M184 132h74M184 153h49" stroke="#bed4fb" stroke-width="9" stroke-linecap="round"/><rect x="332" y="88" width="25" height="30" rx="6" fill="#c5dbff" transform="rotate(14 332 88)"/><rect x="43" y="157" width="24" height="27" rx="5" fill="#88b3fb" transform="rotate(-12 43 157)"/></svg></section>
    <form class="card login-card" @submit.prevent="submit">
      <h2>登录账号</h2><p class="muted">刷新页面或打开新标签页后需要重新登录。</p>
      <label for="username">账号</label><input id="username" v-model="username" required maxlength="64" autocomplete="username" :disabled="busy">
      <label for="password">密码</label><div class="password-control"><input id="password" v-model="password" :type="passwordVisible?'text':'password'" required maxlength="128" autocomplete="current-password" :disabled="busy"><button class="password-toggle" type="button" :disabled="busy" :aria-pressed="passwordVisible" :aria-label="passwordVisible?'隐藏密码':'显示密码'" @click="passwordVisible=!passwordVisible"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path v-if="!passwordVisible" d="m3 3 18 18"/></svg></button></div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button>
    </form>
  </main>
</template>
