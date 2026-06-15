import { createRouter, createWebHashHistory } from 'vue-router'
import PrintStation from '@/views/PrintStation.vue'
import StatusView from '@/views/StatusView.vue'
import HistoryView from '@/views/HistoryView.vue'

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
  {
    path: '/history',
    name: 'history',
    component: HistoryView,
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
