<template>
  <!-- 用户管理页面（仅管理员可见） -->
  <div class="user-manage">
    <!-- 操作栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>
        新建用户
      </el-button>
      <el-button @click="loadUsers" :loading="tableLoading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 用户列表 -->
    <el-card shadow="never" style="margin-top: 16px">
      <el-table
        :data="userList"
        v-loading="tableLoading"
        border
        stripe
        style="width: 100%"
      >
        <el-table-column prop="username" label="用户名" width="130" />
        <el-table-column label="头像" width="80" align="center">
          <template #default="{ row }">
            <el-avatar :size="40" :src="row.avatar">
              {{ row.real_name?.charAt(0) || row.username?.charAt(0) }}
            </el-avatar>
          </template>
        </el-table-column>
        <el-table-column prop="real_name" label="真实姓名" width="120" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag
              :type="getRoleTagType(row.role)"
              size="small"
            >
              {{ getRoleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="部门" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login_at" label="最后登录" width="170">
          <template #default="{ row }">
            <span>{{ row.last_login_at || '从未登录' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openEditDialog(row)">
              编辑
            </el-button>
            <el-button
              text
              :type="row.is_active ? 'warning' : 'success'"
              size="small"
              @click="handleToggleStatus(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button text type="danger" size="small" @click="handleResetPassword(row)">
              重置密码
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑用户对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑用户' : '新建用户'"
      width="500px"
      :close-on-click-modal="false"
      @close="resetDialog"
    >
      <el-form
        ref="dialogFormRef"
        :model="dialogForm"
        :rules="dialogRules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="dialogForm.username"
            placeholder="请输入用户名"
            :disabled="isEditing"
            clearable
          />
        </el-form-item>
        <el-form-item label="真实姓名" prop="real_name">
          <el-input
            v-model="dialogForm.real_name"
            placeholder="请输入真实姓名"
            clearable
          />
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="!isEditing">
          <el-input
            v-model="dialogForm.password"
            type="password"
            placeholder="请输入密码（至少8位，含大小写字母、数字、特殊字符）"
            show-password
            clearable
            @input="onPasswordInput"
          />
          <div v-if="dialogForm.password" class="password-strength">
            <div class="strength-bar">
              <div
                class="strength-fill"
                :class="passwordStrengthClass"
                :style="{ width: passwordStrengthPercent + '%' }"
              ></div>
            </div>
            <span class="strength-text" :class="passwordStrengthClass">
              {{ passwordStrengthLabel }}
            </span>
          </div>
          <div v-if="dialogForm.password" class="password-rules">
            <div v-for="rule in passwordRules" :key="rule.label" class="rule-item">
              <el-icon :class="rule.passed ? 'rule-passed' : 'rule-failed'">
                <CircleCheck v-if="rule.passed" />
                <CircleClose v-else />
              </el-icon>
              <span>{{ rule.label }}</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="dialogForm.role" placeholder="请选择角色" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="出纳" value="cashier" />
            <el-option label="会计" value="accountant" />
            <el-option label="审核员" value="reviewer" />
            <el-option label="查看者" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input
            v-model="dialogForm.department"
            placeholder="请输入部门"
            clearable
          />
        </el-form-item>
        <el-form-item label="头像" v-if="isEditing">
          <div class="avatar-upload">
            <el-avatar :size="64" :src="avatarPreviewUrl" style="margin-right: 16px">
              {{ dialogForm.real_name?.charAt(0) || dialogForm.username?.charAt(0) }}
            </el-avatar>
            <el-upload
              :show-file-list="false"
              :before-upload="beforeAvatarUpload"
              :http-request="handleAvatarUpload"
              accept=".jpg,.jpeg,.png,.gif,.webp"
            >
              <el-button type="primary" size="small" :loading="avatarUploading">
                更换头像
              </el-button>
            </el-upload>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="handleSubmit">
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import request from '@/api/request'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ===== 状态 =====

// 用户列表
const userList = ref([])
const tableLoading = ref(false)

// 对话框
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const isEditing = ref(false)
const editingUserId = ref(null)
const dialogFormRef = ref(null)

// 头像上传
const avatarUploading = ref(false)
const avatarPreviewUrl = ref(null)

const dialogForm = reactive({
  username: '',
  real_name: '',
  password: '',
  role: 'accountant',
  department: ''
})

const dialogRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度 3-50 个字符', trigger: 'blur' }
  ],
  real_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 个字符', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (!value) return callback()
        const hasUpper = /[A-Z]/.test(value)
        const hasLower = /[a-z]/.test(value)
        const hasDigit = /\d/.test(value)
        const hasSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(value)
        if (!hasUpper) return callback(new Error('密码必须包含大写字母'))
        if (!hasLower) return callback(new Error('密码必须包含小写字母'))
        if (!hasDigit) return callback(new Error('密码必须包含数字'))
        if (!hasSpecial) return callback(new Error('密码必须包含特殊字符'))
        callback()
      },
      trigger: 'change'
    }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ]
}

// ===== 密码强度相关 =====

const passwordRules = computed(() => {
  const pw = dialogForm.password || ''
  return [
    { label: '至少 8 个字符', passed: pw.length >= 8 },
    { label: '包含大写字母', passed: /[A-Z]/.test(pw) },
    { label: '包含小写字母', passed: /[a-z]/.test(pw) },
    { label: '包含数字', passed: /\d/.test(pw) },
    { label: '包含特殊字符', passed: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(pw) },
  ]
})

const passwordStrengthScore = computed(() => {
  const pw = dialogForm.password || ''
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[A-Z]/.test(pw)) score++
  if (/[a-z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(pw)) score++
  if (pw.length >= 16) score++
  return score
})

const passwordStrengthPercent = computed(() => {
  return Math.min(100, passwordStrengthScore.value * 14)
})

