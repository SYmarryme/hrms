<script setup lang="ts">
import { computed,onMounted,onBeforeUnmount } from 'vue';
import { useRoute,useRouter } from 'vue-router';
import { logout } from '../api';
import { visiblePages,allPages,cacheNames,canAccess } from '../policy';
import { workspace,verifySession,closeTab,markDirty,openTab } from '../workspace';
import { rolesText } from '../presentation';
import NavIcon from './NavIcon.vue';
import AccountMenu from './AccountMenu.vue';
const route=useRoute(),router=useRouter();
const menu=computed(()=>visiblePages(workspace.profile));
const groups=computed(()=>[...new Set(menu.value.map(p=>p.group).filter(Boolean))]);
const current=computed(()=>allPages.find(p=>p.path===route.path));
const included=computed(()=>workspace.tabs.map(t=>cacheNames[t.path]).filter(Boolean));
async function close(path:string){const index=workspace.tabs.findIndex(t=>t.path===path);const next=workspace.tabs[index-1]?.path||'/';
 if(closeTab(path,()=>window.confirm('此页面有未保存修改，确定关闭并放弃吗？'))&&route.path===path)await router.push(next);}
function dirty(event:Event){const target=event.target as HTMLElement;
 const form=target.closest('form');if(form&&!form.classList.contains('search-row'))markDirty(route.path,true,form.dataset.dirtyScope||'editor');
 if(target.matches('input[type=file]'))markDirty(route.path,true,'file');}
function cleared(event:MouseEvent){const button=(event.target as HTMLElement).closest<HTMLElement>('[data-clear-dirty]');if(button)markDirty(route.path,false,button.dataset.clearDirty||'editor');}
async function recheck(){if(!document.hidden){await verifySession();if(workspace.profile){if(workspace.profile.must_change_password){await router.replace('/password-required');return;}if(!canAccess(route.path,workspace.profile))await router.replace('/');else openTab(route.path);}}}
function visibility(){if(document.hidden)workspace.cover=true;else void recheck();}
function unload(event:BeforeUnloadEvent){if(workspace.tabs.some(t=>t.dirty)){event.preventDefault();event.returnValue='';}}
let timer:ReturnType<typeof setInterval>;
onMounted(()=>{timer=setInterval(async()=>{if(!document.hidden){await verifySession(false);if(workspace.profile){if(workspace.profile.must_change_password){await router.replace('/password-required');return;}if(!canAccess(route.path,workspace.profile))await router.replace('/');else openTab(route.path);}}},5000);
 window.addEventListener('focus',recheck);document.addEventListener('visibilitychange',visibility);window.addEventListener('beforeunload',unload);});
onBeforeUnmount(()=>{clearInterval(timer);window.removeEventListener('focus',recheck);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('beforeunload',unload);});
async function signOut(){try{await logout();}catch{window.alert('已退出当前页面，暂时无法确认账号是否已完全退出，请稍后重新登录。');}}
</script>
<template><div :class="['app-frame',{'nav-collapsed':workspace.collapsed}]">
 <aside class="sidebar" aria-label="业务导航"><div class="shell-brand"><span class="brand-mark">H</span><span v-if="!workspace.collapsed">HRMS <small>员工管理系统</small></span></div>
  <nav aria-label="业务菜单"><template v-if="workspace.collapsed"><router-link v-for="(p,index) in menu" :key="p.path" :to="p.path" :title="p.label" :aria-label="p.label" :class="['nav-leaf','collapsed-leaf',{selected:route.path===p.path,'group-start':index>0&&p.group!==menu[index-1]?.group}]" :aria-current="route.path===p.path?'page':undefined"><NavIcon :path="p.path"/><span class="sr-only">{{p.label}}</span></router-link></template><template v-else><router-link v-for="p in menu.filter(x=>!x.group)" :key="p.path" :to="p.path" :aria-label="p.label" :class="['nav-leaf',{selected:route.path===p.path}]" :aria-current="route.path===p.path?'page':undefined"><span aria-hidden="true">▦</span><span>{{p.label}}</span></router-link>
   <details v-for="group in groups" :key="group" open><summary>{{group}}</summary><router-link v-for="p in menu.filter(x=>x.group===group)" :key="p.path" :to="p.path" :title="p.label" :aria-label="p.label" :class="['nav-leaf',{selected:route.path===p.path}]" :aria-current="route.path===p.path?'page':undefined"><span class="nav-dot" aria-hidden="true"></span><span>{{p.label}}</span></router-link></details>
  </template></nav></aside>
 <div class="shell-body"><header class="shell-top"><button class="collapse-button" :aria-expanded="!workspace.collapsed" aria-label="折叠业务导航" @click="workspace.collapsed=!workspace.collapsed">☰</button><span class="shell-caption">企业员工管理系统</span><AccountMenu :profile="workspace.profile" @settings="router.push('/settings')" @logout="signOut"/></header>
 <nav class="tab-strip" aria-label="已打开的页面"><div v-for="tab in workspace.tabs" :key="tab.path" :class="['page-tab',{active:route.path===tab.path}]"><router-link :to="tab.path" :aria-current="route.path===tab.path?'page':undefined">{{tab.label}}<span v-if="tab.dirty" aria-label="未保存修改"> ·</span></router-link><button v-if="tab.path!=='/'" :aria-label="`关闭${tab.label}标签`" @click="close(tab.path)">×</button></div></nav>
 <div class="workspace-content"><nav class="breadcrumb" aria-label="面包屑"><router-link to="/">首页</router-link><span v-if="current?.group">/ {{current.group}}</span><span>/ {{current?.label||'工作空间'}}</span></nav>
  <div v-if="workspace.cover" class="verification workspace-verification" role="status">{{workspace.connectionError||'正在确认访问权限…'}}<button v-if="workspace.connectionError" @click="recheck">重试</button></div>
  <div v-if="workspace.profile&&!workspace.profile.must_change_password" :style="{visibility:workspace.cover?'hidden':undefined}" :inert="workspace.cover" :aria-hidden="workspace.cover||undefined" @input="dirty" @change="dirty" @click="cleared"><router-view v-slot="{Component,route:pageRoute}"><keep-alive :include="included" :key="workspace.epoch"><component :is="Component" :key="pageRoute.path"/></keep-alive></router-view></div>
 <main v-if="workspace.profile?.must_change_password" class="restricted-background" aria-hidden="true"><h1>系统主页</h1><section class="card"><p>请先完成密码修改。</p></section></main></div></div></div></template>
