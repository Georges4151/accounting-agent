<template>
  <!-- 模型选择器：在顶栏显示当前模型和配置选项 -->
  <div class="model-selector">
    <el-dropdown trigger="click" @command="handleCommand">
      <span class="model-trigger">
        <el-icon><Cpu /></el-icon>
        <span class="model-label">{{ modelStore.modelLabel }}</span>
        <el-icon class="arrow-icon"><ArrowDown /></el-icon>
      </span>
      <template #dropdown>
        <el-dropdown-menu>
          <!-- 运行模式选择 -->
          <el-dropdown-item command="mode:auto" :class="{ active: modelStore.currentMode === 'auto' }">
            <el-icon><Switch /></el-icon>
            <span>自动（优先外部 API）</span>
          </el-dropdown-item>
          <el-dropdown-item command="mode:ollama" :class="{ active: modelStore.currentMode === 'ollama' }">
            <el-icon><Monitor /></el-icon>
            <span>本地 Ollama</span>
          </el-dropdown-item>
          <el-dropdown-item command="mode:external" :class="{ active: modelStore.currentMode === 'external' }">
            <el-icon><Connection /></el-icon>
            <span>外部 API</span>
          </el-dropdown-item>

          <el-divider style="margin: 4px 0" />

          <!-- 联网搜索开关 -->
          <div class="search-toggle-item" @click.stop>
            <el-icon><Search /></el-icon>
            <span>联网搜索</span>
            <el-switch
              :model-value="modelStore.enableWebSearch"
              @change="modelStore.toggleWebSearch()"
              size="small"
              style="margin-left: auto"
            />
          </div>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup>
import { useModelStore } from '@/stores/model'

const modelStore = useModelStore()

/**
 * 处理下拉菜单命令
 */
function handleCommand(command) {
  if (command.startsWith('mode:')) {
    const mode = command.replace('mode:', '')
    modelStore.setMode(mode)
  }
}
</script>

<style scoped>
.model-selector {
  display: flex;
  align-items: center;
}

.model-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #303133;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.model-trigger:hover {
  background-color: #f5f7fa;
}

.model-label {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow-icon {
  font-size: 12px;
  color: #909399;
}

.search-toggle-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 16px;
  font-size: 14px;
  color: #606266;
  cursor: default;
}

.active {
  color: #409eff !important;
  font-weight: 500;
}
</style>