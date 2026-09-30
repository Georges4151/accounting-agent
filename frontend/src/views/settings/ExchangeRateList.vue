<template>
  <div class="exchange-rate-list">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>汇率管理</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              添加汇率
            </el-button>
            <el-button type="success" @click="batchDialogVisible = true">
              <el-icon><Upload /></el-icon>
              批量导入
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="币种">
          <el-select v-model="filters.currency_code" placeholder="全部币种" clearable style="width: 150px">
            <el-option
              v-for="c in currencyOptions"
              :key="c.code"
              :label="`${c.code} (${c.name})`"
              :value="c.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <el-empty v-else-if="rates.length === 0" description="暂无汇率数据" />

      <template v-else>
        <el-table :data="rates" border stripe style="width: 100%">
          <el-table-column prop="currency_code" label="币种" width="100" />
          <el-table-column prop="rate_date" label="日期" width="130" />
          <el-table-column prop="rate" label="汇率" width="150">
            <template #default="{ row }">
              {{ row.rate.toFixed(8) }}
            </template>
          </el-table-column>
          <el-table-column prop="rate_type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="rateTypeColor(row.rate_type)" size="small">
                {{ rateTypeLabel(row.rate_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="handleDelete(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-container">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.page_size"
            :total="pagination.total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadRates"
            @current-change="loadRates"
          />
        </div>
      </template>
    </el-card>

    <!-- 添加汇率对话框 -->
    <el-dialog
      v-model="dialogVisible"
      title="添加汇率"
      width="480px"
      :close-on-click-modal="false"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="币种" prop="currency_code">
          <el-select v-model="form.currency_code" placeholder="选择币种" style="width: 100%">
            <el-option
              v-for="c in currencyOptions"
              :key="c.code"
              :label="`${c.code} (${c.name})`"
              :value="c.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="汇率日期" prop="rate_date">
          <el-date-picker
            v-model="form.rate_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="汇率" prop="rate">
          <el-input-number
            v-model="form.rate"
            :precision="8"
            :step="0.0001"
            :min="0"
            placeholder="1外币=?本位币"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="汇率类型" prop="rate_type">
          <el-select v-model="form.rate_type" style="width: 100%">
            <el-option label="中间价" value="middle" />
            <el-option label="买入价" value="buy" />
            <el-option label="卖出价" value="sell" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">添加</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog
      v-model="batchDialogVisible"
      title="批量导入汇率"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="每行一条汇率数据，格式: 币种代码,日期(YYYY-MM-DD),汇率,类型(middle/buy/sell)"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-input
        v-model="batchText"
        type="textarea"
        :rows="10"
        placeholder="USD,2024-01-15,7.1234,middle&#10;EUR,2024-01-15,7.8567,middle&#10;JPY,2024-01-15,0.0482,middle"
      />
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchSubmitting" @click="handleBatchImport">
          导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  getExchangeRates, createExchangeRate, batchImportRates, deleteExchangeRate
} from '@/api/currency'
import { getCurrencies } from '@/api/currency'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const batchSubmitting = ref(false)
const rates = ref([])
const currencyOptions = ref([])
const dialogVisible = ref(false)
const batchDialogVisible = ref(false)
const formRef = ref(null)
const dateRange = ref(null)

const filters = reactive({
  currency_code: '',
  start_date: '',
  end_date: ''
})

const form = reactive({
  currency_code: '',
  rate_date: '',
  rate: 1.0,
  rate_type: 'middle'
})

const rules = {
  currency_code: [{ required: true, message: '请选择币种', trigger: 'change' }],
  rate_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  rate: [{ required: true, message: '请输入汇率', trigger: 'blur' }]
}

const pagination = reactive({
  page: 1,
  page_size: 50,
  total: 0
})

const batchText = ref('')

onMounted(() => {
  loadCurrencies()
  loadRates()
})

async function loadCurrencies() {
  try {
    const res = await getCurrencies()
    currencyOptions.value = res.data.items || []
  } catch (e) {
    // ignore
  }
}

async function loadRates() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size
    }
    if (filters.currency_code) params.currency_code = filters.currency_code
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getExchangeRates(params)
    rates.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载汇率列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadRates()
}

function handleReset() {
  filters.currency_code = ''
  dateRange.value = null
  pagination.page = 1
  loadRates()
}

function handleAdd() {
  resetForm()
  dialogVisible.value = true
}

function resetForm() {
  form.currency_code = ''
  form.rate_date = ''
  form.rate = 1.0
  form.rate_type = 'middle'
  formRef.value?.resetFields()
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createExchangeRate({
      currency_code: form.currency_code,
      rate_date: form.rate_date,
      rate: form.rate,
      rate_type: form.rate_type
    })
    ElMessage.success('汇率添加成功')
    dialogVisible.value = false
    await loadRates()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  } finally {
    submitting.value = false
  }
}

async function handleBatchImport() {
  if (!batchText.value.trim()) {
    ElMessage.warning('请输入汇率数据')
    return
  }

  const lines = batchText.value.trim().split('\n').filter(l => l.trim())
  const rateItems = []
  const errors = []

  for (let i = 0; i < lines.length; i++) {
    const parts = lines[i].split(',').map(p => p.trim())
    if (parts.length < 3) {
      errors.push(`第${i + 1}行格式不正确`)
      continue
    }
    rateItems.push({
      currency_code: parts[0],
      rate_date: parts[1],
      rate: parseFloat(parts[2]),
      rate_type: parts[3] || 'middle'
    })
  }

  if (errors.length > 0) {
    ElMessage.warning(`有 ${errors.length} 行格式不正确，已跳过`)
  }

  if (rateItems.length === 0) {
    ElMessage.warning('没有有效数据')
    return
  }

  batchSubmitting.value = true
  try {
    const res = await batchImportRates({ rates: rateItems })
    ElMessage.success(res.data.message || '导入完成')
    batchDialogVisible.value = false
    batchText.value = ''
    await loadRates()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    batchSubmitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${row.currency_code} ${row.rate_date} 的汇率记录吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteExchangeRate(row.id)
    ElMessage.success('删除成功')
    await loadRates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

function rateTypeLabel(type) {
  const map = { middle: '中间价', buy: '买入价', sell: '卖出价' }
  return map[type] || type
}

function rateTypeColor(type) {
  const map = { middle: 'primary', buy: 'success', sell: 'warning' }
  return map[type] || 'info'
}
</script>

<style scoped>
.exchange-rate-list {
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
  gap: 8px;
}

.filter-form {
  margin-bottom: 16px;
}

.loading-container {
  padding: 20px 0;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>