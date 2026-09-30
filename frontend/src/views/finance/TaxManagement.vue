<template>
  <div class="tax-management">
    <!-- 截止提醒横幅 -->
    <el-alert
      v-if="urgentDeadlines.length > 0"
      type="error"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>
        <div class="deadline-banner">
          <span class="deadline-banner-title">申报截止提醒</span>
          <span class="deadline-banner-content">
            <span v-for="(item, idx) in urgentDeadlines" :key="idx" class="deadline-item">
              {{ item.tax_type }}（{{ item.period }}）截止 {{ item.deadline_date }}
              <template v-if="item.remaining_amount > 0">
                未缴 {{ formatMoney(item.remaining_amount) }}
              </template>
              <template v-if="idx < urgentDeadlines.length - 1">；</template>
            </span>
          </span>
        </div>
      </template>
    </el-alert>

    <!-- 操作栏 -->
    <el-card shadow="never" class="toolbar-card">
      <el-form :inline="true" :model="filters" size="default">
        <el-form-item label="所属期间">
          <el-date-picker
            v-model="filters.period"
            type="month"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
            clearable
            @change="handleFilterChange"
          />
        </el-form-item>
        <el-form-item label="税种">
          <el-select v-model="filters.tax_type" placeholder="全部" clearable style="width: 140px" @change="handleFilterChange">
            <el-option label="增值税" value="增值税" />
            <el-option label="企业所得税" value="企业所得税" />
            <el-option label="附加税" value="附加税" />
            <el-option label="印花税" value="印花税" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px" @change="handleFilterChange">
            <el-option label="待计算" value="pending" />
            <el-option label="已计算" value="calculated" />
            <el-option label="已缴纳" value="paid" />
            <el-option label="逾期" value="overdue" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            @change="handleFilterChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchRecords">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="success" @click="showCalculateDialog">计算税费</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 税务记录表格 -->
    <el-card shadow="never" style="margin-top: 16px">
      <el-table :data="records" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="tax_type" label="税种" width="120" />
        <el-table-column prop="tax_period" label="期间" width="100" />
        <el-table-column label="应纳税基数" min-width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.taxable_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="税率" width="90" align="center">
          <template #default="{ row }">
            {{ (row.tax_rate * 100).toFixed(2) }}%
          </template>
        </el-table-column>
        <el-table-column label="应纳税额" min-width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.tax_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="已缴纳税额" min-width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.paid_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="未缴纳税额" min-width="140" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.remaining_amount > 0 }">
              {{ formatMoney(row.remaining_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="截止日期" width="110" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.status === 'overdue' }">
              {{ row.due_date || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="180" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'calculated' || row.status === 'overdue'"
              type="primary" size="small" link
              @click="handlePay(row)"
            >
              标记已缴
            </el-button>
            <el-button
              v-if="row.status !== 'paid'"
              size="small" link
              @click="handleEdit(row)"
            >
              调整
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.page_size"
          :total="pagination.total"
          layout="total, prev, pager, next"
          @current-change="fetchRecords"
        />
      </div>

      <el-empty v-if="!loading && records.length === 0" description="暂无税务记录" :image-size="80" />
    </el-card>

    <!-- 计算税费对话框 -->
    <el-dialog v-model="calculateVisible" title="计算税费" width="450px">
      <el-form :model="calculateForm" label-width="100px">
        <el-form-item label="税种" required>
          <el-select v-model="calculateForm.tax_type" placeholder="选择税种" style="width: 100%">
            <el-option label="增值税" value="增值税" />
            <el-option label="企业所得税" value="企业所得税" />
            <el-option label="附加税" value="附加税" />
            <el-option label="印花税" value="印花税" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属期间" required>
          <el-date-picker
            v-model="calculateForm.period"
            type="month"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="税率">
          <el-input-number v-model="calculateForm.tax_rate" :precision="4" :min="0" :max="1" :step="0.01" style="width: 100%" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">留空使用默认税率</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="calculateVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCalculate" :loading="calculating">开始计算</el-button>
      </template>
    </el-dialog>

    <!-- 标记已缴对话框 -->
    <el-dialog v-model="payVisible" title="标记已缴" width="450px">
      <el-form :model="payForm" label-width="100px">
        <el-form-item label="税种">
          <span>{{ payForm.tax_type }}</span>
        </el-form-item>
        <el-form-item label="应纳税额">
          <span class="amount-text">{{ formatMoney(payForm.tax_amount) }}</span>
        </el-form-item>
        <el-form-item label="已缴金额">
          <span class="amount-text">{{ formatMoney(payForm.current_paid) }}</span>
        </el-form-item>
        <el-form-item label="实缴金额" required>
          <el-input-number v-model="payForm.paid_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="缴纳日期">
          <el-date-picker v-model="payForm.paid_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPay" :loading="paying">确认缴纳</el-button>
      </template>
    </el-dialog>

    <!-- 手动调整对话框 -->
    <el-dialog v-model="editVisible" title="手动调整" width="500px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="税种">
          <el-input :model-value="editForm.tax_type" disabled />
        </el-form-item>
        <el-form-item label="计税基数">
          <el-input-number v-model="editForm.taxable_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="税率">
          <el-input-number v-model="editForm.tax_rate" :precision="4" :min="0" :max="1" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="应纳税额">
          <el-input-number v-model="editForm.tax_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit" :loading="editing">确认调整</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTaxRecords, calculateTax, payTax, updateTaxRecord, getTaxDeadlines } from '@/api/tax'

const records = ref([])
const loading = ref(false)
const urgentDeadlines = ref([])

const filters = reactive({
  tax_type: '',
  period: '',
  status: '',
  dateRange: null,
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const calculateVisible = ref(false)
const calculating = ref(false)
const calculateForm = reactive({
  tax_type: '增值税',
  period: '',
  tax_rate: null,
})

const payVisible = ref(false)
const paying = ref(false)
const payForm = reactive({
  id: null,
  tax_type: '',
  tax_amount: 0,
  current_paid: 0,
  paid_amount: 0,
  paid_date: new Date().toISOString().slice(0, 10),
})

const editVisible = ref(false)
const editing = ref(false)
const editForm = reactive({
  id: null,
  tax_type: '',
  tax_amount: 0,
  taxable_amount: 0,
  tax_rate: 0,
  notes: '',
})

function formatMoney(val) {
  if (val == null || val === '') return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function statusTagType(status) {
  const map = { pending: 'info', calculated: '', paid: 'success', overdue: 'danger' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { pending: '待计算', calculated: '已计算', paid: '已缴纳', overdue: '逾期' }
  return map[status] || status
}

async function fetchDeadlines() {
  try {
    const res = await getTaxDeadlines()
    const items = res.data.items || []
    const now = new Date()
    const thirtyDaysLater = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000)
    urgentDeadlines.value = items.filter(item => {
      if (!item.deadline_date) return false
      const deadline = new Date(item.deadline_date)
      return deadline >= now && deadline <= thirtyDaysLater
    })
  } catch (e) {
    // handled by interceptor
  }
}

async function fetchRecords() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.tax_type) params.tax_type = filters.tax_type
    if (filters.period) params.period = filters.period
    if (filters.status) params.status = filters.status
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }
    const res = await getTaxRecords(params)
    records.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    records.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  pagination.page = 1
  fetchRecords()
}

function resetFilters() {
  filters.tax_type = ''
  filters.period = ''
  filters.status = ''
  filters.dateRange = null
  pagination.page = 1
  fetchRecords()
}

function showCalculateDialog() {
  calculateForm.tax_type = '增值税'
  calculateForm.period = ''
  calculateForm.tax_rate = null
  calculateVisible.value = true
}

async function submitCalculate() {
  if (!calculateForm.tax_type || !calculateForm.period) {
    ElMessage.warning('请选择税种和所属期间')
    return
  }
  calculating.value = true
  try {
    const data = {
      tax_type: calculateForm.tax_type,
      period: calculateForm.period,
    }
    if (calculateForm.tax_rate != null) {
      data.tax_rate = calculateForm.tax_rate
    }
    await calculateTax(data)
    ElMessage.success('税费计算完成')
    calculateVisible.value = false
    fetchRecords()
  } catch (e) {
    // handled by interceptor
  } finally {
    calculating.value = false
  }
}

function handlePay(row) {
  payForm.id = row.id
  payForm.tax_type = row.tax_type
  payForm.tax_amount = row.tax_amount
  payForm.current_paid = row.paid_amount || 0
  payForm.paid_amount = row.remaining_amount || 0
  payForm.paid_date = new Date().toISOString().slice(0, 10)
  payVisible.value = true
}

async function submitPay() {
  paying.value = true
  try {
    await payTax(payForm.id, {
      paid_amount: payForm.paid_amount,
      paid_date: payForm.paid_date || null,
    })
    ElMessage.success('标记成功')
    payVisible.value = false
    fetchRecords()
    fetchDeadlines()
  } catch (e) {
    // handled by interceptor
  } finally {
    paying.value = false
  }
}

function handleEdit(row) {
  editForm.id = row.id
  editForm.tax_type = row.tax_type
  editForm.tax_amount = row.tax_amount || 0
  editForm.taxable_amount = row.taxable_amount || 0
  editForm.tax_rate = row.tax_rate || 0
  editForm.notes = row.notes || ''
  editVisible.value = true
}

async function submitEdit() {
  editing.value = true
  try {
    await updateTaxRecord(editForm.id, {
      tax_amount: editForm.tax_amount,
      taxable_amount: editForm.taxable_amount,
      tax_rate: editForm.tax_rate,
      notes: editForm.notes || null,
    })
    ElMessage.success('调整成功')
    editVisible.value = false
    fetchRecords()
  } catch (e) {
    // handled by interceptor
  } finally {
    editing.value = false
  }
}

onMounted(() => {
  fetchDeadlines()
  fetchRecords()
})
</script>

<style scoped>
.tax-management {
  max-width: 1400px;
}

.deadline-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.deadline-banner-title {
  font-weight: 700;
  white-space: nowrap;
  font-size: 14px;
}

.deadline-banner-content {
  font-size: 13px;
  line-height: 1.6;
}

.deadline-item {
  white-space: nowrap;
}

.toolbar-card {
  margin-bottom: 0;
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.text-danger {
  color: #f56c6c;
  font-weight: 600;
}

.amount-text {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  font-size: 15px;
}
</style>