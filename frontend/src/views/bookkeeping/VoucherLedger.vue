<template>
  <div class="voucher-ledger">
    <!-- 筛选条件 -->
    <el-card shadow="never" class="filter-card">
      <el-form :model="filterForm" inline>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
            @change="handleSearch"
          />
        </el-form-item>
        <el-form-item label="科目">
          <el-tree-select
            v-model="filterForm.account_code"
            :data="accountTreeData"
            :render-after-expand="false"
            :filter-node-method="filterAccountNode"
            filterable
            clearable
            check-strictly
            placeholder="全部科目"
            style="width: 240px"
            :props="{ value: 'code', label: 'label', children: 'children' }"
            @change="handleSearch"
          />
        </el-form-item>
        <el-form-item label="凭证字">
          <el-select
            v-model="filterForm.voucher_type"
            clearable
            placeholder="全部"
            style="width: 100px"
            @change="handleSearch"
          >
            <el-option label="记" value="记" />
            <el-option label="转" value="转" />
            <el-option label="收" value="收" />
            <el-option label="付" value="付" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filterForm.status"
            clearable
            placeholder="全部"
            style="width: 120px"
            @change="handleSearch"
          >
            <el-option label="草稿" value="draft" />
            <el-option label="已提交" value="submitted" />
            <el-option label="出纳已复核" value="cashier_reviewed" />
            <el-option label="已审核" value="reviewed" />
            <el-option label="已审批" value="approved" />
            <el-option label="已过账" value="posted" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="filterForm.keyword"
            placeholder="凭证号/摘要"
            clearable
            style="width: 180px"
            @keydown.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 汇总统计卡片 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card--total">
          <div class="stat-label">分录总数</div>
          <div class="stat-value">{{ ledgerTotal }}</div>
        </el-card>
      </el-col>
      <el-col :span="9">
        <el-card shadow="hover" class="stat-card stat-card--debit">
          <div class="stat-label">借方合计</div>
          <div class="stat-value">{{ formatMoney(totalDebit) }}</div>
        </el-card>
      </el-col>
      <el-col :span="9">
        <el-card shadow="hover" class="stat-card stat-card--credit">
          <div class="stat-label">贷方合计</div>
          <div class="stat-value">{{ formatMoney(totalCredit) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 台账表格 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>凭证台账</span>
          <div>
            <el-button type="primary" @click="handleExportPdf" :loading="exportingPdf">
              <el-icon><Printer /></el-icon>
              导出PDF
            </el-button>
            <el-button type="success" @click="handleExport" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出Excel
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="ledgerData"
        v-loading="loading"
        border
        stripe
        size="small"
        style="width: 100%"
        :header-cell-style="{ background: '#f5f7fa', color: '#303133', fontWeight: 600 }"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="voucher_date" label="日期" width="110" sortable="custom" />
        <el-table-column prop="voucher_type" label="凭证字" width="70" />
        <el-table-column prop="voucher_no" label="凭证号" width="160" />
        <el-table-column prop="voucher_summary" label="凭证摘要" min-width="150" show-overflow-tooltip />
        <el-table-column prop="account_code" label="科目代码" width="110" />
        <el-table-column prop="account_name" label="科目名称" width="130" />
        <el-table-column prop="description" label="分录摘要" min-width="150" show-overflow-tooltip />
        <el-table-column prop="debit_amount" label="借方金额" width="130" align="right">
          <template #default="{ row }">
            <span class="amount-debit">{{ row.debit_amount > 0 ? formatMoney(row.debit_amount) : '' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="credit_amount" label="贷方金额" width="130" align="right">
          <template #default="{ row }">
            <span class="amount-credit">{{ row.credit_amount > 0 ? formatMoney(row.credit_amount) : '' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cash_flow_tag" label="现金流量" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.cash_flow_tag" :type="getCashFlowTagType(row.cash_flow_tag)" size="small">
              {{ getCashFlowLabel(row.cash_flow_tag) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="制单人" width="90" />
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="ledgerTotal"
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
import request from '@/api/request'
import { useAmountMask } from '@/composables/useAmountMask'
import { ElMessage } from 'element-plus'

const { formatAmount } = useAmountMask()

// 筛选条件
const filterForm = reactive({
  dateRange: null,
  account_code: '',
  voucher_type: '',
  status: '',
  keyword: ''
})

// 科目选项
const accountOptions = ref([])
const accountTreeData = ref([])

function buildTreeLabels(tree, depth = 0) {
  const prefix = depth > 0 ? '\u00A0\u00A0'.repeat(depth) + '\u2514 ' : ''
  return tree.map(node => ({
    ...node,
    label: `${prefix}${node.code} ${node.name}`,
    children: node.children ? buildTreeLabels(node.children, depth + 1) : []
  }))
}

function filterAccountNode(value, data) {
  if (!value) return true
  const label = `${data.code} ${data.name}`.toLowerCase()
  return label.includes(value.toLowerCase())
}

async function loadAccounts() {
  try {
    const res = await request.get('/vouchers/accounts')
    accountOptions.value = res.data.accounts || []
  } catch {
    // 静默
  }
  try {
    const treeRes = await request.get('/vouchers/accounts/tree')
    accountTreeData.value = buildTreeLabels(treeRes.data.tree || [])
  } catch {
    accountTreeData.value = accountOptions.value.map(a => ({
      code: a.code,
      name: a.name,
      label: `${a.code} ${a.name}`,
      children: []
    }))
  }
}

// 台账数据
const loading = ref(false)
const ledgerData = ref([])
const ledgerTotal = ref(0)
const totalDebit = ref(0)
const totalCredit = ref(0)
const exporting = ref(false)
const exportingPdf = ref(false)

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 50
})

// 排序
const sortParams = reactive({
  sortBy: '',
  sortOrder: ''
})

onMounted(async () => {
  await loadAccounts()
  await fetchLedger()
})

async function fetchLedger() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filterForm.dateRange && filterForm.dateRange.length === 2) {
      params.start_date = filterForm.dateRange[0]
      params.end_date = filterForm.dateRange[1]
    }
    if (filterForm.account_code) params.account_code = filterForm.account_code
    if (filterForm.voucher_type) params.voucher_type = filterForm.voucher_type
    if (filterForm.status) params.status = filterForm.status
    if (filterForm.keyword) params.keyword = filterForm.keyword

    const res = await request.get('/vouchers/ledger', { params })
    ledgerData.value = res.data.items || []
    ledgerTotal.value = res.data.total || 0
    totalDebit.value = res.data.total_debit || 0
    totalCredit.value = res.data.total_credit || 0
  } catch (error) {
    ElMessage.error('加载台账失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  fetchLedger()
}

function handleReset() {
  filterForm.dateRange = null
  filterForm.account_code = ''
  filterForm.voucher_type = ''
  filterForm.status = ''
  filterForm.keyword = ''
  handleSearch()
}

function handleSortChange({ prop, order }) {
  sortParams.sortBy = prop
  sortParams.sortOrder = order === 'ascending' ? 'asc' : order === 'descending' ? 'desc' : ''
  handleSearch()
}

async function handleExport() {
  exporting.value = true
  try {
    const params = {
      page: 1,
      page_size: 10000  // 导出全部
    }
    if (filterForm.dateRange && filterForm.dateRange.length === 2) {
      params.start_date = filterForm.dateRange[0]
      params.end_date = filterForm.dateRange[1]
    }
    if (filterForm.account_code) params.account_code = filterForm.account_code
    if (filterForm.voucher_type) params.voucher_type = filterForm.voucher_type
    if (filterForm.status) params.status = filterForm.status
    if (filterForm.keyword) params.keyword = filterForm.keyword

    const res = await request.get('/vouchers/ledger', { params })
    const items = res.data.items || []

    if (items.length === 0) {
      ElMessage.warning('没有可导出的数据')
      return
    }

    // 生成Excel CSV
    const headers = ['日期', '凭证字', '凭证号', '凭证摘要', '科目代码', '科目名称', '分录摘要', '借方金额', '贷方金额', '状态', '制单人']
    const rows = items.map(item => [
      item.voucher_date,
      item.voucher_type,
      item.voucher_no,
      item.voucher_summary,
      item.account_code,
      item.account_name,
      item.description,
      item.debit_amount > 0 ? item.debit_amount.toFixed(2) : '',
      item.credit_amount > 0 ? item.credit_amount.toFixed(2) : '',
      getStatusLabel(item.status),
      item.created_by_name
    ])

    // 添加BOM以支持Excel正确识别中文
    const BOM = '\uFEFF'
    let csv = BOM + headers.join(',') + '\n'
    rows.forEach(row => {
      csv += row.map(cell => {
        const val = String(cell || '')
        return val.includes(',') || val.includes('"') || val.includes('\n')
          ? `"${val.replace(/"/g, '""')}"`
          : val
      }).join(',') + '\n'
    })

    // 添加汇总行
    csv += `\n,,,合计,,,,${totalDebit.value.toFixed(2)},${totalCredit.value.toFixed(2)},,\n`

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const dateStr = new Date().toISOString().split('T')[0]
    link.download = `凭证台账_${dateStr}.csv`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${items.length} 条分录`)
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

async function handleExportPdf() {
  exportingPdf.value = true
  try {
    const params = {
      page: 1,
      page_size: 10000
    }
    if (filterForm.dateRange && filterForm.dateRange.length === 2) {
      params.start_date = filterForm.dateRange[0]
      params.end_date = filterForm.dateRange[1]
    }
    if (filterForm.account_code) params.account_code = filterForm.account_code
    if (filterForm.voucher_type) params.voucher_type = filterForm.voucher_type
    if (filterForm.status) params.status = filterForm.status
    if (filterForm.keyword) params.keyword = filterForm.keyword

    const res = await request.get('/vouchers/ledger', { params })
    const items = res.data.items || []

    if (items.length === 0) {
      ElMessage.warning('没有可导出的数据')
      return
    }

    // 按凭证分组
    const voucherMap = {}
    items.forEach(item => {
      const key = item.voucher_id
      if (!voucherMap[key]) {
        voucherMap[key] = {
          voucher_no: item.voucher_no,
          voucher_type: item.voucher_type,
          voucher_date: item.voucher_date,
          voucher_summary: item.voucher_summary,
          status: item.status,
          created_by_name: item.created_by_name,
          items: []
        }
      }
      voucherMap[key].items.push(item)
    })

    // 构建HTML打印内容
    const voucherIds = Object.keys(voucherMap)
    let html = `
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>凭证台账</title>
    <style>
      @page { size: A4 landscape; margin: 10mm; }
      body { font-family: SimSun, 'Microsoft YaHei', sans-serif; font-size: 12px; }
      h2 { text-align: center; margin: 0 0 10px; }
      .summary { display: flex; gap: 30px; margin-bottom: 10px; padding: 8px; background: #f5f7fa; }
      table { width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 15px; }
      th { background: #e8eaed; padding: 5px; border: 1px solid #ccc; }
      td { padding: 4px 5px; border: 1px solid #ccc; }
      .text-right { text-align: right; }
      .text-center { text-align: center; }
      .voucher-header { background: #f0f5ff; font-weight: bold; }
      .total-row { font-weight: bold; background: #f5f7fa; }
      @media print { .page-break { page-break-before: always; } }
    </style></head><body>
    <h2>凭证台账</h2>
    <div class="summary">
      <span>分录总数: ${items.length}</span>
      <span>借方合计: ${totalDebit.value.toFixed(2)}</span>
      <span>贷方合计: ${totalCredit.value.toFixed(2)}</span>
    </div>`

    voucherIds.forEach((vid, idx) => {
      const v = voucherMap[vid]
      if (idx > 0 && idx % 8 === 0) html += '<div class="page-break"></div>'
      html += `
      <div class="voucher-header" style="margin-top:10px;padding:4px 8px;border:1px solid #ccc;">
        ${v.voucher_date} | ${v.voucher_type}-${v.voucher_no} | ${v.voucher_summary} | ${getStatusLabel(v.status)} | 制单: ${v.created_by_name}
      </div>
      <table>
        <tr><th>科目代码</th><th>科目名称</th><th>分录摘要</th><th class="text-right">借方金额</th><th class="text-right">贷方金额</th></tr>`
      let vDebit = 0, vCredit = 0
      v.items.forEach(item => {
        vDebit += item.debit_amount
        vCredit += item.credit_amount
        html += `<tr>
          <td>${item.account_code}</td><td>${item.account_name}</td><td>${item.description || ''}</td>
          <td class="text-right">${item.debit_amount > 0 ? item.debit_amount.toFixed(2) : ''}</td>
          <td class="text-right">${item.credit_amount > 0 ? item.credit_amount.toFixed(2) : ''}</td>
        </tr>`
      })
      html += `<tr class="total-row"><td colspan="3" class="text-center">小计</td>
        <td class="text-right">${vDebit.toFixed(2)}</td><td class="text-right">${vCredit.toFixed(2)}</td></tr></table>`
    })

    html += '</body></html>'

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const win = window.open(url, '_blank')
    if (win) {
      win.onload = () => { win.print() }
    }
    URL.revokeObjectURL(url)
    ElMessage.success('已打开打印预览')
  } catch (error) {
    ElMessage.error('导出PDF失败')
  } finally {
    exportingPdf.value = false
  }
}

function formatMoney(value) {
  return formatAmount(value)
}

function getStatusType(status) {
  const map = {
    draft: 'info',
    submitted: 'warning',
    cashier_reviewed: '',
    reviewed: '',
    approved: 'success',
    posted: ''
  }
  return map[status] || 'info'
}

function getStatusLabel(status) {
  const map = {
    draft: '草稿',
    submitted: '已提交',
    cashier_reviewed: '出纳已复核',
    reviewed: '已审核',
    approved: '已审批',
    posted: '已过账'
  }
  return map[status] || status
}

function getCashFlowLabel(tag) {
  const map = { operating: '经营', investing: '投资', financing: '筹资' }
  return map[tag] || tag
}

function getCashFlowTagType(tag) {
  const map = { operating: 'success', investing: 'warning', financing: 'danger' }
  return map[tag] || 'info'
}
</script>

<style scoped>
.voucher-ledger {
  max-width: 1400px;
}

.filter-card {
  margin-bottom: 0;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.stat-card {
  text-align: center;
}

.stat-card--total {
  border-left: 4px solid #409eff;
}

.stat-card--debit {
  border-left: 4px solid #67c23a;
}

.stat-card--credit {
  border-left: 4px solid #e6a23c;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}

.amount-debit {
  color: #409eff;
  font-family: 'Courier New', monospace;
}

.amount-credit {
  color: #67c23a;
  font-family: 'Courier New', monospace;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>