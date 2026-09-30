<template>
  <div class="budget-manage">
    <el-tabs v-model="activeTab" type="border-card" @tab-change="handleTabChange">
      <!-- 预算编制 Tab -->
      <el-tab-pane label="预算编制" name="planning">
        <!-- 汇总卡片 -->
        <el-row :gutter="16" class="summary-row">
          <el-col :xs="24" :sm="8">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">预算总额</div>
              <div class="summary-value primary">¥{{ formatMoney(summary.total_budget) }}</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">实际支出</div>
              <div class="summary-value warning">¥{{ formatMoney(summary.total_actual) }}</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">执行进度</div>
              <div class="summary-value" :class="progressColor(summary.overall_percentage)">
                {{ summary.overall_percentage }}%
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 筛选栏 -->
        <div class="filter-bar">
          <el-select v-model="filterYear" placeholder="选择年份" style="width: 120px" @change="loadBudgets">
            <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
          </el-select>
          <el-select v-model="filterMonth" placeholder="月份" style="width: 100px" clearable @change="loadBudgets">
            <el-option label="全年" :value="0" />
            <el-option v-for="m in 12" :key="m" :label="m + '月'" :value="m" />
          </el-select>
          <el-select v-model="filterStatus" placeholder="状态" style="width: 100px" clearable @change="loadBudgets">
            <el-option label="活跃" value="active" />
            <el-option label="已关闭" value="closed" />
          </el-select>
          <el-input v-model="filterAccount" placeholder="科目编码" style="width: 140px" clearable @change="loadBudgets" />
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>新建预算
          </el-button>
        </div>

        <!-- 预算列表 -->
        <el-table :data="budgets" v-loading="loading" stripe border style="width: 100%; margin-top: 16px">
          <el-table-column prop="account_code" label="科目编码" width="120" />
          <el-table-column prop="account_name" label="科目名称" width="150" />
          <el-table-column prop="name" label="预算名称" min-width="150" />
          <el-table-column prop="year" label="年份" width="80" />
          <el-table-column label="月份" width="80">
            <template #default="{ row }">
              {{ row.month === 0 ? '全年' : row.month + '月' }}
            </template>
          </el-table-column>
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
          <el-table-column label="使用进度" width="200">
            <template #default="{ row }">
              <el-progress
                :percentage="Math.min(row.used_percentage, 100)"
                :color="progressColor(row.used_percentage)"
                :format="() => row.used_percentage + '%'"
              />
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status === 'active' ? '活跃' : '关闭' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 预算执行 Tab -->
      <el-tab-pane label="预算执行" name="execution">
        <div class="execution-header">
          <el-select v-model="execBudgetId" placeholder="选择预算" style="width: 320px" @change="loadExecution">
            <el-option
              v-for="b in budgets"
              :key="b.id"
              :label="b.name + ' - ' + b.account_name"
              :value="b.id"
            />
          </el-select>
        </div>

        <template v-if="executionData">
          <!-- 执行概览 -->
          <el-row :gutter="16" style="margin-top: 16px">
            <el-col :xs="24" :sm="6">
              <el-card shadow="hover" class="exec-card">
                <div class="exec-label">预算金额</div>
                <div class="exec-value">¥{{ formatMoney(executionData.budget.budget_amount) }}</div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="6">
              <el-card shadow="hover" class="exec-card">
                <div class="exec-label">实际支出</div>
                <div class="exec-value">¥{{ formatMoney(executionData.budget.actual_amount) }}</div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="6">
              <el-card shadow="hover" class="exec-card">
                <div class="exec-label">执行进度</div>
                <div class="exec-value">{{ executionData.budget.used_percentage }}%</div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="6">
              <el-card shadow="hover" class="exec-card">
                <div class="exec-label">剩余预算</div>
                <div class="exec-value">
                  ¥{{ formatMoney(executionData.budget.budget_amount - executionData.budget.actual_amount) }}
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 月度执行表格 -->
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
                    :percentage="Math.min(row.used_percentage, 100)"
                    :color="progressColor(row.used_percentage)"
                    :format="() => row.used_percentage + '%'"
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
          </el-card>

          <!-- 趋势数据 -->
          <el-card shadow="hover" style="margin-top: 16px">
            <template #header>
              <span>累计趋势</span>
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
        </template>
        <el-empty v-else description="请选择预算查看执行详情" />
      </el-tab-pane>

      <!-- 预警设置 Tab -->
      <el-tab-pane label="预警设置" name="alerts">
        <div class="alert-header">
          <el-button type="primary" @click="showAlertDialog">
            <el-icon><Plus /></el-icon>添加预警
          </el-button>
        </div>

        <el-table :data="alerts" v-loading="alertLoading" stripe border style="margin-top: 16px">
          <el-table-column prop="budget_name" label="预算名称" min-width="150" />
          <el-table-column prop="account_code" label="科目编码" width="120" />
          <el-table-column prop="account_name" label="科目名称" width="150" />
          <el-table-column label="预算金额" width="140" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.budget_amount) }}</template>
          </el-table-column>
          <el-table-column label="实际金额" width="140" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.actual_amount) }}</template>
          </el-table-column>
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
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_triggered ? 'danger' : 'success'" size="small">
                {{ row.is_triggered ? '已触发' : '正常' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="触发时间" width="180">
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
      </el-tab-pane>
    </el-tabs>

    <!-- 新建/编辑预算对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingBudget ? '编辑预算' : '新建预算'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="预算名称" prop="name">
          <el-input v-model="formData.name" placeholder="如：2026年度预算" />
        </el-form-item>
        <el-form-item label="预算年份" prop="year">
          <el-input-number v-model="formData.year" :min="2000" :max="2099" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预算月份" prop="month">
          <el-select v-model="formData.month" style="width: 100%">
            <el-option label="全年" :value="0" />
            <el-option v-for="m in 12" :key="m" :label="m + '月'" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目编码" prop="account_code">
          <el-input v-model="formData.account_code" placeholder="如：6601" />
        </el-form-item>
        <el-form-item label="科目名称" prop="account_name">
          <el-input v-model="formData.account_name" placeholder="如：销售费用" />
        </el-form-item>
        <el-form-item label="预算金额" prop="budget_amount">
          <el-input-number
            v-model="formData.budget_amount"
            :min="0"
            :precision="2"
            :step="1000"
            style="width: 100%"
            placeholder="请输入预算金额"
          />
        </el-form-item>
        <el-form-item v-if="editingBudget" label="状态" prop="status">
          <el-select v-model="formData.status" style="width: 100%">
            <el-option label="活跃" value="active" />
            <el-option label="关闭" value="closed" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 添加预警对话框 -->
    <el-dialog v-model="alertDialogVisible" title="添加预警" width="450px" :close-on-click-modal="false">
      <el-form ref="alertFormRef" :model="alertFormData" :rules="alertFormRules" label-width="100px">
        <el-form-item label="选择预算" prop="budget_id">
          <el-select v-model="alertFormData.budget_id" placeholder="选择预算" style="width: 100%" filterable>
            <el-option
              v-for="b in budgets"
              :key="b.id"
              :label="b.name + ' - ' + b.account_name"
              :value="b.id"
            />
          </el-select>
        </el-form-item>
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getBudgets, createBudget, updateBudget, deleteBudget,
  getBudgetExecution, getBudgetAlerts, createBudgetAlert, deleteBudgetAlert,
  getBudgetSummary
} from '@/api/budget'

// ===== Tab 状态 =====
const activeTab = ref('planning')

// ===== 预算编制 =====
const loading = ref(false)
const budgets = ref([])
const summary = reactive({
  total_budget: 0,
  total_actual: 0,
  overall_percentage: 0,
  alert_count: 0,
  budget_count: 0
})

const filterYear = ref(new Date().getFullYear())
const filterMonth = ref(0)
const filterStatus = ref('')
const filterAccount = ref('')

const yearOptions = computed(() => {
  const current = new Date().getFullYear()
  const years = []
  for (let i = current - 5; i <= current + 2; i++) {
    years.push(i)
  }
  return years
})

const dialogVisible = ref(false)
const editingBudget = ref(null)
const submitting = ref(false)
const formRef = ref(null)

const formData = reactive({
  name: '',
  year: new Date().getFullYear(),
  month: 0,
  account_code: '',
  account_name: '',
  budget_amount: 0,
  status: 'active'
})

const formRules = {
  name: [{ required: true, message: '请输入预算名称', trigger: 'blur' }],
  year: [{ required: true, message: '请选择预算年份', trigger: 'change' }],
  account_code: [{ required: true, message: '请输入科目编码', trigger: 'blur' }],
  account_name: [{ required: true, message: '请输入科目名称', trigger: 'blur' }],
  budget_amount: [{ required: true, message: '请输入预算金额', trigger: 'blur' }]
}

// ===== 预算执行 =====
const execBudgetId = ref(null)
const executionData = ref(null)

// ===== 预警设置 =====
const alertLoading = ref(false)
const alerts = ref([])
const alertDialogVisible = ref(false)
const alertSubmitting = ref(false)
const alertFormRef = ref(null)

const alertFormData = reactive({
  budget_id: null,
  alert_type: 'threshold',
  threshold_percentage: 80
})

const alertFormRules = {
  budget_id: [{ required: true, message: '请选择预算', trigger: 'change' }],
  alert_type: [{ required: true, message: '请选择预警类型', trigger: 'change' }],
  threshold_percentage: [{ required: true, message: '请输入触发阈值', trigger: 'blur' }]
}

// ===== 工具函数 =====
function formatMoney(value) {
  if (value == null || isNaN(value)) return '0.00'
  return Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function progressColor(percentage) {
  if (percentage >= 100) return '#f56c6c'
  if (percentage >= 80) return '#e6a23c'
  return '#67c23a'
}

// ===== 数据加载 =====
async function loadBudgets() {
  loading.value = true
  try {
    const params = {
      year: filterYear.value,
      month: filterMonth.value
    }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterAccount.value) params.account_code = filterAccount.value

    const res = await getBudgets(params)
    budgets.value = res.data || []
  } catch {
    budgets.value = []
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const res = await getBudgetSummary(filterYear.value)
    Object.assign(summary, res.data)
  } catch {
    // 静默处理
  }
}

async function loadExecution() {
  if (!execBudgetId.value) {
    executionData.value = null
    return
  }
  try {
    const res = await getBudgetExecution(execBudgetId.value)
    executionData.value = res.data
  } catch {
    executionData.value = null
  }
}

async function loadAlerts() {
  alertLoading.value = true
  try {
    const res = await getBudgetAlerts(false)
    alerts.value = res.data || []
  } catch {
    alerts.value = []
  } finally {
    alertLoading.value = false
  }
}

// ===== 预算操作 =====
function showCreateDialog() {
  editingBudget.value = null
  formData.name = ''
  formData.year = new Date().getFullYear()
  formData.month = 0
  formData.account_code = ''
  formData.account_name = ''
  formData.budget_amount = 0
  formData.status = 'active'
  dialogVisible.value = true
}

function showEditDialog(row) {
  editingBudget.value = row
  formData.name = row.name
  formData.year = row.year
  formData.month = row.month
  formData.account_code = row.account_code
  formData.account_name = row.account_name
  formData.budget_amount = row.budget_amount
  formData.status = row.status
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      name: formData.name,
      year: formData.year,
      month: formData.month,
      account_code: formData.account_code,
      account_name: formData.account_name,
      budget_amount: formData.budget_amount
    }

    if (editingBudget.value) {
      payload.status = formData.status
      await updateBudget(editingBudget.value.id, payload)
      ElMessage.success('预算更新成功')
    } else {
      await createBudget(payload)
      ElMessage.success('预算创建成功')
    }
    dialogVisible.value = false
    await loadBudgets()
    await loadSummary()
  } catch (err) {
    const msg = err.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定要删除预算"${row.name}"吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await deleteBudget(row.id)
    ElMessage.success('预算已删除')
    await loadBudgets()
    await loadSummary()
  } catch (err) {
    const msg = err.response?.data?.detail || '删除失败'
    ElMessage.error(msg)
  }
}

// ===== 预警操作 =====
function showAlertDialog() {
  alertFormData.budget_id = null
  alertFormData.alert_type = 'threshold'
  alertFormData.threshold_percentage = 80
  alertDialogVisible.value = true
}

async function handleAlertSubmit() {
  const valid = await alertFormRef.value.validate().catch(() => false)
  if (!valid) return

  alertSubmitting.value = true
  try {
    await createBudgetAlert(alertFormData.budget_id, {
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

// ===== Tab 切换 =====
function handleTabChange(tabName) {
  if (tabName === 'planning') {
    loadBudgets()
    loadSummary()
  } else if (tabName === 'execution') {
    loadBudgets()
  } else if (tabName === 'alerts') {
    loadAlerts()
  }
}

// ===== 初始化 =====
onMounted(() => {
  loadBudgets()
  loadSummary()
})
</script>

<style scoped>
.budget-manage {
  padding: 0;
}

.summary-row {
  margin-bottom: 16px;
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

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.execution-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.exec-card {
  text-align: center;
}

.exec-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.exec-value {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>