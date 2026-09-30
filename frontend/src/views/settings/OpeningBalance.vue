<template>
  <div class="opening-balance-container">
    <div class="page-header">
      <h2>期初余额管理</h2>
      <div class="header-actions">
        <el-select
          v-model="fiscalYear"
          placeholder="选择年度"
          style="width: 120px"
          @change="loadData"
          filterable
        >
          <el-option
            v-for="year in yearOptions"
            :key="year"
            :label="year + '年'"
            :value="year"
          />
        </el-select>
        <el-button type="primary" @click="handleSave" :loading="saving">
          保存
        </el-button>
      </div>
    </div>

    <!-- 试算平衡提示 -->
    <el-alert
      v-if="loaded"
      :title="balanceMsg"
      :type="isBalanced ? 'success' : 'warning'"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <!-- 科目搜索 -->
    <div class="filter-bar">
      <el-input
        v-model="searchText"
        placeholder="搜索科目编码或名称"
        clearable
        style="width: 280px"
        prefix-icon="Search"
      />
      <el-checkbox
        v-model="showOnlyWithBalance"
        border
        style="margin-left: 12px"
      >
        仅显示有余额的科目
      </el-checkbox>
      <span class="filter-summary">
        共 {{ accountTypes.length }} 类科目，{{ filteredAccounts.length }} 项
      </span>
    </div>

    <el-skeleton :loading="loading" animated :count="5" />

    <template v-if="!loading">
      <div
        v-for="type in accountTypes"
        :key="type"
        class="account-type-group"
      >
        <div class="type-header">
          <span class="type-tag" :class="'type-' + type">{{ type }}</span>
          <span class="type-count">
            {{ getTypeBalance(type) }}
          </span>
        </div>

        <el-table
          :data="getTypeAccounts(type)"
          size="small"
          stripe
          border
          :key="type"
        >
          <el-table-column prop="account_code" label="科目编码" width="120" />
          <el-table-column prop="account_name" label="科目名称" min-width="180" />
          <el-table-column label="余额方向" width="100" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.balance_direction === 'debit' ? 'primary' : 'success'"
                size="small"
                effect="plain"
              >
                {{ row.balance_direction === 'debit' ? '借方' : '贷方' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="期初借方余额" width="200">
            <template #default="{ row }">
              <el-input-number
                v-model="formData[row.account_code].opening_debit"
                :min="0"
                :precision="2"
                :disabled="row.balance_direction !== 'debit'"
                controls-position="right"
                style="width: 100%"
              />
            </template>
          </el-table-column>
          <el-table-column label="期初贷方余额" width="200">
            <template #default="{ row }">
              <el-input-number
                v-model="formData[row.account_code].opening_credit"
                :min="0"
                :precision="2"
                :disabled="row.balance_direction !== 'credit'"
                controls-position="right"
                style="width: 100%"
              />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useBookStore } from '@/stores/book'
import request from '@/api/request'
import { getOpeningBalances, saveOpeningBalances } from '@/api/opening_balance'

const bookStore = useBookStore()

// 状态
const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const searchText = ref('')
const showOnlyWithBalance = ref(false)
const fiscalYear = ref(new Date().getFullYear())
const accounts = ref([])
const formData = ref({})
const isBalanced = ref(false)
const balanceMsg = ref('')

// 年度选项
const yearOptions = computed(() => {
  const currentYear = new Date().getFullYear()
  const years = []
  for (let y = currentYear - 5; y <= currentYear + 1; y++) {
    years.push(y)
  }
  return years
})

// 科目类型
const accountTypes = computed(() => {
  const types = [...new Set(accounts.value.map(a => a.account_type))]
  return types.sort()
})

// 筛选后的科目
const filteredAccounts = computed(() => {
  let list = accounts.value
  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    list = list.filter(
      a =>
        a.account_code.toLowerCase().includes(keyword) ||
        a.account_name.toLowerCase().includes(keyword)
    )
  }
  if (showOnlyWithBalance.value) {
    list = list.filter(a => {
      const data = formData.value[a.account_code]
      return data && (data.opening_debit > 0 || data.opening_credit > 0)
    })
  }
  return list
})

