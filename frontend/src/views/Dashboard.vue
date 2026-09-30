<template>
  <div class="dashboard">
    <!-- 欢迎卡片 -->
    <el-card class="welcome-card" shadow="hover">
      <div class="welcome-content">
        <div class="welcome-text">
          <h2>欢迎回来，{{ authStore.userInfo?.real_name || authStore.userInfo?.username }}</h2>
          <p class="welcome-time">{{ greetingText }}</p>
        </div>
        <div class="welcome-icon">
          <el-icon :size="64" color="#409eff"><DataBoard /></el-icon>
        </div>
      </div>
    </el-card>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="6" animated />
    </div>

    <template v-else>
      <!-- 第一行：4 个关键指标卡片 -->
      <el-row :gutter="16" class="metric-row">
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card class="metric-card" shadow="hover">
            <div class="metric-header">
              <span class="metric-label">本月收入</span>
              <el-tag :type="overview.revenue_change_pct >= 0 ? 'success' : 'danger'" size="small" effect="plain">
                <span class="trend-arrow">{{ overview.revenue_change_pct >= 0 ? '▲' : '▼' }}</span>
                {{ Math.abs(overview.revenue_change_pct) }}%
              </el-tag>
            </div>
            <div class="metric-value revenue">¥{{ formatMoney(overview.total_revenue) }}</div>
            <div class="metric-sub">环比变化</div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card class="metric-card" shadow="hover">
            <div class="metric-header">
              <span class="metric-label">本月支出</span>
              <el-tag :type="overview.expenses_change_pct <= 0 ? 'success' : 'danger'" size="small" effect="plain">
                <span class="trend-arrow">{{ overview.expenses_change_pct <= 0 ? '▼' : '▲' }}</span>
                {{ Math.abs(overview.expenses_change_pct) }}%
              </el-tag>
            </div>
            <div class="metric-value expenses">¥{{ formatMoney(overview.total_expenses) }}</div>
            <div class="metric-sub">环比变化</div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card class="metric-card" shadow="hover">
            <div class="metric-header">
              <span class="metric-label">净利润</span>
            </div>
            <div class="metric-value" :class="overview.net_profit >= 0 ? 'profit' : 'loss'">
              ¥{{ formatMoney(overview.net_profit) }}
            </div>
            <div class="metric-sub">
              {{ overview.voucher_count }} 笔凭证 · {{ overview.pending_review_count }} 待审
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card class="metric-card health-card" shadow="hover">
            <div class="metric-header">
              <span class="metric-label">经营健康度</span>
            </div>
            <div class="health-score-wrapper">
              <svg class="health-circle" viewBox="0 0 100 100">
                <circle class="health-bg" cx="50" cy="50" r="42" fill="none"
                  stroke="#e5e7eb" stroke-width="8" />
                <circle class="health-fill" cx="50" cy="50" r="42" fill="none"
                  :stroke="healthColor"
                  stroke-width="8"
                  stroke-linecap="round"
                  :stroke-dasharray="healthDasharray"
                  :stroke-dashoffset="0"
                  transform="rotate(-90 50 50)" />
              </svg>
              <div class="health-text">
                <span class="health-score-num" :style="{ color: healthColor }">{{ overview.health_score }}</span>
                <span class="health-label">分</span>
              </div>
            </div>
            <div class="health-tag" :style="{ background: healthColor + '20', color: healthColor }">
              {{ healthLabel }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 工作待办统计卡片 -->
      <el-row :gutter="16" class="metric-row">
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--review" @click="router.push('/voucher/list?status=submitted')">
            <div class="workbench-card-icon"><el-icon><DocumentChecked /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.pending_review_count }}</div>
            <div class="workbench-card-label">待审核</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--cashier" @click="router.push('/voucher/list?status=submitted')">
            <div class="workbench-card-icon"><el-icon><Money /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.pending_cashier_review_count }}</div>
            <div class="workbench-card-label">出纳复核</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--approval" @click="router.push('/voucher/list?status=reviewed')">
            <div class="workbench-card-icon"><el-icon><Select /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.pending_approval_count }}</div>
            <div class="workbench-card-label">待审批</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--post" @click="router.push('/voucher/list?status=approved')">
            <div class="workbench-card-icon"><el-icon><Finished /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.pending_post_count }}</div>
            <div class="workbench-card-label">待过账</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--gap" :class="{ 'has-warning': workbench.gap_count > 0 }" @click="router.push('/voucher/list')">
            <div class="workbench-card-icon"><el-icon><WarningFilled /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.gap_count }}</div>
            <div class="workbench-card-label">断号提醒</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--invoice" :class="{ 'has-warning': workbench.pending_invoice_count > 0 }" @click="router.push('/invoice')">
            <div class="workbench-card-icon"><el-icon><Receipt /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.pending_invoice_count }}</div>
            <div class="workbench-card-label">待处理发票</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--carry" :class="{ 'has-warning': workbench.carry_forward_needed }" @click="router.push('/voucher/period-close')">
            <div class="workbench-card-icon"><el-icon><Refresh /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.carry_forward_needed ? '待处理' : '已完成' }}</div>
            <div class="workbench-card-label">期末结转</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6" :lg="3">
          <div class="workbench-card workbench-card--depr" :class="{ 'has-warning': workbench.pending_depreciation_count > 0 }" @click="router.push('/fixed-assets')">
            <div class="workbench-card-icon"><el-icon><TrendCharts /></el-icon></div>
            <div class="workbench-card-count">{{ workbench.pending_depreciation_count }}</div>
            <div class="workbench-card-label">待折旧资产</div>
          </div>
        </el-col>
      </el-row>

      <!-- 看板列 -->
      <el-row :gutter="16" class="kanban-row" v-if="!workbenchLoading">
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card shadow="hover" class="kanban-column">
            <template #header>
              <div class="kanban-column-header">
                <el-tag type="warning" effect="dark">待审核</el-tag>
                <span class="kanban-count">{{ workbench.pending_review_count }}</span>
              </div>
            </template>
            <div v-if="workbench.pending_review_tasks.length === 0" class="kanban-empty">
              <el-empty :image-size="40" description="暂无待审核凭证" />
            </div>
            <div v-else class="kanban-cards">
              <div
                v-for="task in workbench.pending_review_tasks"
                :key="task.id"
                class="kanban-card"
                @click="goVoucherEdit(task.id)"
              >
                <div class="kanban-card-title">{{ task.title }}</div>
                <div class="kanban-card-subtitle">{{ task.subtitle || '无摘要' }}</div>
                <div class="kanban-card-footer">
                  <span class="kanban-card-date">{{ task.date }}</span>
                  <span class="kanban-card-amount">¥{{ formatMoney(task.amount) }}</span>
                </div>
                <div class="kanban-card-actions">
                  <el-button size="small" type="primary" @click.stop="goVoucherEdit(task.id)">审核</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card shadow="hover" class="kanban-column">
            <template #header>
              <div class="kanban-column-header">
                <el-tag type="warning" effect="dark">出纳复核</el-tag>
                <span class="kanban-count">{{ workbench.pending_cashier_review_count }}</span>
              </div>
            </template>
            <div v-if="workbench.pending_cashier_review_tasks.length === 0" class="kanban-empty">
              <el-empty :image-size="40" description="暂无待出纳复核凭证" />
            </div>
            <div v-else class="kanban-cards">
              <div
                v-for="task in workbench.pending_cashier_review_tasks"
                :key="task.id"
                class="kanban-card"
                @click="goVoucherEdit(task.id)"
              >
                <div class="kanban-card-title">{{ task.title }}</div>
                <div class="kanban-card-subtitle">{{ task.subtitle || '无摘要' }}</div>
                <div class="kanban-card-footer">
                  <span class="kanban-card-date">{{ task.date }}</span>
                  <span class="kanban-card-amount">¥{{ formatMoney(task.amount) }}</span>
                </div>
                <div class="kanban-card-actions">
                  <el-button size="small" type="warning" @click.stop="goVoucherEdit(task.id)">复核</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card shadow="hover" class="kanban-column">
            <template #header>
              <div class="kanban-column-header">
                <el-tag type="primary" effect="dark">待审批</el-tag>
                <span class="kanban-count">{{ workbench.pending_approval_count }}</span>
              </div>
            </template>
            <div v-if="workbench.pending_approval_tasks.length === 0" class="kanban-empty">
              <el-empty :image-size="40" description="暂无待审批凭证" />
            </div>
            <div v-else class="kanban-cards">
              <div
                v-for="task in workbench.pending_approval_tasks"
                :key="task.id"
                class="kanban-card"
                @click="goVoucherEdit(task.id)"
              >
                <div class="kanban-card-title">{{ task.title }}</div>
                <div class="kanban-card-subtitle">{{ task.subtitle || '无摘要' }}</div>
                <div class="kanban-card-footer">
                  <span class="kanban-card-date">{{ task.date }}</span>
                  <span class="kanban-card-amount">¥{{ formatMoney(task.amount) }}</span>
                </div>
                <div class="kanban-card-actions">
                  <el-button size="small" type="success" @click.stop="goVoucherEdit(task.id)">审批</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12" :lg="6">
          <el-card shadow="hover" class="kanban-column">
            <template #header>
              <div class="kanban-column-header">
                <el-tag type="success" effect="dark">待过账</el-tag>
                <span class="kanban-count">{{ workbench.pending_post_count }}</span>
              </div>
            </template>
            <div v-if="workbench.pending_post_tasks.length === 0" class="kanban-empty">
              <el-empty :image-size="40" description="暂无待过账凭证" />
            </div>
            <div v-else class="kanban-cards">
              <div
                v-for="task in workbench.pending_post_tasks"
                :key="task.id"
                class="kanban-card"
                @click="goVoucherEdit(task.id)"
              >
                <div class="kanban-card-title">{{ task.title }}</div>
                <div class="kanban-card-subtitle">{{ task.subtitle || '无摘要' }}</div>
                <div class="kanban-card-footer">
                  <span class="kanban-card-date">{{ task.date }}</span>
                  <span class="kanban-card-amount">¥{{ formatMoney(task.amount) }}</span>
                </div>
                <div class="kanban-card-actions">
                  <el-button size="small" type="primary" @click.stop="goVoucherEdit(task.id)">过账</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 异常检测卡片 -->
      <el-row :gutter="16" class="chart-row" v-if="anomalies.length > 0 || !anomaliesLoading">
        <el-col :span="24">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="card-title">
                  <el-icon style="margin-right: 4px"><WarningFilled /></el-icon>
                  异常检测
                </span>
                <el-tag :type="anomalySeverityTag" size="small">
                  {{ anomalies.length }} 项异常
                </el-tag>
              </div>
            </template>
            <div v-if="anomaliesLoading" class="chart-container">
              <el-skeleton :rows="2" animated />
            </div>
            <el-empty v-else-if="anomalies.length === 0" description="未检测到异常，数据正常" :image-size="60" />
            <div v-else class="anomaly-list">
              <div
                v-for="(item, index) in anomalies"
                :key="index"
                class="anomaly-item"
                :class="'severity-' + item.severity"
              >
                <div class="anomaly-severity">
                  <el-tag :type="severityType(item.severity)" size="small" effect="dark">
                    {{ severityLabel(item.severity) }}
                  </el-tag>
                </div>
                <div class="anomaly-content">
                  <div class="anomaly-type">
                    <el-tag :type="anomalyTypeTag(item.type)" size="small" effect="plain">
                      {{ anomalyTypeLabel(item.type) }}
                    </el-tag>
                  </div>
                  <div class="anomaly-message">{{ item.message }}</div>
                  <div class="anomaly-detail" v-if="item.detail">{{ item.detail }}</div>
                </div>
                <div class="anomaly-action">
                  <el-button
                    text
                    type="primary"
                    size="small"
                    @click="goVoucher({ id: item.voucher_id })"
                  >
                    查看凭证
                  </el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 第二行：收支趋势图 -->
      <el-row :gutter="16" class="chart-row">
        <el-col :span="24">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="card-title">收支趋势（近6个月）</span>
              </div>
            </template>
            <div class="chart-container">
              <v-chart v-if="trendData.length" :option="trendChartOption" autoresize style="height: 360px; width: 100%" />
              <el-empty v-else description="暂无趋势数据" :image-size="80" />
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 第三行：科目占比 + 月度对比 -->
      <el-row :gutter="16" class="chart-row">
        <el-col :xs="24" :lg="12">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="card-title">支出科目占比</span>
              </div>
            </template>
            <div class="chart-container">
              <v-chart v-if="categoryData.length" :option="pieChartOption" autoresize style="height: 320px; width: 100%" />
              <el-empty v-else description="暂无支出数据" :image-size="80" />
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="card-title">月度对比</span>
              </div>
            </template>
            <div v-if="comparison" class="comparison-table">
              <el-table :data="comparisonTableData" size="small" stripe :show-header="true">
                <el-table-column prop="label" label="指标" width="100" fixed />
                <el-table-column prop="current" label="本月" align="right" />
                <el-table-column prop="previous" label="上月" align="right" />
                <el-table-column prop="yoy" label="去年同期" align="right" />
                <el-table-column prop="change" label="环比" align="right" width="90">
                  <template #default="{ row }">
                    <span :style="{ color: row.changeColor }">{{ row.change }}</span>
                  </template>
                </el-table-column>
              </el-table>
              <div v-if="!comparison" class="empty-hint">
                <el-empty description="暂无对比数据" :image-size="60" />
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 第四行：最近凭证 -->
      <el-row :gutter="16" class="chart-row">
        <el-col :span="24">
          <el-card shadow="hover">
            <template #header>
              <div class="card-header">
                <span class="card-title">最近凭证</span>
                <el-button text type="primary" @click="router.push('/voucher/list')">查看全部</el-button>
              </div>
            </template>
            <el-table v-if="recentVouchers.length" :data="recentVouchers" size="small" stripe
              @row-click="goVoucher" style="cursor: pointer">
              <el-table-column prop="voucher_no" label="凭证号" width="140" />
              <el-table-column prop="voucher_date" label="日期" width="120" />
              <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column prop="debit_total" label="借方金额" width="140" align="right">
                <template #default="{ row }">¥{{ formatMoney(row.debit_total) }}</template>
              </el-table-column>
              <el-table-column prop="credit_total" label="贷方金额" width="140" align="right">
                <template #default="{ row }">¥{{ formatMoney(row.credit_total) }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无凭证记录" :image-size="80" />
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { WarningFilled } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent, TitleComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  getOverview, getTrends, getCategoryBreakdown,
  getMonthlyComparison, getRecentVouchers, getAnomalies,
  getWorkbench
} from '@/api/dashboard'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const router = useRouter()
const authStore = useAuthStore()

