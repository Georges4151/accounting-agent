<template>
  <div class="import-export-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据导入导出</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" type="border-card">
        <!-- Tab 1: 导入凭证 -->
        <el-tab-pane label="导入凭证" name="import-vouchers">
          <div class="tab-content">
            <!-- 下载模板 -->
            <div class="section">
              <h4>第一步：下载模板</h4>
              <el-button type="primary" @click="downloadVoucherTemplate" :loading="downloadingTemplate">
                <el-icon><Download /></el-icon>
                下载凭证导入模板
              </el-button>
              <span class="tip-text">下载模板后，按模板格式填写凭证数据</span>
            </div>

            <!-- 上传文件 -->
            <div class="section">
              <h4>第二步：上传文件</h4>
              <el-upload
                ref="voucherUploadRef"
                drag
                :auto-upload="false"
                :limit="1"
                accept=".xlsx"
                :on-change="handleVoucherFileChange"
                :on-remove="handleVoucherFileRemove"
                :file-list="voucherFileList"
              >
                <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                <div class="el-upload__text">
                  将 Excel 文件拖到此处，或<em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    仅支持 .xlsx 格式的 Excel 文件。模板列：voucher_date, summary, account_code, account_name, description, debit_amount, credit_amount
                  </div>
                </template>
              </el-upload>
            </div>

            <!-- 预览数据 -->
            <div class="section" v-if="voucherPreviewData.length > 0">
              <h4>第三步：预览数据</h4>
              <el-table :data="voucherPreviewData" border stripe max-height="400" style="width: 100%">
                <el-table-column prop="voucher_date" label="凭证日期" width="120" />
                <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
                <el-table-column prop="account_code" label="科目编码" width="120" />
                <el-table-column prop="account_name" label="科目名称" width="140" />
                <el-table-column prop="description" label="分录描述" min-width="180" show-overflow-tooltip />
                <el-table-column prop="debit_amount" label="借方金额" width="120" align="right" />
                <el-table-column prop="credit_amount" label="贷方金额" width="120" align="right" />
              </el-table>
            </div>

            <!-- 导入按钮 -->
            <div class="section" v-if="voucherFile">
              <h4>第四步：执行导入</h4>
              <el-button
                type="success"
                size="large"
                @click="executeVoucherImport"
                :loading="importingVouchers"
              >
                <el-icon><Upload /></el-icon>
                开始导入
              </el-button>
            </div>

            <!-- 导入结果 -->
            <div class="section" v-if="voucherImportResult">
              <h4>导入结果</h4>
              <el-alert
                :type="voucherImportResult.error_count === 0 ? 'success' : 'warning'"
                :closable="false"
                show-icon
              >
                <template #title>
                  共 {{ voucherImportResult.total_count }} 条记录，
                  成功 {{ voucherImportResult.success_count }} 条，
                  失败 {{ voucherImportResult.error_count }} 条
                </template>
              </el-alert>
              <div v-if="voucherImportResult.errors && voucherImportResult.errors.length > 0" class="error-list">
                <h4>错误详情：</h4>
                <el-table :data="voucherImportResult.errors" border size="small" max-height="300">
                  <el-table-column prop="row" label="行号" width="80" />
                  <el-table-column prop="message" label="错误信息" show-overflow-tooltip />
                </el-table>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Tab 2: 导入科目 -->
        <el-tab-pane label="导入科目" name="import-accounts">
          <div class="tab-content">
            <div class="section">
              <h4>第一步：下载模板</h4>
              <el-button type="primary" @click="downloadAccountTemplate" :loading="downloadingTemplate">
                <el-icon><Download /></el-icon>
                下载科目导入模板
              </el-button>
              <span class="tip-text">下载模板后，按模板格式填写科目数据</span>
            </div>

            <div class="section">
              <h4>第二步：上传文件</h4>
              <el-upload
                ref="accountUploadRef"
                drag
                :auto-upload="false"
                :limit="1"
                accept=".xlsx"
                :on-change="handleAccountFileChange"
                :on-remove="handleAccountFileRemove"
                :file-list="accountFileList"
              >
                <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                <div class="el-upload__text">
                  将 Excel 文件拖到此处，或<em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    仅支持 .xlsx 格式。列：account_code, account_name, account_type, parent_code, balance_direction
                  </div>
                </template>
              </el-upload>
            </div>

            <div class="section" v-if="accountPreviewData.length > 0">
              <h4>第三步：预览数据</h4>
              <el-table :data="accountPreviewData" border stripe max-height="400" style="width: 100%">
                <el-table-column prop="account_code" label="科目编码" width="120" />
                <el-table-column prop="account_name" label="科目名称" width="160" />
                <el-table-column prop="account_type" label="科目类型" width="120" />
                <el-table-column prop="parent_code" label="上级编码" width="120" />
                <el-table-column prop="balance_direction" label="余额方向" width="120" />
              </el-table>
            </div>

            <div class="section" v-if="accountFile">
              <h4>第四步：执行导入</h4>
              <el-button
                type="success"
                size="large"
                @click="executeAccountImport"
                :loading="importingAccounts"
              >
                <el-icon><Upload /></el-icon>
                开始导入
              </el-button>
            </div>

            <div class="section" v-if="accountImportResult">
              <h4>导入结果</h4>
              <el-alert
                :type="accountImportResult.error_count === 0 ? 'success' : 'warning'"
                :closable="false"
                show-icon
              >
                <template #title>
                  共 {{ accountImportResult.total_count }} 条记录，
                  成功 {{ accountImportResult.success_count }} 条，
                  失败 {{ accountImportResult.error_count }} 条
                </template>
              </el-alert>
              <div v-if="accountImportResult.errors && accountImportResult.errors.length > 0" class="error-list">
                <h4>错误详情：</h4>
                <el-table :data="accountImportResult.errors" border size="small" max-height="300">
                  <el-table-column prop="row" label="行号" width="80" />
                  <el-table-column prop="message" label="错误信息" show-overflow-tooltip />
                </el-table>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Tab 3: 导出数据 -->
        <el-tab-pane label="导出数据" name="export-data">
          <div class="tab-content">
            <!-- 凭证导出 -->
            <div class="section">
              <h4>导出凭证</h4>
              <el-form :inline="true" class="export-form">
                <el-form-item label="开始日期">
                  <el-date-picker
                    v-model="exportFilters.start_date"
                    type="date"
                    placeholder="选择开始日期"
                    value-format="YYYY-MM-DD"
                    clearable
                  />
                </el-form-item>
                <el-form-item label="结束日期">
                  <el-date-picker
                    v-model="exportFilters.end_date"
                    type="date"
                    placeholder="选择结束日期"
                    value-format="YYYY-MM-DD"
                    clearable
                  />
                </el-form-item>
                <el-form-item label="状态">
                  <el-select v-model="exportFilters.status" placeholder="全部" clearable style="width: 120px">
                    <el-option label="草稿" value="draft" />
                    <el-option label="已提交" value="submitted" />
                    <el-option label="已审核" value="reviewed" />
                    <el-option label="已过账" value="posted" />
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="executeVoucherExport" :loading="exportingVouchers">
                    <el-icon><Download /></el-icon>
                    导出凭证 Excel
                  </el-button>
                </el-form-item>
              </el-form>
            </div>

            <el-divider />

            <!-- 报表导出 -->
            <div class="section">
              <h4>导出报表</h4>
              <el-form :inline="true" class="export-form">
                <el-form-item label="报表类型">
                  <el-select v-model="exportFilters.report_type" placeholder="选择报表类型" style="width: 180px">
                    <el-option label="资产负债表" value="balance-sheet" />
                    <el-option label="利润表" value="income-statement" />
                    <el-option label="现金流量表" value="cash-flow" />
                    <el-option label="科目余额表" value="account-ledger" />
                  </el-select>
                </el-form-item>
                <el-form-item label="报表月份">
                  <el-date-picker
                    v-model="exportFilters.report_period"
                    type="month"
                    placeholder="选择月份"
                    value-format="YYYY-MM"
                    clearable
                  />
                </el-form-item>
                <el-form-item>
                  <el-button
                    type="primary"
                    @click="executeReportExport"
                    :loading="exportingReport"
                    :disabled="!exportFilters.report_type"
                  >
                    <el-icon><Download /></el-icon>
                    导出报表 Excel
                  </el-button>
                </el-form-item>
              </el-form>
            </div>
          </div>
        </el-tab-pane>

        <!-- Tab 4: 备份与恢复 -->
        <el-tab-pane label="备份与恢复" name="backup">
          <div class="tab-content">
            <!-- 创建备份 -->
            <div class="section">
              <h4>创建备份</h4>
              <p class="section-desc">将所有凭证、分录和科目数据导出为 JSON 备份文件</p>
              <el-button type="primary" @click="executeBackup" :loading="creatingBackup">
                <el-icon><Download /></el-icon>
                创建备份并下载
              </el-button>
            </div>

            <el-divider />

            <!-- 恢复备份 -->
            <div class="section">
              <h4>从备份恢复</h4>
              <el-alert
                type="error"
                :closable="false"
                show-icon
                class="warning-alert"
              >
                <template #title>
                  警告：恢复操作将清除所有现有数据（凭证、分录、科目），并用备份文件中的数据替换！
                </template>
              </el-alert>

              <div style="margin-top: 16px">
                <el-upload
                  ref="restoreUploadRef"
                  drag
                  :auto-upload="false"
                  :limit="1"
                  accept=".json"
                  :on-change="handleRestoreFileChange"
                  :on-remove="handleRestoreFileRemove"
                  :file-list="restoreFileList"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">
                    将 JSON 备份文件拖到此处，或<em>点击上传</em>
                  </div>
                  <template #tip>
                    <div class="el-upload__tip">仅支持 .json 格式的备份文件</div>
                  </template>
                </el-upload>
              </div>

              <div v-if="restoreFile" style="margin-top: 16px">
                <el-popconfirm
                  title="确定要从备份文件恢复吗？当前所有数据将被清除！"
                  confirm-button-text="确定恢复"
                  cancel-button-text="取消"
                  @confirm="executeRestore"
                >
                  <template #reference>
                    <el-button type="danger" size="large" :loading="restoringBackup">
                      <el-icon><WarningFilled /></el-icon>
                      从备份文件恢复
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>

              <div v-if="restoreResult" class="restore-result" style="margin-top: 16px">
                <el-alert type="success" :closable="false" show-icon>
                  <template #title>恢复成功！</template>
                  已恢复科目 {{ restoreResult.accounts_count }} 个，
                  凭证 {{ restoreResult.vouchers_count }} 个，
                  分录 {{ restoreResult.items_count }} 条
                </el-alert>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import {
  importVouchers,
  importAccounts,
  exportVouchers,
  exportReport,
  downloadBackup,
  restoreBackup,
  downloadTemplate
} from '@/api/importExport'

