<template>
  <!-- AI 对话助手页面 -->
  <div class="chat-assistant">
    <el-row :gutter="16" style="height: 100%">
      <!-- 左侧：对话历史列表 -->
      <el-col :span="6" class="chat-sidebar-col">
        <el-card class="chat-sidebar" shadow="never">
          <template #header>
            <div class="sidebar-header">
              <span>对话列表</span>
              <el-button type="primary" size="small" @click="newConversation">
                <el-icon><Plus /></el-icon>
                <span>新建对话</span>
              </el-button>
            </div>
          </template>

          <!-- 对话列表 -->
          <div class="conversation-list" v-if="conversations.length > 0">
            <div
              v-for="conv in conversations"
              :key="conv.id"
              class="conversation-item"
              :class="{ active: conv.id === currentConversationId }"
              @click="selectConversation(conv.id)"
            >
              <div class="conv-info">
                <div class="conv-title">{{ conv.title || '新对话' }}</div>
                <div class="conv-time">{{ formatTime(conv.updated_at) }}</div>
              </div>
              <el-button
                text
                size="small"
                class="conv-delete-btn"
                @click.stop="handleDeleteConversation(conv.id)"
              >
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
          </div>
          <el-empty v-else description="暂无对话记录" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右侧：对话区域 -->
      <el-col :span="18" class="chat-main-col">
        <el-card class="chat-main" shadow="never">
          <!-- 对话标题栏 -->
          <div class="chat-header">
            <div class="chat-header-left">
              <span class="chat-title">{{ currentConversationTitle }}</span>
            </div>
            <div class="chat-header-right">
              <!-- 记忆指示器 -->
              <el-tooltip
                :content="memoryTooltipContent"
                placement="bottom"
                :disabled="memoryCount === 0"
              >
                <el-tag
                  size="small"
                  type="info"
                  effect="plain"
                  class="memory-indicator"
                >
                  <el-icon><DataBoard /></el-icon>
                  已学习 {{ memoryCount }} 条记忆
                </el-tag>
              </el-tooltip>

              <!-- 清除记忆 -->
              <el-popconfirm
                title="确定要清除所有AI记忆吗？"
                confirm-button-text="确定"
                cancel-button-text="取消"
                @confirm="handleClearMemories"
              >
                <template #reference>
                  <el-button text size="small" type="warning">
                    <el-icon><Delete /></el-icon>
                    清除记忆
                  </el-button>
                </template>
              </el-popconfirm>

              <!-- 模型选择 -->
              <el-select
                v-model="chatModel"
                placeholder="选择模型"
                size="small"
                style="width: 220px"
                filterable
              >
                <el-option label="自动选择" value="auto">
                  <span>自动选择</span>
                  <span style="float: right; color: #8492a6; font-size: 12px">优先外部</span>
                </el-option>
                <el-option-group label="本地 Ollama">
                  <el-option label="Ollama（默认）" value="ollama" />
                  <el-option
                    v-for="m in localModels"
                    :key="'local:' + m.name"
                    :label="m.name"
                    :value="'ollama:' + m.name"
                  />
                </el-option-group>
                <el-option-group
                  v-for="group in externalModelGroups"
                  :key="group.provider"
                  :label="group.provider"
                >
                  <el-option
                    v-for="m in group.models"
                    :key="group.provider_code + ':' + m.name"
                    :label="m.name"
                    :value="group.provider_code + ':' + m.name"
                  />
                </el-option-group>
              </el-select>

              <!-- 联网搜索开关 -->
              <el-switch
                v-model="enableWebSearch"
                active-text="搜索"
                size="small"
                style="margin-left: 12px"
              />

              <!-- 知识库检索开关 -->
              <el-switch
                v-model="enableRag"
                active-text="知识库"
                size="small"
                style="margin-left: 8px"
              />

              <!-- 清空对话 -->
              <el-button text type="danger" size="small" @click="clearMessages">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- 消息列表 -->
          <el-scrollbar ref="scrollbarRef" class="messages-container" @scroll="onScroll">
            <div class="messages-list">
              <!-- 加载中 -->
              <div v-if="isLoadingMessages" class="loading-messages">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>加载消息中...</span>
              </div>

              <!-- 欢迎提示 -->
              <div v-if="!isLoadingMessages && messages.length === 0" class="welcome-message">
                <el-icon :size="48" color="#dcdfe6"><ChatDotRound /></el-icon>
                <h3>你好！我是财务智能助手</h3>
                <p>我可以帮你处理财务问题、生成凭证、分析报表等</p>
                <div class="suggestion-chips">
                  <el-tag
                    v-for="tip in suggestionTips"
                    :key="tip"
                    class="suggestion-chip"
                    @click="sendMessage(tip)"
                  >
                    {{ tip }}
                  </el-tag>
                </div>
              </div>

              <!-- 消息气泡 -->
              <div
                v-for="(msg, index) in messages"
                :key="index"
                class="message-item"
                :class="msg.role"
              >
                <!-- AI 头像 -->
                <div v-if="msg.role === 'assistant'" class="message-avatar">
                  <el-avatar :size="36" style="background-color: #67c23a">
                    <el-icon><Cpu /></el-icon>
                  </el-avatar>
                </div>

                <!-- 消息内容 -->
                <div class="message-bubble" :class="msg.role">
                  <div class="message-text" v-html="renderMarkdown(msg.content)" />
                  <div class="message-time">{{ msg.time }}</div>
                  <!-- 复制按钮 -->
                  <el-button
                    v-if="msg.role === 'assistant' && msg.content"
                    text
                    size="small"
                    class="copy-btn"
                    @click="copyMessage(msg.content)"
                  >
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
                </div>

                <!-- 用户头像 -->
                <div v-if="msg.role === 'user'" class="message-avatar">
                  <el-avatar :size="36" style="background-color: #409eff">
                    {{ userInitial }}
                  </el-avatar>
                </div>
              </div>

              <!-- 加载指示器 -->
              <div v-if="isStreaming" class="message-item assistant">
                <div class="message-avatar">
                  <el-avatar :size="36" style="background-color: #67c23a">
                    <el-icon><Cpu /></el-icon>
                  </el-avatar>
                </div>
                <div class="message-bubble assistant">
                  <span class="typing-indicator">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                  </span>
                </div>
              </div>
            </div>
          </el-scrollbar>

          <!-- 输入区域 -->
          <div class="input-area">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              placeholder="输入您的问题，按 Enter 发送，Shift+Enter 换行..."
              :disabled="isStreaming"
              @keydown.enter="handleKeyDown"
            />
            <div class="input-actions">
              <span class="input-hint">Enter 发送 / Shift+Enter 换行</span>
              <el-button
                type="primary"
                :disabled="!inputMessage.trim() || isStreaming"
                :loading="isStreaming"
                @click="sendMessage()"
              >
                <el-icon><Promotion /></el-icon>
                <span>发送</span>
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, watch, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useModelStore } from '@/stores/model'
import { chatStream, getAvailableModels } from '@/api/chat'
import { getConversations, createConversation, getConversation, deleteConversation, addMessage } from '@/api/conversation'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import request from '@/api/request'

