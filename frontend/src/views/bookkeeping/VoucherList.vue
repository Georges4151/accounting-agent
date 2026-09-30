<template>
  <!-- 凭证列表页面 -->
  <div class="voucher-list">
    <!-- 搜索筛选区 -->
    <el-card class="filter-card" shadow="never">
      <el-form :model="searchForm" inline>
        <el-form-item label="凭证号">
          <el-input
            v-model="searchForm.voucher_no"
            placeholder="请输入凭证号"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="凭证字">
          <el-select
            v-model="searchForm.voucher_type"
            placeholder="全部"
            clearable
            style="width: 100px"
          >
            <el-option label="记" value="记" />
            <el-option label="转" value="转" />
            <el-option label="收" value="收" />
            <el-option label="付" value="付" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.status"
            placeholder="全部状态"
            clearable
            multiple
            collapse-tags
            collapse-tags-tooltip
            style="width: 180px"
          >
            <el-option label="草稿" value="draft" />
            <el-option label="已提交" value="submitted" />
            <el-option label="出纳已复核" value="cashier_reviewed" />
            <el-option label="已审核" value="reviewed" />
            <el-option label="已审批" value="approved" />
            <el-option label="已过账" value="posted" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额范围">
          <el-input-number
            v-model="searchForm.amountMin"
            :min="0"
            :precision="2"
            placeholder="最小"
            controls-position="right"
            style="width: 130px"
          />
          <span style="margin: 0 8px; color: #909399">-</span>
          <el-input-number
            v-model="searchForm.amountMax"
            :min="0"
            :precision="2"
            placeholder="最大"
            controls-position="right"
            style="width: 130px"
          />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input
            v-model="searchForm.keyword"
            placeholder="关键词搜索"
            clearable
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><RefreshLeft /></el-icon>
            清空筛选
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 操作栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="$router.push('/voucher/create')">
        <el-icon><Plus /></el-icon>
        新建凭证
      </el-button>

      <el-button
        type="warning"
        @click="showCarryForwardDialog = true"
      >
        <el-icon><Switch /></el-icon>
        期末结转
      </el-button>

      <el-button
        type="info"
        @click="openGapDialog"
      >
        <el-icon><Sort /></el-icon>
        断号整理
      </el-button>

      <!-- 批量操作工具栏 -->
      <template v-if="batch.hasSelection">
        <el-divider direction="vertical" />
        <el-tag type="info" size="large" effect="plain">
          已选 {{ batch.selectedCount }} 项
        </el-tag>
        <el-button
          v-if="canBatchSubmit"
          type="warning"
          :loading="batch.batchLoading"
          @click="handleBatchSubmit"
        >
          <el-icon><Select /></el-icon>
          批量提交审核
        </el-button>
        <el-button
          v-if="canBatchReview"
          type="success"
          :loading="batch.batchLoading"
          @click="handleBatchReview"
        >
          <el-icon><Check /></el-icon>
          批量审核通过
        </el-button>
        <el-button
          v-if="canBatchApprove"
          type="success"
          :loading="batch.batchLoading"
          @click="handleBatchApprove"
        >
          <el-icon><Check /></el-icon>
          批量审批通过
        </el-button>
        <el-button
          v-if="canBatchPost"
          type="primary"
          :loading="batch.batchLoading"
          @click="handleBatchPost"
        >
          <el-icon><Check /></el-icon>
          批量过账
        </el-button>
        <el-button
          v-if="canBatchReject"
          type="danger"
          :loading="batch.batchLoading"
          @click="handleBatchReject"
        >
          <el-icon><Close /></el-icon>
          批量驳回
        </el-button>
        <el-button
          v-if="canBatchDelete"
          type="danger"
          :loading="batch.batchLoading"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除
        </el-button>
        <el-button @click="handleClearSelection">
          <el-icon><CircleClose /></el-icon>
          取消选择
        </el-button>
      </template>
    </div>

    <!-- 凭证列表 -->
    <el-card shadow="never">
      <el-table
        ref="tableRef"
        :data="voucherList"
        v-loading="tableLoading"
        border
        stripe
        style="width: 100%"
        @selection-change="batch.handleSelectionChange"
        @sort-change="handleSortChange"
      >
        <el-table-column type="selection" width="50" fixed="left" />
        <el-table-column prop="voucher_type" label="凭证字" width="70" />
        <el-table-column prop="voucher_no" label="凭证号" width="180" sortable="custom" />
        <el-table-column prop="voucher_date" label="日期" width="110" sortable="custom" />
        <el-table-column prop="summary" label="摘要" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="display: inline-flex; align-items: center; gap: 4px">
              {{ row.summary }}
              <el-icon v-if="row.attachment_count > 0" style="color: #909399" title="有附件">
                <Paperclip />
              </el-icon>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="借方合计" width="140" align="right" sortable="custom" prop="total_debit">
          <template #default="{ row }">
            <span class="amount-debit">{{ formatMoney(row.total_debit) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="贷方合计" width="140" align="right" sortable="custom" prop="total_credit">
          <template #default="{ row }">
            <span class="amount-credit">{{ formatMoney(row.total_credit) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" sortable="custom" prop="status">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="操作人" width="100" />
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="handleView(row)">
              查看
            </el-button>
            <el-button
              text
              type="primary"
              size="small"
              :disabled="!canEdit(row)"
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="row.status === 'draft'"
              text
              type="warning"
              size="small"
              @click="handleSubmit(row)"
            >
              提交
            </el-button>
            <el-button
              v-if="canCashierReview(row)"
              text
              type="warning"
              size="small"
              @click="handleCashierReview(row)"
            >
              出纳复核
            </el-button>
            <el-button
              v-if="canReview(row)"
              text
              type="success"
              size="small"
              @click="handleReview(row)"
            >
              审核
            </el-button>
            <el-button
              v-if="canReview(row)"
              text
              type="danger"
              size="small"
              @click="handleReject(row)"
            >
              驳回
            </el-button>
            <el-button
              v-if="canApprove(row)"
              text
              type="success"
              size="small"
              @click="handleApprove(row)"
            >
              审批
            </el-button>
            <el-button
            v-if="row.status === 'draft'"
            text
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
          <el-button
            text
            type="primary"
            size="small"
            @click="handleCopy(row)"
          >
            复制
          </el-button>
            <el-popconfirm
              title="确定要创建红字冲销凭证吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleReverse(row)"
            >
              <template #reference>
                <el-button text type="warning" size="small">
                  红字冲销
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>

    <!-- 凭证详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      :title="currentVoucher ? '凭证详情 - ' + currentVoucher.voucher_no : '凭证详情'"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="currentVoucher" class="voucher-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="凭证号">{{ currentVoucher.voucher_no }}</el-descriptions-item>
          <el-descriptions-item label="日期">{{ currentVoucher.voucher_date }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentVoucher.status)" size="small">
              {{ getStatusLabel(currentVoucher.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建人">{{ currentVoucher.created_by_name || currentVoucher.created_by }}</el-descriptions-item>
          <el-descriptions-item label="摘要" :span="2">{{ currentVoucher.summary }}</el-descriptions-item>
        </el-descriptions>

        <!-- 分录明细 -->
        <h4 style="margin: 16px 0 8px">分录明细</h4>
        <el-table :data="currentVoucher.items" border stripe size="small">
          <el-table-column prop="account_code" label="科目代码" width="120" />
          <el-table-column prop="account_name" label="科目名称" width="150" />
          <el-table-column prop="description" label="摘要" min-width="180" show-overflow-tooltip />
          <el-table-column prop="debit_amount" label="借方金额" width="130" align="right">
            <template #default="{ row }">
              <span class="amount-debit">{{ formatMoney(row.debit_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="credit_amount" label="贷方金额" width="130" align="right">
            <template #default="{ row }">
              <span class="amount-credit">{{ formatMoney(row.credit_amount) }}</span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 合计 -->
        <div class="detail-totals">
          <span>借方合计：<strong class="amount-debit">{{ formatMoney(detailTotalDebit) }}</strong></span>
          <span>贷方合计：<strong class="amount-credit">{{ formatMoney(detailTotalCredit) }}</strong></span>
        </div>
      </div>
    </el-dialog>

    <!-- 期末结转弹窗 -->
    <el-dialog v-model="showCarryForwardDialog" title="期末结转" width="500px">
      <el-form :model="carryForm" label-width="100px">
        <el-form-item label="期末日期">
          <el-date-picker
            v-model="carryForm.period_end_date"
            type="date"
            placeholder="选择期末日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结转类型">
          <el-checkbox-group v-model="carryForm.carry_types">
            <el-checkbox label="损益结转" />
            <el-checkbox label="成本结转" />
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <div v-if="carryResults.length > 0" style="margin-top: 16px">
        <el-alert
          v-for="r in carryResults"
          :key="r.carry_type"
          :title="r.message"
          :type="r.voucher_id ? 'success' : 'info'"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        />
      </div>

      <template #footer>
        <el-button @click="showCarryForwardDialog = false">关闭</el-button>
        <el-button
          type="warning"
          :loading="carryForwarding"
          :disabled="!canCarryForward"
          @click="handleCarryForward"
        >
          执行结转
        </el-button>
      </template>
    </el-dialog>

    <!-- 断号整理弹窗 -->
    <el-dialog v-model="gapDialogVisible" title="断号检测与整理" width="700px">
      <div v-if="gapLoading" v-loading="gapLoading" style="min-height: 120px" />

      <div v-else-if="!gapData">
        <el-button type="primary" :loading="gapLoading" @click="detectGaps">
          <el-icon><Search /></el-icon>
          检测断号
        </el-button>
      </div>

      <template v-else>
        <el-alert
          :title="gapData.has_gaps ? `发现 ${gapData.total_missing} 个断号` : '未发现断号，凭证编号连续'"
          :type="gapData.has_gaps ? 'warning' : 'success'"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />

        <div v-if="gapData.has_gaps">
          <el-table :data="gapData.gaps" border size="small" style="margin-bottom: 16px">
            <el-table-column prop="voucher_type" label="凭证字" width="80" />
            <el-table-column prop="gap_start" label="起始断号" width="180" />
            <el-table-column prop="gap_end" label="结束断号" width="180" />
            <el-table-column prop="missing_count" label="缺失数量" width="90" align="center" />
            <el-table-column label="缺失编号" min-width="200">
              <template #default="{ row }">
                <el-tag
                  v-for="n in row.missing_numbers.slice(0, 8)"
                  :key="n"
                  size="small"
                  type="danger"
                  effect="plain"
                  style="margin: 2px"
                >{{ n }}</el-tag>
                <el-tag v-if="row.missing_numbers.length > 8" size="small" type="info" effect="plain">
                  等{{ row.missing_numbers.length }}个
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-form inline>
            <el-form-item label="凭证字">
              <el-select v-model="gapForm.voucher_type" clearable placeholder="全部" style="width: 100px">
                <el-option label="记" value="记" />
                <el-option label="转" value="转" />
                <el-option label="收" value="收" />
                <el-option label="付" value="付" />
              </el-select>
            </el-form-item>
            <el-form-item label="起始日期">
              <el-date-picker
                v-model="gapForm.start_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 160px"
              />
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #footer>
        <el-button @click="gapDialogVisible = false">关闭</el-button>
        <el-button @click="gapData = null; gapForm.voucher_type = ''; gapForm.start_date = ''">重新检测</el-button>
        <el-button
          v-if="gapData && gapData.has_gaps"
          type="warning"
          :loading="renumbering"
          @click="handleRenumber"
        >
          执行整理
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getVouchers, getVoucher, deleteVoucher, submitVoucher, reviewVoucher, rejectVoucher, approveVoucher, reverseVoucher, copyVoucher, cashierReviewVoucher, cashierUnreviewVoucher } from '@/api/voucher'
import { carryForward } from '@/api/period_close'
import request from '@/api/request'
import { useAmountMask } from '@/composables/useAmountMask'
import { useBatchOperations } from '@/composables/useBatchOperations'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const { formatAmount } = useAmountMask()
const batch = useBatchOperations()

// ===== 期末结转 =====
const showCarryForwardDialog = ref(false)
const carryForwarding = ref(false)
const carryResults = ref([])
const carryForm = reactive({
  period_end_date: new Date().toISOString().slice(0, 10),
  carry_types: ['损益结转'],
})

const canCarryForward = computed(() => {
  return carryForm.period_end_date && carryForm.carry_types.length > 0
})

async function handleCarryForward() {
  carryForwarding.value = true
  carryResults.value = []
  try {
    const res = await carryForward({
      period_end_date: carryForm.period_end_date,
      carry_types: carryForm.carry_types,
    })
    carryResults.value = res.data.results || []
    loadVouchers() // 刷新凭证列表
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    carryForwarding.value = false
  }
}

// ===== 断号整理 =====

const gapDialogVisible = ref(false)
const gapLoading = ref(false)
const gapData = ref(null)
const renumbering = ref(false)
const gapForm = reactive({
  voucher_type: '',
  start_date: ''
})

function openGapDialog() {
  gapData.value = null
  gapForm.voucher_type = ''
  gapForm.start_date = ''
  gapDialogVisible.value = true
}

async function detectGaps() {
  gapLoading.value = true
  try {
    const params = {}
    if (gapForm.voucher_type) params.voucher_type = gapForm.voucher_type
    const res = await request.get('/vouchers/gaps/detect', { params })
    gapData.value = res.data
  } catch (error) {
    ElMessage.error('断号检测失败')
  } finally {
    gapLoading.value = false
  }
}

async function handleRenumber() {
  try {
    await ElMessageBox.confirm(
      '断号整理将对凭证重新编号，消除断号。此操作不可撤销，确定继续？',
      '确认整理',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    renumbering.value = true
    const body = {}
    if (gapForm.voucher_type) body.voucher_type = gapForm.voucher_type
    if (gapForm.start_date) body.start_date = gapForm.start_date
    const res = await request.post('/vouchers/gaps/renumber', body)
    ElMessage.success(res.data.message || '断号整理完成')
    gapDialogVisible.value = false
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '整理失败')
    }
  } finally {
    renumbering.value = false
  }
}

// ===== 表格引用 =====
const tableRef = ref(null)

// ===== 搜索表单 =====

const searchForm = reactive({
  voucher_no: '',
  voucher_type: '',
  dateRange: [],
  status: [],
  amountMin: null,
  amountMax: null,
  keyword: ''
})

// ===== 排序状态 =====

const sortState = reactive({
  prop: '',
  order: ''
})

// ===== 列表数据 =====

const voucherList = ref([])
const tableLoading = ref(false)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// ===== 详情弹窗 =====

const detailVisible = ref(false)
const currentVoucher = ref(null)

const detailTotalDebit = computed(() => {
  if (!currentVoucher.value?.items) return 0
  return currentVoucher.value.items.reduce((sum, item) => sum + (item.debit_amount || 0), 0)
})

const detailTotalCredit = computed(() => {
  if (!currentVoucher.value?.items) return 0
  return currentVoucher.value.items.reduce((sum, item) => sum + (item.credit_amount || 0), 0)
})

// ===== 批量操作权限判断 =====

const isAdmin = computed(() => authStore.hasPermission('admin'))
const isReviewer = computed(() => authStore.hasPermission('reviewer') || isAdmin.value)

const canBatchSubmit = computed(() => {
  return batch.hasSelection && batch.draftCount > 0
})

const canBatchReview = computed(() => {
  return isReviewer.value && batch.hasSelection && batch.submittedCount > 0
})

const canBatchReject = computed(() => {
  return isReviewer.value && batch.hasSelection && batch.submittedCount > 0
})

const canBatchApprove = computed(() => {
  return isReviewer.value && batch.hasSelection && batch.reviewedCount > 0
})

const canBatchPost = computed(() => {
  return isReviewer.value && batch.hasSelection && batch.canPost.value
})

const canBatchDelete = computed(() => {
  return isAdmin.value && batch.hasSelection && batch.draftCount > 0
})

// ===== 生命周期 =====

onMounted(() => {
  handleSearch()
})

// ===== 数据加载 =====

/**
 * 搜索凭证
 */
async function handleSearch() {
  tableLoading.value = true
  // 搜索时清除选择
  batch.clearSelection()
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: searchForm.keyword || undefined,
      voucher_no: searchForm.voucher_no || undefined,
      voucher_type: searchForm.voucher_type || undefined,
      start_date: searchForm.dateRange?.[0] || undefined,
      end_date: searchForm.dateRange?.[1] || undefined,
      status: searchForm.status?.length > 0 ? searchForm.status.join(',') : undefined,
    }

    // 排序参数
    if (sortState.prop) {
      params.sort_by = sortState.prop
      params.sort_order = sortState.order === 'ascending' ? 'asc' : 'desc'
    }

    const res = await getVouchers(params)
    voucherList.value = res.data?.items || []
    pagination.total = res.data?.total || 0

    // 前端金额范围筛选（后端暂不支持金额范围查询）
    if (searchForm.amountMin != null || searchForm.amountMax != null) {
      voucherList.value = voucherList.value.filter(item => {
        const maxAmount = Math.max(item.total_debit || 0, item.total_credit || 0)
        if (searchForm.amountMin != null && maxAmount < searchForm.amountMin) return false
        if (searchForm.amountMax != null && maxAmount > searchForm.amountMax) return false
        return true
      })
    }
  } catch (error) {
    ElMessage.error('加载凭证列表失败')
  } finally {
    tableLoading.value = false
  }
}

/**
 * 重置搜索
 */
function resetSearch() {
  searchForm.voucher_no = ''
  searchForm.voucher_type = ''
  searchForm.dateRange = []
  searchForm.status = []
  searchForm.amountMin = null
  searchForm.amountMax = null
  searchForm.keyword = ''
  sortState.prop = ''
  sortState.order = ''
  pagination.page = 1
  handleSearch()
}

/**
 * 排序变化处理
 */
function handleSortChange({ prop, order }) {
  sortState.prop = prop || ''
  sortState.order = order || ''
  pagination.page = 1
  handleSearch()
}

// ===== 批量操作方法 =====

/**
 * 取消批量选择
 */
function handleClearSelection() {
  batch.clearSelection()
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

/**
 * 批量提交审核
 */
async function handleBatchSubmit() {
  const success = await batch.batchSubmit()
  if (success) {
    handleSearch()
  }
}

/**
 * 批量审核通过
 */
async function handleBatchReview() {
  const success = await batch.batchReview()
  if (success) {
    handleSearch()
  }
}

/**
 * 批量驳回
 */
async function handleBatchReject() {
  const success = await batch.batchReject()
  if (success) {
    handleSearch()
  }
}

/**
 * 批量审批通过
 */
async function handleBatchApprove() {
  const success = await batch.batchApprove()
  if (success) {
    handleSearch()
  }
}

/**
 * 批量过账
 */
async function handleBatchPost() {
  const success = await batch.batchPost()
  if (success) {
    handleSearch()
  }
}

/**
 * 批量删除
 */
async function handleBatchDelete() {
  const success = await batch.batchDelete()
  if (success) {
    handleSearch()
  }
}

// ===== 单条操作方法 =====

/**
 * 查看凭证详情
 */
async function handleView(row) {
  try {
    const res = await getVoucher(row.id)
    currentVoucher.value = res.data
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('加载凭证详情失败')
  }
}

/**
 * 编辑凭证
 */
function handleEdit(row) {
  router.push(`/voucher/create?id=${row.id}`)
}

/**
 * 提交审核
 */
async function handleSubmit(row) {
  try {
    await ElMessageBox.confirm(
      `确定要提交凭证 "${row.voucher_no}" 进行审核吗？`,
      '提交审核',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await submitVoucher(row.id)
    ElMessage.success('凭证已提交审核')
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '提交失败')
    }
  }
}

/**
 * 审核通过
 */
async function handleReview(row) {
  try {
    await ElMessageBox.confirm(
      `确定审核通过凭证 "${row.voucher_no}" 吗？`,
      '审核通过',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await reviewVoucher(row.id)
    ElMessage.success('凭证审核通过')
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '审核失败')
    }
  }
}

/**
 * 驳回凭证
 */
async function handleReject(row) {
  try {
    await ElMessageBox.confirm(
      `确定驳回凭证 "${row.voucher_no}" 吗？`,
      '驳回凭证',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await rejectVoucher(row.id)
    ElMessage.success('凭证已驳回')
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '驳回失败')
    }
  }
}

/**
 * 审批通过
 */
async function handleApprove(row) {
  try {
    await ElMessageBox.confirm(
      `确定审批通过凭证 "${row.voucher_no}" 吗？`,
      '审批通过',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await approveVoucher(row.id)
    ElMessage.success('凭证审批通过')
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '审批失败')
    }
  }
}

/**
 * 删除凭证
 */
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除凭证 "${row.voucher_no}" 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteVoucher(row.id)
    ElMessage.success('凭证已删除')
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

/**
 * 复制凭证
 */
async function handleCopy(row) {
  try {
    await ElMessageBox.confirm(
      `确定要复制凭证 "${row.voucher_no}" 吗？将生成一份新的草稿凭证。`,
      '复制凭证',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
    )
    const res = await copyVoucher(row.id)
    ElMessage.success(`凭证已复制为 ${res.data.voucher_no}`)
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '复制失败')
    }
  }
}

/**
 * 红字冲销
 */
async function handleReverse(row) {
  try {
    const res = await reverseVoucher(row.id)
    ElMessage.success(`红字冲销凭证 ${res.data.voucher_no} 已创建`)
    handleSearch()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '红字冲销失败')
  }
}

