<template>
  <!-- 会话管理页面 -->
  <div class="session-manage">
    <!-- 页面标题 -->
    <el-card class="header-card" shadow="never">
      <div class="header-content">
        <div>
          <h2>会话管理</h2>
          <p class="header-desc">管理当前账户的活跃会话，可在所有设备上强制登出</p>
        </div>
        <el-button type="danger" @click="handleLogoutAll" :loading="loggingOut">
          <el-icon><SwitchButton /></el-icon>
          登出所有设备
        </el-button>
      </div>
    </el-card>

    <!-- 活跃会话列表 -->
    <el-card class="list-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>活跃会话</span>
          <el-button @click="loadSessions" :loading="loading" text>
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-table
        :data="sessions"
        v-loading="loading"
        border
        stripe
        style="width: 100%"
        :empty-text="'暂无会话信息'"
      >
        <el-table-column prop="device" label="设备" min-width="180">
          <template #default="{ row }">
            <div class="device-cell">
              <el-icon :size="20" color="#409eff">
                <Monitor v-if="row.is_current" />
                <Iphone v-else />
              </el-icon>
              <span>{{ row.device }}</span>
              <el-tag v-if="row.is_current" type="success" size="small" style="margin-left: 8px">
                当前设备
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP 地址" width="160" />
        <el-table-column label="登录时间" width="200">
          <template #default="{ row }">
            <span>{{ row.login_time || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最后活跃" width="200">
          <template #default="{ row }">
            <span>{{ row.last_active || row.login_time || '--' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="session-tips" v-if="sessions.length > 0">
        <el-alert
          title="安全提示"
          type="info"
          :closable="false"
          show-icon
        >
          <template #default>
            <p>如果您怀疑账户被盗用，或发现不认识的设备登录，请立即使用"登出所有设备"功能。</p>
            <p>登出后所有设备上的会话将失效，需要重新登录。</p>
          </template>
        </el-alert>
      </div>

      <el-empty
        v-if="!loading && sessions.length === 0"
        description="暂无活跃会话"
        :image-size="80"
      />
    </el-card>

    <!-- 当前账户信息 -->
    <el-card class="info-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <span>账户安全信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ authStore.userInfo?.username || '--' }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag :type="roleTagType" size="small">{{ roleLabel }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最后登录 IP">{{ authStore.userInfo?.login_ip || '--' }}</el-descriptions-item>
        <el-descriptions-item label="最后登录时间">{{ authStore.userInfo?.last_login || '--' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Monitor, Iphone } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()

// ===== 状态 =====
const loading = ref(false)
const loggingOut = ref(false)
const sessions = ref([])

// ===== 计算属性 =====
const roleLabel = computed(() => {
  const labels = { admin: '管理员', cashier: '出纳', accountant: '会计', reviewer: '审核员', viewer: '查看者' }
  return labels[authStore.userInfo?.role] || '未知'
})

const roleTagType = computed(() => {
  const types = { admin: 'danger', cashier: 'warning', accountant: 'primary', reviewer: 'warning', viewer: 'info' }
  return types[authStore.userInfo?.role] || 'info'
})

// ===== 生命周期 =====
onMounted(() => {
  loadSessions()
})

// ===== 数据加载 =====
async function loadSessions() {
  loading.value = true
  try {
    const res = await authStore.getSessions()
    sessions.value = res.sessions || []
  } catch (error) {
    ElMessage.error('加载会话列表失败')
  } finally {
    loading.value = false
  }
}

// ===== 操作 =====
async function handleLogoutAll() {
  try {
    await ElMessageBox.confirm(
      '确定要登出所有设备吗？所有设备上的会话将失效，需要重新登录。',
      '登出所有设备',
      {
        confirmButtonText: '确定登出',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    loggingOut.value = true
    await authStore.logoutAllDevices()
    ElMessage.success('所有设备已成功登出')
    router.push('/login')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  } finally {
    loggingOut.value = false
  }
}
</script>

<style scoped>
.session-manage {
  max-width: 900px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.header-content h2 {
  font-size: 20px;
  color: #303133;
  margin-bottom: 4px;
}

.header-desc {
  font-size: 13px;
  color: #909399;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.device-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-tips {
  margin-top: 16px;
}

.session-tips p {
  margin: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}
</style>