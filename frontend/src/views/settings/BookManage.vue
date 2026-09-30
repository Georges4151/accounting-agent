<template>
  <div class="book-manage">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>账套管理</span>
          <el-button type="primary" @click="showCreateDialog = true" v-if="authStore.hasPermission('admin')">
            <el-icon><Plus /></el-icon>
            新建账套
          </el-button>
        </div>
      </template>

      <el-table :data="bookStore.bookList" v-loading="bookStore.loading" stripe>
        <el-table-column prop="name" label="账套名称" min-width="150" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="company_name" label="公司全称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="currency" label="币种" width="80" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '活跃' : '已归档' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_default" label="默认" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="member_count" label="成员数" width="80" align="center" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showMembers(row)">成员</el-button>
            <el-button link type="primary" @click="editBook(row)" v-if="authStore.hasPermission('admin')">编辑</el-button>
            <el-popconfirm
              title="确定要归档该账套吗？"
              @confirm="archiveBook(row)"
              v-if="authStore.hasPermission('admin') && !row.is_default && row.status !== 'archived'"
            >
              <template #reference>
                <el-button link type="danger">归档</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 归档密钥管理 -->
    <el-card shadow="never" style="margin-top: 16px" v-if="authStore.hasPermission('admin')">
      <template #header>
        <div class="card-header">
          <span>归档密钥管理</span>
          <el-tag v-if="keyStatus.exists" type="success" size="small">密钥已设置</el-tag>
          <el-tag v-else type="warning" size="small">未设置密钥</el-tag>
        </div>
      </template>
      <div v-if="keyStatus.exists">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="密钥标签">{{ keyStatus.key_label }}</el-descriptions-item>
          <el-descriptions-item label="U盘绑定">
            <el-tag v-if="keyStatus.usb_bound" type="success" size="small">已绑定</el-tag>
            <el-tag v-else type="info" size="small">未绑定</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ keyStatus.created_at ? formatTime(keyStatus.created_at) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="最后使用">{{ keyStatus.last_used_at ? formatTime(keyStatus.last_used_at) : '从未使用' }}</el-descriptions-item>
        </el-descriptions>
        <el-button
          type="primary"
          style="margin-top: 12px"
          :loading="generatingKey"
          @click="showGenerateKeyDialog = true"
        >
          重新生成密钥文件
        </el-button>
        <el-text type="info" size="small" style="margin-left: 8px">
          生成新密钥后旧密钥自动失效
        </el-text>
      </div>
      <div v-else>
        <el-alert
          title="尚未设置归档密钥"
          description="归档操作需要 U 盘密钥文件验证，请先生成密钥文件并保存到专用 U 盘"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />
        <el-button type="primary" :loading="generatingKey" @click="showGenerateKeyDialog = true">
          生成密钥文件
        </el-button>
      </div>
    </el-card>

    <!-- 密钥验证对话框 -->
    <el-dialog
      v-model="showKeyDialog"
      title="归档密钥验证"
      width="450px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="请插入包含密钥文件的 U 盘"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        <template #default>
          <p style="margin: 4px 0">选择 U 盘中的 .key 密钥文件进行验证</p>
        </template>
      </el-alert>
      <el-upload
        ref="keyUploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".key"
        :on-change="onKeyFileChange"
        :on-remove="onKeyFileRemove"
      >
        <el-button type="primary">
          <el-icon><Upload /></el-icon>
          选择密钥文件
        </el-button>
        <template #tip>
          <div class="el-upload__tip">仅支持 .key 格式的密钥文件</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showKeyDialog = false">取消</el-button>
        <el-button
          type="danger"
          :loading="verifyingKey"
          :disabled="!keyFile"
          @click="handleVerifyKey"
        >
          验证并归档
        </el-button>
      </template>
    </el-dialog>

    <!-- 生成密钥对话框 -->
    <el-dialog
      v-model="showGenerateKeyDialog"
      title="生成归档密钥"
      width="450px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="建议绑定专用 U 盘"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        <template #default>
          <p style="margin: 4px 0">绑定后密钥文件只能在指定 U 盘上使用</p>
        </template>
      </el-alert>
      <el-form label-width="100px">
        <el-form-item label="密钥标签">
          <el-input v-model="genKeyLabel" placeholder="如：归档专用U盘" maxlength="100" />
        </el-form-item>
        <el-form-item label="U盘序列号">
          <el-input
            v-model="genUsbSerial"
            placeholder="留空则不绑定U盘，或点击自动检测"
            style="width: 200px"
          />
          <el-button
            :loading="detectingUsb"
            @click="autoDetectUsb()"
            style="margin-left: 8px"
          >
            自动检测
          </el-button>
          <el-tooltip placement="top" effect="dark">
            <template #content>
              <div>将自动检测当前已连接的 USB 存储设备</div>
              <div>请确保目标 U 盘已插入</div>
            </template>
            <el-button link type="primary" style="margin-left: 4px">?</el-button>
          </el-tooltip>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateKeyDialog = false">取消</el-button>
        <el-button type="primary" :loading="generatingKey" @click="handleGenerateKey">
          生成并下载密钥文件
        </el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑账套对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingBook ? '编辑账套' : '新建账套'"
      width="550px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-form-item label="账套名称" prop="name">
          <el-input v-model="form.name" placeholder="如：XX科技有限公司" />
        </el-form-item>
        <el-form-item label="账套编码" prop="code">
          <el-input v-model="form.code" placeholder="如：COMPANY_A" :disabled="!!editingBook" />
        </el-form-item>
        <el-form-item label="公司全称" prop="company_name">
          <el-input v-model="form.company_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="统一社会信用代码" prop="tax_id">
          <el-input v-model="form.tax_id" placeholder="可选" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="会计年度起始月" prop="fiscal_year_start">
              <el-input-number v-model="form.fiscal_year_start" :min="1" :max="12" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="会计年度结束月" prop="fiscal_year_end">
              <el-input-number v-model="form.fiscal_year_end" :min="1" :max="12" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="币种" prop="currency">
              <el-select v-model="form.currency" style="width: 100%">
                <el-option label="人民币 (CNY)" value="CNY" />
                <el-option label="美元 (USD)" value="USD" />
                <el-option label="欧元 (EUR)" value="EUR" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="小数位数" prop="decimal_places">
              <el-input-number v-model="form.decimal_places" :min="0" :max="4" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          {{ editingBook ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 成员管理对话框 -->
    <el-dialog
      v-model="showMembersDialog"
      :title="`成员管理 - ${selectedBook?.name}`"
      width="600px"
    >
      <el-table :data="members" v-loading="membersLoading" stripe max-height="280">
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="姓名" width="100" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="roleType(row.role)" size="small">{{ roleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-popconfirm
              title="确定移除此成员？"
              @confirm="removeMember(row)"
            >
              <template #reference>
                <el-button link type="danger" size="small">移除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <template v-if="authStore.hasPermission('admin')">
        <el-divider />
        <el-tabs v-model="addMode" type="border-card" class="batch-add-tabs">
          <el-tab-pane label="按用户选择" name="users">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
              <template #title>
                选择用户添加到当前账套，账套角色将跟随用户管理系统角色
              </template>
            </el-alert>
            <div style="margin-bottom: 12px">
              <el-select
                v-model="batchAdd.user_ids"
                placeholder="选择用户（可多选）"
                filterable
                multiple
                collapse-tags
                collapse-tags-tooltip
                style="width: 100%"
              >
                <el-option
                  v-for="user in userOptions"
                  :key="user.id"
                  :label="`${user.username} (${user.real_name || '未设置'}) [${user.role}]`"
                  :value="user.id"
                />
              </el-select>
            </div>
            <el-button type="primary" @click="batchAddByUsers" :loading="batchAdding" :disabled="!batchAdd.user_ids?.length">
              批量添加 ({{ batchAdd.user_ids?.length || 0 }})
            </el-button>
          </el-tab-pane>

          <el-tab-pane label="按角色添加" name="role">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
              <template #title>
                将系统中所有指定角色的用户批量加入当前账套，账套角色跟随用户系统角色
              </template>
            </el-alert>
            <div class="add-member">
              <el-select v-model="batchAdd.role" placeholder="选择系统角色" style="width: 180px">
                <el-option label="出纳" value="cashier" />
                <el-option label="会计" value="accountant" />
                <el-option label="审核员" value="reviewer" />
                <el-option label="查看者" value="viewer" />
              </el-select>
              <el-button type="primary" @click="batchAddByRole" :loading="batchAdding" :disabled="!batchAdd.role">
                批量添加
              </el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="按部门添加" name="department">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
              <template #title>
                将指定部门的所有用户批量加入当前账套，账套角色跟随用户系统角色
              </template>
            </el-alert>
            <div class="add-member">
              <el-select v-model="batchAdd.department" placeholder="选择部门" filterable allow-create style="width: 200px">
                <el-option
                  v-for="dept in departmentOptions"
                  :key="dept"
                  :label="dept"
                  :value="dept"
                />
              </el-select>
              <el-button type="primary" @click="batchAddByDept" :loading="batchAdding" :disabled="!batchAdd.department">
                批量添加
              </el-button>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useBookStore } from '@/stores/book'
import { useAuthStore } from '@/stores/auth'
import { createBook, updateBook, deleteBook, archiveBook as archiveBookApi, getBookMembers, addBookMember, removeBookMember, batchAddBookMembers } from '@/api/book'
import { getKeyStatus, generateKey, verifyKey, detectUsbDrives } from '@/api/archive_key'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import request from '@/api/request'

const bookStore = useBookStore()
const authStore = useAuthStore()

const showCreateDialog = ref(false)
const showMembersDialog = ref(false)
const editingBook = ref(null)
const submitting = ref(false)
const formRef = ref(null)
const selectedBook = ref(null)
const members = ref([])
const membersLoading = ref(false)
const addingMember = ref(false)
const userOptions = ref([])

const form = reactive({
  name: '',
  code: '',
  company_name: '',
  tax_id: '',
  description: '',
  fiscal_year_start: 1,
  fiscal_year_end: 12,
  currency: 'CNY',
  decimal_places: 2,
})

const newMember = reactive({
  user_id: null,
})

const addMode = ref('users')
const batchAdding = ref(false)
const batchAdd = reactive({
  role: '',
  department: '',
  user_ids: [],
})

const departmentOptions = ref([])

const rules = {
  name: [{ required: true, message: '请输入账套名称', trigger: 'blur' }],
  code: [
    { required: true, message: '请输入账套编码', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]+$/, message: '编码只能包含字母、数字和下划线', trigger: 'blur' },
  ],
}

function roleLabel(role) {
  const labels = { admin: '管理员', cashier: '出纳', accountant: '会计', reviewer: '审核员', viewer: '查看者' }
  return labels[role] || role
}

function roleType(role) {
  const types = { admin: 'danger', cashier: 'warning', accountant: 'primary', reviewer: 'warning', viewer: 'info' }
  return types[role] || 'info'
}

function resetForm() {
  editingBook.value = null
  formRef.value?.resetFields()
  form.name = ''
  form.code = ''
  form.company_name = ''
  form.tax_id = ''
  form.description = ''
  form.fiscal_year_start = 1
  form.fiscal_year_end = 12
  form.currency = 'CNY'
  form.decimal_places = 2
}

function editBook(row) {
  editingBook.value = row
  form.name = row.name
  form.code = row.code
  form.company_name = row.company_name || ''
  form.tax_id = row.tax_id || ''
  form.description = row.description || ''
  form.fiscal_year_start = row.fiscal_year_start
  form.fiscal_year_end = row.fiscal_year_end
  form.currency = row.currency
  form.decimal_places = row.decimal_places
  showCreateDialog.value = true
}

async function loadAllBooks() {
  await bookStore.loadBooks(true)
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingBook.value) {
      await updateBook(editingBook.value.id, form)
      ElMessage.success('账套更新成功')
    } else {
      await createBook(form)
      ElMessage.success('账套创建成功')
    }
    showCreateDialog.value = false
    await loadAllBooks()
  } catch (error) {
    // 错误由拦截器处理
  } finally {
    submitting.value = false
  }
}