const authStore = useAuthStore()
const modelStore = useModelStore()

// ===== 对话管理 =====

// 对话列表
const conversations = ref([])

// 当前对话 ID
const currentConversationId = ref(null)

// 消息列表
const messages = ref([])

// 是否正在加载历史消息
const isLoadingMessages = ref(false)

// 是否正在流式输出
const isStreaming = ref(false)

// 当前流式请求控制器
let currentStreamController = null

// 队列管理器引用
const scrollbarRef = ref(null)

// ===== 输入状态 =====

// 输入消息
const inputMessage = ref('')

// 模型选择（从 modelStore 初始化，保持与顶栏 ModelSelector 同步）
const chatModel = ref('auto')

// 联网搜索开关（从 modelStore 初始化）
const enableWebSearch = ref(false)

// 知识库检索开关
const enableRag = ref(true)

// ===== 记忆管理 =====

// 记忆数量
const memoryCount = ref(0)

// 记忆列表（用于 tooltip）
const memoryList = ref([])

// 记忆 tooltip 内容
const memoryTooltipContent = computed(() => {
  if (memoryList.value.length === 0) return ''
  const items = memoryList.value.slice(0, 5).map(m =>
    `[${m.memory_type}] ${m.memory_key}: ${m.memory_value}`
  )
  let text = items.join('\n')
  if (memoryList.value.length > 5) {
    text += `\n... 还有 ${memoryList.value.length - 5} 条记忆`
  }
  return text
})