// 状态
const loading = ref(true)
const overview = ref({
  total_revenue: 0, total_expenses: 0, net_profit: 0,
  voucher_count: 0, pending_review_count: 0,
  revenue_change_pct: 0, expenses_change_pct: 0, health_score: 50
})
const trendData = ref([])
const categoryData = ref([])
const comparison = ref(null)
const recentVouchers = ref([])

// 异常检测
const anomalies = ref([])
const anomaliesLoading = ref(false)

// 工作看板
const workbenchLoading = ref(false)
const workbench = ref({
  pending_review_count: 0,
  pending_cashier_review_count: 0,
  pending_approval_count: 0,
  pending_post_count: 0,
  gap_count: 0,
  pending_invoice_count: 0,
  carry_forward_needed: false,
  pending_depreciation_count: 0,
  pending_review_tasks: [],
  pending_cashier_review_tasks: [],
  pending_approval_tasks: [],
  pending_post_tasks: [],
})

// 问候语
const greetingText = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了，注意休息 🌙'
  if (hour < 9) return '早上好！新的一天开始了 ☀️'
  if (hour < 12) return '上午好！工作顺利'
  if (hour < 14) return '中午好！记得休息'
  if (hour < 18) return '下午好！精力充沛'
  return '晚上好！辛苦了'
})

