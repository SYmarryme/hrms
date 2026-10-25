import { createRouter, createWebHistory, type RouterHistory } from 'vue-router';
import { hasSession, setExpiredHandler } from './api';
import Login from './views/Login.vue';
import Home from './views/Home.vue';
import Departments from './views/Departments.vue';

export function makeRouter(history: RouterHistory = createWebHistory()) {
  const router = createRouter({ history, routes: [
    { path: '/login', component: Login },
    { path: '/', component: Home, meta: { authenticated: true } },
    { path: '/departments', component: Departments, meta: { authenticated: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ] });
  router.beforeEach(to => {
    if (to.meta.authenticated && !hasSession()) return '/login';
    if (to.path === '/login' && hasSession()) return '/';
  });
  setExpiredHandler(() => { void router.replace('/login'); });
  return router;
}
