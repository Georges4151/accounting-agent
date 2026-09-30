<template>
  <!-- 登录页面：居中卡片布局，蓝色渐变背景 -->
  <div class="login-container">
    <div class="login-card-wrapper">
      <el-card class="login-card" shadow="always">
        <!-- 标题区域 -->
        <div class="login-header">
          <el-icon :size="48" color="#409eff"><Money /></el-icon>
          <h1 class="login-title">企业财务智能助手</h1>
          <p class="login-subtitle">基于 AI 的智能财务管理系统</p>
        </div>

        <!-- 登录表单 -->
        <el-form
          ref="formRef"
          :model="loginForm"
          :rules="rules"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <!-- 用户名 -->
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
              clearable
            />
          </el-form-item>

          <!-- 密码 -->
          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              size="large"
              show-password
              clearable
            />
          </el-form-item>

          <!-- 登录按钮 -->
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="login-btn"
              @click="handleLogin"
            >
              {{ loading ? '登录中...' : '登 录' }}
            </el-button>
          </el-form-item>
        </el-form>

        <!-- 底部提示 -->
        <div class="login-footer">
          <span>首次使用请联系管理员获取账号</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 表单引用
const formRef = ref(null)

// 加载状态
const loading = ref(false)

// 登录表单数据
const loginForm = reactive({
  username: '',
  password: ''
})

// 表单验证规则
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在 2 到 50 个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 100, message: '密码长度至少 6 个字符', trigger: 'blur' }
  ]
}

/**
 * 处理登录
 */
async function handleLogin() {
  if (!formRef.value) return

  try {
    // 表单验证
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    await authStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')

    // 跳转到目标页面（如果有 redirect 参数）或默认工作台
    const redirect = route.query.redirect || '/dashboard'
    router.push(redirect)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a3a5c 0%, #2d6aa0 50%, #409eff 100%);
  position: relative;
  overflow: hidden;
}

/* 背景装饰圆圈 */
.login-container::before {
  content: '';
  position: absolute;
  width: 600px;
  height: 600px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.05);
  top: -200px;
  right: -100px;
}

.login-container::after {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.03);
  bottom: -100px;
  left: -50px;
}

.login-card-wrapper {
  z-index: 1;
}

.login-card {
  width: 420px;
  border-radius: 12px;
  padding: 20px;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-title {
  font-size: 24px;
  color: #303133;
  margin: 12px 0 8px;
  font-weight: 600;
}

.login-subtitle {
  font-size: 14px;
  color: #909399;
}

.login-form {
  margin-top: 20px;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  letter-spacing: 4px;
}

.login-footer {
  text-align: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

.login-footer span {
  font-size: 12px;
  color: #c0c4cc;
}
</style>