// 当前激活的 Tab
const activeTab = ref('import-vouchers')

// ========== 导入凭证 ==========
const voucherUploadRef = ref(null)
const voucherFileList = ref([])
const voucherFile = ref(null)
const voucherPreviewData = ref([])
const voucherImportResult = ref(null)
const importingVouchers = ref(false)
const downloadingTemplate = ref(false)

function handleVoucherFileChange(file) {
  voucherFile.value = file.raw
  voucherFileList.value = [file]
  voucherImportResult.value = null
  parseVoucherExcel(file.raw)
}

function handleVoucherFileRemove() {
  voucherFile.value = null
  voucherFileList.value = []
  voucherPreviewData.value = []
  voucherImportResult.value = null
}

function parseVoucherExcel(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array' })
      const sheet = workbook.Sheets[workbook.SheetNames[0]]
      const jsonData = XLSX.utils.sheet_to_json(sheet, { header: 1 })
      if (jsonData.length < 2) {
        ElMessage.warning('Excel 文件至少需要包含表头行和一行数据')
        return
      }
      const headers = jsonData[0].map(h => String(h || '').trim())
      const rows = jsonData.slice(1).filter(row =>
        row && row.some(cell => cell !== null && cell !== undefined && String(cell).trim() !== '')
      )
      voucherPreviewData.value = rows.map(row => {
        const item = {}
        headers.forEach((h, i) => {
          item[h] = row[i] !== undefined && row[i] !== null ? String(row[i]).trim() : ''
        })
        return item
      })
    } catch (err) {
      ElMessage.error('Excel 文件解析失败: ' + err.message)
    }
  }
  reader.readAsArrayBuffer(file)
}

