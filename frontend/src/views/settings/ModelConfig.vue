<template>
  <!-- 模型配置页面 -->
  <div class="model-config">
    <!-- 默认模型设置 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>默认模型设置</span>
        </div>
      </template>

      <el-form label-width="140px">
        <el-form-item label="默认模式">
          <el-radio-group v-model="defaultMode">
            <el-radio-button value="auto">自动选择（优先外部 API）</el-radio-button>
            <el-radio-button value="ollama">本地 Ollama</el-radio-button>
            <el-radio-button value="external">外部 API</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="默认 Ollama 模型">
          <el-select
            v-model="defaultOllamaModel"
            placeholder="选择默认模型（可选）"
            clearable
            filterable
            style="width: 360px"
          >
            <el-option
              v-for="m in localModels"
              :key="'ollama-' + m.name"
              :label="m.name"
              :value="m.name"
            />
          </el-select>
          <div class="form-tip">
            选择"本地 Ollama"模式但未指定具体模型时，默认使用此模型
          </div>
        </el-form-item>

        <el-form-item label="默认外部模型">
          <el-select
            v-model="defaultExternalModel"
            placeholder="选择默认模型（可选）"
            clearable
            filterable
            style="width: 360px"
          >
            <el-option
              v-for="m in externalModels"
              :key="'ext-' + m.provider_code + ':' + m.model_name"
              :label="m.provider_code + ':' + m.model_name"
              :value="m.provider_code + ':' + m.model_name"
            />
          </el-select>
          <div class="form-tip">
            选择"外部 API"模式但未指定具体模型时，默认使用此模型
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveDefaultSettings" :loading="saving">
            保存设置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 本地模型列表 -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>本地模型（Ollama）</span>
          <el-button text type="primary" @click="loadAllModels" :loading="localLoading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col
          :span="8"
          v-for="model in localModels"
          :key="model.name"
          style="margin-bottom: 16px"
        >
          <el-card
            class="model-card"
            :class="{ 'is-default': isDefaultOllamaModel(model.name) }"
            shadow="hover"
            @click="setAsDefaultOllama(model.name)"
          >
            <div class="model-info">
              <div class="model-name">
                <el-icon color="#409eff"><Cpu /></el-icon>
                <span>{{ model.name }}</span>
              </div>
              <div class="model-meta">
                <span class="meta-item">大小：{{ model.size || '未知' }}</span>
                <span class="meta-item">修改时间：{{ model.modified_at || '未知' }}</span>
              </div>
              <el-tag
                :type="isDefaultOllamaModel(model.name) ? 'success' : 'info'"
                size="small"
                style="margin-top: 8px"
              >
                {{ isDefaultOllamaModel(model.name) ? '当前默认' : '点击设为默认' }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty
        v-if="!localLoading && localModels.length === 0"
        description="未检测到本地 Ollama 模型，请确保 Ollama 服务已启动"
        :image-size="80"
      >
        <el-button type="primary" @click="loadAllModels">重新检测</el-button>
      </el-empty>
    </el-card>

    <!-- 外部模型列表 -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>外部模型（通过 API Key 配置）</span>
          <el-button text type="primary" @click="$router.push('/settings/api-keys')">
            管理 API Key
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </template>

      <el-table
        :data="externalModels"
        v-loading="externalLoading"
        border
        stripe
        style="width: 100%"
      >
        <el-table-column prop="model_name" label="模型名称" min-width="150" />
        <el-table-column prop="provider_name" label="提供商" width="120" />
        <el-table-column prop="provider_code" label="提供商代码" width="130" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '可用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="primary" size="small">默认</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              text
              type="primary"
              size="small"
              @click="setAsDefaultExternal(row.provider_code, row.model_name)"
            >
              设为默认
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!externalLoading && externalModels.length === 0"
        description="暂无外部模型，请先添加 API Key"
        :image-size="80"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useModelStore } from '@/stores/model'
import { getAvailableModels } from '@/api/chat'
import { ElMessage } from 'element-plus'

const modelStore = useModelStore()

