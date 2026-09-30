<template>
  <!-- 审计日志页面（仅 reviewer 和 admin 可见） -->
  <div class="audit-log">
    <!-- 搜索筛选区 -->
    <el-card class="filter-card" shadow="never">
      <el-form :model="searchForm" inline>
        <el-form-item label="用户">
          <el-input
            v-model="searchForm.username"
            placeholder="搜索用户"
            clearable
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select
            v-model="searchForm.action_type"
            placeholder="全部类型"
            clearable
            style="width: 150px"
          >
            <el-option label="登录" value="login" />
            <el-option label="注销" value="logout" />
            <el-option label="创建" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
            <el-option label="审核" value="review" />
            <el-option label="导出" value="export" />
            <el-option label="API 调用" value="api_call" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作分类">
          <el-select
            v-model="searchForm.operation_category"
            placeholder="全部分类"
            clearable
            style="width: 180px"
          >
            <el-option label="用户登录" value="user/login" />
            <el-option label="用户注销" value="user/logout" />
            <el-option label="密码修改" value="user/change_password" />
            <el-option label="凭证创建" value="voucher/create" />
            <el-option label="凭证更新" value="voucher/update" />
            <el-option label="凭证删除" value="voucher/delete" />
            <el-option label="凭证提交" value="voucher/submit" />
            <el-option label="凭证审核" value="voucher/review" />
            <el-option label="用户创建" value="user/create" />
            <el-option label="用户更新" value="user/update" />
            <el-option label="报表查看" value="report/view" />
            <el-option label="报表导出" value="report/export" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.status"
            placeholder="全部状态"
            clearable
            style="width: 120px"
          >
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failure" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
          <el-button type="success" @click="handleExport" :loading="exporting">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 日志列表 -->
    <el-card class="list-card" shadow="never" style="margin-top: 16px">
      <el-table
        :data="logList"
        v-loading="tableLoading"
        border
        stripe
        style="width: 100%"
      >
        <el-table-column prop="created_at" label="时间" width="170" sortable />
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column label="操作类型" width="110">
          <template #default="{ row }">
            <el-tag :type="getActionTypeTag(row.action_type)" size="small">
              {{ getActionTypeLabel(row.action_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="120">
          <template #default="{ row }">
            <span>{{ row.resource_type || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="250" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tooltip :content="row.detail" placement="top" :disabled="!row.detail">
              <span>{{ row.detail || '--' }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP 地址" width="140" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="showDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>

      <el-empty
        v-if="!tableLoading && logList.length === 0"
        description="暂无审计日志"
        :image-size="80"
      />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="日志详情"
      width="650px"
    >
      <el-descriptions v-if="currentLog" :column="2" border>
        <el-descriptions-item label="ID">{{ currentLog.id }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ currentLog.created_at }}</el-descriptions-item>
        <el-descriptions-item label="用户">{{ currentLog.username }}</el-descriptions-item>
        <el-descriptions-item label="操作类型">
          <el-tag :type="getActionTypeTag(currentLog.action_type)" size="small">
            {{ getActionTypeLabel(currentLog.action_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="操作分类">{{ currentLog.operation_category || '--' }}</el-descriptions-item>
        <el-descriptions-item label="资源类型">{{ currentLog.resource_type || '--' }}</el-descriptions-item>
        <el-descriptions-item label="资源 ID">{{ currentLog.affected_resource_id || '--' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentLog.status === 'success' ? 'success' : 'danger'" size="small">
            {{ currentLog.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="HTTP 状态码">{{ currentLog.response_status || '--' }}</el-descriptions-item>
        <el-descriptions-item label="IP 地址">{{ currentLog.ip_address || '--' }}</el-descriptions-item>
        <el-descriptions-item label="User Agent" :span="2">
          <span style="font-size: 12px; word-break: break-all">{{ currentLog.user_agent || '--' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="详情" :span="2">
          {{ currentLog.detail || '无' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

// ===== 搜索表单 =====

const searchForm = reactive({
  username: '',
  action_type: '',
  operation_category: '',
  dateRange: [],
  status: ''
})

// ===== 列表数据 =====

const logList = ref([])
const tableLoading = ref(false)
const exporting = ref(false)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// ===== 详情对话框 =====

const detailDialogVisible = ref(false)
const currentLog = ref(null)

// ===== 生命周期 =====

onMounted(() => {
  handleSearch()
})

// ===== 数据加载 =====

/**
 * 搜索审计日志
 */
async function handleSearch() {
  tableLoading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      username: searchForm.username || undefined,
      action_type: searchForm.action_type || undefined,
      operation_category: searchForm.operation_category || undefined,
      start_time: searchForm.dateRange?.[0] || undefined,
      end_time: searchForm.dateRange?.[1] || undefined,
      status: searchForm.status || undefined
    }

    const res = await request.get('/audit-logs', { params })
    logList.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } catch (error) {
    ElMessage.error('加载审计日志失败')
  } finally {
    tableLoading.value = false
  }
}

/**
 * 重置搜索
 */
function resetSearch() {
  searchForm.username = ''
  searchForm.action_type = ''
  searchForm.operation_category = ''
  searchForm.dateRange = []
  searchForm.status = ''
  pagination.page = 1
  handleSearch()
}

// ===== 操作方法 =====

/**
 * 查看日志详情
 */
function showDetail(row) {
  currentLog.value = row
  detailDialogVisible.value = true
}

/**
 * 导出审计日志为 CSV
 */
async function handleExport() {
  exporting.value = true
  try {
    // 获取所有日志数据（不分页）
    const params = {
      page: 1,
      page_size: 10000,
      username: searchForm.username || undefined,
      action_type: searchForm.action_type || undefined,
      operation_category: searchForm.operation_category || undefined,
      start_time: searchForm.dateRange?.[0] || undefined,
      end_time: searchForm.dateRange?.[1] || undefined,
      status: searchForm.status || undefined
    }
    const res = await request.get('/audit-logs', { params })
    const items = res.data?.items || []

    if (items.length === 0) {
      ElMessage.warning('没有可导出的数据')
      return
    }

    // 生成 CSV
    const headers = ['ID', '时间', '用户', '操作类型', '操作分类', '资源类型', '资源ID', '状态', 'HTTP状态码', 'IP地址', '详情']
    const rows = items.map(item => [
      item.id,
      item.created_at || '',
      item.username,
      getActionTypeLabel(item.action_type),
      item.operation_category || '',
      item.resource_type || '',
      item.affected_resource_id || '',
      item.status === 'success' ? '成功' : '失败',
      item.response_status || '',
      item.ip_address || '',
      (item.detail || '').replace(/"/g, '""')
    ])

    const csvContent = '\uFEFF' + headers.join(',') + '\n' +
      rows.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `审计日志_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${items.length} 条审计日志`)
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// ===== 工具方法 =====

/**
 * 获取操作类型标签
 */
function getActionTypeLabel(type) {
  const labels = {
    login: '登录',
    logout: '注销',
    create: '创建',
    update: '更新',
    delete: '删除',
    review: '审核',
    export: '导出',
    api_call: 'API 调用',
    other: '其他'
  }
  return labels[type] || type || '--'
}

/**
 * 获取操作类型标签颜色
 */
function getActionTypeTag(type) {
  const tags = {
    login: 'info',
    logout: 'info',
    create: 'success',
    update: 'warning',
    delete: 'danger',
    review: 'primary',
    export: 'success',
    api_call: 'warning',
    other: 'info'
  }
  return tags[type] || 'info'
}
</script>

<style scoped>
.audit-log {
  max-width: 1400px;
}

.filter-card {
  margin-bottom: 0;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>