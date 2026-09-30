<template>
  <div class="period-close">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>会计期间管理</span>
          <div class="header-actions">
            <el-select
              v-model="selectedYear"
              placeholder="选择年份"
              style="width: 120px"
              @change="loadPeriods"
            >
              <el-option
                v-for="y in yearOptions"
                :key="y"
                :label="y + '年'"
                :value="y"
              />
            </el-select>
            <el-button type="primary" @click="loadPeriods" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        title="结账后该期间凭证将不可修改，反结账需管理员权限。请按顺序逐月结账。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <!-- 加载状态 -->
      <div v-if="loading && periods.length === 0" class="loading-container">
        <el-skeleton :rows="4" animated />
      </div>

      <!-- 空数据状态 -->
      <el-empty
        v-else-if="!loading && periods.length === 0"
        description="暂无会计期间数据，请先选择账套"
      />

      <!-- 期间卡片网格 -->
      <div v-else class="period-grid">
        <div
          v-for="period in periods"
          :key="period.period_month"
          class="period-card"
          :class="{
            'period-card--closed': period.status === 'closed',
            'period-card--open': period.status === 'open',
            'period-card--checking': checkingPeriod === period.period_month
          }"
        >
          <!-- 月份标题 -->
          <div class="period-card-header">
            <span class="period-month">{{ period.period_month }}月</span>
            <el-tag
              :type="period.status === 'closed' ? 'success' : 'info'"
              effect="dark"
              size="small"
            >
              {{ period.status === 'closed' ? '已结账' : '未结账' }}
            </el-tag>
          </div>

          <!-- 结账信息 -->
          <div class="period-card-body">
            <template v-if="period.status === 'closed'">
              <div class="period-info-item">
                <span class="info-label">结账人：</span>
                <span class="info-value">{{ period.closed_by_name || '--' }}</span>
              </div>
              <div class="period-info-item">
                <span class="info-label">结账时间：</span>
                <span class="info-value">{{ formatTime(period.closed_at) }}</span>
              </div>
            </template>
            <template v-else>
              <div class="period-info-item">
                <span class="info-label">状态：</span>
                <span class="info-value">待结账</span>
              </div>
            </template>
          </div>

          <!-- 检查结果 -->
          <div v-if="checkResults[period.period_month]" class="period-check-results">
            <div
              v-for="(check, ci) in checkResults[period.period_month]"
              :key="ci"
              class="check-item"
              :class="{ 'check-item--pass': check.passed, 'check-item--fail': !check.passed }"
            >
              <el-icon v-if="check.passed" class="check-icon check-icon--pass"><CircleCheck /></el-icon>
              <el-icon v-else class="check-icon check-icon--fail"><CircleClose /></el-icon>
              <div class="check-detail">
                <span class="check-name">{{ check.name }}</span>
                <span v-if="check.detail" class="check-msg">{{ check.detail }}</span>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="period-card-footer">
            <template v-if="period.status === 'open'">
              <el-button
                type="primary"
                size="small"
                :loading="operatingPeriod === period.period_month && operatingAction === 'close'"
                :disabled="operatingPeriod === period.period_month"
                @click="handleCheckAndClose(period)"
              >
                <el-icon><Lock /></el-icon>
                检查并结账
              </el-button>
            </template>
            <template v-else>
              <el-button
                v-if="canReopen"
                type="warning"
                size="small"
                :loading="operatingPeriod === period.period_month && operatingAction === 'reopen'"
                :disabled="operatingPeriod === period.period_month"
                @click="handleReopen(period)"
              >
                <el-icon><Unlock /></el-icon>
                反结账
              </el-button>
            </template>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 结账确认对话框 -->
    <el-dialog
      v-model="closeDialogVisible"
      title="确认结账"
      width="450px"
      :close-on-click-modal="false"
    >
      <div v-if="closeTargetPeriod">
        <p style="margin-bottom: 12px; font-size: 15px;">
          确定要对 <strong>{{ selectedYear }}年{{ closeTargetPeriod.period_month }}月</strong> 执行结账吗？
        </p>
        <el-alert
          title="结账后该期间的所有凭证将不可修改"
          type="warning"
          :closable="false"
          show-icon
        />
      </div>
      <template #footer>
        <el-button @click="closeDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="operatingPeriod === closeTargetPeriod?.period_month"
          @click="executeClose"
        >
          确认结账
        </el-button>
      </template>
    </el-dialog>

    <!-- 反结账确认对话框 -->
    <el-dialog
      v-model="reopenDialogVisible"
      title="确认反结账"
      width="450px"
      :close-on-click-modal="false"
    >
      <div v-if="reopenTargetPeriod">
        <p style="margin-bottom: 12px; font-size: 15px;">
          确定要对 <strong>{{ selectedYear }}年{{ reopenTargetPeriod.period_month }}月</strong> 执行反结账吗？
        </p>
        <el-alert
          title="反结账后该期间凭证可重新编辑，请谨慎操作！"
          type="error"
          :closable="false"
          show-icon
        />
        <el-alert
          v-if="hasLaterClosedPeriods(reopenTargetPeriod)"
          title="后续期间已结账，需先反结账后续期间再操作当前期间"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 8px"
        />
      </div>
      <template #footer>
        <el-button @click="reopenDialogVisible = false">取消</el-button>
        <el-button
          type="danger"
          :loading="operatingPeriod === reopenTargetPeriod?.period_month"
          @click="executeReopen"
        >
          确认反结账
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useBookStore } from '@/stores/book'
import { useAuthStore } from '@/stores/auth'
import { getPeriods, checkPeriod, closePeriod, reopenPeriod } from '@/api/period'
import { ElMessage } from 'element-plus'

