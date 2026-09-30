<template>
  <div class="fixed-asset-container">
    <div class="page-header">
      <h2>固定资产管理</h2>
      <div class="header-actions">
        <el-button type="warning" @click="handleDepreciate" :loading="depreciating">
          计提折旧
        </el-button>
        <el-button type="primary" @click="showCreateDialog = true">
          新增资产
        </el-button>
      </div>
    </div>

    <!-- 汇总卡片 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-statistic title="资产总数" :value="summary.count" />
      </el-col>
      <el-col :span="6">
        <el-statistic title="原值合计" :value="summary.total_original" :precision="2" />
      </el-col>
      <el-col :span="6">
        <el-statistic title="累计折旧" :value="summary.total_depreciation" :precision="2" />
      </el-col>
      <el-col :span="6">
        <el-statistic title="净值合计" :value="summary.total_net" :precision="2" />
      </el-col>
    </el-row>

    <!-- 筛选 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="资产类别">
          <el-select v-model="filterCategory" clearable placeholder="全部" @change="loadData" style="width: 150px">
            <el-option label="房屋建筑" value="房屋建筑" />
            <el-option label="机器设备" value="机器设备" />
            <el-option label="运输工具" value="运输工具" />
            <el-option label="电子设备" value="电子设备" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" clearable placeholder="全部" @change="loadData" style="width: 120px">
            <el-option label="使用中" value="in_use" />
            <el-option label="已提足" value="fully_depreciated" />
            <el-option label="已报废" value="scrapped" />
            <el-option label="已处置" value="disposed" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 资产列表 -->
    <el-table :data="assets" v-loading="loading" border stripe>
      <el-table-column prop="asset_code" label="资产编码" width="120" />
      <el-table-column prop="asset_name" label="资产名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="类别" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="categoryTag(row.category)">{{ row.category }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="原值" width="130" align="right">
        <template #default="{ row }">
          {{ row.original_value.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column label="月折旧额" width="120" align="right">
        <template #default="{ row }">
          {{ row.monthly_depreciation.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column label="累计折旧" width="130" align="right">
        <template #default="{ row }">
          {{ row.accumulated_depreciation.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column label="净值" width="130" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.net_value <= row.salvage_value ? '#909399' : '#303133' }">
            {{ row.net_value.toFixed(2) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="使用进度" width="120" align="center">
        <template #default="{ row }">
          <el-progress
            :percentage="depreciationProgress(row)"
            :status="row.status === 'fully_depreciated' ? 'success' : undefined"
            :stroke-width="6"
            :show-text="false"
          />
          <span style="font-size: 12px; color: #909399">{{ depreciationProgressLabel(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="购置日期" width="120">
        <template #default="{ row }">
          {{ row.purchase_date }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="showHistory(row)">折旧历史</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增资产弹窗 -->
    <el-dialog v-model="showCreateDialog" title="新增固定资产" width="550px">
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="资产编码" required>
          <el-input v-model="createForm.asset_code" placeholder="如：FA-2024-001" />
        </el-form-item>
        <el-form-item label="资产名称" required>
          <el-input v-model="createForm.asset_name" placeholder="如：联想笔记本电脑" />
        </el-form-item>
        <el-form-item label="资产类别" required>
          <el-select v-model="createForm.category" style="width: 100%">
            <el-option label="房屋建筑" value="房屋建筑" />
            <el-option label="机器设备" value="机器设备" />
            <el-option label="运输工具" value="运输工具" />
            <el-option label="电子设备" value="电子设备" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="数量">
              <el-input-number v-model="createForm.quantity" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位">
              <el-input v-model="createForm.unit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="购置日期" required>
          <el-date-picker v-model="createForm.purchase_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="原值" required>
              <el-input-number v-model="createForm.original_value" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计净残值">
              <el-input-number v-model="createForm.salvage_value" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="使用月数" required>
          <el-input-number v-model="createForm.useful_life_months" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="!canCreate" @click="handleCreate">
          确认
        </el-button>
      </template>
    </el-dialog>

    <!-- 计提折旧弹窗 -->
    <el-dialog v-model="showDepreciateDialog" title="计提折旧" width="500px">
      <el-form label-width="100px">
        <el-form-item label="折旧期间">
          <el-date-picker
            v-model="depreciatePeriod"
            type="month"
            value-format="YYYY-MM"
            placeholder="选择月份"
            style="width: 100%"
          />
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon style="margin-top: 8px">
          <template #title>
            系统将自动跳过已计提资产和已提足资产，仅处理使用中且未计提的资产
          </template>
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="showDepreciateDialog = false">取消</el-button>
        <el-button type="warning" :loading="depreciating" :disabled="!depreciatePeriod" @click="doDepreciate">
          确认计提
        </el-button>
      </template>
    </el-dialog>

    <!-- 折旧结果弹窗 -->
    <el-dialog v-model="showResultDialog" title="折旧结果" width="550px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="折旧期间">{{ depreciateResult.period }}</el-descriptions-item>
        <el-descriptions-item label="凭证号">{{ depreciateResult.voucher_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="计提资产数">
          <el-tag type="success" size="small">{{ depreciateResult.depreciated }} 项</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="跳过资产数">
          <el-tag type="info" size="small">{{ depreciateResult.skipped }} 项</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="折旧总额" :span="2">
          <span style="color: #e6a23c; font-weight: bold; font-size: 16px">
            {{ (depreciateResult.total_depreciation || 0).toFixed(2) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>
      <el-table
        v-if="depreciateResult.results && depreciateResult.results.length > 0"
        :data="depreciateResult.results"
        size="small"
        style="margin-top: 12px"
        max-height="300"
      >
        <el-table-column prop="asset_name" label="资产名称" show-overflow-tooltip />
        <el-table-column label="本期折旧" width="120" align="right">
          <template #default="{ row }">
            {{ row.depreciation_amount.toFixed(2) }}
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="showResultDialog = false">知道了</el-button>
      </template>
    </el-dialog>

    <!-- 折旧历史弹窗 -->
    <el-dialog v-model="showHistoryDialog" title="折旧历史" width="600px">
      <el-table :data="historyRecords" v-loading="historyLoading" border size="small">
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column label="本期折旧" width="130" align="right">
          <template #default="{ row }">
            {{ row.depreciation_amount.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="折旧前累计" width="130" align="right">
          <template #default="{ row }">
            {{ row.accumulated_before.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="折旧后累计" width="130" align="right">
          <template #default="{ row }">
            {{ row.accumulated_after.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="voucher_id" label="凭证" width="80">
          <template #default="{ row }">
            <span v-if="row.voucher_id">#{{ row.voucher_id }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAssets,
  createAsset,
  deleteAsset,
  calculateDepreciation,
  getDepreciationHistory,
} from '@/api/fixed_asset'

// 状态
const loading = ref(false)
const creating = ref(false)
const depreciating = ref(false)
const showCreateDialog = ref(false)
const showDepreciateDialog = ref(false)
const showResultDialog = ref(false)
const showHistoryDialog = ref(false)
const depreciateResult = ref({})
const historyLoading = ref(false)
const assets = ref([])
const historyRecords = ref([])
const filterCategory = ref('')
const filterStatus = ref('')
const depreciatePeriod = ref('')

const summary = ref({
  count: 0,
  total_original: 0,
  total_depreciation: 0,
  total_net: 0,
})

const createForm = reactive({
  asset_code: '',
  asset_name: '',
  category: '',
  quantity: 1,
  unit: '台',
  purchase_date: '',
  original_value: 0,
  salvage_value: 0,
  useful_life_months: 60,
  description: '',
})

const canCreate = computed(() => {
  return createForm.asset_code && createForm.asset_name && createForm.category &&
    createForm.purchase_date && createForm.original_value > 0 && createForm.useful_life_months > 0
})

// 加载数据
async function loadData() {
  loading.value = true
  try {
    const params = {}
    if (filterCategory.value) params.category = filterCategory.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getAssets(params)
    assets.value = res.data.items || []
    summary.value = res.data.summary || { count: 0, total_original: 0, total_depreciation: 0, total_net: 0 }
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}

// 创建资产
async function handleCreate() {
  creating.value = true
  try {
    const res = await createAsset({ ...createForm })
    const msg = res.data.message || '资产创建成功'
    ElMessage.success(msg)
    showCreateDialog.value = false
    Object.assign(createForm, {
      asset_code: '', asset_name: '', category: '', quantity: 1, unit: '台',
      purchase_date: '', original_value: 0, salvage_value: 0, useful_life_months: 60, description: '',
    })
    loadData()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    creating.value = false
  }
}

// 删除资产
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除资产 "${row.asset_name}"？`, '确认', { type: 'warning' })
    await deleteAsset(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    // 取消或错误
  }
}

// 计提折旧
function handleDepreciate() {
  depreciatePeriod.value = ''
  showDepreciateDialog.value = true
}

async function doDepreciate() {
  depreciating.value = true
  try {
    const res = await calculateDepreciation(depreciatePeriod.value)
    depreciateResult.value = {
      period: depreciatePeriod.value,
      ...res.data,
    }
    showDepreciateDialog.value = false
    showResultDialog.value = true
    loadData()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    depreciating.value = false
  }
}

// 折旧历史
async function showHistory(row) {
  showHistoryDialog.value = true
  historyLoading.value = true
  try {
    const res = await getDepreciationHistory(row.id)
    historyRecords.value = res.data.items || []
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    historyLoading.value = false
  }
}

// 工具函数
function categoryTag(category) {
  const map = { '房屋建筑': '', '机器设备': 'warning', '运输工具': 'success', '电子设备': 'primary', '其他': 'info' }
  return map[category] || ''
}

function statusLabel(status) {
  const map = { in_use: '使用中', fully_depreciated: '已提足', scrapped: '已报废', disposed: '已处置' }
  return map[status] || status
}

function statusTagType(status) {
  const map = { in_use: 'success', fully_depreciated: 'warning', scrapped: 'info', disposed: 'info' }
  return map[status] || 'info'
}

function depreciationProgress(row) {
  if (!row.purchase_date || !row.useful_life_months) return 0
  const purchaseDate = new Date(row.purchase_date)
  const now = new Date()
  const monthsUsed = (now.getFullYear() - purchaseDate.getFullYear()) * 12 + (now.getMonth() - purchaseDate.getMonth())
  const progress = Math.min(100, Math.round((monthsUsed / row.useful_life_months) * 100))
  return progress
}

function depreciationProgressLabel(row) {
  if (!row.purchase_date || !row.useful_life_months) return '-'
  const purchaseDate = new Date(row.purchase_date)
  const now = new Date()
  const monthsUsed = (now.getFullYear() - purchaseDate.getFullYear()) * 12 + (now.getMonth() - purchaseDate.getMonth())
  const remaining = row.useful_life_months - monthsUsed
  if (remaining <= 0) return '已到期'
  return `剩余 ${remaining} 月`
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.fixed-asset-container {
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

.header-actions {
  display: flex;
  gap: 12px;
}

.text-muted {
  color: #c0c4cc;
}
</style>