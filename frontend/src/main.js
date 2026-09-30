import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import 'element-plus/dist/index.css'
import '@/assets/styles.css'

// 创建 Vue 应用实例
const app = createApp(App)

// 创建 Pinia 状态管理实例，启用持久化插件
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

// 注册 Element Plus 图标组件
// 全局注册所有图标，方便在各组件中直接使用
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 安装插件
app.use(pinia)
app.use(router)
app.use(ElementPlus, {
  locale: zhCn, // 使用中文语言包
})

// 挂载应用到 #app
app.mount('#app')