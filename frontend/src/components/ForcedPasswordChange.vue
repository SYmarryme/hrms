<script setup lang="ts">
import Modal from './Modal.vue';
import PasswordChangeForm from './PasswordChangeForm.vue';
</script>
<template><Modal title="首次登录 · 请修改密码" :dismissible="false" :track-changes="false" wide><div class="forced-password"><p class="muted">当前账号使用的是管理员分配的临时密码。为保护账号安全，请设置仅由您掌握的新密码。完成后需要重新登录。</p><PasswordChangeForm forced/></div></Modal></template>
