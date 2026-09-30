<template>
  <div class="general-ledger-view">
    <!-- 标题和操作栏 -->
    <el-card class="header-card" shadow="never">
      <div class="header-row">
        <div class="title-area">
          <h2>总账</h2>
          <p class="desc">按科目汇总期初余额、本期发生额和期末余额</p>
        </div>
        <div class="actions">
          <el-select
            v-model="filters.accountCode"
            placeholder="选择科目"
            clearable
            filterable
            style="width: 200px"
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

    <!-- 数据表格 -->
    <el-card class="content-card" shadow="never" style="margin-top: 16px" v-loading="loading">
      <el-table :data="tableData" border stripe style="width: 100%" max-height="600">
        <el-table-column prop="account_code" label="科目代码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="160">
          <template #default="{ row }">
            <el-link type="primary" @click="goToSubsidiary(row.account_code)">
              {{ row.account_name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="opening_balance" label="期初余额" width="160" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-negative': row.balance_direction === 'debit' ? row.opening_balance < 0 : row.opening_balance > 0 }">
              {{ formatMoney(row.opening_balance) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="current_debit" label="本期借方" width="160" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_credit" label="本期贷方" width="160" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_credit) }}
          </template>
        </el-table-column>
        <el-table-column prop="ending_balance" label="期末余额" width="160" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-negative': row.balance_direction === 'debit' ? row.ending_balance < 0 : row.ending_balance > 0 }">
              {{ formatMoney(row.ending_balance) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && tableData.length === 0" description="暂无数据" :image-size="80" />

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
import { useRouter } from 'vue-router'
import { getGeneralLedger } from '@/api/report'
import { getAccounts } from '@/api/voucher'
import { useAmountMask } from '@/composables/useAmountMask'
import { ElMessage } from 'element-plus'

const router = useRouter()
const { formatAmount } = useAmountMask()

const loading = ref(false)
const accounts = ref([])
const tableData = ref([])
const total = ref(0)

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

function goToSubsidiary(accountCode) {
  const [startDate, endDate] = filters.dateRange || getDefaultDateRange()
  router.push({
    name: 'SubsidiaryLedger',
    query: {
      account_code: accountCode,
      start_date: startDate,
      end_date: endDate
    }
  })
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
  loading.value = true
  try {
    const [startDate, endDate] = filters.dateRange || getDefaultDateRange()
    const params = {
      start_date: startDate,
      end_date: endDate,
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.accountCode) {
      params.account_code = filters.accountCode
    }
    const res = await getGeneralLedger(params)
    tableData.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('加载总账数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAccounts()
  handleSearch()
})
</script>

<style scoped>
.general-ledger-view {
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