async function archiveBook(row) {
  // 先检查密钥状态
  try {
    const statusRes = await getKeyStatus()
    if (!statusRes.data.exists) {
      ElMessage.warning('请先生成归档密钥文件')
      return
    }
  } catch (e) {
    ElMessage.error('无法获取密钥状态')
    return
  }
  // 弹出密钥验证对话框
  pendingArchiveBook.value = row
  keyFile.value = null
  keyUploadRef.value?.clearFiles()
  showKeyDialog.value = true
}

// ===== 归档密钥管理 =====

const showKeyDialog = ref(false)
const showGenerateKeyDialog = ref(false)
const keyFile = ref(null)
const keyUploadRef = ref(null)
const verifyingKey = ref(false)
const generatingKey = ref(false)
const pendingArchiveBook = ref(null)
const genKeyLabel = ref('默认密钥')
const genUsbSerial = ref('')
const detectingUsb = ref(false)

const keyStatus = reactive({
  exists: false,
  key_label: '',
  usb_bound: false,
  created_at: '',
  last_used_at: '',
})

async function loadKeyStatus() {
  try {
    const res = await getKeyStatus()
    Object.assign(keyStatus, res.data)
  } catch (e) {
    // 忽略
  }
}

async function handleGenerateKey() {
  generatingKey.value = true
  try {
    const res = await generateKey(genKeyLabel.value, genUsbSerial.value)
    // 下载密钥文件
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `archive_key_${new Date().toISOString().slice(0, 10)}.key`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    const bindMsg = genUsbSerial.value ? '，已绑定U盘序列号' : ''
    ElMessage.success('密钥文件已生成，请保存到专用 U 盘' + bindMsg)
    showGenerateKeyDialog.value = false
    genKeyLabel.value = '默认密钥'
    genUsbSerial.value = ''
    await loadKeyStatus()
  } catch (e) {
    ElMessage.error('生成密钥文件失败')
  } finally {
    generatingKey.value = false
  }
}