// 本地模型列表
const localModels = ref([])

// 外部模型分组: [{ provider: 'DeepSeek', provider_code: 'deepseek', models: [{ name: 'deepseek-chat' }, ...] }]
const externalModelGroups = ref([])

// ===== 计算属性 =====

// 用户名首字母
const userInitial = computed(() => {
  const name = authStore.userInfo?.real_name || authStore.userInfo?.username || 'U'
  return name.charAt(0).toUpperCase()
})

// 当前对话标题
const currentConversationTitle = computed(() => {
  const conv = conversations.value.find(c => c.id === currentConversationId.value)
  return conv?.title || '新对话'
})

// 建议提示
const suggestionTips = [
  '帮我录入一笔凭证：销售商品收入 10000 元',
  '查看本月资产负债表',
  '如何计算增值税？',
  '分析本月利润情况'
]

// ===== 初始化 =====

onMounted(async () => {
  await loadModels()
  await loadConversations()
  await loadMemories()
  // 校验当前模型：如果 localStorage 缓存了 embedding 模型（如 qwen3-embedding），重置为 auto
  validateModelSelection()
})

/**
 * 加载对话列表
 */
async function loadConversations() {
  try {
    const list = await getConversations()
    conversations.value = list
    if (list.length > 0) {
      // 自动选择最近一次对话
      await selectConversation(list[0].id)
    } else {
      // 没有对话，自动创建
      await _createAndSelectConversation()
    }
  } catch (error) {
    console.error('加载对话列表失败:', error)
    // 加载失败，创建本地对话兜底
    _createLocalConversation()
  }
}

/**
 * 创建对话并选中（后端+本地）
 */
async function _createAndSelectConversation(title = '新对话') {
  try {
    const conv = await createConversation(title)
    conversations.value.unshift(conv)
    currentConversationId.value = conv.id
    messages.value = []
  } catch (error) {
    console.error('创建对话失败:', error)
    _createLocalConversation()
  }
}

/**
 * 创建本地对话（后端不可用时的兜底）
 */
function _createLocalConversation() {
  const id = Date.now()
  conversations.value.unshift({
    id,
    title: '新对话',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    message_count: 0
  })
  currentConversationId.value = id
  messages.value = []
}

/**
 * 加载可用模型列表（本地 + 外部 API）
 */
async function loadModels() {
  try {
    const res = await getAvailableModels()
    // 本地模型（前端二次过滤，排除 embedding 模型）
    const embedKeywords = ['embed', 'bge', 'nomic', 'stella', 'e5', 'gte', 'clip', 'blip', 'vision', 'ocr', 'paraphrase', 'all-minilm', 'all-mpnet', 'multilingual']
    localModels.value = (res.local || [])
      .filter(m => !embedKeywords.some(kw => m.name.toLowerCase().includes(kw)))
      .map(m => ({ name: m.name }))
    // 外部模型按提供商分组
    const groups = {}
    for (const m of (res.external || [])) {
      const key = m.provider_code
      if (!groups[key]) {
        groups[key] = { provider: m.provider, provider_code: m.provider_code, models: [] }
      }
      groups[key].models.push({ name: m.name })
    }
    externalModelGroups.value = Object.values(groups)
  } catch (error) {
    console.error('加载模型列表失败:', error)
  }
}

/**
 * 加载 AI 记忆
 */
async function loadMemories() {
  try {
    const res = await request.get('/memories')
    const data = res.data
    memoryList.value = Array.isArray(data) ? data : []
    memoryCount.value = memoryList.value.length
  } catch (error) {
    console.error('加载记忆失败:', error)
  }
}

/**
 * 清除所有 AI 记忆
 */
async function handleClearMemories() {
  try {
    await request.delete('/memories/clear')
    memoryList.value = []
    memoryCount.value = 0
    ElMessage.success('AI 记忆已清除')
  } catch (error) {
    // 如果 /memories/clear 不存在，尝试逐条删除
    try {
      const promises = memoryList.value.map(m => request.delete(`/memories/${m.id}`))
      await Promise.allSettled(promises)
      memoryList.value = []
      memoryCount.value = 0
      ElMessage.success('AI 记忆已清除')
    } catch (e) {
      console.error('清除记忆失败:', e)
      ElMessage.error('清除失败')
    }
  }
}

