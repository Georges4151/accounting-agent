<template>
  <div class="reconciliation-list">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>应收应付核销</span>
          <div class="header-actions">
            <el-button type="primary" @click="showCreateDialog">
              <el-icon><Plus /></el-icon>
              新增记录
            </el-button>
            <el-button
              type="warning"
              :disabled="selectedRows.length === 0"
              @click="handleBatchWriteOff"
            >
              <el-icon><Check /></el-icon>
              批量核销
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选区 -->
      <div class="filter-bar">
        <el-radio-group v-model="filters.reconciliation_type" @change="handleFilterChange" size="small">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="ar">应收</el-radio-button>
          <el-radio-button value="ap">应付</el-radio-button>
        </el-radio-group>
        <el-select
          v-model="filters.party_type"
          placeholder="往来方类型"
          clearable
          style="width: 130px; margin-left: 12px"
          @change="handleFilterChange"
        >
          <el-option label="客户" value="customer" />
          <el-option label="供应商" value="supplier" />
        </el-select>
        <el-select
          v-model="filters.status"
          placeholder="状态"
          clearable
          style="width: 130px; margin-left: 8px"
          @change="handleFilterChange"
        >
          <el-option label="未核销" value="pending" />
          <el-option label="部分核销" value="partial" />
          <el-option label="已核销" value="reconciled" />
        </el-select>
        <el-input
          v-model="filters.party_name"
          placeholder="搜索客户/供应商名称"
          clearable
          style="width: 220px; margin-left: 8px"
          @clear="handleFilterChange"
          @keyup.enter="handleFilterChange"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          style="margin-left: 8px"
          @change="handleFilterChange"
        />
      </div>

      <!-- 加载状态 -->
      <div v-if="loading && tableData.length === 0" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <!-- 空数据 -->
      <el-empty
        v-else-if="!loading && tableData.length === 0"
        description="暂无应收应付记录"
      />

      <!-- 表格 -->
      <el-table
        v-else
        :data="tableData"
        v-loading="loading"
        stripe
        style="margin-top: 16px"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="reconciliation_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.reconciliation_type === 'ar' ? 'success' : 'warning'" size="small">
              {{ row.reconciliation_type === 'ar' ? '应收' : '应付' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="party_type" label="往来方类别" width="100">
          <template #default="{ row }">
            {{ row.party_type === 'customer' ? '客户' : '供应商' }}
          </template>
        </el-table-column>
        <el-table-column prop="party_name" label="客户/供应商" min-width="150">
          <template #default="{ row }">
            <el-link type="primary" @click="goToStatement(row)">
              {{ row.party_name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="invoice_no" label="发票号" width="140" />
        <el-table-column prop="amount" label="金额" width="130" align="right">
          <template #default="{ row }">
            <span class="amount-cell">{{ formatMoney(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reconciled_amount" label="已核销" width="130" align="right">
          <template #default="{ row }">
            <span class="amount-cell">{{ formatMoney(row.reconciled_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="remaining_amount" label="未核销" width="130" align="right">
          <template #default="{ row }">
            <span class="amount-cell" :class="{ 'text-danger': row.remaining_amount > 0 }">
              {{ formatMoney(row.remaining_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'reconciled' ? 'success' : row.status === 'partial' ? 'warning' : 'info'"
              size="small"
            >
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status !== 'reconciled'"
              type="primary"
              link
              size="small"
              @click="openWriteOffDialog(row)"
            >
              <el-icon><Check /></el-icon>
              核销
            </el-button>
            <el-button type="primary" link size="small" @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-popconfirm
              title="确定要删除该记录吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button type="danger" link size="small">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div v-if="total > 0" class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="formDialogVisible"
      :title="isEditing ? '编辑核销记录' : '新增核销记录'"
      width="550px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-form-item label="核销类型" prop="reconciliation_type">
          <el-radio-group v-model="form.reconciliation_type">
            <el-radio value="ar">应收</el-radio>
            <el-radio value="ap">应付</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="往来方类型" prop="party_type">
          <el-radio-group v-model="form.party_type">
            <el-radio value="customer">客户</el-radio>
            <el-radio value="supplier">供应商</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="客户/供应商" prop="party_name">
          <el-input v-model="form.party_name" placeholder="请输入客户或供应商名称" />
        </el-form-item>
        <el-form-item label="编码" prop="party_code">
          <el-input v-model="form.party_code" placeholder="客户/供应商编码(选填)" />
        </el-form-item>
        <el-form-item label="发票号" prop="invoice_no">
          <el-input v-model="form.invoice_no" placeholder="发票号(选填)" />
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number
            v-model="form.amount"
            :min="0.01"
            :precision="2"
            :step="100"
            style="width: 100%"
            placeholder="请输入金额"
          />
        </el-form-item>
        <el-form-item label="到期日" prop="due_date">
          <el-date-picker
            v-model="form.due_date"
            type="date"
            placeholder="选择到期日"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注" prop="notes">
          <el-input
            v-model="form.notes"
            type="textarea"
            :rows="2"
            placeholder="备注信息(选填)"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="submitForm">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 核销对话框 -->
    <el-dialog
      v-model="writeOffDialogVisible"
      title="核销操作"
      width="480px"
      :close-on-click-modal="false"
    >
      <div v-if="writeOffTarget">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="类型">
            <el-tag :type="writeOffTarget.reconciliation_type === 'ar' ? 'success' : 'warning'" size="small">
              {{ writeOffTarget.reconciliation_type === 'ar' ? '应收' : '应付' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="往来方">{{ writeOffTarget.party_name }}</el-descriptions-item>
          <el-descriptions-item label="发票号">{{ writeOffTarget.invoice_no || '--' }}</el-descriptions-item>
          <el-descriptions-item label="到期日">{{ writeOffTarget.due_date || '--' }}</el-descriptions-item>
          <el-descriptions-item label="金额">{{ formatMoney(writeOffTarget.amount) }}</el-descriptions-item>
          <el-descriptions-item label="已核销">
            <span class="text-warning">{{ formatMoney(writeOffTarget.reconciled_amount) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="未核销" :span="2">
            <span class="text-danger">{{ formatMoney(writeOffTarget.remaining_amount) }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-form style="margin-top: 20px" label-width="100px">
          <el-form-item label="本次核销金额">
            <el-input-number
              v-model="writeOffAmount"
              :min="0.01"
              :max="writeOffTarget.remaining_amount"
              :precision="2"
              :step="100"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="writeOffDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="writeOffLoading" @click="executeWriteOff">
          确认核销
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量核销对话框 -->
    <el-dialog
      v-model="batchWriteOffDialogVisible"
      title="批量核销"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="未设置核销金额的记录将自动全额核销"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-table :data="batchWriteOffRows" stripe size="small">
        <el-table-column prop="party_name" label="往来方" min-width="120" />
        <el-table-column prop="reconciliation_type" label="类型" width="70">
          <template #default="{ row }">
            {{ row.reconciliation_type === 'ar' ? '应收' : '应付' }}
          </template>
        </el-table-column>
        <el-table-column prop="remaining_amount" label="未核销" width="120" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.remaining_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="本次核销" width="160">
          <template #default="{ row }">
            <el-input-number
              v-model="batchAmounts[row.id]"
              :min="0"
              :max="row.remaining_amount"
              :precision="2"
              :step="100"
              size="small"
              style="width: 140px"
              controls-position="right"
            />
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="batchWriteOffDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchWriteOffLoading" @click="executeBatchWriteOff">
          确认核销
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useBookStore } from '@/stores/book'
import {
  getReconciliations,
  createReconciliation,
  updateReconciliation,
  deleteReconciliation,
  writeOffReconciliation,
  batchWriteOff,
} from '@/api/reconciliation'
import { ElMessage } from 'element-plus'

const router = useRouter()
const bookStore = useBookStore()

// ===== 状态 =====
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const selectedRows = ref([])

const filters = reactive({
  reconciliation_type: '',
  party_type: '',
  status: '',
  party_name: '',
  dateRange: null,
})

const pagination = reactive({
  page: 1,
  page_size: 20,
})

// ===== 表单 =====
const formDialogVisible = ref(false)
const isEditing = ref(false)
const formLoading = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  reconciliation_type: 'ar',
  party_type: 'customer',
  party_name: '',
  party_code: '',
  invoice_no: '',
  amount: 0,
  due_date: null,
  notes: '',
})

const formRules = {
  reconciliation_type: [{ required: true, message: '请选择核销类型', trigger: 'change' }],
  party_type: [{ required: true, message: '请选择往来方类型', trigger: 'change' }],
  party_name: [{ required: true, message: '请输入客户/供应商名称', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
}

// ===== 核销 =====
const writeOffDialogVisible = ref(false)
const writeOffTarget = ref(null)
const writeOffAmount = ref(0)
const writeOffLoading = ref(false)

const batchWriteOffDialogVisible = ref(false)
const batchWriteOffRows = ref([])
const batchAmounts = ref({})
const batchWriteOffLoading = ref(false)

// ===== 生命周期 =====
onMounted(() => {
  loadData()
})

// ===== 数据加载 =====
async function loadData() {
  const bookId = bookStore.currentBookId
  if (!bookId) {
    ElMessage.warning('请先选择账套')
    return
  }

  loading.value = true
  try {
    const params = {
      book_id: bookId,
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.reconciliation_type) params.reconciliation_type = filters.reconciliation_type
    if (filters.party_type) params.party_type = filters.party_type
    if (filters.status) params.status = filters.status
    if (filters.party_name) params.party_name = filters.party_name
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }
    const res = await getReconciliations(params)
    tableData.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载数据失败')
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  pagination.page = 1
  loadData()
}

// ===== 选择 =====
function handleSelectionChange(rows) {
  selectedRows.value = rows
}

// ===== 创建/编辑 =====
function showCreateDialog() {
  isEditing.value = false
  editingId.value = null
  resetForm()
  formDialogVisible.value = true
}

function handleEdit(row) {
  isEditing.value = true
  editingId.value = row.id
  form.reconciliation_type = row.reconciliation_type
  form.party_type = row.party_type
  form.party_name = row.party_name
  form.party_code = row.party_code || ''
  form.invoice_no = row.invoice_no || ''
  form.amount = row.amount
  form.due_date = row.due_date
  form.notes = row.notes || ''
  formDialogVisible.value = true
}

function resetForm() {
  form.reconciliation_type = 'ar'
  form.party_type = 'customer'
  form.party_name = ''
  form.party_code = ''
  form.invoice_no = ''
  form.amount = 0
  form.due_date = null
  form.notes = ''
  if (formRef.value) {
    formRef.value.resetFields()
  }
}

async function submitForm() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  formLoading.value = true
  try {
    const data = {
      reconciliation_type: form.reconciliation_type,
      party_type: form.party_type,
      party_name: form.party_name,
      party_code: form.party_code || null,
      invoice_no: form.invoice_no || null,
      amount: form.amount,
      due_date: form.due_date || null,
      notes: form.notes || null,
    }
    if (isEditing.value) {
      await updateReconciliation(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createReconciliation(data)
      ElMessage.success('创建成功')
    }
    formDialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    formLoading.value = false
  }
}

// ===== 删除 =====
async function handleDelete(id) {
  try {
    await deleteReconciliation(id)
    ElMessage.success('删除成功')
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

// ===== 核销 =====
function openWriteOffDialog(row) {
  writeOffTarget.value = row
  writeOffAmount.value = row.remaining_amount
  writeOffDialogVisible.value = true
}

async function executeWriteOff() {
  if (!writeOffTarget.value) return
  writeOffLoading.value = true
  try {
    await writeOffReconciliation(writeOffTarget.value.id, {
      write_off_amount: writeOffAmount.value,
    })
    ElMessage.success('核销成功')
    writeOffDialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '核销失败')
  } finally {
    writeOffLoading.value = false
  }
}

// ===== 批量核销 =====
function handleBatchWriteOff() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择需要核销的记录')
    return
  }
  const pendingRows = selectedRows.value.filter(r => r.status !== 'reconciled')
  if (pendingRows.length === 0) {
    ElMessage.warning('所选记录均已核销完毕')
    return
  }
  batchWriteOffRows.value = pendingRows
  batchAmounts.value = {}
  pendingRows.forEach(r => {
    batchAmounts.value[r.id] = r.remaining_amount
  })
  batchWriteOffDialogVisible.value = true
}

async function executeBatchWriteOff() {
  batchWriteOffLoading.value = true
  try {
    const ids = batchWriteOffRows.value.map(r => r.id)
    const amounts = {}
    ids.forEach(id => {
      amounts[id] = batchAmounts.value[id] || 0
    })
    await batchWriteOff({ ids, write_off_amounts: amounts })
    ElMessage.success('批量核销完成')
    batchWriteOffDialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '批量核销失败')
  } finally {
    batchWriteOffLoading.value = false
  }
}

// ===== 跳转对账单 =====
function goToStatement(row) {
  router.push({
    path: '/finance/statement',
    query: {
      party_type: row.party_type,
      party_name: row.party_name,
    },
  })
}

// ===== 辅助函数 =====
function statusLabel(status) {
  const map = { pending: '未核销', partial: '部分核销', reconciled: '已核销' }
  return map[status] || status
}

function formatMoney(val) {
  if (val === null || val === undefined) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<style scoped>
.reconciliation-list {
  max-width: 100%;
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

.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.loading-container {
  padding: 20px 0;
}

.amount-cell {
  font-family: 'Courier New', monospace;
  font-weight: 500;
}

.text-danger {
  color: #f56c6c;
}

.text-warning {
  color: #e6a23c;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>