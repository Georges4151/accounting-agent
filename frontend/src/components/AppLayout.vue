<template>
  <!-- 主布局：侧边栏 + 顶栏 + 内容区 -->
  <el-container class="app-layout">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="app-aside" :class="{ 'mobile-open': isMobileOpen }">
      <!-- Logo 区域 -->
      <div class="logo-area" @click="router.push('/dashboard')">
        <el-icon :size="28" color="#409eff"><Money /></el-icon>
        <span v-show="!isCollapse" class="logo-text">财务智能助手</span>
      </div>

      <!-- 导航菜单 -->
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        class="side-menu"
      >
        <!-- 工作台 -->
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <template #title>工作台</template>
        </el-menu-item>

        <!-- AI 助手 -->
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>AI 助手</template>
        </el-menu-item>

        <!-- 凭证管理 -->
        <el-sub-menu index="voucher">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>凭证管理</span>
          </template>
          <el-menu-item index="/voucher/list">凭证列表</el-menu-item>
          <el-menu-item index="/voucher/create">录入凭证</el-menu-item>
          <el-menu-item index="/voucher/templates">凭证模板</el-menu-item>
        </el-sub-menu>

        <!-- 预算管理 -->
        <el-sub-menu index="budget">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>预算管理</span>
          </template>
          <el-menu-item index="/finance/budget">预算列表</el-menu-item>
          <el-menu-item index="/finance/budget/summary">预算汇总</el-menu-item>
        </el-sub-menu>

        <!-- 报表中心 -->
        <el-sub-menu index="report">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>报表中心</span>
          </template>
          <el-menu-item index="/report/balance-sheet">资产负债表</el-menu-item>
          <el-menu-item index="/report/income-statement">利润表</el-menu-item>
          <el-menu-item index="/report/cash-flow">现金流量表</el-menu-item>
          <el-menu-item index="/report/account-ledger">科目余额表</el-menu-item>
          <el-menu-item index="/report/trial-balance">试算平衡表</el-menu-item>
          <el-menu-item index="/report/general-ledger">总账</el-menu-item>
          <el-menu-item index="/report/subsidiary-ledger">明细账</el-menu-item>
          <el-menu-item index="/report/journal">日记账</el-menu-item>
        </el-sub-menu>

        <!-- 发票管理 -->
        <el-menu-item index="/invoice">
          <el-icon><Tickets /></el-icon>
          <template #title>发票管理</template>
        </el-menu-item>

        <!-- 税务管理 -->
        <el-sub-menu index="tax">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>税务管理</span>
          </template>
          <el-menu-item index="/finance/tax">税务申报</el-menu-item>
          <el-menu-item index="/finance/tax/summary">税务汇总</el-menu-item>
          <el-menu-item index="/finance/tax/analysis">税负分析</el-menu-item>
        </el-sub-menu>

        <!-- 工具 -->
        <el-sub-menu index="tools">
          <template #title>
            <el-icon><Tools /></el-icon>
            <span>工具</span>
          </template>
          <el-menu-item index="/tools/import-export">数据导入导出</el-menu-item>
          <el-menu-item index="/tools/import-voucher">导入凭证</el-menu-item>
          <el-menu-item index="/tools/bank-reconciliation">银行对账</el-menu-item>
        </el-sub-menu>

        <!-- 往来管理 -->
        <el-sub-menu index="finance">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>往来管理</span>
          </template>
          <el-menu-item index="/finance/reconciliation">应收应付核销</el-menu-item>
          <el-menu-item index="/finance/aging">账龄分析</el-menu-item>
          <el-menu-item index="/finance/statement">对账单</el-menu-item>
        </el-sub-menu>

        <!-- 固定资产 -->
        <el-menu-item index="/fixed-asset">
          <el-icon><OfficeBuilding /></el-icon>
          <span>固定资产</span>
        </el-menu-item>

        <!-- 系统设置 -->
        <el-sub-menu index="settings">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item index="/settings/api-keys">API Key 管理</el-menu-item>
          <el-menu-item index="/settings/model">模型配置</el-menu-item>
          <el-menu-item index="/knowledge">知识库管理</el-menu-item>
          <el-menu-item
            v-if="authStore.hasPermission('admin')"
            index="/settings/users"
          >
            用户管理
          </el-menu-item>
          <el-menu-item
            v-if="authStore.hasPermission('admin')"
            index="/settings/books"
          >
            账套管理
          </el-menu-item>
          <el-menu-item
            v-if="authStore.hasPermission('accountant')"
            index="/settings/notifications"
          >
            通知管理
          </el-menu-item>
          <el-menu-item
            v-if="authStore.hasPermission('admin')"
            index="/settings/opening-balance"
          >
            期初余额
          </el-menu-item>
          <el-menu-item index="/settings/sessions">
            会话管理
          </el-menu-item>
          <el-menu-item
            v-if="authStore.hasPermission('admin') || authStore.hasPermission('accountant')"
            index="/settings/period-close"
          >
            会计期间
          </el-menu-item>
          <el-menu-item
            v-if="authStore.hasPermission('admin')"
            index="/settings/backup"
          >
            数据备份
          </el-menu-item>
          <el-menu-item index="/settings/currencies">
            币种管理
          </el-menu-item>
          <el-menu-item index="/settings/exchange-rates">
            汇率管理
          </el-menu-item>
        </el-sub-menu>

        <!-- 工资管理 -->
        <el-sub-menu index="payroll">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>工资管理</span>
          </template>
          <el-menu-item index="/finance/salary-items">工资项目</el-menu-item>
          <el-menu-item index="/finance/salary">工资表</el-menu-item>
        </el-sub-menu>

        <!-- 审计日志（仅 reviewer 和 admin 可见） -->
        <el-menu-item
          v-if="authStore.hasPermission('admin') || authStore.hasPermission('reviewer')"
          index="/audit"
        >
          <el-icon><Warning /></el-icon>
          <template #title>审计日志</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 移动端遮罩 -->
    <div v-if="isMobileOpen" class="mobile-overlay" @click="isMobileOpen = false"></div>

    <!-- 右侧区域 -->
    <el-container>
      <!-- 顶栏 -->
      <el-header class="app-header">
        <div class="header-left">
          <!-- 折叠按钮 -->
          <el-icon
            class="collapse-btn"
            :size="20"
            @click="isCollapse = !isCollapse"
          >
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>

          <!-- 移动端菜单按钮 -->
          <el-icon
            class="mobile-menu-btn"
            :size="20"
            @click="isMobileOpen = !isMobileOpen"
          >
            <Menu />
          </el-icon>

          <!-- 面包屑导航 -->
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <!-- 模型选择器 -->
          <ModelSelector />

          <!-- 账套切换器 -->
          <BookSwitcher />

          <!-- 通知铃铛 -->
          <el-popover
            :visible="notificationVisible"
            placement="bottom-end"
            :width="360"
            trigger="click"
            :teleported="true"
            @show="loadNotifications"
            @hide="notificationVisible = false"
          >
            <template #reference>
              <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99" class="notification-badge">
                <el-icon
                  :size="20"
                  class="notification-bell"
                  @click="notificationVisible = !notificationVisible"
                >
                  <Bell />
                </el-icon>
              </el-badge>
            </template>

            <div class="notification-popover">
              <div class="notification-header">
                <span class="notification-title">通知</span>
                <el-button
                  v-if="unreadCount > 0"
                  type="primary"
                  link
                  size="small"
                  @click="handleMarkAllAsRead"
                >
                  全部已读
                </el-button>
              </div>
              <div class="notification-list" v-loading="notificationLoading">
                <template v-if="notifications.length > 0">
                  <div
                    v-for="item in notifications"
                    :key="item.id"
                    class="notification-item"
                    :class="{ 'is-unread': !item.is_read }"
                    @click="handleNotificationClick(item)"
                  >
                    <div class="notification-item-header">
                      <el-tag
                        :type="getNotificationTagType(item.type)"
                        size="small"
                        effect="plain"
                      >
                        {{ getNotificationTypeLabel(item.type) }}
                      </el-tag>
                      <span class="notification-time">{{ formatTime(item.created_at) }}</span>
                    </div>
                    <div class="notification-item-title">{{ item.title }}</div>
                    <div class="notification-item-content">{{ item.content }}</div>
                  </div>
                </template>
                <el-empty v-else description="暂无通知" :image-size="60" />
              </div>
              <div class="notification-footer" v-if="notificationTotal > notifications.length">
                <el-button type="primary" link size="small" @click="loadMoreNotifications">
                  查看更多
                </el-button>
              </div>
            </div>
          </el-popover>

          <!-- 用户信息下拉菜单 -->
          <el-dropdown trigger="click" @command="handleUserCommand">
            <span class="user-info">
              <el-avatar :size="32" :src="userAvatar" style="background-color: #409eff">
                {{ userInitial }}
              </el-avatar>
              <span class="username">{{ authStore.userInfo?.username || '用户' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <div class="user-detail">
                    <div>{{ authStore.userInfo?.real_name || authStore.userInfo?.username }}</div>
                    <div class="user-role">{{ roleLabel }}</div>
                  </div>
                </el-dropdown-item>
                <el-divider style="margin: 4px 0" />
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="app-main">
        <el-alert
          v-if="currentBookArchived"
          title="当前账套已归档，所有数据为只读状态，不可新增或修改"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useBookStore } from '@/stores/book'
import { ElMessageBox } from 'element-plus'
import ModelSelector from './ModelSelector.vue'
import BookSwitcher from './BookSwitcher.vue'
import { getNotifications, getUnreadCount, markAsRead, markAllAsRead } from '@/api/notification'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const bookStore = useBookStore()

// 侧边栏折叠状态
const isCollapse = ref(false)

// 移动端侧边栏展开状态
const isMobileOpen = ref(false)

// 当前激活的菜单项
const activeMenu = computed(() => {
  return route.path
})

// 当前页面标题
const currentTitle = computed(() => {
  return route.meta?.title || ''
})

// 当前账套是否已归档
const currentBookArchived = computed(() => {
  return bookStore.currentBook?.status === 'archived'
})

// 用户名首字母（用于头像）
const userInitial = computed(() => {
  const name = authStore.userInfo?.real_name || authStore.userInfo?.username || 'U'
  return name.charAt(0).toUpperCase()
})

// 用户头像 URL
const userAvatar = computed(() => {
  return authStore.userInfo?.avatar || null
})

// 角色标签
const roleLabel = computed(() => {
  const labels = {
    admin: '管理员',
    accountant: '会计',
    cashier: '出纳',
    reviewer: '审核员',
    viewer: '查看者'
  }
  return labels[authStore.userInfo?.role] || authStore.userInfo?.role || '未知'
})

// ========== 通知相关 ==========
const notificationVisible = ref(false)
const notificationLoading = ref(false)
const notifications = ref([])
const unreadCount = ref(0)
const notificationPage = ref(1)
const notificationTotal = ref(0)
const notificationPageSize = 10

// 定时刷新未读数量
let unreadTimer = null

onMounted(() => {
  if (authStore.isLoggedIn) {
    fetchUnreadCount()
    unreadTimer = setInterval(fetchUnreadCount, 30000) // 每30秒刷新
  }
})

onUnmounted(() => {
  if (unreadTimer) {
    clearInterval(unreadTimer)
  }
})

async function fetchUnreadCount() {
  try {
    const res = await getUnreadCount()
    unreadCount.value = res.data.count
  } catch (e) {
    // 静默失败
  }
}

async function loadNotifications() {
  notificationLoading.value = true
  notificationPage.value = 1
  try {
    const res = await getNotifications({ page: 1, page_size: notificationPageSize })
    notifications.value = res.data.items || []
    notificationTotal.value = res.data.total || 0
  } catch (e) {
    // ignore
  } finally {
    notificationLoading.value = false
  }
}

async function loadMoreNotifications() {
  notificationPage.value++
  notificationLoading.value = true
  try {
    const res = await getNotifications({
      page: notificationPage.value,
      page_size: notificationPageSize
    })
    notifications.value = [...notifications.value, ...(res.data.items || [])]
    notificationTotal.value = res.data.total || 0
  } catch (e) {
    notificationPage.value--
  } finally {
    notificationLoading.value = false
  }
}

async function handleNotificationClick(item) {
  // 标记已读
  if (!item.is_read) {
    try {
      await markAsRead(item.id)
      item.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch (e) {
      // ignore
    }
  }
  // 跳转链接
  if (item.link) {
    notificationVisible.value = false
    router.push(item.link)
  }
}

async function handleMarkAllAsRead() {
  try {
    await markAllAsRead()
    notifications.value.forEach(n => { n.is_read = true })
    unreadCount.value = 0
  } catch (e) {
    // ignore
  }
}

function getNotificationTagType(type) {
  const map = { info: 'info', warning: 'warning', success: 'success', error: 'danger' }
  return map[type] || 'info'
}

function getNotificationTypeLabel(type) {
  const map = { info: '信息', warning: '提醒', success: '成功', error: '异常' }
  return map[type] || '信息'
}

function formatTime(timeStr) {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}

/**
 * 处理用户菜单命令
 */
async function handleUserCommand(command) {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })
      await authStore.logout()
      router.push('/login')
    } catch (e) {
      // 用户取消操作
    }
  }
}
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

