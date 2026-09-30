import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 模型选择状态管理
 * 管理 AI 对话时的模型选择配置
 */
export const useModelStore = defineStore('model', () => {
  // ===== 状态 =====

  // 当前模式：'auto'（自动优先外部）| 'ollama'（本地）| 'external'（外部 API）
  const currentMode = ref('auto')

  // 当前选中的模型名称
  const currentModel = ref('')

  // 提供商代码（如 'openai', 'anthropic', 'ollama' 等）
  const providerCode = ref('')

  // 是否启用联网搜索
  const enableWebSearch = ref(false)

  // ===== 默认模型设置 =====

  // 默认 Ollama 模型（如 qwen2.5:7b），当用户选择"本地 Ollama"但未指定具体模型时使用
  const defaultOllamaModel = ref('')

  // 默认外部模型（如 deepseek-chat），当用户选择"外部 API"但未指定具体模型时使用
  const defaultExternalModel = ref('')

  // 默认外部提供商代码（如 deepseek）
  const defaultExternalProvider = ref('')

  // ===== 计算属性 =====

  // 模式描述文本
  const modeLabel = computed(() => {
    const labels = {
      auto: '自动（优先外部）',
      ollama: '本地 Ollama',
      external: '外部 API'
    }
    return labels[currentMode.value] || '自动'
  })

  // 当前模型显示文本
  const modelLabel = computed(() => {
    if (currentModel.value) return currentModel.value
    if (currentMode.value === 'auto') return '自动选择'
    if (currentMode.value === 'ollama' && defaultOllamaModel.value) {
      return defaultOllamaModel.value
    }
    if (currentMode.value === 'ollama') return '本地模型'
    if (currentMode.value === 'external' && defaultExternalModel.value) {
      return defaultExternalModel.value
    }
    return '外部模型'
  })

  // ===== 操作方法 =====

  /**
   * 设置运行模式
   * @param {string} mode - 'auto' | 'ollama' | 'external'
   */
  function setMode(mode) {
    currentMode.value = mode
  }

  /**
   * 设置当前模型
   * @param {string} model - 模型名称
   */
  function setModel(model) {
    currentModel.value = model
  }

  /**
   * 设置提供商代码
   * @param {string} code - 提供商代码
   */
  function setProvider(code) {
    providerCode.value = code
  }

  /**
   * 切换联网搜索开关
   */
  function toggleWebSearch() {
    enableWebSearch.value = !enableWebSearch.value
  }

  // ===== 默认模型操作方法 =====

  function setDefaultOllamaModel(model) {
    defaultOllamaModel.value = model || ''
  }

  function setDefaultExternalModel(model) {
    defaultExternalModel.value = model || ''
  }

  function setDefaultExternalProvider(provider) {
    defaultExternalProvider.value = provider || ''
  }

  return {
    // 状态
    currentMode,
    currentModel,
    providerCode,
    enableWebSearch,
    // 默认模型
    defaultOllamaModel,
    defaultExternalModel,
    defaultExternalProvider,
    // 计算属性
    modeLabel,
    modelLabel,
    // 操作方法
    setMode,
    setModel,
    setProvider,
    toggleWebSearch,
    // 默认模型方法
    setDefaultOllamaModel,
    setDefaultExternalModel,
    setDefaultExternalProvider,
  }
}, {
  // 持久化配置：记住用户的模型选择偏好
  persist: {
    key: 'model-store',
    storage: localStorage,
    pick: [
      'currentMode', 'currentModel', 'providerCode', 'enableWebSearch',
      'defaultOllamaModel', 'defaultExternalModel', 'defaultExternalProvider'
    ]
  }
})