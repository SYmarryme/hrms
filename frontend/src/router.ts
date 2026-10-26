import { createRouter, createWebHistory, type RouterHistory } from 'vue-router';
import { hasSession, setExpiredHandler } from './api';
import Login from './views/Login.vue';
import Home from './views/Home.vue';
import Departments from './views/Departments.vue';
import Positions from './views/Positions.vue';
import Employees from './views/Employees.vue';
import Attendance from './views/Attendance.vue';
import Leaves from './views/Leaves.vue';
import Salaries from './views/Salaries.vue';
import Dashboard from './views/Dashboard.vue';
import Users from './views/Users.vue';

export function makeRouter(history: RouterHistory = createWebHistory()) {
  const router = createRouter({ history, routes: [
    { path: '/login', component: Login },
    { path: '/', component: Home, meta: { authenticated: true } },
    { path: '/departments', component: Departments, meta: { authenticated: true } },
    { path: '/positions', component: Positions, meta: { authenticated: true } },
    { path: '/employees', component: Employees, meta: { authenticated: true } },
    { path: '/attendance', component: Attendance, meta: { authenticated: true } },
    { path: '/leaves', component: Leaves, meta: { authenticated: true } },
    { path: '/salaries', component: Salaries, meta: { authenticated: true } },
    { path: '/dashboard', component: Dashboard, meta: { authenticated: true } },
    { path: '/users', component: Users, meta: { authenticated: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ] });
  router.beforeEach(to => {
    if (to.meta.authenticated && !hasSession()) return '/login';
    if (to.path === '/login' && hasSession()) return '/';
  });
  setExpiredHandler(() => { void router.replace('/login'); });
  return router;
}
