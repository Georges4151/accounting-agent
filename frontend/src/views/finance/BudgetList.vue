<template>
  <div class="budget-list">
    <!-- 汇总卡片 -->
    <el-row :gutter="16" class="summary-row">
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
          <div class="summary-label">执行进度</div>
          <div class="summary-value" :class="progressColor(summary.overall_percentage)">
            {{ summary.overall_percentage || 0 }}%
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
      <el-input
        v-model="filterAccount"
        placeholder="科目编码"
        style="width: 140px"
        clearable
        @change="loadBudgets"
      />
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>新建预算
      </el-button>
    </div>

    <!-- 预算列表 -->
    <el-table
      :data="budgets"
      v-loading="loading"
      stripe
      border
      style="width: 100%; margin-top: 16px"
      @row-click="goToExecution"
      row-class-name="clickable-row"
    >
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
            :percentage="Math.min(row.used_percentage || 0, 100)"
            :color="progressColor(row.used_percentage)"
            :format="() => (row.used_percentage || 0) + '%'"
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
          <el-button link type="primary" size="small" @click.stop="showEditDialog(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click.stop="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && budgets.length === 0" description="暂无预算数据" />

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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getBudgets, createBudget, updateBudget, deleteBudget, getBudgetSummary
} from '@/api/budget'

const router = useRouter()

// ===== 汇总数据 =====
const summary = reactive({
  total_budget: 0,
  total_actual: 0,
  overall_percentage: 0,
  alert_count: 0,
  budget_count: 0
})

// ===== 筛选条件 =====
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

// ===== 预算列表 =====
const loading = ref(false)
const budgets = ref([])

// ===== 对话框 =====
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
async function loadBudgets() {
  loading.value = true
  try {
    const params = { year: filterYear.value, month: filterMonth.value }
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

// ===== 预算操作 =====
function goToExecution(row) {
  router.push(`/finance/budget/${row.id}/execution`)
}

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

// ===== 初始化 =====
onMounted(() => {
  loadBudgets()
  loadSummary()
})
</script>

<style scoped>
.budget-list {
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

:deep(.clickable-row) {
  cursor: pointer;
}

:deep(.clickable-row:hover) {
  background-color: #f5f7fa;
}
</style>