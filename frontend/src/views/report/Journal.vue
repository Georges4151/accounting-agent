<template>
  <div class="journal-view">
    <!-- 标题和操作栏 -->
    <el-card class="header-card" shadow="never">
      <div class="header-row">
        <div class="title-area">
          <h2>日记账</h2>
          <p class="desc">按日期顺序显示现金和银行存款科目的凭证分录</p>
        </div>
        <div class="actions">
          <el-radio-group v-model="filters.accountType" @change="handleSearch">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="cash">现金日记账</el-radio-button>
            <el-radio-button value="bank">银行日记账</el-radio-button>
          </el-radio-group>
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
      <el-table :data="tableData" border stripe style="width: 100%" max-height="500" show-summary :summary-method="getSummaries">
        <el-table-column prop="voucher_date" label="日期" width="110" />
        <el-table-column prop="voucher_no" label="凭证号" width="140" />
        <el-table-column prop="summary" label="摘要" min-width="180" show-overflow-tooltip />
        <el-table-column prop="account_code" label="科目代码" width="110" />
        <el-table-column prop="account_name" label="科目名称" width="120" />
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
import { getJournal } from '@/api/report'
import { useAmountMask } from '@/composables/useAmountMask'
import { ElMessage } from 'element-plus'

const { formatAmount } = useAmountMask()

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const summaryData = reactive({
  total_debit: 0,
  total_credit: 0
})

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
  accountType: '',
  dateRange: getDefaultDateRange()
})

const pagination = reactive({
  page: 1,
  pageSize: 50
})

function formatMoney(value) {
  return formatAmount(value)
}

function getSummaries(param) {
  const { columns } = param
  const sums = []
  columns.forEach((column, index) => {
    if (index === 0) {
      sums[index] = '合计'
      return
    }
    if (column.property === 'debit_amount') {
      sums[index] = formatAmount(summaryData.total_debit)
    } else if (column.property === 'credit_amount') {
      sums[index] = formatAmount(summaryData.total_credit)
    } else {
      sums[index] = ''
    }
  })
  return sums
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
    if (filters.accountType) {
      params.account_type = filters.accountType
    }
    const res = await getJournal(params)
    tableData.value = res.data.items || []
    total.value = res.data.total || 0
    summaryData.total_debit = res.data.total_debit || 0
    summaryData.total_credit = res.data.total_credit || 0
  } catch (e) {
    ElMessage.error('加载日记账数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  handleSearch()
})
</script>

<style scoped>
.journal-view {
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
</style>