/* 侧边栏 */
.app-aside {
  background-color: #304156;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.3s;
}

/* 侧边栏滚动条美化 */
.app-aside::-webkit-scrollbar {
  width: 4px;
}

.app-aside::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}

.app-aside::-webkit-scrollbar-thumb:hover {
  background-color: rgba(255, 255, 255, 0.35);
}

.app-aside::-webkit-scrollbar-track {
  background-color: transparent;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-text {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.side-menu {
  border-right: none;
}

.side-menu:not(.el-menu--collapse) {
  width: 220px;
}

/* 顶栏 */
.app-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 60px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  cursor: pointer;
  color: #606266;
  transition: color 0.2s;
}

.collapse-btn:hover {
  color: #409eff;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.username {
  font-size: 14px;
  color: #303133;
}

.user-detail {
  text-align: center;
}

.user-role {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

/* 内容区 */
.app-main {
  background-color: #f0f2f5;
  min-height: calc(100vh - 60px);
  padding: 20px;
}

/* 通知铃铛 */
.notification-bell {
  cursor: pointer;
  color: #606266;
  transition: color 0.2s;
}

.notification-bell:hover {
  color: #409eff;
}

.notification-badge {
  margin-right: 4px;
}

/* 通知弹窗 */
.notification-popover {
  max-height: 420px;
  display: flex;
  flex-direction: column;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 4px;
}

.notification-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.notification-list {
  overflow-y: auto;
  max-height: 320px;
  flex: 1;
}

.notification-item {
  padding: 10px 12px;
  border-bottom: 1px solid #f2f2f2;
  cursor: pointer;
  transition: background-color 0.2s;
}

.notification-item:hover {
  background-color: #f5f7fa;
}

.notification-item.is-unread {
  background-color: #ecf5ff;
}

.notification-item.is-unread:hover {
  background-color: #d9ecff;
}

.notification-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.notification-time {
  font-size: 12px;
  color: #909399;
}

.notification-item-title {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 2px;
}

.notification-item-content {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.notification-footer {
  text-align: center;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
  margin-top: 4px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .app-aside {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.3s;
  }

  .app-aside.mobile-open {
    transform: translateX(0);
  }

  .app-header {
    padding: 0 12px;
  }

  .app-main {
    padding: 12px;
  }

  .header-right {
    gap: 8px;
  }

  .username {
    display: none;
  }

  /* 移动端菜单按钮 */
  .mobile-menu-btn {
    display: inline-flex;
    cursor: pointer;
    color: #606266;
    transition: color 0.2s;
  }

  .mobile-menu-btn:hover {
    color: #409eff;
  }

  /* 桌面端隐藏移动端菜单按钮 */
  .collapse-btn {
    display: none;
  }

  /* 移动端遮罩层 */
  .mobile-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }
}

/* 桌面端隐藏移动端菜单按钮 */
@media (min-width: 769px) {
  .mobile-menu-btn {
    display: none;
  }
}
</style>