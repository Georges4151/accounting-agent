<template>
  <el-card shadow="hover" class="budget-overview">
    <template #header>
      <div class="card-header">
        <span class="card-title">预算概览</span>
        <el-button link type="primary" @click="$router.push('/budget')">查看详情</el-button>
      </div>
    </template>

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <template v-else-if="summary">
      <div class="budget-stats">
        <div class="stat-item">
          <div class="stat-label">预算总额</div>
          <div class="stat-value primary">¥{{ formatMoney(summary.total_budget) }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">实际支出</div>
          <div class="stat-value warning">¥{{ formatMoney(summary.total_actual) }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">执行进度</div>
          <div class="stat-value" :class="progressColor(summary.overall_percentage)">
            {{ summary.overall_percentage }}%
          </div>
        </div>
      </div>

      <el-progress
        :percentage="Math.min(summary.overall_percentage, 100)"
        :color="progressColor(summary.overall_percentage)"
        :stroke-width="12"
        style="margin-top: 16px"
      />

      <div class="budget-footer">
        <span>共 {{ summary.budget_count }} 项预算</span>
        <span v-if="summary.alert_count > 0" class="alert-badge">
          <el-tag type="danger" size="small">{{ summary.alert_count }} 条预警</el-tag>
        </span>
      </div>
    </template>

    <el-empty v-else description="暂无预算数据" :image-size="80" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getBudgetSummary } from '@/api/budget'

const loading = ref(false)
const summary = ref(null)

function formatMoney(value) {
  if (value == null || isNaN(value)) return '0.00'
  return Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function progressColor(percentage) {
  if (percentage >= 100) return '#f56c6c'
  if (percentage >= 80) return '#e6a23c'
  return '#67c23a'
}

async function loadSummary() {
  loading.value = true
  try {
    const year = new Date().getFullYear()
    const res = await getBudgetSummary(year)
    summary.value = res.data
  } catch {
    summary.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadSummary()
})
</script>

<style scoped>
.budget-overview {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.loading-container {
  padding: 8px 0;
}

.budget-stats {
  display: flex;
  justify-content: space-around;
  text-align: center;
}

.stat-item {
  flex: 1;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.stat-value.primary {
  color: #409eff;
}

.stat-value.warning {
  color: #e6a23c;
}

.stat-value.danger {
  color: #f56c6c;
}

.stat-value.success {
  color: #67c23a;
}

.budget-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  font-size: 13px;
  color: #909399;
}

.alert-badge {
  display: flex;
  align-items: center;
}
</style>