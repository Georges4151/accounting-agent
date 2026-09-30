import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  batchSubmitVouchers,
  batchReviewVouchers,
  batchRejectVouchers,
  batchApproveVouchers,
  batchPostVouchers,
  batchDeleteVouchers,
  getBatchStatus,
} from '@/api/voucher'

/**
 * 批量操作组合式函数
 * 管理批量选择状态和批量操作逻辑
 */
export function useBatchOperations() {
  // ===== 状态 =====

  const selectedIds = ref([])
  const selectedRows = ref([])
  const batchLoading = ref(false)
  const batchProgress = ref({ current: 0, total: 0 })
  const batchResult = ref(null)
  const batchPreview = ref(null)

  // ===== 计算属性 =====

  /** 是否有选中的项目 */
  const hasSelection = computed(() => selectedIds.value.length > 0)

  /** 选中数量 */
  const selectedCount = computed(() => selectedIds.value.length)

  /** 是否可以提交审核（所有选中项都是草稿状态） */
  const canSubmit = computed(() => {
    return selectedRows.value.length > 0 && selectedRows.value.every(r => r.status === 'draft')
  })

  /** 是否可以审核通过（所有选中项都是已提交状态） */
  const canReview = computed(() => {
    return selectedRows.value.length > 0 && selectedRows.value.every(r => r.status === 'submitted')
  })

  /** 是否可以驳回（所有选中项都是已提交状态） */
  const canReject = computed(() => {
    return selectedRows.value.length > 0 && selectedRows.value.every(r => r.status === 'submitted')
  })

  /** 是否可以审批（所有选中项都是已审核状态） */
  const canApprove = computed(() => {
    return selectedRows.value.length > 0 && selectedRows.value.every(r => r.status === 'reviewed')
  })

  /** 是否可以过账（所有选中项都是已审批状态） */
  const canPost = computed(() => {
    return selectedRows.value.length > 0 && selectedRows.value.every(r => r.status === 'approved')
  })

  /** 是否可以删除（所有选中项都是草稿状态） */
  const canDelete = computed(() => {
    return selectedRows.value.length > 0 && selectedRows.value.every(r => r.status === 'draft')
  })

  

  /** 选中项的凭证号列表 */
  const selectedVoucherNos = computed(() => {
    return selectedRows.value.map(r => r.voucher_no)
  })

  /** 草稿状态数量 */
  const draftCount = computed(() => {
    return selectedRows.value.filter(r => r.status === 'draft').length
  })

  /** 已提交状态数量 */
  const submittedCount = computed(() => {
    return selectedRows.value.filter(r => r.status === 'submitted').length
  })

  /** 已审核状态数量 */
  const reviewedCount = computed(() => {
    return selectedRows.value.filter(r => r.status === 'reviewed').length
  })

  /** 其他状态数量（不可操作） */
  const otherStatusCount = computed(() => {
    return selectedRows.value.filter(r => r.status !== 'draft' && r.status !== 'submitted' && r.status !== 'reviewed').length
  })

  // ===== 操作方法 =====

  /**
   * 处理表格选择变化
   */
  function handleSelectionChange(selection) {
    selectedRows.value = selection
    selectedIds.value = selection.map(item => item.id)
  }

  /**
   * 清除所有选择
   */
  function clearSelection() {
    selectedIds.value = []
    selectedRows.value = []
    batchResult.value = null
    batchPreview.value = null
  }

  /**
   * 获取批量操作状态预览
   */
  async function fetchBatchPreview() {
    if (selectedIds.value.length === 0) return null
    try {
      const res = await getBatchStatus(selectedIds.value)
      batchPreview.value = res.data
      return res.data
    } catch {
      batchPreview.value = null
      return null
    }
  }

  /**
   * 显示批量操作确认对话框（含预览信息）
   * @param {string} action - 操作名称
   * @param {number} eligibleCount - 符合条件的数量
   * @param {number} totalCount - 总数量
   * @param {string} warningText - 额外的警告文本
   */
  async function showBatchConfirm(action, eligibleCount, totalCount, warningText = '') {
    if (totalCount === 0) {
      ElMessage.warning('请先选择凭证')
      return false
    }

    const ineligibleCount = totalCount - eligibleCount
    let message = ''
    if (eligibleCount === 0) {
      message = `选中的 ${totalCount} 条凭证均不符合 ${action} 条件，无法执行操作。`
    } else if (ineligibleCount > 0) {
      message = `确认要对 ${eligibleCount} 条符合条件的凭证执行【${action}】吗？`
      if (warningText) {
        message += `\n${warningText}`
      }
      message += `\n\n注意：${ineligibleCount} 条凭证因状态不符合将被跳过。`
    } else {
      message = `确认要对 ${eligibleCount} 条凭证执行【${action}】吗？`
      if (warningText) {
        message += `\n${warningText}`
      }
    }

    if (eligibleCount === 0) {
      ElMessage.warning(message)
      return false
    }

    try {
      await ElMessageBox.confirm(
        message,
        `批量${action}`,
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
          dangerouslyUseHTMLString: false,
        }
      )
      return true
    } catch {
      return false
    }
  }

  /**
   * 显示批量操作结果摘要对话框
   * @param {object} result - 操作结果 {action, successCount, failedCount, results}
   */
  function showBatchResultDialog(result) {
    const { action, successCount, failedCount, results } = result
    const failures = (results || []).filter(r => r.status === 'failed')

    let message = ''
    if (failedCount === 0) {
      message = `<p style="color: #67c23a; font-size: 16px; margin-bottom: 8px;">
        全部操作成功！共处理 ${successCount} 条凭证。
      </p>`
    } else if (successCount === 0) {
      message = `<p style="color: #f56c6c; font-size: 16px; margin-bottom: 8px;">
        全部操作失败！共 ${failedCount} 条凭证处理失败。
      </p>`
    } else {
      message = `<p style="color: #e6a23c; font-size: 16px; margin-bottom: 8px;">
        部分操作完成：成功 ${successCount} 条，失败 ${failedCount} 条。
      </p>`
    }

    if (failures.length > 0) {
      message += '<div style="margin-top: 12px; max-height: 200px; overflow-y: auto;">'
      message += '<p style="font-weight: bold; margin-bottom: 4px;">失败详情：</p>'
      failures.forEach(f => {
        message += `<p style="font-size: 13px; color: #909399; margin: 2px 0;">
          • 凭证ID: ${f.id} - ${f.error || '未知错误'}
        </p>`
      })
      message += '</div>'
    }

    ElMessageBox.alert(message, `批量${action} - 结果`, {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '知道了',
      type: failedCount === 0 ? 'success' : failedCount > 0 && successCount > 0 ? 'warning' : 'error',
    })
  }

  /**
   * 显示操作结果
   */
  function showBatchResult(actionName, res) {
    const data = res.data || res
    const success = data.success_count || 0
    const failed = data.failed_count || 0
    if (failed === 0) {
      ElMessage.success(`${actionName}完成：成功 ${success} 条`)
    } else {
      ElMessage.warning(`${actionName}完成：成功 ${success} 条，失败 ${failed} 条`)
    }
    batchResult.value = {
      action: actionName,
      successCount: success,
      failedCount: failed,
      results: data.results || [],
    }
    return { success, failed }
  }

  /**
   * 批量提交审核
   */
  async function batchSubmit() {
    if (selectedIds.value.length === 0) return
    const total = selectedRows.value.length
    const eligible = draftCount.value

    const confirmed = await showBatchConfirm(
      '提交审核',
      eligible,
      total,
      eligible < total ? '仅草稿状态的凭证可提交审核。' : ''
    )
    if (!confirmed) return

    batchLoading.value = true
    try {
      const res = await batchSubmitVouchers(selectedIds.value)
      showBatchResult('批量提交', res)
      clearSelection()
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '批量提交失败')
      return false
    } finally {
      batchLoading.value = false
    }
  }

  /**
   * 批量审核通过
   */
  async function batchReview() {
    if (selectedIds.value.length === 0) return
    const total = selectedRows.value.length
    const eligible = submittedCount.value

    const confirmed = await showBatchConfirm(
      '审核通过',
      eligible,
      total,
      eligible < total ? '仅已提交状态的凭证可审核通过。' : ''
    )
    if (!confirmed) return

    batchLoading.value = true
    try {
      const res = await batchReviewVouchers(selectedIds.value)
      showBatchResult('批量审核', res)
      clearSelection()
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '批量审核失败')
      return false
    } finally {
      batchLoading.value = false
    }
  }

  /**
   * 批量驳回
   */
  async function batchReject() {
    if (selectedIds.value.length === 0) return
    const total = selectedRows.value.length
    const eligible = submittedCount.value

    const confirmed = await showBatchConfirm(
      '驳回',
      eligible,
      total,
      eligible < total ? '仅已提交状态的凭证可驳回。' : ''
    )
    if (!confirmed) return

    batchLoading.value = true
    try {
      const res = await batchRejectVouchers(selectedIds.value)
      showBatchResult('批量驳回', res)
      clearSelection()
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '批量驳回失败')
      return false
    } finally {
      batchLoading.value = false
    }
  }

  /**
   * 批量审批通过
   */
  async function batchApprove() {
    if (selectedIds.value.length === 0) return
    const total = selectedRows.value.length
    const eligible = reviewedCount.value

    const confirmed = await showBatchConfirm(
      '审批通过',
      eligible,
      total,
      eligible < total ? '仅已审核状态的凭证可审批通过。' : ''
    )
    if (!confirmed) return

    batchLoading.value = true
    try {
      const res = await batchApproveVouchers(selectedIds.value)
      showBatchResult('批量审批', res)
      clearSelection()
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '批量审批失败')
      return false
    } finally {
      batchLoading.value = false
    }
  }

  /**
   * 批量过账
   */
  async function batchPost() {
    if (selectedIds.value.length === 0) return
    const total = selectedRows.value.length
    const eligible = selectedRows.value.filter(r => r.status === 'approved').length

    const confirmed = await showBatchConfirm(
      '过账',
      eligible,
      total,
      eligible < total ? '仅已审批状态的凭证可过账。' : ''
    )
    if (!confirmed) return

    batchLoading.value = true
    try {
      const res = await batchPostVouchers(selectedIds.value)
      showBatchResult('批量过账', res)
      clearSelection()
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '批量过账失败')
      return false
    } finally {
      batchLoading.value = false
    }
  }

  /**
   * 批量删除
   */
  async function batchDelete() {
    if (selectedIds.value.length === 0) return
    const total = selectedRows.value.length
    const eligible = draftCount.value

    const confirmed = await showBatchConfirm(
      '删除',
      eligible,
      total,
      '此操作不可恢复。' + (eligible < total ? '仅草稿状态的凭证可删除。' : '')
    )
    if (!confirmed) return

    batchLoading.value = true
    try {
      const res = await batchDeleteVouchers(selectedIds.value)
      showBatchResult('批量删除', res)
      clearSelection()
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '批量删除失败')
      return false
    } finally {
      batchLoading.value = false
    }
  }

  return {
    // 状态
    selectedIds,
    selectedRows,
    batchLoading,
    batchProgress,
    batchResult,
    batchPreview,
    // 计算属性
    hasSelection,
    selectedCount,
    canSubmit,
    canReview,
    canReject,
    canApprove,
    canPost,
    canDelete,
    selectedVoucherNos,
    draftCount,
    submittedCount,
    reviewedCount,
    otherStatusCount,
    // 操作方法
    handleSelectionChange,
    clearSelection,
    fetchBatchPreview,
    showBatchConfirm,
    showBatchResultDialog,
    batchSubmit,
    batchReview,
    batchReject,
    batchApprove,
    batchPost,
    batchDelete,
  }
}