// 按类型分组
function getTypeAccounts(type) {
  return filteredAccounts.value.filter(a => a.account_type === type)
}

// 类型余额汇总
function getTypeBalance(type) {
  const accounts = getTypeAccounts(type)
  let totalDebit = 0
  let totalCredit = 0
  accounts.forEach(a => {
    const data = formData.value[a.account_code]
    if (data) {
      totalDebit += data.opening_debit || 0
      totalCredit += data.opening_credit || 0
    }
  })
  return `借方合计: ${totalDebit.toFixed(2)} | 贷方合计: ${totalCredit.toFixed(2)}`
}

// 加载科目和期初余额
async function loadData() {
  loading.value = true
  loaded.value = false
  try {
    // 获取科目列表
    const accRes = await request.get('/vouchers/accounts', {
      params: { book_id: bookStore.currentBookId }
    })
    accounts.value = accRes.data.accounts || []

    // 初始化表单
    const fd = {}
    accounts.value.forEach(a => {
      fd[a.account_code] = {
        account_code: a.account_code,
        account_name: a.account_name,
        opening_debit: 0,
        opening_credit: 0,
      }
    })

    // 加载已有期初余额
    try {
      const balRes = await getOpeningBalances(bookStore.currentBookId, fiscalYear.value)
      if (balRes.data && balRes.data.items) {
        balRes.data.items.forEach(item => {
          if (fd[item.account_code]) {
            fd[item.account_code].opening_debit = item.opening_debit
            fd[item.account_code].opening_credit = item.opening_credit
          }
        })
        isBalanced.value = balRes.data.is_balanced
        updateBalanceMsg()
      }
    } catch (e) {
      // 没有期初余额数据，使用默认值
      isBalanced.value = false
      updateBalanceMsg()
    }

    formData.value = fd
    loaded.value = true
  } catch (e) {
    ElMessage.error('加载科目失败')
  } finally {
    loading.value = false
  }
}

// 更新试算平衡提示
function updateBalanceMsg() {
  let totalDebit = 0
  let totalCredit = 0
  Object.values(formData.value).forEach(item => {
    totalDebit += item.opening_debit || 0
    totalCredit += item.opening_credit || 0
  })
  const diff = Math.abs(totalDebit - totalCredit)
  if (diff < 0.01) {
    isBalanced.value = true
    balanceMsg.value = `试算平衡 — 借方合计 ${totalDebit.toFixed(2)} = 贷方合计 ${totalCredit.toFixed(2)}`
  } else {
    isBalanced.value = false
    balanceMsg.value = `试算不平衡 — 借方合计 ${totalDebit.toFixed(2)}，贷方合计 ${totalCredit.toFixed(2)}，差额 ${diff.toFixed(2)}`
  }
}

// 保存
async function handleSave() {
  // 先检查试算平衡
  updateBalanceMsg()
  if (!isBalanced.value) {
    try {
      await ElMessage.warning('期初余额试算不平衡，确认保存？')
    } catch {
      return
    }
  }

  saving.value = true
  try {
    const items = Object.values(formData.value).filter(
      item => item.opening_debit > 0 || item.opening_credit > 0
    )
    await saveOpeningBalances(bookStore.currentBookId, {
      fiscal_year: fiscalYear.value,
      items,
    })
    ElMessage.success('期初余额保存成功')
    updateBalanceMsg()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
  }
}

// 监听表单变化，实时更新试算平衡
watch(formData, () => {
  if (loaded.value) {
    updateBalanceMsg()
  }
}, { deep: true })

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.opening-balance-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.filter-bar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-summary {
  color: #909399;
  font-size: 13px;
  margin-left: auto;
}

.account-type-group {
  margin-bottom: 20px;
}

.type-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.type-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  color: #fff;
}

.type-tag.type-资产 { background: #409eff; }
.type-tag.type-负债 { background: #e6a23c; }
.type-tag.type-权益 { background: #67c23a; }
.type-tag.type-成本 { background: #f56c6c; }
.type-tag.type-损益 { background: #909399; }

.type-count {
  color: #909399;
  font-size: 12px;
}
</style>