const passwordStrengthClass = computed(() => {
  if (passwordStrengthScore.value <= 2) return 'weak'
  if (passwordStrengthScore.value <= 4) return 'medium'
  return 'strong'
})

const passwordStrengthLabel = computed(() => {
  if (passwordStrengthScore.value <= 2) return '弱'
  if (passwordStrengthScore.value <= 4) return '中等'
  return '强'
})

function onPasswordInput() {
  // 密码输入时实时更新强度指示器
}

// ===== 生命周期 =====

onMounted(() => {
  loadUsers()
})

// ===== 数据加载 =====

/**
 * 加载用户列表
 */
async function loadUsers() {
  tableLoading.value = true
  try {
    const res = await request.get('/users')
    userList.value = res.data?.items || []
  } catch (error) {
    ElMessage.error('加载用户列表失败')
  } finally {
    tableLoading.value = false
  }
}

// ===== 对话框操作 =====

/**
 * 打开新建用户对话框
 */
function openCreateDialog() {
  isEditing.value = false
  editingUserId.value = null
  resetDialogForm()
  dialogVisible.value = true
}

/**
 * 打开编辑用户对话框
 */
function openEditDialog(user) {
  isEditing.value = true
  editingUserId.value = user.id
  dialogForm.username = user.username
  dialogForm.real_name = user.real_name
  dialogForm.role = user.role
  dialogForm.department = user.department || ''
  avatarPreviewUrl.value = user.avatar || null
  dialogVisible.value = true
}

/**
 * 重置对话框
 */
function resetDialog() {
  dialogFormRef.value?.resetFields()
  resetDialogForm()
}

function resetDialogForm() {
  dialogForm.username = ''
  dialogForm.real_name = ''
  dialogForm.password = ''
  dialogForm.role = 'accountant'
  dialogForm.department = ''
  avatarPreviewUrl.value = null
}

/**
 * 提交表单
 */
async function handleSubmit() {
  if (!dialogFormRef.value) return
  try {
    await dialogFormRef.value.validate()
  } catch {
    return
  }

  dialogLoading.value = true
  try {
    if (isEditing.value) {
      // 编辑用户
      await request.put(`/users/${editingUserId.value}`, {
        real_name: dialogForm.real_name,
        role: dialogForm.role,
        department: dialogForm.department
      })
      ElMessage.success('用户信息更新成功')
    } else {
      // 创建用户
      await request.post('/users', {
        username: dialogForm.username,
        real_name: dialogForm.real_name,
        password: dialogForm.password,
        role: dialogForm.role,
        department: dialogForm.department
      })
      ElMessage.success('用户创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    dialogLoading.value = false
  }
}

/**
 * 头像上传前校验
 */
function beforeAvatarUpload(file) {
  const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!validTypes.includes(file.type)) {
    ElMessage.error('仅支持 JPG、PNG、GIF、WebP 格式')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('头像大小不能超过 2MB')
    return false
  }
  return true
}

/**
 * 自定义头像上传
 */
async function handleAvatarUpload({ file }) {
  avatarUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await request.post(`/users/${editingUserId.value}/avatar`, formData)
    avatarPreviewUrl.value = res.data.avatar
    ElMessage.success('头像更新成功')
    loadUsers()
  } catch (e) {
    // 错误已在拦截器中处理
  } finally {
    avatarUploading.value = false
  }
}

// ===== 用户操作 =====

/**
 * 启用/禁用用户
 */
async function handleToggleStatus(user) {
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确定要${action}用户 "${user.username}" 吗？`,
      '提示',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await request.put(`/users/${user.id}/toggle-active`)
    ElMessage.success(`用户已${action}`)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

/**
 * 重置密码
 */
async function handleResetPassword(user) {
  try {
    const { value: newPassword } = await ElMessageBox.prompt(
      `请输入用户 "${user.username}" 的新密码`,
      '重置密码',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputType: 'password',
        inputValidator: (val) => {
          if (!val) return '密码不能为空'
          if (val.length < 6) return '密码至少 6 个字符'
          return true
        }
      }
    )
    await request.put(`/users/${user.id}/reset-password`, { password: newPassword })
    ElMessage.success('密码重置成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置失败')
    }
  }
}

// ===== 工具方法 =====

/**
 * 获取角色标签
 */
function getRoleLabel(role) {
  const labels = { admin: '管理员', cashier: '出纳', accountant: '会计', reviewer: '审核员', viewer: '查看者' }
  return labels[role] || role
}

/**
 * 获取角色标签颜色
 */
function getRoleTagType(role) {
  const types = { admin: 'danger', cashier: 'warning', accountant: 'primary', reviewer: 'warning', viewer: 'info' }
  return types[role] || 'info'
}
</script>

<style scoped>
.user-manage {
  max-width: 1200px;
}

.toolbar {
  display: flex;
  gap: 8px;
}

/* 密码强度指示器 */
.password-strength {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.strength-bar {
  flex: 1;
  height: 6px;
  background-color: #ebeef5;
  border-radius: 3px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.strength-fill.weak {
  background-color: #f56c6c;
}

.strength-fill.medium {
  background-color: #e6a23c;
}

.strength-fill.strong {
  background-color: #67c23a;
}

.strength-text {
  font-size: 12px;
  font-weight: 600;
  min-width: 30px;
}

.strength-text.weak {
  color: #f56c6c;
}

.strength-text.medium {
  color: #e6a23c;
}

.strength-text.strong {
  color: #67c23a;
}

/* 密码规则检查 */
.password-rules {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.rule-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.rule-passed {
  color: #67c23a;
}

.rule-failed {
  color: #c0c4cc;
}

/* 头像上传 */
.avatar-upload {
  display: flex;
  align-items: center;
}
</style>