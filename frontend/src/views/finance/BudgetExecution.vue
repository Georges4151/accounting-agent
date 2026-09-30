<template>
  <div class="budget-execution" v-loading="loading">
    <!-- 面包屑导航 -->
    <div class="page-header">
      <el-button link type="primary" @click="router.push('/finance/budget')">
        <el-icon><ArrowLeft /></el-icon>返回预算列表
      </el-button>
    </div>

    <template v-if="executionData">
      <!-- 预算基本信息卡片 -->
      <el-card shadow="hover" class="info-card">
        <template #header>
          <div class="info-card-header">
            <span class="info-title">{{ executionData.budget.name }}</span>
            <el-tag :type="executionData.budget.status === 'active' ? 'success' : 'info'" size="small">
              {{ executionData.budget.status === 'active' ? '活跃' : '关闭' }}
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="科目编码">{{ executionData.budget.account_code }}</el-descriptions-item>
          <el-descriptions-item label="科目名称">{{ executionData.budget.account_name }}</el-descriptions-item>
          <el-descriptions-item label="预算年份">{{ executionData.budget.year }}年</el-descriptions-item>
          <el-descriptions-item label="预算月份">
            {{ executionData.budget.month === 0 ? '全年' : executionData.budget.month + '月' }}
          </el-descriptions-item>
          <el-descriptions-item label="预算金额">
            <span class="amount">¥{{ formatMoney(executionData.budget.budget_amount) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="实际金额">
            <span class="amount">¥{{ formatMoney(executionData.budget.actual_amount) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="使用进度">
            <el-progress
              :percentage="Math.min(executionData.budget.used_percentage || 0, 100)"
              :color="progressColor(executionData.budget.used_percentage)"
              :format="() => (executionData.budget.used_percentage || 0) + '%'"
              style="width: 200px"
            />
          </el-descriptions-item>
          <el-descriptions-item label="剩余预算">
            <span class="amount" :style="{ color: executionData.budget.budget_amount - executionData.budget.actual_amount < 0 ? '#f56c6c' : '#67c23a' }">
              ¥{{ formatMoney(executionData.budget.budget_amount - executionData.budget.actual_amount) }}
            </span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 月度执行数据表格 -->
      <el-card shadow="hover" style="margin-top: 16px">
        <template #header>
          <span>月度执行明细</span>
        </template>
        <el-table :data="executionData.monthly_executions" stripe border>
          <el-table-column label="月份" width="100">
            <template #default="{ row }">{{ row.month }}月</template>
          </el-table-column>
          <el-table-column label="预算金额" width="150" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.budget_amount) }}</template>
          </el-table-column>
          <el-table-column label="实际金额" width="150" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.actual_amount) }}</template>
          </el-table-column>
          <el-table-column label="执行率" width="200">
            <template #default="{ row }">
              <el-progress
                :percentage="Math.min(row.used_percentage || 0, 100)"
                :color="progressColor(row.used_percentage)"
                :format="() => (row.used_percentage || 0) + '%'"
              />
            </template>
          </el-table-column>
          <el-table-column label="差异" width="150" align="right">
            <template #default="{ row }">
              <span :style="{ color: row.actual_amount > row.budget_amount ? '#f56c6c' : '#67c23a' }">
                ¥{{ formatMoney(row.actual_amount - row.budget_amount) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!executionData.monthly_executions || executionData.monthly_executions.length === 0" description="暂无月度执行数据" />
      </el-card>

      <!-- 趋势图表 -->
      <el-card shadow="hover" style="margin-top: 16px">
        <template #header>
          <span>预算执行趋势</span>
        </template>
        <div v-if="executionData.trend && executionData.trend.length > 0" ref="chartRef" style="width: 100%; height: 400px"></div>
        <el-empty v-else description="暂无趋势数据" />
      </el-card>

      <!-- 累计趋势表格 -->
      <el-card v-if="executionData.trend && executionData.trend.length > 0" shadow="hover" style="margin-top: 16px">
        <template #header>
          <span>累计趋势数据</span>
        </template>
        <el-table :data="executionData.trend" stripe border>
          <el-table-column label="月份" width="100">
            <template #default="{ row }">{{ row.month }}月</template>
          </el-table-column>
          <el-table-column label="月度预算" width="150" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.budget) }}</template>
          </el-table-column>
          <el-table-column label="月度实际" width="150" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.actual) }}</template>
          </el-table-column>
          <el-table-column label="累计实际" width="150" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.cumulative) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 预警管理 -->
      <el-card shadow="hover" style="margin-top: 16px">
        <template #header>
          <div class="section-header">
            <span>预警管理</span>
            <el-button type="primary" size="small" @click="showAlertDialog">
              <el-icon><Plus /></el-icon>添加预警
            </el-button>
          </div>
        </template>
        <el-table :data="alerts" v-loading="alertLoading" stripe border>
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
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_triggered ? 'danger' : 'success'" size="small">
                {{ row.is_triggered ? '已触发' : '正常' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="triggered_at" label="触发时间" width="180">
            <template #default="{ row }">
              {{ row.triggered_at || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" size="small" @click="handleDeleteAlert(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!alertLoading && alerts.length === 0" description="暂无预警设置" />
      </el-card>

      <!-- 备注管理 -->
      <el-card shadow="hover" style="margin-top: 16px">
        <template #header>
          <div class="section-header">
            <span>备注管理</span>
            <el-button type="primary" size="small" @click="showNoteDialog">
              <el-icon><Plus /></el-icon>添加备注
            </el-button>
          </div>
        </template>
        <el-table :data="notes" v-loading="noteLoading" stripe border>
          <el-table-column prop="content" label="备注内容" min-width="300" />
          <el-table-column prop="created_by" label="创建人" width="120" />
          <el-table-column prop="created_at" label="创建时间" width="180" />
        </el-table>
        <el-empty v-if="!noteLoading && notes.length === 0" description="暂无备注" />
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="预算数据不存在" />

    <!-- 添加预警对话框 -->
    <el-dialog v-model="alertDialogVisible" title="添加预警" width="450px" :close-on-click-modal="false">
      <el-form ref="alertFormRef" :model="alertFormData" :rules="alertFormRules" label-width="100px">
        <el-form-item label="预警类型" prop="alert_type">
          <el-select v-model="alertFormData.alert_type" style="width: 100%">
            <el-option label="超支预警" value="overspend" />
            <el-option label="阈值预警" value="threshold" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发阈值" prop="threshold_percentage">
          <el-input-number
            v-model="alertFormData.threshold_percentage"
            :min="1"
            :max="200"
            style="width: 100%"
          >
            <template #suffix>%</template>
          </el-input-number>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="alertDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="alertSubmitting" @click="handleAlertSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 添加备注对话框 -->
    <el-dialog v-model="noteDialogVisible" title="添加备注" width="450px" :close-on-click-modal="false">
      <el-form ref="noteFormRef" :model="noteFormData" :rules="noteFormRules" label-width="80px">
        <el-form-item label="备注内容" prop="content">
          <el-input
            v-model="noteFormData.content"
            type="textarea"
            :rows="4"
            placeholder="请输入备注内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="noteDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="noteSubmitting" @click="handleNoteSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  getBudgetExecution, getBudgetAlerts, createBudgetAlert, deleteBudgetAlert,
  getBudgetNotes, createBudgetNote
} from '@/api/budget'

const route = useRoute()
const router = useRouter()

// ===== 预算执行 =====
const loading = ref(false)
const executionData = ref(null)
const chartRef = ref(null)
let chartInstance = null

// ===== 预警 =====
const alertLoading = ref(false)
const alerts = ref([])
const alertDialogVisible = ref(false)
const alertSubmitting = ref(false)
const alertFormRef = ref(null)

const alertFormData = reactive({
  alert_type: 'threshold',
  threshold_percentage: 80
})

const alertFormRules = {
  alert_type: [{ required: true, message: '请选择预警类型', trigger: 'change' }],
  threshold_percentage: [{ required: true, message: '请输入触发阈值', trigger: 'blur' }]
}

// ===== 备注 =====
const noteLoading = ref(false)
const notes = ref([])
const noteDialogVisible = ref(false)
const noteSubmitting = ref(false)
const noteFormRef = ref(null)

const noteFormData = reactive({
  content: ''
})

const noteFormRules = {
  content: [{ required: true, message: '请输入备注内容', trigger: 'blur' }]
}

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
async function loadExecution() {
  const budgetId = route.params.id
  if (!budgetId) return

  loading.value = true
  try {
    const res = await getBudgetExecution(budgetId)
    executionData.value = res.data
    await nextTick()
    renderChart()
  } catch {
    executionData.value = null
  } finally {
    loading.value = false
  }
}

async function loadAlerts() {
  alertLoading.value = true
  try {
    const res = await getBudgetAlerts(false)
    alerts.value = (res.data || []).filter(a => a.budget_id === parseInt(route.params.id))
  } catch {
    alerts.value = []
  } finally {
    alertLoading.value = false
  }
}

async function loadNotes() {
  noteLoading.value = true
  try {
    const res = await getBudgetNotes(route.params.id)
    notes.value = res.data || []
  } catch {
    notes.value = []
  } finally {
    noteLoading.value = false
  }
}

// ===== 图表渲染 =====
function renderChart() {
  if (!chartRef.value || !executionData.value) return

  const trend = executionData.value.trend || []
  if (trend.length === 0) return

  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = echarts.init(chartRef.value)

  const months = trend.map(t => t.month + '月')
  const budgetData = trend.map(t => t.budget)
  const actualData = trend.map(t => t.actual)
  const cumulativeData = trend.map(t => t.cumulative)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['月度预算', '月度实际', '累计实际'],
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '12%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: months,
      boundaryGap: true
    },
    yAxis: [
      {
        type: 'value',
        name: '金额 (元)',
        axisLabel: {
          formatter: function (value) {
            if (value >= 10000) return (value / 10000).toFixed(1) + '万'
            return value
          }
        }
      }
    ],
    series: [
      {
        name: '月度预算',
        type: 'bar',
        data: budgetData,
        itemStyle: { color: '#409eff' },
        barWidth: '20%'
      },
      {
        name: '月度实际',
        type: 'bar',
        data: actualData,
        itemStyle: { color: '#67c23a' },
        barWidth: '20%'
      },
      {
        name: '累计实际',
        type: 'line',
        yAxisIndex: 0,
        data: cumulativeData,
        itemStyle: { color: '#e6a23c' },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 6
      }
    ]
  }

  chartInstance.setOption(option)
}

// ===== 预警操作 =====
function showAlertDialog() {
  alertFormData.alert_type = 'threshold'
  alertFormData.threshold_percentage = 80
  alertDialogVisible.value = true
}

async function handleAlertSubmit() {
  const valid = await alertFormRef.value.validate().catch(() => false)
  if (!valid) return

  alertSubmitting.value = true
  try {
    await createBudgetAlert(route.params.id, {
      alert_type: alertFormData.alert_type,
      threshold_percentage: alertFormData.threshold_percentage
    })
    ElMessage.success('预警创建成功')
    alertDialogVisible.value = false
    await loadAlerts()
  } catch (err) {
    const msg = err.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    alertSubmitting.value = false
  }
}

async function handleDeleteAlert(row) {
  try {
    await ElMessageBox.confirm('确定要删除此预警吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await deleteBudgetAlert(row.id)
    ElMessage.success('预警已删除')
    await loadAlerts()
  } catch (err) {
    const msg = err.response?.data?.detail || '删除失败'
    ElMessage.error(msg)
  }
}

// ===== 备注操作 =====
function showNoteDialog() {
  noteFormData.content = ''
  noteDialogVisible.value = true
}

async function handleNoteSubmit() {
  const valid = await noteFormRef.value.validate().catch(() => false)
  if (!valid) return

  noteSubmitting.value = true
  try {
    await createBudgetNote(route.params.id, { content: noteFormData.content })
    ElMessage.success('备注添加成功')
    noteDialogVisible.value = false
    await loadNotes()
  } catch (err) {
    const msg = err.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    noteSubmitting.value = false
  }
}

// ===== 窗口 resize 处理 =====
function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

// ===== 初始化 =====
onMounted(() => {
  loadExecution()
  loadAlerts()
  loadNotes()
  window.addEventListener('resize', handleResize)
})

// 清理
watch(() => route.params.id, () => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  loadExecution()
  loadAlerts()
  loadNotes()
})
</script>

<style scoped>
.budget-execution {
  padding: 0;
}

.page-header {
  margin-bottom: 16px;
}

.info-card {
  margin-bottom: 0;
}

.info-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.info-title {
  font-size: 16px;
  font-weight: 600;
}

.amount {
  font-weight: 600;
  font-size: 15px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>