/**
 * 解析模型选择值，构建后端请求参数
 */
function buildModelConfig(value) {
  if (value === 'auto') {
    return { model_preference: 'auto' }
  }
  if (value === 'ollama') {
    // 如果用户设了默认 Ollama 模型，注入具体模型名
    const result = { model_preference: 'ollama' }
    if (modelStore.defaultOllamaModel) {
      result.model_name = modelStore.defaultOllamaModel
    }
    return result
  }
  if (value === 'external') {
    // 如果用户设了默认外部模型，注入具体提供商和模型名
    const result = { model_preference: 'external' }
    if (modelStore.defaultExternalModel && modelStore.defaultExternalProvider) {
      result.provider_code = modelStore.defaultExternalProvider
      result.model_name = modelStore.defaultExternalModel
    }
    return result
  }
  if (value.startsWith('ollama:')) {
    return { model_preference: 'ollama', model_name: value.slice(7) }
  }
  const colonIdx = value.indexOf(':')
  if (colonIdx > 0) {
    return {
      model_preference: 'external',
      provider_code: value.slice(0, colonIdx),
      model_name: value.slice(colonIdx + 1)
    }
  }
  return { model_preference: 'auto' }
}

/**
 * 校验当前模型选择：如果缓存了 embedding 模型，重置为 auto
 */
function validateModelSelection() {
  const embedKeywords = ['embed', 'bge', 'nomic', 'stella', 'e5', 'gte', 'clip', 'blip', 'vision', 'ocr', 'paraphrase', 'all-minilm', 'all-mpnet', 'multilingual']
  const config = buildModelConfig(chatModel.value)
  const modelName = (config.model_name || '').toLowerCase()
  if (modelName && embedKeywords.some(kw => modelName.includes(kw))) {
    console.warn(`检测到 embedding 模型 "${config.model_name}" 被选为聊天模型，已自动重置为"自动选择"`)
    chatModel.value = 'auto'
    modelStore.setMode('auto')
    modelStore.setModel('')
    modelStore.setProvider('')
  }
}

/**
 * 从 modelStore 构建 chatModel 选择值
 *
 * 优先级：先看 currentMode 决定行为，再取 currentModel 拼具体值
 * - auto → 始终返回 'auto'（忽略 currentModel）
 * - ollama + currentModel → 'ollama:model_name'
 * - ollama (无 currentModel) → 'ollama'
 * - external + currentModel + providerCode → 'provider:model_name'
 * - external (缺 currentModel/providerCode) → 'external'
 * - 其他 → 'auto'
 */
function buildChatModelFromStore() {
  const mode = modelStore.currentMode || 'auto'
  if (mode === 'ollama' && modelStore.currentModel) {
    return 'ollama:' + modelStore.currentModel
  }
  if (mode === 'external' && modelStore.currentModel && modelStore.providerCode) {
    return modelStore.providerCode + ':' + modelStore.currentModel
  }
  // auto / ollama(默认) / external(缺参数) → 直接返回 mode
  return mode
}

// 监听 chatModel 变化，同步到 modelStore
watch(chatModel, (newVal) => {
  const config = buildModelConfig(newVal)
  modelStore.setMode(config.model_preference || 'auto')
  // 始终清除旧值，避免残留：无 model_name 时设为空字符串
  modelStore.setModel(config.model_name || '')
  modelStore.setProvider(config.provider_code || '')
})

// 监听 enableWebSearch 变化
watch(enableWebSearch, (newVal) => {
  if (modelStore.enableWebSearch !== newVal) {
    modelStore.toggleWebSearch()
  }
})

// 监听 modelStore 模式变化
let _syncingFromStore = false
watch(() => modelStore.currentMode, (newMode) => {
  if (_syncingFromStore) return
  _syncingFromStore = true
  chatModel.value = buildChatModelFromStore()
  nextTick(() => { _syncingFromStore = false })
})

// 初始化：从 modelStore 同步
chatModel.value = buildChatModelFromStore()
enableWebSearch.value = modelStore.enableWebSearch

// ===== 对话管理方法 =====