// ===== 状态 =====

// 默认模式（双向绑定到 store）
const defaultMode = computed({
  get: () => modelStore.currentMode || 'auto',
  set: (val) => { modelStore.setMode(val) }
})

// 默认 Ollama 模型（双向绑定到 store）
const defaultOllamaModel = computed({
  get: () => modelStore.defaultOllamaModel || '',
  set: (val) => { modelStore.setDefaultOllamaModel(val) }
})

// 默认外部模型（双向绑定到 store，格式 provider:model）
const defaultExternalModel = computed({
  get: () => {
    if (modelStore.defaultExternalProvider && modelStore.defaultExternalModel) {
      return modelStore.defaultExternalProvider + ':' + modelStore.defaultExternalModel
    }
    return ''
  },
  set: (val) => {
    const extValue = val || ''
    const colonIdx = extValue.indexOf(':')
    if (colonIdx > 0) {
      modelStore.setDefaultExternalProvider(extValue.slice(0, colonIdx))
      modelStore.setDefaultExternalModel(extValue.slice(colonIdx + 1))
    } else {
      modelStore.setDefaultExternalProvider('')
      modelStore.setDefaultExternalModel('')
    }
  }
})

const saving = ref(false)

// 本地模型
const localModels = ref([])
const localLoading = ref(false)

// 外部模型
const externalModels = ref([])
const externalLoading = ref(false)

// 所有可用模型数据缓存
let allModelsData = null

// ===== 生命周期 =====

onMounted(() => {
  loadAllModels()
})

// ===== 数据加载方法 =====

/**
 * 加载所有模型（本地 + 外部）
 */
async function loadAllModels() {
  localLoading.value = true
  externalLoading.value = true
  try {
    const data = await getAvailableModels()
    allModelsData = data

    // 本地模型：后端返回 {local: [{name, provider}, ...]}
    localModels.value = (data?.local || []).map(m => ({
      name: m.name || m,
      size: m.size || '',
      modified_at: m.modified_at || ''
    }))

    // 外部模型：后端返回 {external: [{name, provider, provider_code}, ...]}
    externalModels.value = (data?.external || []).map(m => ({
      model_name: m.name,
      provider_name: m.provider,
      provider_code: m.provider_code,
      is_active: true,
      is_default: (modelStore.defaultExternalProvider === m.provider_code &&
                   modelStore.defaultExternalModel === m.name)
    }))
  } catch (error) {
    // 本地模型可能不可用，静默处理
    localModels.value = []
    externalModels.value = []
  } finally {
    localLoading.value = false
    externalLoading.value = false
  }
}

// ===== 操作方法 =====

/**
 * 保存默认设置（确认按钮）
 */
async function saveDefaultSettings() {
  saving.value = true
  try {
    // 所有值已通过 computed 双向绑定实时写入 store + localStorage
    ElMessage.success('默认模型设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

/**
 * 判断是否为默认 Ollama 模型
 */
function isDefaultOllamaModel(modelName) {
  return modelStore.defaultOllamaModel === modelName
}

/**
 * 设置为默认 Ollama 模型（点击卡片）
 */
function setAsDefaultOllama(modelName) {
  modelStore.setDefaultOllamaModel(modelName)
  ElMessage.success(`已设置 "${modelName}" 为默认 Ollama 模型`)
}

/**
 * 设置为默认外部模型
 */
function setAsDefaultExternal(providerCode, modelName) {
  modelStore.setDefaultExternalProvider(providerCode)
  modelStore.setDefaultExternalModel(modelName)
  ElMessage.success(`已设置 "${providerCode}:${modelName}" 为默认外部模型`)
}
</script>

<style scoped>
.model-config {
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

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.model-card {
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}

.model-card:hover {
  border-color: #409eff;
}

.model-card.is-default {
  border-color: #67c23a;
  background-color: #f0f9eb;
}

.model-info {
  display: flex;
  flex-direction: column;
}

.model-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
}

.model-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}

.text-muted {
  color: #c0c4cc;
}
</style>