// 健康度颜色
const healthColor = computed(() => {
  const s = overview.value.health_score
  if (s >= 80) return '#67c23a'
  if (s >= 60) return '#409eff'
  if (s >= 40) return '#e6a23c'
  return '#f56c6c'
})

// 健康度标签
const healthLabel = computed(() => {
  const s = overview.value.health_score
  if (s >= 80) return '优秀'
  if (s >= 60) return '良好'
  if (s >= 40) return '一般'
  return '需关注'
})

// 健康度环形进度
const healthDasharray = computed(() => {
  const score = overview.value.health_score
  const circumference = 2 * Math.PI * 42
  const filled = (score / 100) * circumference
  return `${filled} ${circumference}`
})

// 趋势图配置
const trendChartOption = computed(() => {
  const months = trendData.value.map(d => d.month.substring(5))
  const revenues = trendData.value.map(d => d.revenue)
  const expenses = trendData.value.map(d => d.expenses)
  const profits = trendData.value.map(d => d.net_profit)

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const month = trendData.value[params[0].dataIndex].month
        let html = `<strong>${month}</strong><br/>`
        params.forEach(p => {
          html += `${p.marker} ${p.seriesName}: ¥${p.value.toLocaleString()}<br/>`
        })
        return html
      }
    },
    legend: {
      data: ['收入', '支出', '净利润'],
      bottom: 0
    },
    grid: {
      left: '3%', right: '4%', top: '3%', bottom: '12%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (v) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : v
      }
    },
    series: [
      {
        name: '收入',
        type: 'line',
        data: revenues,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#67c23a', width: 2 },
        itemStyle: { color: '#67c23a' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(103,194,58,0.25)' },
              { offset: 1, color: 'rgba(103,194,58,0.02)' }
            ]
          }
        }
      },
      {
        name: '支出',
        type: 'line',
        data: expenses,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#f56c6c', width: 2 },
        itemStyle: { color: '#f56c6c' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(245,108,108,0.25)' },
              { offset: 1, color: 'rgba(245,108,108,0.02)' }
            ]
          }
        }
      },
      {
        name: '净利润',
        type: 'line',
        data: profits,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' }
      }
    ]
  }
})

