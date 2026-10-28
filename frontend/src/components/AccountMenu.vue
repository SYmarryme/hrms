<script setup lang="ts">
import {ref,watch,onBeforeUnmount} from 'vue';
import {useRoute} from 'vue-router';
import {rolesText} from '../presentation';
import type {Profile} from '../api';
const props=defineProps<{profile:Profile|null}>(),emit=defineEmits<{settings:[];logout:[]}>(),route=useRoute();
const trigger=ref<HTMLButtonElement|null>(null),panel=ref<HTMLElement|null>(null),open=ref(false),position=ref({top:'0px',right:'0px'});
function close(restore=false){panel.value?.hidePopover();open.value=false;if(restore)trigger.value?.focus({preventScroll:true});}
function show(last=false){if(open.value){close(true);return;}const box=trigger.value!.getBoundingClientRect();position.value={top:box.bottom+8+'px',right:Math.max(8,innerWidth-box.right)+'px'};panel.value?.showPopover();open.value=true;const items=panel.value?.querySelectorAll<HTMLButtonElement>('button');(last?items?.[1]:items?.[0])?.focus({preventScroll:true});}
function choose(action:'settings'|'logout'){close();if(action==='settings')emit('settings');else emit('logout');}
function keys(event:KeyboardEvent){const items=[...panel.value!.querySelectorAll<HTMLButtonElement>('button')];const index=items.indexOf(document.activeElement as HTMLButtonElement);if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?1:(index+(event.key==='ArrowUp'?-1:1)+2)%2;items[next].focus();}if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close(true);}}
watch(()=>route.path,()=>close());onBeforeUnmount(()=>close());
</script>
<template><div class="account"><button ref="trigger" type="button" class="account-trigger" aria-label="账号菜单" aria-haspopup="menu" :aria-expanded="open" @click="show()" @keydown.down.prevent="show()" @keydown.up.prevent="show(true)"><span class="avatar">{{profile?.username.slice(0,1).toUpperCase()}}</span><span class="account-label">{{profile?.username}}<small>{{profile?rolesText(profile.roles):''}}</small></span><span class="account-chevron" aria-hidden="true">⌄</span></button><div ref="panel" popover="auto" role="menu" aria-label="账号操作" class="account-dropdown" :style="position" @toggle="open=($event as ToggleEvent).newState==='open'" @keydown="keys"><button type="button" role="menuitem" @click="choose('settings')">设置</button><button type="button" role="menuitem" class="logout-item" @click="choose('logout')">退出登录</button></div></div></template>
