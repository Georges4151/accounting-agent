<template>
  <div class="book-switcher">
    <el-dropdown trigger="click" @command="handleSwitch" v-if="bookStore.hasBooks">
      <span class="book-info">
        <el-icon :size="16" color="#67c23a"><FolderOpened /></el-icon>
        <span class="book-name">{{ bookStore.currentBookName }}</span>
        <el-icon><ArrowDown /></el-icon>
      </span>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="book in bookStore.bookList"
            :key="book.id"
            :command="book.id"
            :class="{ 'is-active': book.id === bookStore.currentBookId }"
          >
            <div class="book-item">
              <span class="book-item-name">{{ book.name }}</span>
              <el-tag v-if="book.is_default" size="small" type="success">默认</el-tag>
              <el-tag v-if="book.status === 'archived'" size="small" type="info">已归档</el-tag>
              <el-tag size="small" type="info" class="book-code">{{ book.code }}</el-tag>
            </div>
          </el-dropdown-item>
          <el-divider style="margin: 4px 0" />
          <el-dropdown-item command="manage">
            <el-icon><Setting /></el-icon>
            <span>管理账套</span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
    <span v-else class="book-info no-book">
      <el-icon :size="16" color="#909399"><FolderOpened /></el-icon>
      <span class="book-name">无可用账套</span>
    </span>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useBookStore } from '@/stores/book'
import { ElMessage } from 'element-plus'

const router = useRouter()
const bookStore = useBookStore()

onMounted(async () => {
  await bookStore.loadBooks(true)
})

async function handleSwitch(command) {
  if (command === 'manage') {
    router.push('/settings/books')
    return
  }
  const success = await bookStore.switchBook(command)
  if (success) {
    ElMessage.success(`已切换到账套: ${bookStore.currentBookName}`)
    // 刷新当前页面以使数据更新
    window.location.reload()
  }
}
</script>

<style scoped>
.book-switcher {
  display: flex;
  align-items: center;
}

.book-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 4px;
  background-color: #f0f9eb;
  border: 1px solid #e1f3d8;
  transition: background-color 0.2s;
}

.book-info:hover {
  background-color: #e1f3d8;
}

.book-info.no-book {
  background-color: #f5f7fa;
  border-color: #e4e7ed;
  cursor: default;
}

.book-info.no-book:hover {
  background-color: #f5f7fa;
}

.book-name {
  font-size: 13px;
  color: #303133;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.book-item-name {
  font-size: 14px;
}

.book-code {
  font-size: 11px;
}

.is-active {
  background-color: #ecf5ff;
  color: #409eff;
}
</style>