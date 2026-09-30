<template>
  <div class="system-settings">
    <el-card shadow="never">
      <template #header>
        <span>系统设置</span>
      </template>

      <el-form label-width="200px" v-loading="loading">
        <el-form-item label="出纳复核功能">
          <el-switch
            v-model="cashierReviewEnabled"
            active-text="启用"
            inactive-text="关闭"
            @change="handleToggleCashierReview"
          />
          <div class="setting-desc">
            启用后，涉及现金/银行科目的凭证需要出纳独立复核后才能审核
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const cashierReviewEnabled = ref(true)

onMounted(async () => {
  await loadSettings()
})

async function loadSettings() {
  loading.value = true
  try {
    const res = await request.get('/settings')
    const settings = res.data || []
    const cashierSetting = settings.find(s => s.key === 'cashier_review_enabled')
    if (cashierSetting) {
      cashierReviewEnabled.value = cashierSetting.value === 'true'
    }
  } catch (error) {
    ElMessage.error('加载系统设置失败')
  } finally {
    loading.value = false
  }
}

async function handleToggleCashierReview(value) {
  try {
    await request.put('/settings/cashier_review_enabled', {
      value: value ? 'true' : 'false'
    })
    ElMessage.success(`出纳复核已${value ? '启用' : '关闭'}`)
  } catch (error) {
    // 恢复原值
    cashierReviewEnabled.value = !value
    ElMessage.error(error.response?.data?.detail || '更新设置失败')
  }
}
</script>

<style scoped>
.system-settings {
  max-width: 800px;
}

.setting-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>