/**
 * 新建对话
 */
async function newConversation() {
  // 停止当前流式输出
  if (currentStreamController) {
    currentStreamController.cancel()
    isStreaming.value = false
  }
  await _createAndSelectConversation()
}

/**
 * 选择对话
 */
async function selectConversation(id) {
  if (id === currentConversationId.value) return

  // 停止当前流式输出
  if (currentStreamController) {
    currentStreamController.cancel()
    isStreaming.value = false
  }

  currentConversationId.value = id
  isLoadingMessages.value = true
  messages.value = []

  try {
    const detail = await getConversation(id)
    // 将后端消息格式转换为前端格式
    messages.value = (detail.messages || []).map(m => ({
      role: m.role,
      content: m.content,
      time: formatTime(m.created_at)
    }))
  } catch (error) {
    console.error('加载对话消息失败:', error)
    messages.value = []
  } finally {
    isLoadingMessages.value = false
    await nextTick()
    scrollToBottom()
  }
}

/**
 * 删除对话
 */
async function handleDeleteConversation(id) {
  try {
    await ElMessageBox.confirm('确定要删除这个对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  try {
    await deleteConversation(id)
    conversations.value = conversations.value.filter(c => c.id !== id)

    if (id === currentConversationId.value) {
      // 删除的是当前对话，切换到第一个或新建
      if (conversations.value.length > 0) {
        await selectConversation(conversations.value[0].id)
      } else {
        await _createAndSelectConversation()
      }
    }
    ElMessage.success('对话已删除')
  } catch (error) {
    console.error('删除对话失败:', error)
    ElMessage.error('删除失败')
  }
}

/**
 * 清空当前对话消息
 */
async function clearMessages() {
  try {
    await ElMessageBox.confirm('确定要清空当前对话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  // 删除旧对话并创建新对话
  const oldId = currentConversationId.value
  try {
    await deleteConversation(oldId)
    conversations.value = conversations.value.filter(c => c.id !== oldId)
  } catch {
    // 删除失败不阻塞
  }
  await _createAndSelectConversation()
  ElMessage.success('对话已清空')
}

// ===== 消息发送 =====

/**
 * 处理键盘事件
 */
function handleKeyDown(event) {
  if (!event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

/**
 * 发送消息
 */
async function sendMessage(presetMessage) {
  const text = presetMessage || inputMessage.value.trim()
  if (!text || isStreaming.value) return

  // 构建历史消息
  const history = messages.value
    .filter(m => m.content && (m.role === 'user' || m.role === 'assistant'))
    .map(m => ({ role: m.role, content: m.content }))

  // 添加用户消息到界面
  const userMsg = {
    role: 'user',
    content: text,
    time: getCurrentTime()
  }
  messages.value.push(userMsg)

  // 清空输入框
  if (!presetMessage) {
    inputMessage.value = ''
  }

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  // 持久化用户消息到后端
  const convId = currentConversationId.value
  _saveMessageSilent(convId, 'user', text)

  // 添加 AI 占位消息
  const aiMsg = {
    role: 'assistant',
    content: '',
    time: getCurrentTime()
  }
  messages.value.push(aiMsg)
  const aiMsgIndex = messages.value.length - 1

  // 开始流式请求
  isStreaming.value = true

  // 构建模型配置
  const modelConfig = buildModelConfig(chatModel.value)
  modelConfig.enable_web_search = enableWebSearch.value
  modelConfig.enable_rag = enableRag.value

  currentStreamController = chatStream(text, modelConfig, {
    onToken(token) {
      messages.value[aiMsgIndex].content += token
      requestAnimationFrame(() => {
        scrollToBottom()
      })
    },
    onDone(fullResponse) {
      isStreaming.value = false
      currentStreamController = null
      messages.value[aiMsgIndex].time = getCurrentTime()
      if (!messages.value[aiMsgIndex].content) {
        messages.value[aiMsgIndex].content = '抱歉，我暂时无法回答这个问题，请稍后再试。'
      }
      // 持久化 AI 回复到后端
      _saveMessageSilent(convId, 'assistant', messages.value[aiMsgIndex].content)
      // 刷新对话列表（更新标题和时间）
      _refreshConversationList()
    },
    onError(error) {
      isStreaming.value = false
      currentStreamController = null
      messages.value[aiMsgIndex].content = `请求失败：${error.message}`
      _saveMessageSilent(convId, 'assistant', messages.value[aiMsgIndex].content)
    }
  }, history)
}

/**
 * 静默保存消息到后端（不阻塞 UI）
 */
async function _saveMessageSilent(convId, role, content) {
  try {
    await addMessage(convId, role, content)
  } catch {
    // 保存失败不阻塞用户操作
  }
}

/**
 * 刷新对话列表
 */
async function _refreshConversationList() {
  try {
    const list = await getConversations()
    conversations.value = list
  } catch {
    // 静默失败
  }
}

// ===== 工具方法 =====

function scrollToBottom() {
  const container = scrollbarRef.value?.wrapRef
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

function onScroll() {}

function getCurrentTime() {
  const now = new Date()
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
}

function formatTime(date) {
  if (!date) return ''
  const d = new Date(date)
  const now = new Date()
  const diff = now - d

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch {
    return text
  }
}

async function copyMessage(content) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}
</script>

<style scoped>
.chat-assistant {
  height: calc(100vh - 100px);
  max-height: 800px;
}

.chat-assistant .el-row {
  height: 100%;
}

/* 左侧对话列表 */
.chat-sidebar-col {
  height: 100%;
}

.chat-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-sidebar :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conversation-list {
  padding: 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 4px;
}

.conversation-item:hover {
  background-color: #f5f7fa;
}

.conversation-item.active {
  background-color: #ecf5ff;
  border-left: 3px solid #409eff;
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-time {
  font-size: 12px;
  color: #c0c4cc;
}

.conv-delete-btn {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
  margin-left: 4px;
}

.conversation-item:hover .conv-delete-btn {
  opacity: 1;
}

/* 右侧对话主区域 */
.chat-main-col {
  height: 100%;
}

.chat-main {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-main :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

/* 对话标题栏 */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.memory-indicator {
  cursor: help;
  transition: all 0.2s;
}

.memory-indicator:hover {
  transform: scale(1.05);
}

.chat-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 消息容器 */
.messages-container {
  flex: 1;
  padding: 16px;
  background-color: #fafafa;
}

.messages-list {
  max-width: 800px;
  margin: 0 auto;
}

/* 加载中 */
.loading-messages {
  text-align: center;
  padding: 40px;
  color: #909399;
}

.loading-messages span {
  margin-left: 8px;
}

/* 欢迎消息 */
.welcome-message {
  text-align: center;
  padding: 60px 20px;
}

.welcome-message h3 {
  font-size: 20px;
  color: #303133;
  margin: 16px 0 8px;
}

.welcome-message p {
  font-size: 14px;
  color: #909399;
  margin-bottom: 24px;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.suggestion-chip {
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-chip:hover {
  background-color: #409eff;
  color: #fff;
  border-color: #409eff;
}

/* 消息项 */
.message-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 20px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

/* 消息气泡 */
.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  position: relative;
}

.message-bubble.user {
  background: linear-gradient(135deg, #409eff, #66b1ff);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message-bubble.assistant {
  background-color: #fff;
  border: 1px solid #e4e7ed;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.message-text {
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.message-text :deep(p) {
  margin-bottom: 8px;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(code) {
  background-color: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
  color: #e6a23c;
}

.message-text :deep(pre) {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-text :deep(pre code) {
  background: none;
  padding: 0;
  color: #303133;
}

.message-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.message-text :deep(th),
.message-text :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 6px 12px;
  text-align: left;
}

.message-text :deep(th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
  text-align: right;
}

.message-bubble.user .message-time {
  color: rgba(255, 255, 255, 0.7);
}

.copy-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-bubble:hover .copy-btn {
  opacity: 1;
}

/* 打字动画指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #c0c4cc;
  animation: typing 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }
.dot:nth-child(3) { animation-delay: 0s; }

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 输入区域 */
.input-area {
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  background-color: #fff;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.input-hint {
  font-size: 12px;
  color: #c0c4cc;
}

/* 响应式 */
@media (max-width: 768px) {
  .chat-sidebar-col {
    display: none;
  }

  .chat-main-col {
    width: 100%;
  }

  .message-bubble {
    max-width: 85%;
  }
}
</style>