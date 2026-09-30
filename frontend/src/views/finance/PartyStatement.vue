<template>
  <div class="party-statement">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>客户/供应商对账单</span>
          <div class="header-actions">
            <el-button type="primary" @click="handlePrint" :disabled="!statementData">
              <el-icon><Printer /></el-icon>
              打印
            </el-button>
          </div>
        </div>
      </template>

      <!-- 查询条件 -->
      <div class="filter-bar">
        <el-select
          v-model="filters.party_type"
          placeholder="往来方类型"
          style="width: 120px"
          @change="handlePartyTypeChange"
        >
          <el-option label="客户" value="customer" />
          <el-option label="供应商" value="supplier" />
        </el-select>
        <el-select
          v-model="filters.party_name"
          placeholder="选择客户/供应商"
          filterable
          clearable
          style="width: 220px; margin-left: 12px"
          :loading="partyNamesLoading"
        >
          <el-option
            v-for="p in partyNames"
            :key="p.party_name"
            :label="p.party_name"
            :value="p.party_name"
          />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          style="margin-left: 12px"
        />
        <el-button type="primary" style="margin-left: 12px" @click="loadStatement" :loading="loading">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading && !statementData" class="loading-container">
        <el-skeleton :rows="6" animated />
      </div>

      <!-- 空数据 -->
      <el-empty
        v-else-if="!loading && !statementData"
        description="请选择客户/供应商和日期范围后查询对账单"
      />

      <!-- 对账单内容 -->
      <div v-else class="statement-content" ref="printRef">
        <!-- 对账单标题 -->
        <div class="statement-header">
          <h2>{{ statementData.party_type === 'customer' ? '客户' : '供应商' }}对账单</h2>
          <div class="statement-meta">
            <span>{{ statementData.party_type === 'customer' ? '客户' : '供应商' }}：</span>
            <strong>{{ statementData.party_name }}</strong>
            <span v-if="statementData.party_code" style="margin-left: 16px">编码：{{ statementData.party_code }}</span>
            <span style="margin-left: 16px">期间：{{ statementData.start_date }} 至 {{ statementData.end_date }}</span>
          </div>
        </div>

        <!-- 期初/期末余额 -->
        <div class="balance-row">
          <div class="balance-item">
            <span class="balance-label">期初余额：</span>
            <span class="balance-value" :class="{ 'text-danger': statementData.opening_balance > 0 }">
              ¥{{ formatMoney(statementData.opening_balance) }}
            </span>
          </div>
          <div class="balance-item">
            <span class="balance-label">本期借方合计：</span>
            <span class="balance-value">¥{{ formatMoney(statementData.total_debit) }}</span>
          </div>
          <div class="balance-item">
            <span class="balance-label">本期贷方合计：</span>
            <span class="balance-value">¥{{ formatMoney(statementData.total_credit) }}</span>
          </div>
          <div class="balance-item">
            <span class="balance-label">期末余额：</span>
            <span class="balance-value" :class="{ 'text-danger': statementData.closing_balance > 0 }">
              ¥{{ formatMoney(statementData.closing_balance) }}
            </span>
          </div>
        </div>

        <!-- 明细表 -->
        <el-table :data="statementData.items" stripe border size="small" style="margin-top: 16px">
          <el-table-column prop="date" label="日期" width="120" />
          <el-table-column prop="document_type" label="单据类型" width="100" />
          <el-table-column prop="document_no" label="单据号" width="140" />
          <el-table-column prop="description" label="摘要" min-width="180" />
          <el-table-column prop="debit_amount" label="借方金额" width="140" align="right">
            <template #default="{ row }">
              <span class="amount-cell">{{ formatMoney(row.debit_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="credit_amount" label="贷方金额" width="140" align="right">
            <template #default="{ row }">
              <span class="amount-cell">{{ formatMoney(row.credit_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="balance" label="余额" width="140" align="right">
            <template #default="{ row }">
              <span class="amount-cell" :class="{ 'text-danger': row.balance > 0 }">
                {{ formatMoney(row.balance) }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 累计行 -->
        <div class="summary-row">
          <span class="summary-label">本期合计：</span>
          <span class="summary-item">借方 ¥{{ formatMoney(statementData.total_debit) }}</span>
          <span class="summary-item">贷方 ¥{{ formatMoney(statementData.total_credit) }}</span>
          <span class="summary-item">期末余额 ¥{{ formatMoney(statementData.closing_balance) }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useBookStore } from '@/stores/book'
import { getPartyStatement, getPartyNames } from '@/api/reconciliation'
import { ElMessage } from 'element-plus'

const route = useRoute()
const bookStore = useBookStore()

// ===== 状态 =====
const loading = ref(false)
const partyNamesLoading = ref(false)
const partyNames = ref([])
const statementData = ref(null)
const printRef = ref(null)

const filters = reactive({
  party_type: 'customer',
  party_name: '',
  dateRange: null,
})

// ===== 生命周期 =====
onMounted(() => {
  // 从路由参数中获取预填值
  if (route.query.party_type) {
    filters.party_type = route.query.party_type
  }
  if (route.query.party_name) {
    filters.party_name = route.query.party_name
  }
  loadPartyNames()
})

// ===== 往来方名称列表 =====
async function loadPartyNames() {
  partyNamesLoading.value = true
  try {
    const params = { book_id: bookStore.currentBookId }
    if (filters.party_type) params.party_type = filters.party_type
    const res = await getPartyNames(params)
    partyNames.value = res.data || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载往来方列表失败')
  } finally {
    partyNamesLoading.value = false
  }
}

function handlePartyTypeChange() {
  filters.party_name = ''
  loadPartyNames()
}

// ===== 查询对账单 =====
async function loadStatement() {
  if (!filters.party_name) {
    ElMessage.warning('请选择客户/供应商')
    return
  }
  if (!filters.dateRange || filters.dateRange.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }

  loading.value = true
  try {
    const res = await getPartyStatement(
      filters.party_type,
      filters.party_name,
      {
        book_id: bookStore.currentBookId,
        start_date: filters.dateRange[0],
        end_date: filters.dateRange[1],
      }
    )
    statementData.value = res.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '查询对账单失败')
  } finally {
    loading.value = false
  }
}

// ===== 打印 =====
function handlePrint() {
  if (!printRef.value) return
  const printContent = printRef.value.innerHTML
  const originalContent = document.body.innerHTML

  const printWindow = window.open('', '_blank')
  printWindow.document.write(`
    <html>
      <head>
        <title>对账单</title>
        <style>
          body { font-family: 'Microsoft YaHei', sans-serif; padding: 30px; }
          .statement-header { text-align: center; margin-bottom: 20px; }
          .statement-header h2 { font-size: 20px; margin-bottom: 8px; }
          .statement-meta { color: #666; font-size: 14px; }
          .balance-row { display: flex; gap: 24px; margin: 16px 0; padding: 12px; background: #f5f7fa; border-radius: 4px; }
          .balance-item { font-size: 14px; }
          .balance-label { color: #606266; }
          .balance-value { font-weight: 600; }
          .text-danger { color: #f56c6c; }
          .amount-cell { font-family: 'Courier New', monospace; }
          table { width: 100%; border-collapse: collapse; margin-top: 12px; }
          th, td { border: 1px solid #dcdfe6; padding: 8px 12px; text-align: left; font-size: 13px; }
          th { background: #f5f7fa; font-weight: 600; }
          td { text-align: right; }
          td:nth-child(1), td:nth-child(2), td:nth-child(3), td:nth-child(4) { text-align: left; }
          .summary-row { margin-top: 12px; padding: 10px 12px; background: #f5f7fa; border-radius: 4px; font-size: 14px; }
          .summary-label { font-weight: 600; margin-right: 16px; }
          .summary-item { margin-right: 24px; }
        </style>
      </head>
      <body>
        ${printContent}
      </body>
    </html>
  `)
  printWindow.document.close()
  printWindow.focus()
  setTimeout(() => {
    printWindow.print()
    printWindow.close()
  }, 500)
}

// ===== 辅助函数 =====
function formatMoney(val) {
  if (val === null || val === undefined) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<style scoped>
.party-statement {
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
  margin-bottom: 16px;
}

.loading-container {
  padding: 20px 0;
}

.statement-content {
  margin-top: 4px;
}

.statement-header {
  text-align: center;
  margin-bottom: 20px;
}

.statement-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px 0;
}

.statement-meta {
  color: #606266;
  font-size: 14px;
}

.balance-row {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.balance-item {
  font-size: 14px;
}

.balance-label {
  color: #606266;
}

.balance-value {
  font-weight: 600;
  color: #303133;
}

.text-danger {
  color: #f56c6c;
}

.amount-cell {
  font-family: 'Courier New', monospace;
  font-weight: 500;
}

.summary-row {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
}

.summary-label {
  font-weight: 600;
  color: #303133;
  margin-right: 16px;
}

.summary-item {
  margin-right: 24px;
  color: #303133;
}
</style>