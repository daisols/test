import { createRouter, createWebHistory } from 'vue-router';
const Dashboard = () => import('../views/Dashboard.vue');
const Generate = () => import('../views/Generate.vue');

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/generate', name: 'generate', component: Generate },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
});

router.afterEach(() => {
  document.title = 'FieldMoist | Daily Soil Moisture Products';
});

export default router;