// 饼图配置
const pieChartOption = computed(() => {
  const names = categoryData.value.map(d => d.account_name)
  const pieData = categoryData.value.map(d => ({
    name: d.account_name,
    value: d.amount
  }))

  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399',
    '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272']

  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: '5%',
      top: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 11 }
    },
    color: colors,
    series: [
      {
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold'
          }
        },
        data: pieData
      }
    ]
  }
})

// 月度对比表数据
const comparisonTableData = computed(() => {
  if (!comparison.value) return []
  const c = comparison.value.current
  const p = comparison.value.previous
  const y = comparison.value.yoy
  const mom = comparison.value.mom_change
  const yoy = comparison.value.yoy_change

  const fmt = (v) => v != null ? '¥' + v.toLocaleString() : '--'
  const fmtPct = (v) => v != null ? (v >= 0 ? '+' : '') + v + '%' : '--'
  const pctColor = (v) => v == null ? '#909399' : (v >= 0 ? '#67c23a' : '#f56c6c')

  return [
    {
      label: '收入',
      current: fmt(c.revenue),
      previous: fmt(p.revenue),
      yoy: fmt(y.revenue),
      change: fmtPct(mom.revenue_pct),
      changeColor: pctColor(mom.revenue_pct)
    },
    {
      label: '支出',
      current: fmt(c.expenses),
      previous: fmt(p.expenses),
      yoy: fmt(y.expenses),
      change: fmtPct(mom.expenses_pct),
      changeColor: pctColor(mom.expenses_pct)
    },
    {
      label: '净利润',
      current: fmt(c.net_profit),
      previous: fmt(p.net_profit),
      yoy: fmt(y.net_profit),
      change: fmtPct(mom.net_profit_pct),
      changeColor: pctColor(mom.net_profit_pct)
    },
    {
      label: '凭证数',
      current: c.voucher_count,
      previous: p.voucher_count,
      yoy: y.voucher_count,
      change: '--',
      changeColor: '#909399'
    }
  ]
})

