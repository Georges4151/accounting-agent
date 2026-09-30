import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

/**
 * 金额脱敏组合式函数
 * 根据用户角色决定是否对金额进行脱敏显示
 */
export function useAmountMask() {
  const authStore = useAuthStore()

  /**
   * 当前用户角色是否需要脱敏
   */
  const isMasked = computed(() => {
    const role = authStore.userInfo?.role
    return role === 'viewer'
  })

  /**
   * 格式化金额（根据角色决定是否脱敏）
   * @param {number|string} amount - 金额
   * @returns {string} 格式化后的金额字符串
   */
  function formatAmount(amount) {
    if (isMasked.value) {
      return '****'
    }
    if (amount == null || amount === '' || isNaN(amount)) return '--'
    return Number(amount).toLocaleString('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })
  }

  return {
    isMasked,
    formatAmount
  }
}