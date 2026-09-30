<template>
  <div class="subsidiary-ledger-view">
    <!-- 标题和操作栏 -->
    <el-card class="header-card" shadow="never">
      <div class="header-row">
        <div class="title-area">
          <h2>明细账</h2>
          <p class="desc">查看指定科目在指定期间内的所有凭证分录明细</p>
        </div>
        <div class="actions">
          <el-select
            v-model="filters.accountCode"
            placeholder="选择科目"
            filterable
            style="width: 220px"
            @change="handleSearch"
          >
            <el-option
              v-for="acc in accounts"
              :key="acc.code"
              :label="`${acc.code} ${acc.name}`"
              :value="acc.code"
            />
          </el-select>
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
            @change="handleSearch"
          />
          <el-button type="primary" @click="handleSearch" :loading="loading">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 汇总信息 -->
    <el-card class="summary-card" shadow="never" style="margin-top: 16px" v-if="summary">
      <el-row :gutter="16">
        <el-col :xs="12" :sm="6">
          <div class="summary-item">
            <div class="summary-label">科目</div>
            <div class="summary-value">{{ summary.account_code }} {{ summary.account_name }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="summary-item">
            <div class="summary-label">期初余额</div>
            <div class="summary-value" :class="{ 'text-negative': summary.balance_direction === 'debit' ? summary.opening_balance < 0 : summary.opening_balance > 0 }">
              {{ formatMoney(summary.opening_balance) }}
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="summary-item">
            <div class="summary-label">本期合计</div>
            <div class="summary-value">
              借 {{ formatMoney(summary.period_debit) }} / 贷 {{ formatMoney(summary.period_credit) }}
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="summary-item">
            <div class="summary-label">期末余额</div>
            <div class="summary-value" :class="{ 'text-negative': summary.balance_direction === 'debit' ? summary.ending_balance < 0 : summary.ending_balance > 0 }">
              {{ formatMoney(summary.ending_balance) }}
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="content-card" shadow="never" style="margin-top: 16px" v-loading="loading">
      <el-table :data="tableData" border stripe style="width: 100%" max-height="500">
        <el-table-column prop="voucher_date" label="日期" width="110" />
        <el-table-column prop="voucher_no" label="凭证号" width="140" />
        <el-table-column prop="summary" label="摘要" min-width="180" show-overflow-tooltip />
        <el-table-column prop="debit_amount" label="借方金额" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.debit_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="credit_amount" label="贷方金额" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.credit_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="balance" label="余额" width="160" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-negative': row.balance < 0 }">
              {{ formatMoney(row.balance) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && tableData.length === 0" description="请选择科目进行查询" :image-size="80" />

      <div class="pagination-wrap" v-if="total > 0">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getSubsidiaryLedger } from '@/api/report'
import { getAccounts } from '@/api/voucher'
import { useAmountMask } from '@/composables/useAmountMask'
import { ElMessage } from 'element-plus'

const route = useRoute()
const { formatAmount } = useAmountMask()

const loading = ref(false)
const accounts = ref([])
const tableData = ref([])
const total = ref(0)
const summary = ref(null)

const getDefaultDateRange = () => {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  return [formatDate(start), formatDate(now)]
}

const formatDate = (d) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const filters = reactive({
  accountCode: '',
  dateRange: getDefaultDateRange()
})

const pagination = reactive({
  page: 1,
  pageSize: 50
})

function formatMoney(value) {
  return formatAmount(value)
}

async function loadAccounts() {
  try {
    const res = await getAccounts()
    accounts.value = res.data.accounts || []
  } catch (e) {
    console.error('加载科目列表失败', e)
  }
}

async function handleSearch() {
  if (!filters.accountCode) {
    ElMessage.warning('请选择科目')
    return
  }

  loading.value = true
  try {
    const [startDate, endDate] = filters.dateRange || getDefaultDateRange()
    const params = {
      account_code: filters.accountCode,
      start_date: startDate,
      end_date: endDate,
      page: pagination.page,
      page_size: pagination.pageSize
    }
    const res = await getSubsidiaryLedger(params)
    const data = res.data
    tableData.value = data.items || []
    total.value = data.total || 0
    summary.value = {
      account_code: data.account_code,
      account_name: data.account_name,
      balance_direction: data.balance_direction,
      opening_balance: data.opening_balance,
      period_debit: data.period_debit,
      period_credit: data.period_credit,
      ending_balance: data.ending_balance
    }
  } catch (e) {
    ElMessage.error('加载明细账数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadAccounts()
  // 从路由参数中获取预选的科目
  const queryCode = route.query.account_code
  if (queryCode) {
    filters.accountCode = queryCode
  }
  const queryStart = route.query.start_date
  const queryEnd = route.query.end_date
  if (queryStart && queryEnd) {
    filters.dateRange = [queryStart, queryEnd]
  }
  if (filters.accountCode) {
    handleSearch()
  }
})
</script>

<style scoped>
.subsidiary-ledger-view {
  max-width: 1200px;
}

.header-card {
  margin-bottom: 0;
}

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.title-area h2 {
  font-size: 20px;
  color: #303133;
  margin-bottom: 4px;
}

.desc {
  font-size: 13px;
  color: #909399;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.summary-card {
  margin-bottom: 0;
}

.summary-item {
  text-align: center;
  padding: 8px 0;
}

.summary-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.summary-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  font-family: 'Courier New', monospace;
}

.content-card {
  min-height: 300px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.text-negative {
  color: #f56c6c;
}
</style>