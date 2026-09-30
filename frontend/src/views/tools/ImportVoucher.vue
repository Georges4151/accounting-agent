<template>
  <div class="import-voucher">
    <el-card class="header-card" shadow="never">
      <div class="page-header">
        <div>
          <h2>导入凭证</h2>
          <p class="desc">从 Excel 文件批量导入凭证数据</p>
        </div>
        <el-button type="success" :icon="Download" @click="handleDownloadTemplate">
          下载模板
        </el-button>
      </div>
    </el-card>

    <!-- 上传区域 -->
    <el-card class="upload-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <span class="card-title">上传 Excel 文件</span>
      </template>

      <div class="upload-section">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        >
          <template #title>
            Excel 文件需包含以下列：<strong>voucher_date、summary、account_code、account_name、description、debit_amount、credit_amount</strong>
          </template>
        </el-alert>

        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".xlsx"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          drag
          :disabled="importing"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            将 Excel 文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">仅支持 .xlsx 格式文件</div>
          </template>
        </el-upload>

        <div style="margin-top: 16px; text-align: center">
          <el-button
            type="primary"
            :disabled="!selectedFile"
            :loading="previewing"
            @click="handlePreview"
          >
            预览数据
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 预览区域 -->
    <el-card v-if="previewData.length > 0 || previewErrors.length > 0" class="preview-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span class="card-title">数据预览</span>
          <div>
            <el-tag type="info" size="small" style="margin-right: 8px">
              共 {{ previewData.length }} 条记录
            </el-tag>
            <el-tag type="warning" size="small" style="margin-right: 8px">
              {{ voucherCount }} 个凭证
            </el-tag>
            <el-tag v-if="previewErrors.length > 0" type="danger" size="small">
              {{ previewErrors.length }} 个错误
            </el-tag>
          </div>
        </div>
      </template>

      <!-- 错误提示 -->
      <div v-if="previewErrors.length > 0" style="margin-bottom: 16px">
        <el-alert
          v-for="(err, idx) in previewErrors"
          :key="idx"
          :title="`第 ${err.row} 行: ${err.message}`"
          type="error"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        />
      </div>

      <!-- 预览表格 -->
      <el-table :data="previewData" border stripe style="width: 100%" max-height="500" v-if="previewData.length > 0">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="voucher_group" label="凭证组" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="primary">{{ row.voucher_group }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="voucher_date" label="凭证日期" width="120" />
        <el-table-column prop="summary" label="摘要" min-width="160" />
        <el-table-column prop="account_code" label="科目编码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="160" />
        <el-table-column prop="description" label="分录描述" min-width="120" />
        <el-table-column prop="debit_amount" label="借方金额" width="120" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.debit_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="credit_amount" label="贷方金额" width="120" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.credit_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row._warning" type="warning" size="small">不平衡</el-tag>
            <el-tag v-else type="success" size="small">正常</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- 确认导入按钮 -->
      <div v-if="previewData.length > 0 && previewErrors.length === 0" style="margin-top: 16px; text-align: center">
        <el-button
          type="success"
          :loading="importing"
          @click="handleImport"
          size="large"
        >
          确认导入 {{ voucherCount }} 个凭证
        </el-button>
      </div>
    </el-card>

    <!-- 导入结果 -->
    <el-card v-if="importResult" class="result-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <span class="card-title">导入结果</span>
      </template>
      <div class="result-summary">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-statistic title="总记录数" :value="importResult.total_count" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="成功" :value="importResult.success_count">
              <template #suffix>
                <el-icon style="color: #67c23a"><CircleCheck /></el-icon>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="失败" :value="importResult.error_count">
              <template #suffix>
                <el-icon style="color: #f56c6c"><CircleClose /></el-icon>
              </template>
            </el-statistic>
          </el-col>
        </el-row>
      </div>
      <div v-if="importResult.errors && importResult.errors.length > 0" style="margin-top: 16px">
        <h4>错误详情</h4>
        <el-alert
          v-for="(err, idx) in importResult.errors"
          :key="idx"
          :title="`第 ${err.row} 行: ${err.message}`"
          type="error"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, UploadFilled, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { previewVoucherImport, importVouchers, downloadVoucherTemplate } from '@/api/importExport'

const uploadRef = ref(null)
const selectedFile = ref(null)
const previewing = ref(false)
const importing = ref(false)
const previewData = ref([])
const previewErrors = ref([])
const voucherCount = ref(0)
const importResult = ref(null)

function formatMoney(value) {
  if (value == null || isNaN(value)) return '0.00'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function handleFileChange(file) {
  selectedFile.value = file.raw
  importResult.value = null
}

function handleFileRemove() {
  selectedFile.value = null
  previewData.value = []
  previewErrors.value = []
  importResult.value = null
}

function handleDownloadTemplate() {
  downloadVoucherTemplate().then(res => {
    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'voucher_import_template.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  }).catch(() => {
    ElMessage.error('模板下载失败')
  })
}

async function handlePreview() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  previewing.value = true
  previewData.value = []
  previewErrors.value = []
  importResult.value = null

  try {
    const res = await previewVoucherImport(selectedFile.value)
    previewData.value = res.data.items || []
    previewErrors.value = res.data.errors || []
    voucherCount.value = res.data.voucher_count || 0
    if (previewData.value.length === 0 && previewErrors.value.length === 0) {
      ElMessage.warning('文件中没有有效数据')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '预览失败')
  } finally {
    previewing.value = false
  }
}

async function handleImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  importing.value = true
  try {
    const res = await importVouchers(selectedFile.value)
    importResult.value = res.data
    if (res.data.error_count === 0) {
      ElMessage.success(`成功导入 ${res.data.success_count} 个凭证`)
    } else {
      ElMessage.warning(`导入完成: 成功 ${res.data.success_count} 个, 失败 ${res.data.error_count} 个`)
    }
    selectedFile.value = null
    uploadRef.value?.clearFiles()
    previewData.value = []
    previewErrors.value = []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.import-voucher {
  max-width: 1100px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.page-header h2 {
  font-size: 20px;
  color: #303133;
  margin-bottom: 4px;
}

.desc {
  font-size: 13px;
  color: #909399;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.upload-section {
  padding: 0 20px;
}

.result-summary {
  padding: 10px 0;
}
</style>