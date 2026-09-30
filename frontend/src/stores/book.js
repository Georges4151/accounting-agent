import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getBooks, switchBook as apiSwitchBook } from '@/api/book'

/**
 * 账套状态管理
 */
export const useBookStore = defineStore('book', () => {
  // ===== 状态 =====
  const currentBook = ref(null)
  const bookList = ref([])
  const loading = ref(false)

  // ===== 计算属性 =====
  const currentBookId = computed(() => currentBook.value?.id || null)
  const currentBookName = computed(() => currentBook.value?.name || '未选择账套')
  const hasBooks = computed(() => bookList.value.length > 0)

  // ===== 操作方法 =====

  /**
   * 加载账套列表
   */
  async function loadBooks(includeArchived = false) {
    loading.value = true
    try {
      const res = await getBooks({ include_archived: includeArchived })
      bookList.value = res.data.books || []

      // 如果没有当前账套，选择第一个
      if (!currentBook.value && bookList.value.length > 0) {
        currentBook.value = bookList.value[0]
      }
    } catch (error) {
      console.error('加载账套列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 切换当前账套
   */
  async function switchBook(bookId) {
    loading.value = true
    try {
      const res = await apiSwitchBook(bookId)
      currentBook.value = res.data.book
      return true
    } catch (error) {
      console.error('切换账套失败:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取当前账套ID
   */
  function getCurrentBookId() {
    return currentBook.value?.id || null
  }

  return {
    // 状态
    currentBook,
    bookList,
    loading,
    // 计算属性
    currentBookId,
    currentBookName,
    hasBooks,
    // 方法
    loadBooks,
    switchBook,
    getCurrentBookId,
  }
}, {
  persist: {
    key: 'book-store',
    storage: localStorage,
    pick: ['currentBook'],
  },
})