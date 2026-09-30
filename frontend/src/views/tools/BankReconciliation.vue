<template>
  <div class="bank-reconciliation">
    <div class="page-header">
      <h2>银行对账</h2>
    </div>

    <!-- 操作区 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="银行账号">
          <el-input
            v-model="bankAccount"
            placeholder="请输入银行账号"
            clearable
            style="width: 200px"
          />
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
          <el-button type="primary" @click="loadData">
            查询
          </el-button>
          <el-button @click="importDialogVisible = true">
            导入银行流水
          </el-button>
          <el-button @click="manualAddDialogVisible = true">
            手动添加流水
          </el-button>
          <el-button
            type="success"
            :disabled="!bankAccount"
            @click="handleAutoMatch"
            :loading="matching"
          >
            自动匹配
          </el-button>
          <el-button @click="handleShowReport" :disabled="!bankAccount">
            对账报告
          </el-button>
          <el-button
            type="warning"
            :disabled="!bankAccount || !dateRange || dateRange.length !== 2"
            @click="handleExport"
          >
            导出
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 对账单列表 -->
    <el-table :data="statements" v-loading="loading" border stripe max-height="calc(100vh - 400px)">
      <el-table-column prop="transaction_date" label="交易日期" width="120" />
      <el-table-column prop="description" label="摘要" min-width="250" show-overflow-tooltip />
      <el-table-column label="借方金额" width="140" align="right">
        <template #default="{ row }">
          <span class="amount-debit">{{ row.debit_amount.toFixed(2) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="贷方金额" width="140" align="right">
        <template #default="{ row }">
          <span class="amount-credit">{{ row.credit_amount.toFixed(2) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="余额" width="140" align="right">
        <template #default="{ row }">
          {{ row.balance.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column label="匹配状态" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.match_status === 'matched'" type="success" size="small">已匹配</el-tag>
          <el-tag v-else type="warning" size="small">未匹配</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="匹配凭证" width="120">
        <template #default="{ row }">
          <span v-if="row.matched_voucher_id">
            凭证#{{ row.matched_voucher_id }}
          </span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.notes || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <template v-if="row.match_status === 'unmatched'">
            <el-button type="primary" link size="small" @click="openMatchDialog(row)">
              匹配
            </el-button>
          </template>
          <template v-else>
            <el-button type="warning" link size="small" @click="handleUnmatch(row.id)">
              取消匹配
            </el-button>
          </template>
          <el-button type="danger" link size="small" @click="handleDelete(row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @change="loadData"
      />
    </div>

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="导入银行流水" width="450px" :close-on-click-modal="false">
      <el-form label-width="100px">
        <el-form-item label="银行账号">
          <el-input v-model="importBankAccount" placeholder="请输入银行账号" />
        </el-form-item>
        <el-form-item label="CSV文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".csv"
            :on-change="handleFileChange"
          >
            <el-button type="primary">选择CSV文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                CSV格式: 日期,摘要,借方金额,贷方金额,余额
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile || !importBankAccount" @click="handleImport">
          导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 手动添加流水弹窗 -->
    <el-dialog v-model="manualAddDialogVisible" title="手动添加银行流水" width="500px" :close-on-click-modal="false">
      <el-form ref="manualFormRef" :model="manualForm" :rules="manualFormRules" label-width="100px">
        <el-form-item label="银行账号" prop="bank_account">
          <el-input v-model="manualForm.bank_account" placeholder="请输入银行账号" />
        </el-form-item>
        <el-form-item label="交易日期" prop="transaction_date">
          <el-date-picker
            v-model="manualForm.transaction_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="摘要" prop="description">
          <el-input v-model="manualForm.description" placeholder="请输入交易摘要" />
        </el-form-item>
        <el-form-item label="借方金额">
          <el-input-number v-model="manualForm.debit_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="贷方金额">
          <el-input-number v-model="manualForm.credit_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="余额">
          <el-input-number v-model="manualForm.balance" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="manualForm.notes" type="textarea" :rows="2" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualAddDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="manualAdding" @click="handleManualAdd">确认添加</el-button>
      </template>
    </el-dialog>

    <!-- 手动匹配弹窗 -->
    <el-dialog v-model="matchDialogVisible" title="选择凭证分录进行匹配" width="700px" :close-on-click-modal="false">
      <div style="margin-bottom: 12px">
        <el-input
          v-model="matchKeyword"
          placeholder="搜索凭证号或摘要"
          clearable
          style="width: 280px"
          @input="searchVoucherItems"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <el-table
        :data="voucherItems"
        v-loading="voucherItemsLoading"
        border
        stripe
        max-height="400px"
        highlight-current-row
        @current-change="handleVoucherItemSelect"
      >
        <el-table-column prop="voucher_no" label="凭证号" width="120" />
        <el-table-column prop="voucher_date" label="日期" width="110" />
        <el-table-column prop="description" label="摘要" show-overflow-tooltip />
        <el-table-column label="借方金额" width="120" align="right">
          <template #default="{ row }">
            <span class="amount-debit">{{ row.debit_amount.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="贷方金额" width="120" align="right">
          <template #default="{ row }">
            <span class="amount-credit">{{ row.credit_amount.toFixed(2) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 8px; color: #909399; font-size: 13px">
        当前匹配流水: {{ matchingStatement?.transaction_date }} {{ matchingStatement?.description }}
        ({{ (matchingStatement?.debit_amount || 0) > 0 ? '借' + matchingStatement?.debit_amount.toFixed(2) : '贷' + matchingStatement?.credit_amount.toFixed(2) }})
      </div>
      <template #footer>
        <el-button @click="matchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="matchSubmitting" :disabled="!selectedVoucherItemId" @click="handleManualMatch">
          确认匹配
        </el-button>
      </template>
    </el-dialog>

    <!-- 对账报告弹窗 -->
    <el-dialog v-model="reportDialogVisible" title="对账报告" width="900px" :close-on-click-modal="false">
      <template v-if="report">
        <el-descriptions :column="3" border style="margin-bottom: 20px">
          <el-descriptions-item label="银行余额">
            <span style="font-size: 16px; font-weight: bold; color: #409eff">
              {{ report.bank_balance.toFixed(2) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="账面余额">
            <span style="font-size: 16px; font-weight: bold; color: #67c23a">
              {{ report.book_balance.toFixed(2) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="差异">
            <span
              :style="{
                fontSize: '16px',
                fontWeight: 'bold',
                color: Math.abs(report.difference) > 0.01 ? '#f56c6c' : '#67c23a',
              }"
            >
              {{ report.difference.toFixed(2) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="已匹配笔数">{{ report.matched_count }}</el-descriptions-item>
          <el-descriptions-item label="未匹配银行流水">{{ report.unmatched_bank_count }}</el-descriptions-item>
          <el-descriptions-item label="未匹配凭证分录">{{ report.unmatched_book_count }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs v-model="reportTab">
          <el-tab-pane label="已匹配明细" name="matched">
            <el-table :data="reportMatchedDetails" border stripe max-height="350px" size="small">
              <el-table-column prop="transaction_date" label="日期" width="110" />
              <el-table-column prop="description" label="摘要" show-overflow-tooltip />
              <el-table-column label="借方金额" width="120" align="right">
                <template #default="{ row }">
                  <span class="amount-debit">{{ row.debit_amount.toFixed(2) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="贷方金额" width="120" align="right">
                <template #default="{ row }">
                  <span class="amount-credit">{{ row.credit_amount.toFixed(2) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="匹配凭证" width="110">
                <template #default="{ row }">
                  凭证#{{ row.matched_voucher_id }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="未达账项(银行已记企业未记)" name="unmatched">
            <el-table :data="reportUnmatchedDetails" border stripe max-height="350px" size="small">
              <el-table-column prop="transaction_date" label="日期" width="110" />
              <el-table-column prop="description" label="摘要" show-overflow-tooltip />
              <el-table-column label="借方金额" width="120" align="right">
                <template #default="{ row }">
                  <span class="amount-debit">{{ row.debit_amount.toFixed(2) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="贷方金额" width="120" align="right">
                <template #default="{ row }">
                  <span class="amount-credit">{{ row.credit_amount.toFixed(2) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="balance" label="余额" width="120" align="right">
                <template #default="{ row }">
                  {{ row.balance.toFixed(2) }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="余额调节表" name="adjustment">
            <el-table :data="adjustmentTableData" border stripe size="small" :show-header="false" style="width: 100%">
              <el-table-column prop="col1" width="260" />
              <el-table-column prop="col2" align="right" width="160" />
              <el-table-column prop="col3" width="260" />
              <el-table-column prop="col4" align="right" width="160" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
      <template #footer>
        <el-button @click="reportDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  getBankStatements,
  importBankStatements,
  autoMatchStatements,
  deleteBankStatement,
  getReconciliationReport,
  manualMatchStatement,
  unmatchStatement,
  addManualStatement,
  listVoucherItems,
  exportReconciliation,
} from '@/api/bank'

// 状态
const loading = ref(false)
const matching = ref(false)
const importing = ref(false)
const manualAdding = ref(false)
const matchSubmitting = ref(false)
const bankAccount = ref('')
const dateRange = ref([])
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const statements = ref([])
const report = ref(null)

// 导入相关
const importDialogVisible = ref(false)
const importBankAccount = ref('')
const importFile = ref(null)

// 手动添加流水
const manualAddDialogVisible = ref(false)
const manualFormRef = ref(null)
const manualForm = reactive({
  bank_account: '',
  transaction_date: '',
  description: '',
  debit_amount: 0,
  credit_amount: 0,
  balance: 0,
  notes: '',
})
const manualFormRules = {
  bank_account: [{ required: true, message: '请输入银行账号', trigger: 'blur' }],
  transaction_date: [{ required: true, message: '请选择交易日期', trigger: 'change' }],
  description: [{ required: true, message: '请输入摘要', trigger: 'blur' }],
}

// 手动匹配
const matchDialogVisible = ref(false)
const matchingStatement = ref(null)
const voucherItems = ref([])
const voucherItemsLoading = ref(false)
const matchKeyword = ref('')
const selectedVoucherItemId = ref(null)

// 对账报告弹窗
const reportDialogVisible = ref(false)
const reportTab = ref('matched')
const reportMatchedDetails = ref([])
const reportUnmatchedDetails = ref([])

// 余额调节表数据
const adjustmentTableData = computed(() => {
  if (!report.value) return []
  return [
    { col1: '银行对账单余额', col2: report.value.bank_balance.toFixed(2), col3: '企业账面余额', col4: report.value.book_balance.toFixed(2) },
    { col1: '加: 企业已收银行未收', col2: '0.00', col3: '加: 银行已收企业未收', col4: '0.00' },
    { col1: '减: 企业已付银行未付', col2: '0.00', col3: '减: 银行已付企业未付', col4: '0.00' },
    { col1: '调节后余额', col2: report.value.bank_balance.toFixed(2), col3: '调节后余额', col4: report.value.book_balance.toFixed(2) },
  ]
})

// 加载数据
async function loadData() {
  if (!bankAccount.value) return
  loading.value = true
  try {
    const params = {
      bank_account: bankAccount.value,
      page: page.value,
      page_size: pageSize.value,
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getBankStatements(params)
    statements.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}

// 加载对账报告
async function loadReport() {
  if (!bankAccount.value || !dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择银行账号和日期范围')
    return
  }
  try {
    const res = await getReconciliationReport({
      bank_account: bankAccount.value,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
    })
    report.value = res.data
  } catch (e) {
    // 错误已在拦截器中处理
  }
}

// 显示对账报告弹窗
async function handleShowReport() {
  if (!bankAccount.value || !dateRange.value || dateRange.value.length !== 2) {
    ElMessage.warning('请选择银行账号和日期范围')
    return
  }
  await loadReport()
  if (!report.value) return

  // 加载报告详情数据
  const params = {
    bank_account: bankAccount.value,
    start_date: dateRange.value[0],
    end_date: dateRange.value[1],
  }
  try {
    // 获取已匹配明细
    const matchedRes = await getBankStatements({
      ...params,
      match_status: 'matched',
      page_size: 999,
    })
    reportMatchedDetails.value = matchedRes.data.items

    // 获取未匹配明细
    const unmatchedRes = await getBankStatements({
      ...params,
      match_status: 'unmatched',
      page_size: 999,
    })
    reportUnmatchedDetails.value = unmatchedRes.data.items
  } catch (e) {
    // ignore
  }

  reportTab.value = 'matched'
  reportDialogVisible.value = true
}

// 文件选择
function handleFileChange(file) {
  importFile.value = file.raw
}

// 导入
async function handleImport() {
  if (!importFile.value || !importBankAccount.value) return
  importing.value = true
  try {
    const res = await importBankStatements(importFile.value, importBankAccount.value)
    ElMessage.success(res.data.message)
    importDialogVisible.value = false
    bankAccount.value = importBankAccount.value
    importFile.value = null
    loadData()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    importing.value = false
  }
}

// 手动添加流水
async function handleManualAdd() {
  const valid = await manualFormRef.value?.validate().catch(() => false)
  if (!valid) return
  manualAdding.value = true
  try {
    await addManualStatement({ ...manualForm })
    ElMessage.success('添加成功')
    manualAddDialogVisible.value = false
    if (manualForm.bank_account) {
      bankAccount.value = manualForm.bank_account
    }
    // 重置表单
    manualForm.bank_account = ''
    manualForm.transaction_date = ''
    manualForm.description = ''
    manualForm.debit_amount = 0
    manualForm.credit_amount = 0
    manualForm.balance = 0
    manualForm.notes = ''
    loadData()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    manualAdding.value = false
  }
}

// 自动匹配
async function handleAutoMatch() {
  matching.value = true
  try {
    const res = await autoMatchStatements(bankAccount.value)
    ElMessage.success(res.data.message)
    loadData()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    matching.value = false
  }
}

// 打开手动匹配弹窗
async function openMatchDialog(row) {
  matchingStatement.value = row
  selectedVoucherItemId.value = null
  matchKeyword.value = ''
  matchDialogVisible.value = true
  await searchVoucherItems()
}

// 搜索凭证分录
async function searchVoucherItems() {
  voucherItemsLoading.value = true
  try {
    const params = {}
    if (matchKeyword.value) {
      params.keyword = matchKeyword.value
    }
    const res = await listVoucherItems(params)
    voucherItems.value = res.data.items
  } catch (e) {
    // ignore
  } finally {
    voucherItemsLoading.value = false
  }
}

// 选择凭证分录
function handleVoucherItemSelect(row) {
  selectedVoucherItemId.value = row ? row.id : null
}

// 确认手动匹配
async function handleManualMatch() {
  if (!selectedVoucherItemId.value || !matchingStatement.value) return
  matchSubmitting.value = true
  try {
    await manualMatchStatement(matchingStatement.value.id, selectedVoucherItemId.value)
    ElMessage.success('匹配成功')
    matchDialogVisible.value = false
    loadData()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    matchSubmitting.value = false
  }
}

// 取消匹配
async function handleUnmatch(id) {
  try {
    await ElMessageBox.confirm('确认取消该流水的匹配？', '确认', { type: 'warning' })
    await unmatchStatement(id)
    ElMessage.success('已取消匹配')
    loadData()
  } catch (e) {
    // 取消或错误
  }
}

// 删除
async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确认删除该记录？', '确认', { type: 'warning' })
    await deleteBankStatement(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    // 取消或错误
  }
}

// 导出
async function handleExport() {
  if (!bankAccount.value || !dateRange.value || dateRange.value.length !== 2) return
  try {
    const res = await exportReconciliation({
      bank_account: bankAccount.value,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
    })
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `银行对账_${bankAccount.value}_${dateRange.value[0]}_${dateRange.value[1]}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    // 错误已在拦截器中处理
  }
}

onMounted(() => {
  // 默认不自动加载，等待用户输入银行账号
})
</script>

<style scoped>
.bank-reconciliation {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
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

.amount-debit {
  color: #409eff;
}

.amount-credit {
  color: #e6a23c;
}

.text-muted {
  color: #c0c4cc;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>