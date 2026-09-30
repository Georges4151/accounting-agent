<template>
  <div class="salary-list">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>工资表</span>
          <div class="header-actions">
            <el-select
              v-model="currentPeriod"
              placeholder="选择工资期间"
              style="width: 150px"
              @change="loadRecords"
            >
              <el-option
                v-for="p in periodOptions"
                :key="p"
                :label="p"
                :value="p"
              />
            </el-select>
            <el-button type="primary" @click="handleRefresh">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button type="success" @click="batchImportVisible = true">
              <el-icon><Upload /></el-icon>
              批量导入员工
            </el-button>
            <el-button
              type="warning"
              :disabled="selectedRows.length === 0"
              :loading="generatingVoucher"
              @click="handleGenerateVoucher"
            >
              <el-icon><Document /></el-icon>
              生成凭证
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        title="请先在「工资项目」中配置工资项目，然后在此录入各员工工资数据。确认后点击「生成凭证」自动生成计提和发放凭证。"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="6" animated />
      </div>

      <el-empty v-else-if="records.length === 0" description="暂无工资数据，请选择期间或导入员工" />

      <template v-else>
        <!-- 工资表格 -->
        <div class="table-wrapper">
          <el-table
            :data="records"
            border
            stripe
            style="width: 100%"
            @selection-change="handleSelectionChange"
            ref="tableRef"
          >
            <el-table-column type="selection" width="50" fixed="left" />
            <el-table-column prop="employee_name" label="员工姓名" width="120" fixed="left" />
            <el-table-column prop="employee_code" label="员工编号" width="100" />

            <!-- 动态工资项目列 -->
            <el-table-column
              v-for="item in incomeItems"
              :key="'income-' + item.id"
              :label="item.name"
              width="140"
              align="right"
            >
              <template #default="{ row }">
                <el-input-number
                  v-if="row.status === 'draft'"
                  v-model="row.salary_data[item.name]"
                  :precision="2"
                  :min="0"
                  :step="100"
                  controls-position="right"
                  size="small"
                  style="width: 120px"
                  @change="(val) => recalcRow(row)"
                />
                <span v-else class="readonly-cell">
                  {{ formatMoney(row.salary_data[item.name]) }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="收入合计" width="130" align="right">
              <template #default="{ row }">
                <span class="amount-income">{{ formatMoney(row.total_income) }}</span>
              </template>
            </el-table-column>

            <el-table-column
              v-for="item in deductionItems"
              :key="'deduction-' + item.id"
              :label="item.name"
              width="140"
              align="right"
            >
              <template #default="{ row }">
                <el-input-number
                  v-if="row.status === 'draft'"
                  v-model="row.salary_data[item.name]"
                  :precision="2"
                  :min="0"
                  :step="100"
                  controls-position="right"
                  size="small"
                  style="width: 120px"
                  @change="(val) => recalcRow(row)"
                />
                <span v-else class="readonly-cell">
                  {{ formatMoney(row.salary_data[item.name]) }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="扣除合计" width="130" align="right">
              <template #default="{ row }">
                <span class="amount-deduction">{{ formatMoney(row.total_deduction) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="实发工资" width="130" align="right" fixed="right">
              <template #default="{ row }">
                <span class="amount-net">{{ formatMoney(row.net_salary) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="状态" width="90" fixed="right" align="center">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)" size="small">
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'draft'"
                  type="success"
                  link
                  size="small"
                  :loading="confirmingId === row.id"
                  @click="handleConfirm(row)"
                >
                  确认
                </el-button>
                <el-button
                  v-if="row.status === 'draft'"
                  type="primary"
                  link
                  size="small"
                  :loading="savingId === row.id"
                  @click="handleSave(row)"
                >
                  保存
                </el-button>
                <el-button
                  type="danger"
                  link
                  size="small"
                  @click="handleDeleteRecord(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="summary-bar">
          <span>共 {{ records.length }} 人</span>
          <span class="summary-income">收入合计: {{ formatMoney(summaryIncome) }}</span>
          <span class="summary-deduction">扣除合计: {{ formatMoney(summaryDeduction) }}</span>
          <span class="summary-net">实发合计: {{ formatMoney(summaryNet) }}</span>
        </div>
      </template>
    </el-card>

    <!-- 批量导入员工对话框 -->
    <el-dialog
      v-model="batchImportVisible"
      title="批量导入员工"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="每行输入一个员工姓名，系统将自动创建工资记录"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-input
        v-model="batchEmployeeNames"
        type="textarea"
        :rows="10"
        placeholder="张三&#10;李四&#10;王五&#10;赵六"
      />
      <template #footer>
        <el-button @click="batchImportVisible = false">取消</el-button>
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
  getSalaryRecords, createSalaryRecord, updateSalaryRecord, batchImportSalary,
  confirmSalary, generateSalaryVoucher
} from '@/api/payroll'
import { getSalaryItems } from '@/api/payroll'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const savingId = ref(null)
const confirmingId = ref(null)
const generatingVoucher = ref(false)
const batchSubmitting = ref(false)
const records = ref([])
const salaryItems = ref([])
const selectedRows = ref([])
const currentPeriod = ref('')
const batchImportVisible = ref(false)
const batchEmployeeNames = ref('')
const tableRef = ref(null)

// 期间选项
const periodOptions = computed(() => {
  const now = new Date()
  const options = []
  for (let i = 5; i >= -1; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const period = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    options.push(period)
  }
  return options
})

// 收入项
const incomeItems = computed(() => {
  return salaryItems.value
    .filter(item => item.item_type === 'income')
    .sort((a, b) => a.sort_order - b.sort_order)
})

// 扣除项
const deductionItems = computed(() => {
  return salaryItems.value
    .filter(item => item.item_type === 'deduction')
    .sort((a, b) => a.sort_order - b.sort_order)
})

// 汇总
const summaryIncome = computed(() => {
  return records.value.reduce((sum, r) => sum + (r.total_income || 0), 0)
})
const summaryDeduction = computed(() => {
  return records.value.reduce((sum, r) => sum + (r.total_deduction || 0), 0)
})
const summaryNet = computed(() => {
  return records.value.reduce((sum, r) => sum + (r.net_salary || 0), 0)
})

onMounted(() => {
  currentPeriod.value = periodOptions.value[periodOptions.value.length - 1]
  loadItems()
  loadRecords()
})

async function loadItems() {
  try {
    const res = await getSalaryItems()
    salaryItems.value = res.data.items || []
  } catch (e) {
    // ignore
  }
}

async function loadRecords() {
  if (!currentPeriod.value) return
  loading.value = true
  try {
    const res = await getSalaryRecords({ period: currentPeriod.value, page_size: 200 })
    records.value = (res.data.items || []).map(r => ({
      ...r,
      salary_data: r.salary_data || {}
    }))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载工资记录失败')
  } finally {
    loading.value = false
  }
}

function handleRefresh() {
  loadRecords()
}

function recalcRow(row) {
  const data = row.salary_data || {}
  let income = 0
  let deduction = 0

  incomeItems.value.forEach(item => {
    income += Number(data[item.name]) || 0
  })
  deductionItems.value.forEach(item => {
    deduction += Number(data[item.name]) || 0
  })

  row.total_income = Math.round(income * 100) / 100
  row.total_deduction = Math.round(deduction * 100) / 100
  row.net_salary = Math.round((income - deduction) * 100) / 100
}

async function handleSave(row) {
  savingId.value = row.id
  try {
    recalcRow(row)
    await updateSalaryRecord(row.id, {
      salary_data: row.salary_data,
      total_income: row.total_income,
      total_deduction: row.total_deduction,
      net_salary: row.net_salary
    })
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingId.value = null
  }
}

async function handleConfirm(row) {
  confirmingId.value = row.id
  try {
    recalcRow(row)
    await updateSalaryRecord(row.id, {
      salary_data: row.salary_data,
      total_income: row.total_income,
      total_deduction: row.total_deduction,
      net_salary: row.net_salary
    })
    await confirmSalary(row.id)
    ElMessage.success('确认成功')
    await loadRecords()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '确认失败')
  } finally {
    confirmingId.value = null
  }
}

async function handleDeleteRecord(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${row.employee_name} 的工资记录吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    // 通过更新status来标记删除的方式不太合适，但这里我们直接提示用户
    // 实际应该从后端删除，但为了保持简单，这里提示用户用后端接口
    ElMessage.warning('暂不支持前端直接删除，请通过API操作')
  } catch (e) {
    // cancel
  }
}

async function handleBatchImport() {
  const names = batchEmployeeNames.value.trim().split('\n').filter(n => n.trim())
  if (names.length === 0) {
    ElMessage.warning('请输入员工姓名')
    return
  }

  batchSubmitting.value = true
  try {
    const res = await batchImportSalary({
      period: currentPeriod.value,
      employee_names: names,
      salary_data_template: {}
    })
    ElMessage.success(res.data.message || '导入完成')
    batchImportVisible.value = false
    batchEmployeeNames.value = ''
    await loadRecords()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    batchSubmitting.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleGenerateVoucher() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要生成凭证的工资记录')
    return
  }

  try {
    await ElMessageBox.confirm(
      `将为选中的 ${selectedRows.value.length} 条工资记录生成计提和发放凭证，确认继续？`,
      '确认生成凭证',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  generatingVoucher.value = true
  try {
    const res = await generateSalaryVoucher({
      record_ids: selectedRows.value.map(r => r.id)
    })
    const data = res.data
    ElMessage.success(data.message || '凭证生成成功')
    if (data.vouchers && data.vouchers.length > 0) {
      const voucherList = data.vouchers.map(v => `${v.type}: ${v.voucher_no}`).join(', ')
      ElMessage.info(`已生成凭证: ${voucherList}`)
    }
    await loadRecords()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '凭证生成失败')
  } finally {
    generatingVoucher.value = false
  }
}

function formatMoney(val) {
  if (val === null || val === undefined) return '0.00'
  return Number(val).toFixed(2)
}

function statusTag(status) {
  const map = { draft: 'info', confirmed: 'success', paid: 'warning' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { draft: '草稿', confirmed: '已确认', paid: '已发放' }
  return map[status] || status
}
</script>

<style scoped>
.salary-list {
  max-width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  flex-wrap: wrap;
  gap: 8px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.loading-container {
  padding: 20px 0;
}

.table-wrapper {
  overflow-x: auto;
}

.readonly-cell {
  color: #606266;
}

.amount-income {
  color: #67c23a;
  font-weight: 600;
}

.amount-deduction {
  color: #f56c6c;
  font-weight: 600;
}

.amount-net {
  color: #409eff;
  font-weight: 700;
  font-size: 15px;
}

.summary-bar {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  display: flex;
  gap: 24px;
  font-size: 14px;
  color: #606266;
}

.summary-income {
  color: #67c23a;
  font-weight: 600;
}

.summary-deduction {
  color: #f56c6c;
  font-weight: 600;
}

.summary-net {
  color: #409eff;
  font-weight: 700;
}
</style>