/**
 * 判断是否可以编辑
 */
function canEdit(row) {
  return row.status === 'draft'
}

/**
 * 判断是否可以审核（需要审核权限且状态为已提交）
 */
function canReview(row) {
  return row.status === 'submitted' &&
    (authStore.hasPermission('admin') || authStore.hasPermission('reviewer'))
}

/**
 * 判断是否可以审批（需要审批权限且状态为已审核）
 */
function canApprove(row) {
  return row.status === 'reviewed' &&
    (authStore.hasPermission('admin') || authStore.hasPermission('reviewer') || authStore.hasPermission('accountant'))
}

/**
 * 判断是否可以出纳复核
 */
function canCashierReview(row) {
  return row.status === 'submitted' && !row.cashier_reviewed &&
    (authStore.hasPermission('admin') || authStore.hasPermission('cashier'))
}

/**
 * 出纳复核
 */
async function handleCashierReview(row) {
  try {
    await ElMessageBox.confirm(
      `确定对凭证 "${row.voucher_no}" 进行出纳复核吗？`,
      '出纳复核',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await cashierReviewVoucher(row.id)
    ElMessage.success('出纳复核完成')
    handleSearch()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '出纳复核失败')
    }
  }
}

// ===== 工具方法 =====

/**
 * 格式化金额（含脱敏逻辑）
 */
function formatMoney(value) {
  return formatAmount(value)
}

/**
 * 获取状态标签
 */
function getStatusLabel(status) {
  const labels = { draft: '草稿', submitted: '已提交', reviewed: '已审核', approved: '已审批', posted: '已过账' }
  return labels[status] || status
}

/**
 * 获取状态标签类型
 */
function getStatusType(status) {
  const types = { draft: 'info', submitted: 'warning', reviewed: 'success', approved: '', posted: '' }
  return types[status] || 'info'
}
</script>

<style scoped>
.voucher-list {
  max-width: 1400px;
}

.filter-card {
  margin-bottom: 12px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.toolbar .el-divider--vertical {
  height: 24px;
  margin: 0 4px;
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

/* 详情弹窗 */
.voucher-detail h4 {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.detail-totals {
  display: flex;
  gap: 32px;
  margin-top: 12px;
  padding: 10px 16px;
  background-color: #f5f7fa;
  border-radius: 6px;
  font-size: 14px;
}
</style>