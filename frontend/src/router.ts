import { createRouter, createWebHistory, type RouterHistory } from 'vue-router';
import { hasSession, setExpiredHandler, setPasswordRequiredHandler } from './api';
import Login from './views/Login.vue';
import Settings from './views/Settings.vue';
import Home from './views/Home.vue';
import Departments from './views/Departments.vue';
import Positions from './views/Positions.vue';
import Employees from './views/Employees.vue';
import Attendance from './views/Attendance.vue';
import Leaves from './views/Leaves.vue';
import Salaries from './views/Salaries.vue';
import Dashboard from './views/Dashboard.vue';
import Users from './views/Users.vue';
import { defineComponent,h } from 'vue';
import { canAccess } from './policy';
import { workspace,resetWorkspace,verifySession,openTab,requirePasswordChange } from './workspace';
import {modalCount} from './modal';
const Approvals=defineComponent({name:'Approvals',setup:()=>()=>h(Leaves,{approvalMode:true})});

export function makeRouter(history: RouterHistory = createWebHistory()) {
  const router = createRouter({ history, routes: [
    { path: '/login', component: Login },
    { path:'/settings',component:Settings,meta:{authenticated:true}},
    { path:'/password-required',component:defineComponent({render:()=>null}),meta:{authenticated:true}},
    { path: '/', component: Home, meta: { authenticated: true } },
    { path: '/departments', component: Departments, meta: { authenticated: true } },
    { path: '/positions', component: Positions, meta: { authenticated: true } },
    { path: '/employees', component: Employees, meta: { authenticated: true } },
    { path: '/employee-files', redirect: '/employees' },
    { path: '/attendance', component: Attendance, meta: { authenticated: true } },
    { path: '/leaves', component: Leaves, meta: { authenticated: true } },
    { path: '/approvals', component: Approvals, meta: { authenticated: true } },
    { path: '/salaries', component: Salaries, meta: { authenticated: true } },
    { path: '/dashboard', component: Dashboard, meta: { authenticated: true } },
    { path: '/users', component: Users, meta: { authenticated: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ] });
  router.beforeEach(async (to,from) => {
    if (to.meta.authenticated && !hasSession()) return '/login';
    if (to.path === '/login' && hasSession()) return '/';
    if(modalCount.value&&to.path!==from.path&&to.path!=='/login'&&hasSession()&&canAccess(from.path,workspace.profile))return false;
    if(to.meta.authenticated){if(!await verifySession())return hasSession()?false:'/login';if(workspace.profile?.must_change_password)return to.path==='/password-required'?undefined:'/password-required';if(to.path==='/password-required')return '/';if(!canAccess(to.path,workspace.profile))return '/';openTab(to.path);}
  });
  setExpiredHandler(() => {resetWorkspace();void router.replace('/login');});
  setPasswordRequiredHandler(()=>{requirePasswordChange();void router.replace('/password-required');});
  return router;
}
