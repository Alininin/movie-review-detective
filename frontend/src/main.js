import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Library from './views/Library.vue'
import Analyze from './views/Analyze.vue'
import SearchView from './views/SearchView.vue'
import Challenge from './views/Challenge.vue'
import Lab from './views/Lab.vue'
import './style.css'

// 使用 hash 路由：构建产物由 FastAPI 静态托管时不需要额外的服务端回退规则
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/library' },
    { path: '/library', component: Library, name: 'library' },
    { path: '/analyze', component: Analyze, name: 'analyze' },
    { path: '/search', component: SearchView, name: 'search' },
    { path: '/challenge', component: Challenge, name: 'challenge' },
    { path: '/lab', component: Lab, name: 'lab' },
  ],
})

createApp(App).use(router).mount('#app')
