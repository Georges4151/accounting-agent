<template>
  <!-- 知识库管理页面 -->
  <div class="knowledge-manage">
    <!-- 卡片0：自动更新 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>自动更新</span>
          <div class="card-header-actions">
            <el-tag
              :type="schedulerStatus.is_running ? 'warning' : 'success'"
              size="small"
              effect="plain"
            >
              {{ schedulerStatus.is_running ? '更新中...' : '就绪' }}
            </el-tag>
            <el-button
              type="primary"
              size="small"
              @click="handleTriggerUpdate"
              :loading="schedulerStatus.is_running"
            >
              <el-icon><Refresh /></el-icon>
              立即更新
            </el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col :span="8">
          <div class="scheduler-info-item">
            <span class="scheduler-label">上次更新</span>
            <span class="scheduler-value">{{ schedulerStatus.last_run_at ? formatTime(schedulerStatus.last_run_at) : '从未更新' }}</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="scheduler-info-item">
            <span class="scheduler-label">下次更新</span>
            <span class="scheduler-value">{{ schedulerStatus.next_run_at ? formatTime(schedulerStatus.next_run_at) : '待定' }}</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="scheduler-info-item">
            <span class="scheduler-label">更新次数</span>
            <span class="scheduler-value">{{ schedulerStatus.update_count ?? 0 }}</span>
          </div>
        </el-col>
      </el-row>

      <!-- 更新日志 -->
      <div v-if="schedulerLogs.length > 0" class="scheduler-logs" style="margin-top: 12px">
        <div class="logs-title">最近更新日志</div>
        <el-table :data="schedulerLogs" size="small" border>
          <el-table-column prop="source_url" label="来源" min-width="200" show-overflow-tooltip />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                {{ row.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="new_docs_count" label="新增文档" width="80" align="center" />
          <el-table-column label="时间" width="170">
            <template #default="{ row }">
              <span>{{ formatTime(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="error_message" label="错误信息" min-width="150" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>

    <!-- 卡片1：索引统计看板 -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>索引统计</span>
          <el-button type="warning" @click="handleRebuildIndex" :loading="rebuildLoading">
            <el-icon><RefreshRight /></el-icon>
            重建索引
          </el-button>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon" style="background-color: #ecf5ff; color: #409eff">
              <el-icon :size="28"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_documents ?? '-' }}</div>
              <div class="stat-label">文档总数</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon" style="background-color: #f0f9eb; color: #67c23a">
              <el-icon :size="28"><Grid /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_chunks ?? '-' }}</div>
              <div class="stat-label">索引块数</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon" style="background-color: #fdf6ec; color: #e6a23c">
              <el-icon :size="28"><Collection /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_categories ?? '-' }}</div>
              <div class="stat-label">分类数量</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-icon" :style="indexStatusStyle.iconBg">
              <el-icon :size="28"><CircleCheck v-if="stats.index_initialized" /><WarningFilled v-else /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">
                <el-tag :type="stats.index_initialized ? 'success' : 'info'" size="small">
                  {{ stats.index_initialized ? '已初始化' : '未初始化' }}
                </el-tag>
              </div>
              <div class="stat-label">索引状态</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 卡片2：文档管理 -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>文档管理</span>
          <el-button type="primary" @click="openUploadDialog">
            <el-icon><Upload /></el-icon>
            上传文档
          </el-button>
        </div>
      </template>

      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select
            v-model="filterCategory"
            placeholder="全部分类"
            clearable
            style="width: 200px"
            @change="loadDocuments"
          >
            <el-option
              v-for="cat in categoryList"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>
        </div>
      </div>

      <!-- 文档列表表格 -->
      <el-table
        :data="documentList"
        v-loading="tableLoading"
        border
        stripe
        style="width: 100%; margin-top: 12px"
      >
        <el-table-column prop="title" label="文档标题" min-width="160" show-overflow-tooltip />
        <el-table-column label="分类" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.category" size="small">{{ row.category }}</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <a v-if="row.source_url" :href="row.source_url" target="_blank" class="source-link">
              <el-icon><Link /></el-icon>
              {{ row.source_url }}
            </a>
            <span v-else class="text-muted">本地上传</span>
          </template>
        </el-table-column>
        <el-table-column label="文件类型" width="90">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.file_type || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文件大小" width="90">
          <template #default="{ row }">
            <span>{{ formatFileSize(row.file_size) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="70" align="center" />
        <el-table-column label="版本" width="65" align="center">
          <template #default="{ row }">
            <span>v{{ row.version || 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="row.is_indexed ? 'success' : 'warning'" size="small">
                {{ row.is_indexed ? '已索引' : '待索引' }}
              </el-tag>
              <el-tooltip
                v-if="row.is_stale"
                content="此文档可能已过时，距上次更新超过30天"
                placement="top"
              >
                <el-icon class="stale-icon" color="#e6a23c"><WarningFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">
            <span>{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确定要删除该文档吗？删除后索引数据也将被清除。"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDeleteDocument(row)"
            >
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 空状态 -->
      <el-empty
        v-if="!tableLoading && documentList.length === 0"
        description="暂无文档，请上传"
        :image-size="80"
      />

      <!-- 分页 -->
      <div class="pagination-wrapper" v-if="total > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadDocuments"
          @current-change="loadDocuments"
        />
      </div>
    </el-card>

    <!-- 卡片3：搜索测试 -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>搜索测试</span>
        </div>
      </template>

      <div class="search-area">
        <el-row :gutter="12" align="middle">
          <el-col :span="12">
            <el-input
              v-model="searchQuery"
              placeholder="输入搜索关键词..."
              clearable
              @keyup.enter="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </el-col>
          <el-col :span="4">
            <el-select
              v-model="searchCategory"
              placeholder="全部分类"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="cat in categoryList"
                :key="cat"
                :label="cat"
                :value="cat"
              />
            </el-select>
          </el-col>
          <el-col :span="4">
            <div class="topk-slider">
              <span class="topk-label">Top-K: {{ searchTopK }}</span>
              <el-slider
                v-model="searchTopK"
                :min="1"
                :max="20"
                :step="1"
                show-stops
              />
            </div>
          </el-col>
          <el-col :span="4">
            <el-button
              type="primary"
              @click="handleSearch"
              :loading="searchLoading"
              style="width: 100%"
            >
              <el-icon><Search /></el-icon>
              搜索
            </el-button>
          </el-col>
        </el-row>
      </div>

      <!-- 搜索结果 -->
      <div v-if="searchResults.length > 0" class="search-results" style="margin-top: 16px">
        <div class="result-summary">
          共找到 <strong>{{ searchResults.length }}</strong> 条结果
        </div>
        <el-card
          v-for="(item, index) in searchResults"
          :key="index"
          class="result-item"
          shadow="hover"
        >
          <div class="result-content">{{ item.content || item.text || item.snippet }}</div>
          <div class="result-meta">
            <el-tag size="small" type="info" effect="plain">
              <el-icon><Document /></el-icon>
              {{ item.filename || item.source || item.document_title || '未知来源' }}
            </el-tag>
            <span class="result-score">
              相关度：{{ formatScore(item.score || item.relevance) }}
            </span>
          </div>
        </el-card>
      </div>

      <el-empty
        v-if="searchResults.length === 0 && searchPerformed"
        description="未找到相关结果"
        :image-size="60"
      />
    </el-card>

    <!-- 上传文档弹窗 -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传文档"
      width="560px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="选择文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-exceed="handleUploadExceed"
            :on-change="handleFileChange"
            :accept="acceptFileTypes"
            drag
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 PDF、Word、TXT、Markdown、CSV 格式文件，单个文件不超过 50MB
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="文档分类">
          <el-select
            v-model="uploadForm.category"
            placeholder="请选择分类"
            clearable
            filterable
            allow-create
            style="width: 100%"
          >
            <el-option
              v-for="cat in categoryList"
              :key="cat"
              :label="cat"
              :value="cat"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="文档标题">
          <el-input
            v-model="uploadForm.title"
            placeholder="可选，默认使用文件名"
            clearable
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleUpload"
          :loading="uploadLoading"
          :disabled="!rawFile"
        >
          开始上传
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  getKnowledgeStats,
  getDocuments,
  getCategories,
  deleteDocument,
  rebuildIndex,
  uploadDocument,
  searchKnowledge,
  triggerSchedulerUpdate,
  getSchedulerStatus,
  getSchedulerLogs
} from '@/api/knowledge'
import { ElMessage, ElMessageBox } from 'element-plus'

// ===== 自动更新调度 =====

const schedulerStatus = reactive({
  is_running: false,
  last_run_at: null,
  next_run_at: null,
  update_count: 0,
  error_count: 0,
  last_result: null
})

const schedulerLogs = ref([])

// ===== 索引统计 =====

const stats = reactive({
  total_documents: 0,
  total_chunks: 0,
  total_categories: 0,
  index_initialized: false
})

const rebuildLoading = ref(false)

const indexStatusStyle = computed(() => {
  if (stats.index_initialized) {
    return {
      iconBg: 'background-color: #f0f9eb; color: #67c23a'
    }
  }
  return {
    iconBg: 'background-color: #f4f4f5; color: #909399'
  }
})

// ===== 文档管理 =====

const documentList = ref([])
const tableLoading = ref(false)
const filterCategory = ref('')
const categoryList = ref([])

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ===== 搜索测试 =====

const searchQuery = ref('')
const searchCategory = ref('')
const searchTopK = ref(5)
const searchLoading = ref(false)
const searchResults = ref([])
const searchPerformed = ref(false)

// ===== 上传弹窗 =====

const uploadDialogVisible = ref(false)
const uploadRef = ref(null)
const rawFile = ref(null)       // 实际要上传的 File 对象
const uploadFileList = ref([])  // el-upload 显示用
const uploadLoading = ref(false)
const acceptFileTypes = '.pdf,.docx,.txt,.md,.csv'

const uploadForm = reactive({
  category: '',
  title: ''
})

// ===== 生命周期 =====

onMounted(() => {
  loadStats()
  loadCategories()
  loadDocuments()
  loadSchedulerStatus()
})

// ===== 数据加载方法 =====

/**
 * 加载索引统计
 */
async function loadStats() {
  try {
    const res = await getKnowledgeStats()
    const data = res.data
    stats.total_documents = data.total_documents ?? 0
    stats.total_chunks = data.total_chunks ?? 0
    stats.total_categories = data.total_categories ?? 0
    stats.index_initialized = data.initialized ?? data.index_initialized ?? false
  } catch (error) {
    console.error('加载统计信息失败', error)
  }
}

/**
 * 加载分类列表
 */
async function loadCategories() {
  try {
    const res = await getCategories()
    categoryList.value = res.data?.categories || res.data || []
  } catch (error) {
    console.error('加载分类列表失败', error)
  }
}

/**
 * 加载文档列表
 */
async function loadDocuments() {
  tableLoading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterCategory.value) {
      params.category = filterCategory.value
    }
    const res = await getDocuments(params)
    const data = res.data
    documentList.value = data.documents || data.items || []
    total.value = data.total || data.total_count || 0
  } catch (error) {
    ElMessage.error('加载文档列表失败')
  } finally {
    tableLoading.value = false
  }
}

// ===== 操作方法 =====

/**
 * 加载调度器状态
 */
async function loadSchedulerStatus() {
  try {
    const res = await getSchedulerStatus()
    const data = res.data
    Object.assign(schedulerStatus, {
      is_running: data.is_running ?? false,
      last_run_at: data.last_run_at ?? null,
      next_run_at: data.next_run_at ?? null,
      update_count: data.update_count ?? 0,
      error_count: data.error_count ?? 0,
      last_result: data.last_result ?? null
    })
    schedulerLogs.value = data.recent_logs || []
  } catch (error) {
    console.error('加载调度器状态失败', error)
  }
}

/**
 * 手动触发更新
 */
async function handleTriggerUpdate() {
  try {
    await triggerSchedulerUpdate()
    ElMessage.success('知识库更新任务已触发，请稍后查看结果')
    // 延迟刷新状态
    setTimeout(() => {
      loadSchedulerStatus()
      loadDocuments()
      loadStats()
    }, 3000)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '触发更新失败')
  }
}

/**
 * 重建索引
 */
async function handleRebuildIndex() {
  try {
    await ElMessageBox.confirm(
      '重建索引将清除现有索引数据并重新构建，此过程可能需要一些时间。确定继续吗？',
      '确认重建索引',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  rebuildLoading.value = true
  try {
    await rebuildIndex()
    ElMessage.success('索引重建已开始，请稍后刷新查看状态')
    loadStats()
    loadDocuments()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重建索引失败')
  } finally {
    rebuildLoading.value = false
  }
}

/**
 * 删除文档
 */
async function handleDeleteDocument(row) {
  try {
    await deleteDocument(row.id)
    ElMessage.success('文档已删除')
    loadDocuments()
    loadStats()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

/**
 * 搜索测试
 */
async function handleSearch() {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词')
    return
  }

  searchLoading.value = true
  searchPerformed.value = true
  try {
    const data = {
      query: searchQuery.value,
      top_k: searchTopK.value
    }
    if (searchCategory.value) {
      data.category = searchCategory.value
    }
    const res = await searchKnowledge(data)
    searchResults.value = res.data?.results || res.data || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '搜索失败')
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

/**
 * 打开上传弹窗
 */
function openUploadDialog() {
  uploadForm.category = ''
  uploadForm.title = ''
  rawFile.value = null
  uploadFileList.value = []
  uploadDialogVisible.value = true
}

/**
 * 文件选择变化事件（更可靠地获取 File 对象）
 */
function handleFileChange(file) {
  rawFile.value = file.raw || null
  uploadFileList.value = [file]
}

/**
 * 上传文件超出限制
 */
function handleUploadExceed() {
  ElMessage.warning('一次只能上传一个文件，请先移除当前文件')
  rawFile.value = null
  uploadFileList.value = []
}

/**
 * 执行上传
 */
async function handleUpload() {
  if (!rawFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  uploadLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', rawFile.value)
    if (uploadForm.category) {
      formData.append('category', uploadForm.category)
    }
    if (uploadForm.title) {
      formData.append('title', uploadForm.title)
    }

    await uploadDocument(formData)
    ElMessage.success('文档上传成功')
    uploadDialogVisible.value = false
    loadDocuments()
    loadStats()
    loadCategories()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploadLoading.value = false
  }
}

// ===== 工具函数 =====

/**
 * 格式化文件大小
 */
function formatFileSize(bytes) {
  if (bytes == null) return '-'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const size = (bytes / Math.pow(k, i)).toFixed(i > 0 ? 1 : 0)
  return `${size} ${units[i]}`
}

/**
 * 格式化时间
 */
function formatTime(timeStr) {
  if (!timeStr) return '-'
  try {
    const date = new Date(timeStr)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  } catch {
    return timeStr
  }
}

/**
 * 格式化相关度分数
 */
function formatScore(score) {
  if (score == null) return '-'
  return (Number(score) * 100).toFixed(1) + '%'
}
</script>

<style scoped>
.knowledge-manage {
  max-width: 1400px;
}

.section-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.card-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 调度器信息 */
.scheduler-info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 6px;
}

.scheduler-label {
  font-size: 12px;
  color: #909399;
}

.scheduler-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.logs-title {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
}

/* 来源链接 */
.source-link {
  font-size: 12px;
  color: #409eff;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-link:hover {
  text-decoration: underline;
}

/* 状态单元格 */
.status-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stale-icon {
  font-size: 16px;
  cursor: help;
  flex-shrink: 0;
}

/* 统计卡片 */
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background-color: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  transition: box-shadow 0.2s;
}

.stat-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* 搜索区域 */
.search-area {
  padding: 4px 0;
}

.topk-slider {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.topk-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: -8px;
}

/* 搜索结果 */
.search-results {
  margin-top: 0;
}

.result-summary {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
}

.result-item {
  margin-bottom: 12px;
}

.result-item:last-child {
  margin-bottom: 0;
}

.result-content {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
  margin-bottom: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.result-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.result-score {
  font-size: 13px;
  color: #909399;
}

.text-muted {
  color: #c0c4cc;
}

/* 上传弹窗 */
:deep(.el-upload-dragger) {
  padding: 40px 20px;
}
</style>