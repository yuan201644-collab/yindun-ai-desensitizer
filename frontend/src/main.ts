import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './styles/animations.css'

import IndexPage from './pages/index/index.vue'
import TextPage from './pages/text/index.vue'
import CheckPage from './pages/check/index.vue'

const routes = [
  { path: '/', component: IndexPage },
  { path: '/text', component: TextPage },
  { path: '/check', component: CheckPage },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.mount('#app')