async function autoDetectUsb() {
  detectingUsb.value = true
  try {
    const res = await detectUsbDrives()
    const drives = res.data.drives || []
    if (drives.length === 0) {
      ElMessage.warning('未检测到 USB 存储设备，请确认 U 盘已插入')
      return
    }
    const d = drives[0]
    genUsbSerial.value = d.serial_number
    if (drives.length === 1) {
      ElMessage.success(`已检测到: ${d.friendly_name} ${d.drive_letter} (${d.size_gb}GB)`)
    } else {
      const list = drives.map(d => `${d.friendly_name} ${d.drive_letter}(${d.size_gb}GB): ${d.serial_number}`).join('\n')
      ElMessage.success(`检测到 ${drives.length} 个USB设备，已自动选择第一个。\n全部设备:\n${list}`)
    }
  } catch (e) {
    ElMessage.error('USB 设备检测失败，请重试或手动输入序列号')
  } finally {
    detectingUsb.value = false
  }
}

function onKeyFileChange(file) {
  keyFile.value = file.raw
}

function onKeyFileRemove() {
  keyFile.value = null
}

async function handleVerifyKey() {
  if (!keyFile.value || !pendingArchiveBook.value) return

  verifyingKey.value = true
  try {
    // 验证密钥文件
    const res = await verifyKey(keyFile.value, 'archive', pendingArchiveBook.value.id)
    const token = res.data.token

    // 执行归档
    await archiveBookApi(pendingArchiveBook.value.id, token)
    ElMessage.success('账套已归档')
    showKeyDialog.value = false
    await loadAllBooks()
    await loadKeyStatus()
  } catch (error) {
    const detail = error.response?.data?.detail || '归档失败'
    ElMessage.error(detail)
  } finally {
    verifyingKey.value = false
  }
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

async function showMembers(row) {
  selectedBook.value = row
  showMembersDialog.value = true
  await loadMembers()
  await loadUsers()
}

async function loadMembers() {
  membersLoading.value = true
  try {
    const res = await getBookMembers(selectedBook.value.id)
    members.value = res.data.members || []
  } catch (error) {
    // 错误由拦截器处理
  } finally {
    membersLoading.value = false
  }
}

async function loadUsers() {
  try {
    const res = await request.get('/users', { params: { page_size: 100 } })
    userOptions.value = res.data.items || []
    // 提取不重复的部门列表
    const depts = new Set()
    userOptions.value.forEach(u => {
      if (u.department) depts.add(u.department)
    })
    departmentOptions.value = [...depts].sort()
  } catch (error) {
    // 错误由拦截器处理
  }
}

async function addMember() {
  addingMember.value = true
  try {
    await addBookMember(selectedBook.value.id, {
      user_id: newMember.user_id,
    })
    ElMessage.success('成员添加成功')
    newMember.user_id = null
    await loadMembers()
    await loadAllBooks()
  } catch (error) {
    // 错误由拦截器处理
  } finally {
    addingMember.value = false
  }
}

async function removeMember(row) {
  try {
    await removeBookMember(selectedBook.value.id, row.user_id)
    ElMessage.success('成员已移除')
    await loadMembers()
    await loadAllBooks()
  } catch (error) {
    // 错误由拦截器处理
  }
}

async function batchAddByRole() {
  batchAdding.value = true
  try {
    const res = await batchAddBookMembers(selectedBook.value.id, {
      mode: 'role',
      role: batchAdd.role,
    })
    ElMessage.success(res.data.message)
    batchAdd.role = ''
    await loadMembers()
    await loadAllBooks()
  } catch (error) {
    // 错误由拦截器处理
  } finally {
    batchAdding.value = false
  }
}

async function batchAddByDept() {
  batchAdding.value = true
  try {
    const res = await batchAddBookMembers(selectedBook.value.id, {
      mode: 'department',
      department: batchAdd.department,
    })
    ElMessage.success(res.data.message)
    batchAdd.department = ''
    await loadMembers()
    await loadAllBooks()
  } catch (error) {
    // 错误由拦截器处理
  } finally {
    batchAdding.value = false
  }
}

async function batchAddByUsers() {
  batchAdding.value = true
  try {
    const res = await batchAddBookMembers(selectedBook.value.id, {
      mode: 'users',
      user_ids: batchAdd.user_ids,
    })
    ElMessage.success(res.data.message)
    batchAdd.user_ids = []
    await loadMembers()
    await loadAllBooks()
  } catch (error) {
    // 错误由拦截器处理
  } finally {
    batchAdding.value = false
  }
}

onMounted(async () => {
  await loadAllBooks()
  await loadKeyStatus()
})
</script>

<style scoped>
.book-manage {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.add-member {
  display: flex;
  gap: 12px;
  align-items: center;
}

.batch-add-tabs {
  margin-top: 8px;
}

.batch-add-tabs :deep(.el-tabs__content) {
  padding: 12px;
}
</style>