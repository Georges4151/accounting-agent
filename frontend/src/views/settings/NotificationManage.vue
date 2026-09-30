<template>
  <div class="notification-manage">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>发送通知</span>
        </div>
      </template>

      <el-form :model="form" ref="formRef" :rules="rules" label-width="100px" style="max-width: 700px">
        <el-form-item label="通知标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入通知标题" maxlength="200" show-word-limit />
        </el-form-item>

        <el-form-item label="通知内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            placeholder="请输入通知内容"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="通知类型">
              <el-select v-model="form.type" style="width: 100%">
                <el-option label="信息" value="info" />
                <el-option label="警告" value="warning" />
                <el-option label="成功" value="success" />
                <el-option label="错误" value="error" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类">
              <el-select v-model="form.category" style="width: 100%">
                <el-option label="系统通知" value="system" />
                <el-option label="凭证相关" value="voucher" />
                <el-option label="票据相关" value="invoice" />
                <el-option label="审批相关" value="approval" />
                <el-option label="税务相关" value="tax" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="跳转链接">
          <el-input v-model="form.link" placeholder="可选，如 /voucher/list" />
        </el-form-item>

        <el-divider content-position="left">发送范围</el-divider>

        <el-form-item label="发送模式">
          <el-radio-group v-model="form.recipient_mode" @change="onModeChange">
            <el-radio-button value="all">全部用户</el-radio-button>
            <el-radio-button value="role">按角色</el-radio-button>
            <el-radio-button value="department">按部门</el-radio-button>
            <el-radio-button value="users">指定用户</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.recipient_mode === 'role'" label="选择角色">
          <el-select v-model="form.role" placeholder="选择角色" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="出纳" value="cashier" />
            <el-option label="会计" value="accountant" />
            <el-option label="审核员" value="reviewer" />
            <el-option label="查看者" value="viewer" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.recipient_mode === 'department'" label="选择部门">
          <el-select v-model="form.department" placeholder="选择部门" filterable allow-create style="width: 100%">
            <el-option
              v-for="dept in departmentOptions"
              :key="dept"
              :label="dept"
              :value="dept"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.recipient_mode === 'users'" label="选择用户">
          <el-select
            v-model="form.user_ids"
            multiple
            filterable
            placeholder="搜索并选择用户"
            style="width: 100%"
          >
            <el-option
              v-for="user in userOptions"
              :key="user.id"
              :label="`${user.real_name || user.username} (${user.department || '-'})`"
              :value="user.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="sending" @click="handleSend">
            发送通知
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 发送记录 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>发送记录</span>
          <el-tag size="small" type="info">最近 20 条</el-tag>
        </div>
      </template>

      <el-table :data="sentHistory" v-loading="historyLoading" stripe>
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="recipient_desc" label="发送范围" min-width="120" />
        <el-table-column prop="count" label="接收人数" width="90" align="center" />
        <el-table-column label="发送时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { sendNotification } from '@/api/notification'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

const formRef = ref(null)
const sending = ref(false)

const form = reactive({
  title: '',
  content: '',
  type: 'info',
  category: 'system',
  link: '',
  recipient_mode: 'all',
  role: '',
  department: '',
  user_ids: [],
})

const rules = {
  title: [
    { required: true, message: '请输入通知标题', trigger: 'blur' },
    { max: 200, message: '标题不能超过200字', trigger: 'blur' },
  ],
  content: [
    { required: true, message: '请输入通知内容', trigger: 'blur' },
  ],
}

const userOptions = ref([])
const departmentOptions = ref([])

// 发送记录
const sentHistory = ref([])
const historyLoading = ref(false)

function onModeChange() {
  form.role = ''
  form.department = ''
  form.user_ids = []
}

async function loadUsers() {
  try {
    const res = await request.get('/users', { params: { page_size: 200 } })
    const users = res.data.items || []
    userOptions.value = users
    // 提取部门列表
    const depts = [...new Set(users.map(u => u.department).filter(Boolean))]
    departmentOptions.value = depts.sort()
  } catch (e) {
    // 忽略
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await request.get('/notifications', { params: { page: 1, page_size: 20 } })
    const items = (res.data.items || []).slice(0, 20)
    // 按标题分组，取每组第一条（同一批发送的标题相同，取最早时间）
    const grouped = {}
    for (const item of items) {
      if (!grouped[item.title]) {
        grouped[item.title] = {
          ...item,
          count: 1,
          recipient_desc: '—',
        }
      } else {
        grouped[item.title].count++
        // 取最早时间
        if (item.created_at < grouped[item.title].created_at) {
          grouped[item.title].created_at = item.created_at
        }
      }
    }
    sentHistory.value = Object.values(grouped).sort(
      (a, b) => new Date(b.created_at) - new Date(a.created_at)
    )
  } catch (e) {
    // 忽略
  } finally {
    historyLoading.value = false
  }
}

async function handleSend() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  sending.value = true
  try {
    const res = await sendNotification({
      title: form.title,
      content: form.content,
      type: form.type,
      category: form.category,
      link: form.link || null,
      recipient_mode: form.recipient_mode,
      role: form.recipient_mode === 'role' ? form.role : null,
      department: form.recipient_mode === 'department' ? form.department : null,
      user_ids: form.recipient_mode === 'users' ? form.user_ids : null,
    })
    ElMessage.success(res.data.message)
    resetForm()
    await loadHistory()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '发送失败')
  } finally {
    sending.value = false
  }
}

function resetForm() {
  form.title = ''
  form.content = ''
  form.type = 'info'
  form.category = 'system'
  form.link = ''
  form.recipient_mode = 'all'
  form.role = ''
  form.department = ''
  form.user_ids = []
  formRef.value?.clearValidate()
}

function typeTag(type) {
  const map = { info: '', warning: 'warning', success: 'success', error: 'danger' }
  return map[type] || ''
}

function typeLabel(type) {
  const map = { info: '信息', warning: '警告', success: '成功', error: '错误' }
  return map[type] || type
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadUsers()
  loadHistory()
})
</script>