// 工具函数
function formatMoney(val) {
  if (val == null) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function statusType(status) {
  const map = { draft: 'info', submitted: 'warning', reviewed: 'success', posted: '' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { draft: '草稿', submitted: '待审核', reviewed: '已审核', posted: '已过账' }
  return map[status] || status
}

function goVoucher(row) {
  router.push(`/voucher/list?id=${row.id}`)
}

function goVoucherEdit(id) {
  router.push(`/voucher/${id}/edit`)
}

// 加载工作看板数据
async function loadWorkbench() {
  workbenchLoading.value = true
  try {
    const res = await getWorkbench()
    workbench.value = res.data
  } catch (e) {
    console.error('加载工作看板数据失败:', e)
  } finally {
    workbenchLoading.value = false
  }
}

// 异常检测相关
const anomalySeverityTag = computed(() => {
  const severities = anomalies.value.map(a => a.severity)
  if (severities.includes('high')) return 'danger'
  if (severities.includes('medium')) return 'warning'
  return 'info'
})

function severityType(severity) {
  const map = { high: 'danger', medium: 'warning', low: 'info' }
  return map[severity] || 'info'
}

function severityLabel(severity) {
  const map = { high: '高', medium: '中', low: '低' }
  return map[severity] || severity
}

function anomalyTypeTag(type) {
  const map = { imbalance: 'danger', duplicate: 'danger', large_amount: 'warning', negative_amount: 'warning' }
  return map[type] || 'info'
}

function anomalyTypeLabel(type) {
  const map = {
    imbalance: '借贷不平衡',
    large_amount: '金额异常',
    duplicate: '疑似重复',
    negative_amount: '负数金额'
  }
  return map[type] || type
}

async function loadAnomalies() {
  anomaliesLoading.value = true
  try {
    const res = await getAnomalies({})
    anomalies.value = res.data.anomalies || []
  } catch (e) {
    console.error('加载异常检测数据失败:', e)
  } finally {
    anomaliesLoading.value = false
  }
}

// 加载数据
async function loadData() {
  loading.value = true
  try {
    const now = new Date()
    const period = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

    const [overviewRes, trendsRes, categoryRes, comparisonRes, vouchersRes] = await Promise.allSettled([
      getOverview(period),
      getTrends(6),
      getCategoryBreakdown(period),
      getMonthlyComparison(period),
      getRecentVouchers(5)
    ])

    if (overviewRes.status === 'fulfilled') {
      overview.value = overviewRes.value.data
    }
    if (trendsRes.status === 'fulfilled') {
      trendData.value = trendsRes.value.data.data || []
    }
    if (categoryRes.status === 'fulfilled') {
      categoryData.value = categoryRes.value.data.categories || []
    }
    if (comparisonRes.status === 'fulfilled') {
      comparison.value = comparisonRes.value.data
    }
    if (vouchersRes.status === 'fulfilled') {
      recentVouchers.value = vouchersRes.value.data.vouchers || []
    }
  } catch (e) {
    console.error('加载仪表盘数据失败:', e)
  } finally {
    loading.value = false
  }

  // 异常检测单独加载（不阻塞主数据）
  loadAnomalies()
}

onMounted(() => {
  loadData()
  loadWorkbench()
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}

/* 欢迎卡片 */
.welcome-card {
  margin-bottom: 16px;
  background: linear-gradient(135deg, #409eff10, #409eff05);
  border: 1px solid #409eff30;
}

.welcome-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.welcome-text h2 {
  font-size: 22px;
  color: #303133;
  margin-bottom: 8px;
}

.welcome-time {
  font-size: 13px;
  color: #909399;
}

/* 加载状态 */
.loading-container {
  padding: 40px 0;
}

/* 指标卡片行 */
.metric-row {
  margin-bottom: 16px;
}

.metric-card {
  height: 100%;
}

.metric-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.metric-label {
  font-size: 14px;
  color: #909399;
}

.trend-arrow {
  font-size: 11px;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 6px;
  line-height: 1.2;
}

.metric-value.revenue {
  color: #67c23a;
}

.metric-value.expenses {
  color: #f56c6c;
}

.metric-value.profit {
  color: #409eff;
}

.metric-value.loss {
  color: #f56c6c;
}

.metric-sub {
  font-size: 12px;
  color: #909399;
}

/* 健康度卡片 */
.health-card {
  text-align: center;
}

.health-card .metric-header {
  justify-content: center;
}

.health-score-wrapper {
  position: relative;
  width: 100px;
  height: 100px;
  margin: 0 auto 8px;
}

.health-circle {
  width: 100%;
  height: 100%;
}

.health-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.health-score-num {
  font-size: 26px;
  font-weight: 700;
  display: block;
  line-height: 1;
}

.health-label {
  font-size: 11px;
  color: #909399;
}

.health-tag {
  display: inline-block;
  padding: 2px 12px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

/* 图表行 */
.chart-row {
  margin-bottom: 16px;
}

.chart-row .el-card {
  height: 100%;
}

.chart-container {
  width: 100%;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 卡片头部 */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

/* 对比表格 */
.comparison-table {
  min-height: 200px;
}

.empty-hint {
  padding: 20px 0;
}

/* 响应式微调 */
@media (max-width: 768px) {
  .dashboard-container {
    padding: 8px;
  }

  .dashboard-container :deep(.el-row) {
    margin-left: 0 !important;
    margin-right: 0 !important;
  }

  .dashboard-container :deep(.el-col) {
    padding-left: 0 !important;
    padding-right: 0 !important;
    margin-bottom: 12px;
  }

  .metric-value {
    font-size: 22px;
  }

  .chart-container {
    min-height: 160px;
  }
}

/* 异常检测列表 */
.anomaly-list {
  max-height: 400px;
  overflow-y: auto;
}

.anomaly-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s;
}

.anomaly-item:last-child {
  border-bottom: none;
}

.anomaly-item:hover {
  background-color: #fafafa;
}

.anomaly-item.severity-high {
  border-left: 3px solid #f56c6c;
}

.anomaly-item.severity-medium {
  border-left: 3px solid #e6a23c;
}

.anomaly-item.severity-low {
  border-left: 3px solid #909399;
}

.anomaly-severity {
  flex-shrink: 0;
  padding-top: 2px;
}

.anomaly-content {
  flex: 1;
  min-width: 0;
}

.anomaly-type {
  margin-bottom: 4px;
}

.anomaly-message {
  font-size: 13px;
  color: #303133;
  line-height: 1.5;
  word-break: break-all;
}

.anomaly-detail {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.anomaly-action {
  flex-shrink: 0;
  padding-top: 2px;
}

/* ====== 工作看板卡片 ====== */
.workbench-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid #ebeef5;
  margin-bottom: 12px;
  position: relative;
  overflow: hidden;
}

.workbench-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.workbench-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}

.workbench-card--review::before { background: #e6a23c; }
.workbench-card--cashier::before { background: #f56c6c; }
.workbench-card--approval::before { background: #409eff; }
.workbench-card--post::before { background: #67c23a; }
.workbench-card--gap::before { background: #909399; }
.workbench-card--invoice::before { background: #e6a23c; }
.workbench-card--carry::before { background: #409eff; }
.workbench-card--depr::before { background: #67c23a; }

.workbench-card.has-warning {
  border-color: #f56c6c30;
  background: #fef0f0;
}

.workbench-card.has-warning .workbench-card-count {
  color: #f56c6c;
}

.workbench-card-icon {
  font-size: 24px;
  margin-bottom: 8px;
  color: #909399;
}

.workbench-card--review .workbench-card-icon { color: #e6a23c; }
.workbench-card--cashier .workbench-card-icon { color: #f56c6c; }
.workbench-card--approval .workbench-card-icon { color: #409eff; }
.workbench-card--post .workbench-card-icon { color: #67c23a; }
.workbench-card--gap .workbench-card-icon { color: #909399; }
.workbench-card--invoice .workbench-card-icon { color: #e6a23c; }
.workbench-card--carry .workbench-card-icon { color: #409eff; }
.workbench-card--depr .workbench-card-icon { color: #67c23a; }

.workbench-card-count {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.workbench-card-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

/* ====== 看板列 ====== */
.kanban-row {
  margin-bottom: 16px;
}

.kanban-column {
  min-height: 300px;
}

.kanban-column :deep(.el-card__header) {
  padding: 10px 14px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}

.kanban-column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kanban-count {
  font-size: 13px;
  color: #909399;
}

.kanban-empty {
  padding: 30px 0;
}

.kanban-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 500px;
  overflow-y: auto;
}

.kanban-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.kanban-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.kanban-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.kanban-card-subtitle {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kanban-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.kanban-card-date {
  font-size: 11px;
  color: #c0c4cc;
}

.kanban-card-amount {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.kanban-card-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.kanban-card-actions .el-button {
  padding: 4px 10px;
  font-size: 12px;
}
</style>