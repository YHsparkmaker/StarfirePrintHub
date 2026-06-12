import { createRouter, createWebHashHistory } from 'vue-router'
import PrintStation from '@/views/PrintStation.vue'
import StatusView from '@/views/StatusView.vue'

const routes = [
  {
    path: '/',
    name: 'print',
    component: PrintStation,
  },
  {
    path: '/status/:jobId',
    name: 'status',
    component: StatusView,
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
