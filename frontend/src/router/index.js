import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

// 路由配置
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', noAuth: true }
  },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '工作台', icon: 'Monitor' }
      },
      {
        path: 'chat',
        name: 'ChatAssistant',
        component: () => import('@/views/chat/ChatAssistant.vue'),
        meta: { title: 'AI 助手', icon: 'ChatDotRound' }
      },
      {
        path: 'voucher/list',
        name: 'VoucherList',
        component: () => import('@/views/bookkeeping/VoucherList.vue'),
        meta: { title: '凭证列表', icon: 'Document' }
      },
      {
        path: 'voucher/create',
        name: 'VoucherCreate',
        component: () => import('@/views/bookkeeping/VoucherCreate.vue'),
        meta: { title: '录入凭证', icon: 'Edit' }
      },
      {
        path: 'voucher/templates',
        name: 'VoucherTemplate',
        component: () => import('@/views/bookkeeping/VoucherTemplate.vue'),
        meta: { title: '凭证模板', icon: 'CopyDocument' }
      },
      {
        path: 'voucher/ledger',
        name: 'VoucherLedger',
        component: () => import('@/views/bookkeeping/VoucherLedger.vue'),
        meta: { title: '凭证台账', icon: 'Notebook' }
      },
      {
        path: 'budget',
        name: 'BudgetManage',
        component: () => import('@/views/budget/BudgetManage.vue'),
        meta: { title: '预算管理', icon: 'Money' }
      },
      {
        path: 'finance/budget/summary',
        name: 'BudgetSummary',
        component: () => import('@/views/finance/BudgetSummary.vue'),
        meta: { title: '预算汇总', icon: 'Money' }
      },
      {
        path: 'finance/budget',
        name: 'BudgetList',
        component: () => import('@/views/finance/BudgetList.vue'),
        meta: { title: '预算列表', icon: 'Money' }
      },
      {
        path: 'finance/budget/:id/execution',
        name: 'BudgetExecution',
        component: () => import('@/views/finance/BudgetExecution.vue'),
        meta: { title: '预算执行详情', icon: 'Money' }
      },
      {
        path: 'report/general-ledger',
        name: 'GeneralLedger',
        component: () => import('@/views/report/GeneralLedger.vue'),
        meta: { title: '总账', icon: 'DataAnalysis' }
      },
      {
        path: 'report/subsidiary-ledger',
        name: 'SubsidiaryLedger',
        component: () => import('@/views/report/SubsidiaryLedger.vue'),
        meta: { title: '明细账', icon: 'DataAnalysis' }
      },
      {
        path: 'report/journal',
        name: 'Journal',
        component: () => import('@/views/report/Journal.vue'),
        meta: { title: '日记账', icon: 'DataAnalysis' }
      },
      {
        path: 'report/:type',
        name: 'ReportView',
        component: () => import('@/views/report/ReportView.vue'),
        meta: { title: '报表查看', icon: 'DataAnalysis' }
      },
      {
        path: 'knowledge',
        name: 'KnowledgeManage',
        component: () => import('@/views/knowledge/KnowledgeManage.vue'),
        meta: { title: '知识库管理', icon: 'Collection' }
      },
      {
        path: 'settings/api-keys',
        name: 'ApiKeyManage',
        component: () => import('@/views/settings/ApiKeyManage.vue'),
        meta: { title: 'API Key 管理', icon: 'Key' }
      },
      {
        path: 'settings/model',
        name: 'ModelConfig',
        component: () => import('@/views/settings/ModelConfig.vue'),
        meta: { title: '模型配置', icon: 'Cpu' }
      },
      {
        path: 'settings/users',
        name: 'UserManage',
        component: () => import('@/views/settings/UserManage.vue'),
        meta: { title: '用户管理', icon: 'User', permission: 'admin' }
      },
      {
        path: 'settings/sessions',
        name: 'SessionManage',
        component: () => import('@/views/settings/SessionManage.vue'),
        meta: { title: '会话管理', icon: 'Connection' }
      },
      {
      path: 'settings/books',
        name: 'BookManage',
        component: () => import('@/views/settings/BookManage.vue'),
        meta: { title: '账套管理', icon: 'Folder' },
      },
      {
        path: 'settings/notifications',
        name: 'NotificationManage',
        component: () => import('@/views/settings/NotificationManage.vue'),
        meta: { title: '通知管理', icon: 'Bell' },
      },
      {
        path: 'settings/opening-balance',
        name: 'OpeningBalance',
        component: () => import('@/views/settings/OpeningBalance.vue'),
        meta: { title: '期初余额', icon: 'Wallet', permission: 'admin' }
      },
      {
        path: 'settings/system',
        name: 'SystemSettings',
        component: () => import('@/views/settings/SystemSettings.vue'),
        meta: { title: '系统设置', icon: 'Setting', permission: 'admin' }
      },
      {
        path: 'settings/period-close',
        name: 'PeriodClose',
        component: () => import('@/views/settings/PeriodClose.vue'),
        meta: { title: '会计期间', icon: 'Calendar', permission: ['admin', 'accountant'] }
      },
      {
        path: 'settings/currencies',
        name: 'CurrencyList',
        component: () => import('@/views/settings/CurrencyList.vue'),
        meta: { title: '币种管理', icon: 'Money' }
      },
      {
        path: 'settings/exchange-rates',
        name: 'ExchangeRateList',
        component: () => import('@/views/settings/ExchangeRateList.vue'),
        meta: { title: '汇率管理', icon: 'TrendCharts' }
      },
      {
        path: 'finance/salary-items',
        name: 'SalaryItem',
        component: () => import('@/views/finance/SalaryItem.vue'),
        meta: { title: '工资项目', icon: 'Setting' }
      },
      {
        path: 'finance/salary',
        name: 'SalaryList',
        component: () => import('@/views/finance/SalaryList.vue'),
        meta: { title: '工资表', icon: 'Money' }
      },
      {
        path: 'invoice',
        name: 'InvoiceManage',
        component: () => import('@/views/invoice/InvoiceManage.vue'),
        meta: { title: '发票管理', icon: 'Tickets' }
      },
      {
        path: 'finance/tax',
        name: 'TaxManagement',
        component: () => import('@/views/finance/TaxManagement.vue'),
        meta: { title: '税务申报', icon: 'Money' }
      },
      {
        path: 'finance/tax/summary',
        name: 'TaxSummary',
        component: () => import('@/views/finance/TaxSummary.vue'),
        meta: { title: '税务汇总', icon: 'DataAnalysis' }
      },
      {
        path: 'finance/tax/analysis',
        name: 'TaxAnalysis',
        component: () => import('@/views/finance/TaxAnalysis.vue'),
        meta: { title: '税负分析', icon: 'TrendCharts' }
      },
      {
        path: 'tax',
        name: 'TaxManage',
        component: () => import('@/views/tax/TaxManage.vue'),
        meta: { title: '税务管理', icon: 'Money' }
      },
      {
        path: 'audit',
        name: 'AuditLog',
        component: () => import('@/views/audit/AuditLog.vue'),
        meta: { title: '审计日志', icon: 'Warning', permission: ['admin', 'reviewer'] }
      },
      {
        path: 'tools/import-export',
        name: 'DataImportExport',
        component: () => import('@/views/tools/DataImportExport.vue'),
        meta: { title: '数据导入导出', icon: 'Upload' }
      },
      {
        path: 'tools/bank-reconciliation',
        name: 'BankReconciliation',
        component: () => import('@/views/tools/BankReconciliation.vue'),
        meta: { title: '银行对账', icon: 'BankCard' }
      },
      {
        path: 'tools/import-voucher',
        name: 'ImportVoucher',
        component: () => import('@/views/tools/ImportVoucher.vue'),
        meta: { title: '导入凭证', icon: 'Upload' }
      },
      {
        path: 'settings/backup',
        name: 'BackupRestore',
        component: () => import('@/views/settings/BackupRestore.vue'),
        meta: { title: '数据备份', icon: 'Box', permission: 'admin' }
      },
      {
        path: 'fixed-asset',
        name: 'FixedAssetManage',
        component: () => import('@/views/fixed_asset/FixedAssetManage.vue'),
        meta: { title: '固定资产', icon: 'OfficeBuilding' }
      },
      {
        path: 'finance/reconciliation',
        name: 'ReconciliationList',
        component: () => import('@/views/finance/ReconciliationList.vue'),
        meta: { title: '应收应付核销', icon: 'Money' }
      },
      {
        path: 'finance/aging',
        name: 'AgingAnalysis',
        component: () => import('@/views/finance/AgingAnalysis.vue'),
        meta: { title: '账龄分析', icon: 'DataAnalysis' }
      },
      {
        path: 'finance/statement',
        name: 'PartyStatement',
        component: () => import('@/views/finance/PartyStatement.vue'),
        meta: { title: '对账单', icon: 'Document' }
      }
    ]
  },
  {
    // 404 页面
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局路由守卫：鉴权与权限校验
router.beforeEach((to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - 企业财务智能助手` : '企业财务智能助手'

  // 无需认证的页面直接放行
  if (to.meta.noAuth) {
    return next()
  }

  // 检查登录状态
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn || !authStore.accessToken) {
    ElMessage.warning('请先登录')
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }

  // 检查权限要求
  if (to.meta.permission) {
    const requiredPermissions = Array.isArray(to.meta.permission)
      ? to.meta.permission
      : [to.meta.permission]

    const hasPermission = requiredPermissions.some(perm =>
      authStore.hasPermission(perm)
    )

    if (!hasPermission) {
      ElMessage.error('您没有访问该页面的权限')
      return next({ name: 'Dashboard' })
    }
  }

  next()
})

export default router