const bookStore = useBookStore()
const authStore = useAuthStore()

// ===== 状态 =====
const loading = ref(false)
const periods = ref([])
const selectedYear = ref(new Date().getFullYear())
const checkingPeriod = ref(null)
const operatingPeriod = ref(null)
const operatingAction = ref('')
const checkResults = ref({})  // { month: [{ name, passed, detail }] }
const closeDialogVisible = ref(false)
const closeTargetPeriod = ref(null)
const reopenDialogVisible = ref(false)
const reopenTargetPeriod = ref(null)

// ===== 计算属性 =====
const yearOptions = computed(() => {
  const currentYear = new Date().getFullYear()
  const years = []
  for (let y = currentYear - 3; y <= currentYear + 1; y++) {
    years.push(y)
  }
  return years
})

const canReopen = computed(() => {
  return authStore.hasPermission('admin')
})

// ===== 生命周期 =====
onMounted(() => {
  loadPeriods()
})

// ===== 数据加载 =====
async function loadPeriods() {
  const bookId = bookStore.currentBookId
  if (!bookId) {
    ElMessage.warning('请先选择账套')
    return
  }

  loading.value = true
  try {
    const res = await getPeriods({
      book_id: bookId,
      year: selectedYear.value
    })
    periods.value = res.data.periods || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载期间数据失败')
  } finally {
    loading.value = false
  }
}

// ===== 检查并结账 =====
async function handleCheckAndClose(period) {
  const bookId = bookStore.currentBookId
  if (!bookId) return

  checkingPeriod.value = period.period_month
  try {
    const res = await checkPeriod(period.period_year, period.period_month, {
      book_id: bookId
    })

    const checks = res.data.checks || []
    checkResults.value = {
      ...checkResults.value,
      [period.period_month]: checks
    }

    if (res.data.can_close) {
      // 所有检查通过，弹出确认对话框
      closeTargetPeriod.value = period
      closeDialogVisible.value = true
    } else {
      ElMessage.warning('结账条件未满足，请检查未通过的检查项')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '检查失败')
  } finally {
    checkingPeriod.value = null
  }
}

// ===== 执行结账 =====
async function executeClose() {
  const period = closeTargetPeriod.value
  if (!period) return

  const bookId = bookStore.currentBookId
  operatingPeriod.value = period.period_month
  operatingAction.value = 'close'

  try {
    await closePeriod(period.period_year, period.period_month, {
      book_id: bookId
    })
    ElMessage.success(`${selectedYear.value}年${period.period_month}月结账成功`)
    closeDialogVisible.value = false
    closeTargetPeriod.value = null
    delete checkResults.value[period.period_month]
    await loadPeriods()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '结账失败')
  } finally {
    operatingPeriod.value = null
    operatingAction.value = ''
  }
}

// ===== 反结账 =====
function handleReopen(period) {
  reopenTargetPeriod.value = period
  reopenDialogVisible.value = true
}

async function executeReopen() {
  const period = reopenTargetPeriod.value
  if (!period) return

  const bookId = bookStore.currentBookId
  operatingPeriod.value = period.period_month
  operatingAction.value = 'reopen'

  try {
    await reopenPeriod(period.period_year, period.period_month, {
      book_id: bookId
    })
    ElMessage.success(`${selectedYear.value}年${period.period_month}月反结账成功`)
    reopenDialogVisible.value = false
    reopenTargetPeriod.value = null
    await loadPeriods()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '反结账失败')
  } finally {
    operatingPeriod.value = null
    operatingAction.value = ''
  }
}

// ===== 辅助函数 =====
function hasLaterClosedPeriods(targetPeriod) {
  return periods.value.some(p =>
    p.status === 'closed' &&
    (p.period_month > targetPeriod.period_month || p.period_year > targetPeriod.period_year)
  )
}

function formatTime(timeStr) {
  if (!timeStr) return '--'
  const d = new Date(timeStr)
  return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.period-close {
  max-width: 1100px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-container {
  padding: 20px 0;
}

/* 期间卡片网格 */
.period-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.period-card {
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.3s ease;
  background: #fff;
}

.period-card--open {
  border-color: #dcdfe6;
}

.period-card--open:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
}

.period-card--closed {
  border-color: #b3e19d;
  background: #f0f9eb;
}

.period-card--checking {
  opacity: 0.7;
}

.period-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.period-month {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.period-card-body {
  margin-bottom: 12px;
}

.period-info-item {
  display: flex;
  margin-bottom: 4px;
  font-size: 13px;
}

.info-label {
  color: #909399;
  flex-shrink: 0;
}

.info-value {
  color: #606266;
}

/* 检查结果 */
.period-check-results {
  margin-bottom: 12px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.check-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
}

.check-icon {
  margin-top: 1px;
  flex-shrink: 0;
  font-size: 14px;
}

.check-icon--pass {
  color: #67c23a;
}

.check-icon--fail {
  color: #f56c6c;
}

.check-detail {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.check-name {
  font-weight: 500;
  color: #303133;
}

.check-item--fail .check-name {
  color: #f56c6c;
}

.check-msg {
  color: #909399;
  font-size: 11px;
}

/* 操作按钮 */
.period-card-footer {
  padding-top: 10px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 8px;
}

/* 响应式 */
@media (max-width: 768px) {
  .period-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 10px;
  }
}
</style>