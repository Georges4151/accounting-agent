<template>
  <div class="budget-summary">
    <!-- 年份选择 -->
    <div class="filter-bar">
      <el-select v-model="filterYear" placeholder="选择年份" style="width: 120px" @change="loadAll">
        <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
      </el-select>
    </div>

    <!-- 汇总卡片 -->
    <el-row :gutter="16" class="summary-row" v-loading="loading">
      <el-col :xs="24" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">预算总数</div>
          <div class="summary-value primary">{{ summary.budget_count || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">预算总额</div>
          <div class="summary-value primary">¥{{ formatMoney(summary.total_budget) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">实际支出</div>
          <div class="summary-value warning">¥{{ formatMoney(summary.total_actual) }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">预警数量</div>
          <div class="summary-value danger">{{ summary.alert_count || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 总体执行进度 -->
    <el-card shadow="hover" style="margin-top: 16px" v-loading="loading">
      <template #header>
        <span>总体执行进度</span>
      </template>
      <div class="overall-progress">
        <el-progress
          type="dashboard"
          :percentage="Math.min(summary.overall_percentage || 0, 100)"
          :color="progressColor(summary.overall_percentage)"
          :stroke-width="20"
          :width="200"
        >
          <template #default="{ percentage }">
            <span class="progress-text">{{ percentage }}%</span>
          </template>
        </el-progress>
        <div class="progress-detail">
          <div class="progress-item">
            <span class="progress-label">预算总额</span>
            <span class="progress-value">¥{{ formatMoney(summary.total_budget) }}</span>
          </div>
          <div class="progress-item">
            <span class="progress-label">实际支出</span>
            <span class="progress-value">¥{{ formatMoney(summary.total_actual) }}</span>
          </div>
          <div class="progress-item">
            <span class="progress-label">剩余预算</span>
            <span class="progress-value" :class="summary.total_budget - summary.total_actual < 0 ? 'danger' : 'success'">
              ¥{{ formatMoney(summary.total_budget - summary.total_actual) }}
            </span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 按科目类别分组的使用率排行 -->
    <el-card shadow="hover" style="margin-top: 16px" v-loading="loading">
      <template #header>
        <span>预算使用率排行</span>
      </template>
      <el-table :data="budgets" stripe border>
        <el-table-column type="index" label="排名" width="60" />
        <el-table-column prop="account_code" label="科目编码" width="120" />
        <el-table-column prop="account_name" label="科目名称" width="150" />
        <el-table-column prop="name" label="预算名称" min-width="150" />
        <el-table-column label="预算金额" width="140" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.budget_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="实际金额" width="140" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.actual_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="使用率" width="220">
          <template #default="{ row }">
            <div class="usage-cell">
              <el-progress
                :percentage="Math.min(row.used_percentage || 0, 100)"
                :color="progressColor(row.used_percentage)"
                :format="() => (row.used_percentage || 0) + '%'"
                :stroke-width="16"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : '关闭' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && budgets.length === 0" description="暂无预算数据" />
    </el-card>

    <!-- 已触发预警 -->
    <el-card shadow="hover" style="margin-top: 16px" v-loading="alertLoading">
      <template #header>
        <div class="section-header">
          <span>已触发预警</span>
          <el-tag v-if="triggeredAlerts.length > 0" type="danger" size="small">
            {{ triggeredAlerts.length }}条
          </el-tag>
        </div>
      </template>
      <el-table :data="triggeredAlerts" stripe border>
        <el-table-column prop="budget_name" label="预算名称" min-width="150" />
        <el-table-column prop="account_code" label="科目编码" width="120" />
        <el-table-column prop="account_name" label="科目名称" width="150" />
        <el-table-column label="使用率" width="100" align="center">
          <template #default="{ row }">{{ row.used_percentage }}%</template>
        </el-table-column>
        <el-table-column prop="alert_type" label="预警类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.alert_type === 'overspend' ? 'danger' : 'warning'" size="small">
              {{ row.alert_type === 'overspend' ? '超支' : '阈值' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发阈值" width="100" align="center">
          <template #default="{ row }">{{ row.threshold_percentage }}%</template>
        </el-table-column>
        <el-table-column prop="triggered_at" label="触发时间" width="180" />
      </el-table>
      <el-empty v-if="!alertLoading && triggeredAlerts.length === 0" description="暂无触发预警" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { getBudgets, getBudgetSummary, getBudgetAlerts } from '@/api/budget'

// ===== 筛选条件 =====
const filterYear = ref(new Date().getFullYear())

const yearOptions = computed(() => {
  const current = new Date().getFullYear()
  const years = []
  for (let i = current - 5; i <= current + 2; i++) {
    years.push(i)
  }
  return years
})

// ===== 汇总数据 =====
const loading = ref(false)
const summary = reactive({
  total_budget: 0,
  total_actual: 0,
  overall_percentage: 0,
  alert_count: 0,
  budget_count: 0
})

// ===== 预算列表（按使用率排序） =====
const budgets = ref([])

// ===== 预警 =====
const alertLoading = ref(false)
const triggeredAlerts = ref([])

// ===== 工具函数 =====
function formatMoney(value) {
  if (value == null || isNaN(value)) return '0.00'
  return Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function progressColor(percentage) {
  if (!percentage) return '#67c23a'
  if (percentage >= 100) return '#f56c6c'
  if (percentage >= 80) return '#e6a23c'
  return '#67c23a'
}

// ===== 数据加载 =====
async function loadSummary() {
  try {
    const res = await getBudgetSummary(filterYear.value)
    Object.assign(summary, res.data)
  } catch {
    // 静默处理
  }
}

async function loadBudgets() {
  try {
    const res = await getBudgets({ year: filterYear.value, month: 0 })
    const list = res.data || []
    // 按使用率降序排列
    list.sort((a, b) => (b.used_percentage || 0) - (a.used_percentage || 0))
    budgets.value = list
  } catch {
    budgets.value = []
  }
}

async function loadAlerts() {
  alertLoading.value = true
  try {
    const res = await getBudgetAlerts(true)
    triggeredAlerts.value = res.data || []
  } catch {
    triggeredAlerts.value = []
  } finally {
    alertLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadSummary(), loadBudgets(), loadAlerts()])
  } finally {
    loading.value = false
  }
}

// ===== 初始化 =====
onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.budget-summary {
  padding: 0;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.summary-row {
  margin-bottom: 0;
}

.summary-card {
  text-align: center;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
}

.summary-value.primary {
  color: #409eff;
}

.summary-value.warning {
  color: #e6a23c;
}

.summary-value.danger {
  color: #f56c6c;
}

.summary-value.success {
  color: #67c23a;
}

.overall-progress {
  display: flex;
  align-items: center;
  gap: 60px;
  justify-content: center;
}

.progress-text {
  font-size: 24px;
  font-weight: 700;
}

.progress-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-item {
  display: flex;
  justify-content: space-between;
  gap: 24px;
}

.progress-label {
  color: #909399;
  font-size: 14px;
}

.progress-value {
  font-weight: 600;
  font-size: 16px;
  color: #303133;
}

.progress-value.danger {
  color: #f56c6c;
}

.progress-value.success {
  color: #67c23a;
}

.usage-cell {
  display: flex;
  align-items: center;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>