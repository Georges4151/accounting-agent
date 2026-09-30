<template>
  <div class="backup-restore">
    <el-card class="header-card" shadow="never">
      <div class="page-header">
        <div>
          <h2>数据备份与恢复</h2>
          <p class="desc">管理数据库备份文件，支持导出备份和恢复数据</p>
        </div>
        <el-button type="primary" :icon="Plus" @click="handleCreateBackup" :loading="creating">
          创建备份
        </el-button>
      </div>
    </el-card>

    <!-- 备份列表 -->
    <el-card class="backup-list-card" shadow="never" style="margin-top: 16px" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="card-title">备份列表</span>
          <el-tag type="info" size="small">{{ backups.length }} 个备份文件</el-tag>
        </div>
      </template>

      <el-table :data="backups" border stripe style="width: 100%">
        <el-table-column prop="filename" label="文件名" min-width="260" />
        <el-table-column prop="size" label="文件大小" width="120" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="180" align="center" />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :icon="Download" @click="handleDownload(row)">
              下载
            </el-button>
            <el-button type="danger" link size="small" :icon="Delete" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && backups.length === 0" description="暂无备份文件，请点击"创建备份"按钮" :image-size="80" />
    </el-card>

    <!-- 数据恢复 -->
    <el-card class="restore-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span class="card-title">数据恢复</span>
          <el-tag type="warning" size="small">恢复数据将覆盖当前数据库</el-tag>
        </div>
      </template>

      <div class="restore-section">
        <el-alert
          type="warning"
          title="注意：恢复操作将覆盖当前所有数据，请在恢复前创建备份！"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".zip"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          drag
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            将备份文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">仅支持 .zip 格式的备份文件</div>
          </template>
        </el-upload>
        <div style="margin-top: 16px; text-align: center">
          <el-button
            type="danger"
            :disabled="!selectedFile"
            :loading="restoring"
            @click="handleRestore"
          >
            确认恢复数据
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Delete, UploadFilled } from '@element-plus/icons-vue'
import { createBackup, getBackupList, downloadBackup, restoreBackup, deleteBackup } from '@/api/backup'

const loading = ref(false)
const creating = ref(false)
const restoring = ref(false)
const backups = ref([])
const selectedFile = ref(null)
const uploadRef = ref(null)

onMounted(() => {
  loadBackups()
})

async function loadBackups() {
  loading.value = true
  try {
    const res = await getBackupList()
    backups.value = res.data.items || []
  } catch (error) {
    ElMessage.error('加载备份列表失败')
  } finally {
    loading.value = false
  }
}

async function handleCreateBackup() {
  creating.value = true
  try {
    await createBackup()
    ElMessage.success('备份创建成功')
    await loadBackups()
  } catch (error) {
    ElMessage.error('创建备份失败')
  } finally {
    creating.value = false
  }
}

function handleDownload(row) {
  downloadBackup(row.filename).then(res => {
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = row.filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  }).catch(() => {
    ElMessage.error('下载失败')
  })
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定要删除备份文件 "${row.filename}" 吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteBackup(row.filename)
    ElMessage.success('备份已删除')
    await loadBackups()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

function handleFileChange(file) {
  selectedFile.value = file.raw
}

function handleFileRemove() {
  selectedFile.value = null
}

async function handleRestore() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择备份文件')
    return
  }

  try {
    await ElMessageBox.confirm(
      '恢复操作将覆盖当前数据库中的所有数据，此操作不可撤销！请确认是否继续？',
      '严重警告',
      {
        confirmButtonText: '确认恢复',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger'
      }
    )
  } catch {
    return
  }

  restoring.value = true
  try {
    const res = await restoreBackup(selectedFile.value)
    ElMessage.success(res.data.message || '数据恢复成功')
    selectedFile.value = null
    uploadRef.value?.clearFiles()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '恢复失败')
  } finally {
    restoring.value = false
  }
}
</script>

<style scoped>
.backup-restore {
  max-width: 1000px;
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.restore-section {
  padding: 0 20px;
}
</style>