async function downloadVoucherTemplate() {
  downloadingTemplate.value = true
  try {
    const res = await downloadTemplate('voucher-import')
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = 'voucher_import_template.xlsx'
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch (err) {
    ElMessage.error('模板下载失败')
  } finally {
    downloadingTemplate.value = false
  }
}

async function executeVoucherImport() {
  if (!voucherFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importingVouchers.value = true
  try {
    const res = await importVouchers(voucherFile.value)
    voucherImportResult.value = res.data
    if (res.data.error_count === 0) {
      ElMessage.success(`成功导入 ${res.data.success_count} 条凭证`)
    }
  } catch (err) {
    ElMessage.error('导入失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    importingVouchers.value = false
  }
}

// ========== 导入科目 ==========
const accountUploadRef = ref(null)
const accountFileList = ref([])
const accountFile = ref(null)
const accountPreviewData = ref([])
const accountImportResult = ref(null)
const importingAccounts = ref(false)

function handleAccountFileChange(file) {
  accountFile.value = file.raw
  accountFileList.value = [file]
  accountImportResult.value = null
  parseAccountExcel(file.raw)
}

function handleAccountFileRemove() {
  accountFile.value = null
  accountFileList.value = []
  accountPreviewData.value = []
  accountImportResult.value = null
}

function parseAccountExcel(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = new Uint8Array(e.target.result)
      const workbook = XLSX.read(data, { type: 'array' })
      const sheet = workbook.Sheets[workbook.SheetNames[0]]
      const jsonData = XLSX.utils.sheet_to_json(sheet, { header: 1 })
      if (jsonData.length < 2) {
        ElMessage.warning('Excel 文件至少需要包含表头行和一行数据')
        return
      }
      const headers = jsonData[0].map(h => String(h || '').trim())
      const rows = jsonData.slice(1).filter(row =>
        row && row.some(cell => cell !== null && cell !== undefined && String(cell).trim() !== '')
      )
      accountPreviewData.value = rows.map(row => {
        const item = {}
        headers.forEach((h, i) => {
          item[h] = row[i] !== undefined && row[i] !== null ? String(row[i]).trim() : ''
        })
        return item
      })
    } catch (err) {
      ElMessage.error('Excel 文件解析失败: ' + err.message)
    }
  }
  reader.readAsArrayBuffer(file)
}

async function downloadAccountTemplate() {
  downloadingTemplate.value = true
  try {
    const res = await downloadTemplate('account-import')
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = 'account_import_template.xlsx'
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch (err) {
    ElMessage.error('模板下载失败')
  } finally {
    downloadingTemplate.value = false
  }
}

async function executeAccountImport() {
  if (!accountFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importingAccounts.value = true
  try {
    const res = await importAccounts(accountFile.value)
    accountImportResult.value = res.data
    if (res.data.error_count === 0) {
      ElMessage.success(`成功导入 ${res.data.success_count} 条科目`)
    }
  } catch (err) {
    ElMessage.error('导入失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    importingAccounts.value = false
  }
}

// ========== 导出数据 ==========
const exportFilters = reactive({
  start_date: '',
  end_date: '',
  status: '',
  report_type: '',
  report_period: ''
})
const exportingVouchers = ref(false)
const exportingReport = ref(false)

function downloadBlob(data, filename) {
  const url = window.URL.createObjectURL(new Blob([data]))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

async function executeVoucherExport() {
  exportingVouchers.value = true
  try {
    const params = {}
    if (exportFilters.start_date) params.start_date = exportFilters.start_date
    if (exportFilters.end_date) params.end_date = exportFilters.end_date
    if (exportFilters.status) params.status = exportFilters.status
    const res = await exportVouchers(params)
    downloadBlob(res.data, `vouchers_${exportFilters.start_date || 'all'}_${exportFilters.end_date || 'all'}.xlsx`)
    ElMessage.success('凭证导出成功')
  } catch (err) {
    ElMessage.error('导出失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    exportingVouchers.value = false
  }
}

async function executeReportExport() {
  if (!exportFilters.report_type) {
    ElMessage.warning('请选择报表类型')
    return
  }
  exportingReport.value = true
  try {
    const params = {}
    if (exportFilters.report_period) params.period = exportFilters.report_period
    const res = await exportReport(exportFilters.report_type, params)
    const typeNames = {
      'balance-sheet': '资产负债表',
      'income-statement': '利润表',
      'cash-flow': '现金流量表',
      'account-ledger': '科目余额表'
    }
    const name = typeNames[exportFilters.report_type] || exportFilters.report_type
    downloadBlob(res.data, `${name}_${exportFilters.report_period || 'report'}.xlsx`)
    ElMessage.success('报表导出成功')
  } catch (err) {
    ElMessage.error('导出失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    exportingReport.value = false
  }
}

// ========== 备份与恢复 ==========
const creatingBackup = ref(false)
const restoreUploadRef = ref(null)
const restoreFileList = ref([])
const restoreFile = ref(null)
const restoringBackup = ref(false)
const restoreResult = ref(null)

async function executeBackup() {
  creatingBackup.value = true
  try {
    const res = await downloadBackup()
    const now = new Date()
    const ts = now.toISOString().replace(/[:.]/g, '-').slice(0, 19)
    downloadBlob(res.data, `accounting_backup_${ts}.json`)
    ElMessage.success('备份创建成功')
  } catch (err) {
    ElMessage.error('备份失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    creatingBackup.value = false
  }
}

function handleRestoreFileChange(file) {
  restoreFile.value = file.raw
  restoreFileList.value = [file]
  restoreResult.value = null
}

function handleRestoreFileRemove() {
  restoreFile.value = null
  restoreFileList.value = []
  restoreResult.value = null
}

async function executeRestore() {
  if (!restoreFile.value) {
    ElMessage.warning('请先选择备份文件')
    return
  }
  restoringBackup.value = true
  try {
    const res = await restoreBackup(restoreFile.value)
    restoreResult.value = res.data
    ElMessage.success('数据恢复成功')
  } catch (err) {
    ElMessage.error('恢复失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    restoringBackup.value = false
  }
}
</script>

<style scoped>
.import-export-page {
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  font-size: 18px;
  font-weight: 600;
}

.tab-content {
  padding: 16px 0;
}

.section {
  margin-bottom: 24px;
}

.section h4 {
  margin-bottom: 12px;
  color: #303133;
  font-size: 15px;
}

.section-desc {
  color: #909399;
  margin-bottom: 12px;
  font-size: 14px;
}

.tip-text {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}

.export-form {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 6px;
}

.error-list {
  margin-top: 12px;
}

.error-list h4 {
  color: #e6a23c;
  margin-bottom: 8px;
}

.warning-alert {
  margin-bottom: 0;
}

.restore-result {
  margin-top: 16px;
}
</style>