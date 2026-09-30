<template>
  <div class="tax-records">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-form :inline="true" :model="filters" size="default">
        <el-form-item label="税种">
          <el-select v-model="filters.tax_type" placeholder="全部" clearable style="width: 140px">
            <el-option label="增值税" value="增值税" />
            <el-option label="企业所得税" value="企业所得税" />
            <el-option label="附加税" value="附加税" />
            <el-option label="印花税" value="印花税" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="期间">
          <el-date-picker
            v-model="filters.period"
            type="month"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
            clearable
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="待计算" value="pending" />
            <el-option label="已计算" value="calculated" />
            <el-option label="已缴纳" value="paid" />
            <el-option label="逾期" value="overdue" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchRecords">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 数据表格 -->
    <el-table :data="records" v-loading="loading" stripe border style="width: 100%">
      <el-table-column prop="tax_type" label="税种" width="120" />
      <el-table-column prop="tax_period" label="所属期间" width="100" />
      <el-table-column label="计税基数" width="150" align="right">
        <template #default="{ row }">
          {{ formatNum(row.taxable_amount) }}
        </template>
      </el-table-column>
      <el-table-column label="税率" width="90" align="center">
        <template #default="{ row }">
          {{ (row.tax_rate * 100).toFixed(2) }}%
        </template>
      </el-table-column>
      <el-table-column label="应纳税额" width="140" align="right">
        <template #default="{ row }">
          {{ formatNum(row.tax_amount) }}
        </template>
      </el-table-column>
      <el-table-column label="已缴税额" width="140" align="right">
        <template #default="{ row }">
          {{ formatNum(row.paid_amount) }}
        </template>
      </el-table-column>
      <el-table-column label="未缴税额" width="140" align="right">
        <template #default="{ row }">
          <span :class="{ 'text-danger': row.remaining_amount > 0 }">
            {{ formatNum(row.remaining_amount) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="due_date" label="截止日期" width="110" />
      <el-table-column label="操作" min-width="160" align="center" fixed="right">
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

    <!-- 分页 -->
    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="pagination.page"
        :page-size="pagination.page_size"
        :total="pagination.total"
        layout="total, prev, pager, next"
        @current-change="fetchRecords"
      />
    </div>

    <!-- 标记已缴对话框 -->
    <el-dialog v-model="payVisible" title="标记已缴" width="400px">
      <el-form :model="payForm" label-width="100px">
        <el-form-item label="税种">
          <span>{{ payForm.tax_type }}</span>
        </el-form-item>
        <el-form-item label="应纳税额">
          <span class="amount">{{ formatNum(payForm.tax_amount) }}</span>
        </el-form-item>
        <el-form-item label="已缴金额">
          <span class="amount">{{ formatNum(payForm.current_paid) }}</span>
        </el-form-item>
        <el-form-item label="实缴金额">
          <el-input-number v-model="payForm.paid_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="缴纳日期">
          <el-date-picker v-model="payForm.paid_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPay">确认缴纳</el-button>
      </template>
    </el-dialog>

    <!-- 编辑对话框 -->
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
        <el-button type="primary" @click="submitEdit">确认调整</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTaxRecords, payTax, updateTaxRecord } from '@/api/tax'

const records = ref([])
const loading = ref(false)

const filters = reactive({
  tax_type: '',
  period: '',
  status: '',
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const payVisible = ref(false)
const payForm = reactive({
  id: null,
  tax_type: '',
  tax_amount: 0,
  current_paid: 0,
  paid_amount: 0,
  paid_date: new Date().toISOString().slice(0, 10),
})

const editVisible = ref(false)
const editForm = reactive({
  id: null,
  tax_type: '',
  tax_amount: 0,
  taxable_amount: 0,
  tax_rate: 0,
  notes: '',
})

function formatNum(val) {
  if (val == null) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function statusTag(status) {
  const map = { pending: 'info', calculated: 'warning', paid: 'success', overdue: 'danger' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { pending: '待计算', calculated: '已计算', paid: '已缴纳', overdue: '逾期' }
  return map[status] || status
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
    const res = await getTaxRecords(params)
    records.value = res.data.items
    pagination.total = res.data.total
  } catch (e) {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.tax_type = ''
  filters.period = ''
  filters.status = ''
  pagination.page = 1
  fetchRecords()
}

function handlePay(row) {
  payForm.id = row.id
  payForm.tax_type = row.tax_type
  payForm.tax_amount = row.tax_amount
  payForm.current_paid = row.paid_amount
  payForm.paid_amount = row.remaining_amount
  payForm.paid_date = new Date().toISOString().slice(0, 10)
  payVisible.value = true
}

async function submitPay() {
  try {
    await payTax(payForm.id, {
      paid_amount: payForm.paid_amount,
      paid_date: payForm.paid_date || null,
    })
    ElMessage.success('标记成功')
    payVisible.value = false
    fetchRecords()
  } catch (e) {
    // handled by interceptor
  }
}

function handleEdit(row) {
  editForm.id = row.id
  editForm.tax_type = row.tax_type
  editForm.tax_amount = row.tax_amount
  editForm.taxable_amount = row.taxable_amount
  editForm.tax_rate = row.tax_rate
  editForm.notes = row.notes || ''
  editVisible.value = true
}

async function submitEdit() {
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
  }
}

onMounted(() => {
  fetchRecords()
})
</script>

<style scoped>
.tax-records {
  padding: 8px 0;
}
.filter-bar {
  margin-bottom: 16px;
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
.amount {
  font-family: 'Courier New', monospace;
  font-weight: 600;
}
</style>