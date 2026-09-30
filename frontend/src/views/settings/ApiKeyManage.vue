<template>
  <!-- API Key 管理页面 -->
  <div class="apikey-manage">
    <!-- 安全提示 -->
    <el-alert
      title="安全提示"
      type="warning"
      description="请妥善保管您的 API Key，系统将使用加密存储保护您的密钥安全。建议为每个 API Key 设置使用限额并定期轮换。"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <!-- 添加 Key 区域 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>添加 API Key</span>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="addForm"
        :rules="formRules"
        label-width="120px"
        @submit.prevent="handleAddKey"
      >
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="提供商" prop="provider_code">
              <el-select
                v-model="addForm.provider_code"
                placeholder="请选择提供商"
                style="width: 100%"
                @change="onProviderChange"
              >
                <el-option
                  v-for="p in providers"
                  :key="p.code"
                  :label="p.name"
                  :value="p.code"
                >
                  <span>{{ p.name }}</span>
                  <a
                    v-if="p.get_link"
                    :href="p.get_link"
                    target="_blank"
                    style="font-size: 12px; color: #409eff; margin-left: 8px"
                    @click.stop
                  >
                    获取 Key
                  </a>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="别名" prop="alias">
              <el-input
                v-model="addForm.alias"
                placeholder="自定义名称"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="API Key" prop="api_key">
              <el-input
                v-model="addForm.api_key"
                type="password"
                placeholder="请输入 API Key"
                show-password
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="自定义地址" prop="base_url">
          <el-input
            v-model="addForm.base_url"
            placeholder="可选，自定义 API 服务地址（如代理地址）"
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleAddKey" :loading="addLoading">
            添加 Key
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Key 列表 -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>已配置的 API Key</span>
          <el-button text type="primary" @click="loadKeys">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-table
        :data="keyList"
        v-loading="tableLoading"
        border
        stripe
        style="width: 100%"
      >
        <el-table-column prop="alias" label="别名" min-width="120" />
        <el-table-column prop="provider_name" label="提供商" width="120" />
        <el-table-column label="Key 前缀" width="150">
          <template #default="{ row }">
            <el-tooltip :content="row.api_key_preview" placement="top">
              <span>{{ row.api_key_preview || '****' }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="primary" size="small">默认</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="call_count" label="调用次数" width="100" />
        <el-table-column prop="last_used_at" label="最后使用" width="160">
          <template #default="{ row }">
            <span>{{ row.last_used_at || '未使用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button
              text
              type="primary"
              size="small"
              @click="handleToggleKey(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button
              text
              type="warning"
              size="small"
              :disabled="row.is_default"
              @click="handleSetDefault(row)"
            >
              设为默认
            </el-button>
            <el-popconfirm
              title="确定要删除该 API Key 吗？此操作不可恢复。"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDeleteKey(row)"
            >
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!tableLoading && keyList.length === 0"
        description="暂无 API Key，请添加"
        :image-size="80"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getKeys, addKey, setDefaultKey, toggleKey, deleteKey, getProviders } from '@/api/apikey'
import { ElMessage } from 'element-plus'

// ===== 状态 =====

// 添加表单
const formRef = ref(null)
const addLoading = ref(false)

const addForm = reactive({
  provider_code: '',
  alias: '',
  api_key: '',
  base_url: ''
})

// 表单验证规则
const formRules = {
  provider_code: [
    { required: true, message: '请选择提供商', trigger: 'change' }
  ],
  api_key: [
    { required: true, message: '请输入 API Key', trigger: 'blur' }
  ]
}

// 提供商列表
const providers = ref([])

// Key 列表
const keyList = ref([])
const tableLoading = ref(false)

// ===== 生命周期 =====

onMounted(() => {
  loadProviders()
  loadKeys()
})

// ===== 数据加载方法 =====

/**
 * 加载提供商列表
 */
async function loadProviders() {
  try {
    const res = await getProviders()
    providers.value = res.data.providers || []
  } catch (error) {
    ElMessage.error('加载提供商列表失败')
  }
}

/**
 * 加载 Key 列表
 */
async function loadKeys() {
  tableLoading.value = true
  try {
    const res = await getKeys()
    keyList.value = res.data.keys || []
  } catch (error) {
    ElMessage.error('加载 API Key 列表失败')
  } finally {
    tableLoading.value = false
  }
}

// ===== 操作方法 =====

/**
 * 提供商变化处理
 */
function onProviderChange(code) {
  // 可以在这里做一些额外处理
}

/**
 * 添加 API Key
 */
async function handleAddKey() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  addLoading.value = true
  try {
    await addKey({
      provider_code: addForm.provider_code,
      alias: addForm.alias || undefined,
      api_key: addForm.api_key,
      base_url: addForm.base_url || undefined
    })
    ElMessage.success('API Key 添加成功')
    resetForm()
    loadKeys()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  } finally {
    addLoading.value = false
  }
}

/**
 * 重置表单
 */
function resetForm() {
  formRef.value?.resetFields()
  addForm.base_url = ''
}

/**
 * 启用/禁用 Key
 */
async function handleToggleKey(row) {
  try {
    await toggleKey(row.id)
    ElMessage.success(row.is_active ? '已禁用' : '已启用')
    loadKeys()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

/**
 * 设为默认 Key
 */
async function handleSetDefault(row) {
  try {
    await setDefaultKey(row.id)
    ElMessage.success('已设为默认 Key')
    loadKeys()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

/**
 * 删除 Key
 */
async function handleDeleteKey(row) {
  try {
    await deleteKey(row.id)
    ElMessage.success('API Key 已删除')
    loadKeys()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped>
.apikey-manage {
  max-width: 1200px;
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

.text-muted {
  color: #c0c4cc;
}
</style>