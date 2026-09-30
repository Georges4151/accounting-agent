<template>
  <!-- 凭证模板管理页面 -->
  <div class="voucher-template">
    <!-- 分类筛选 -->
    <div class="category-tabs">
      <el-radio-group v-model="categoryFilter" size="default" @change="loadTemplates">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="收入">收入</el-radio-button>
        <el-radio-button value="支出">支出</el-radio-button>
        <el-radio-button value="转账">转账</el-radio-button>
        <el-radio-button value="其他">其他</el-radio-button>
      </el-radio-group>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>
        新建模板
      </el-button>
    </div>

    <!-- 模板卡片列表 -->
    <el-empty v-if="!loading && templates.length === 0" description="暂无模板，点击上方按钮创建" />
    <div v-else v-loading="loading" class="template-grid">
      <el-card
        v-for="tpl in templates"
        :key="tpl.id"
        class="template-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ tpl.name }}</span>
            <el-tag size="small" :type="getCategoryType(tpl.category)">
              {{ tpl.category }}
            </el-tag>
          </div>
        </template>

        <div class="card-body">
          <p class="card-desc">{{ tpl.description || '暂无描述' }}</p>
          <div class="card-meta">
            <span class="meta-item">
              <el-icon><Document /></el-icon>
              {{ tpl.item_count }} 条分录
            </span>
            <span class="meta-item" v-if="tpl.is_default">
              <el-tag size="small" type="success">系统默认</el-tag>
            </span>
          </div>
        </div>

        <div class="card-footer">
          <el-button type="primary" size="small" @click="openApplyDialog(tpl)">
            <el-icon><Select /></el-icon>
            使用模板
          </el-button>
          <el-button size="small" @click="openEditDialog(tpl)">
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
          <el-popconfirm
            title="确定要删除此模板吗？"
            confirm-button-text="确定"
            cancel-button-text="取消"
            @confirm="handleDelete(tpl.id)"
          >
            <template #reference>
              <el-button type="danger" size="small" :disabled="tpl.is_default">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </el-card>
    </div>

    <!-- 创建/编辑模板对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑模板' : '新建模板'"
      width="800px"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form :model="form" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模板名称" required>
              <el-input v-model="form.name" placeholder="如：采购付款" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类" required>
              <el-select v-model="form.category" style="width: 100%">
                <el-option label="收入" value="收入" />
                <el-option label="支出" value="支出" />
                <el-option label="转账" value="转账" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="模板用途描述" />
        </el-form-item>

        <!-- 分录列表 -->
        <el-divider content-position="left">模板分录</el-divider>
        <el-table :data="form.items" border stripe size="small">
          <el-table-column label="科目代码" width="160">
            <template #default="{ row, $index }">
              <el-select
                v-model="row.account_code"
                filterable
                placeholder="选择科目"
                style="width: 100%"
                @change="(val) => onItemAccountChange($index, val)"
              >
                <el-option
                  v-for="acc in accountOptions"
                  :key="acc.code"
                  :label="`${acc.code} ${acc.name}`"
                  :value="acc.code"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="科目名称" width="130">
            <template #default="{ row }">
              <span>{{ row.account_name || '--' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="借方金额" width="140">
            <template #default="{ row }">
              <el-input-number
                v-model="row.debit_amount"
                :min="0"
                :precision="2"
                :controls="false"
                placeholder="0.00"
                style="width: 110px"
              />
            </template>
          </el-table-column>
          <el-table-column label="贷方金额" width="140">
            <template #default="{ row }">
              <el-input-number
                v-model="row.credit_amount"
                :min="0"
                :precision="2"
                :controls="false"
                placeholder="0.00"
                style="width: 110px"
              />
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.description" placeholder="分录摘要" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70" fixed="right">
            <template #default="{ $index }">
              <el-button
                text
                type="danger"
                size="small"
                :disabled="form.items.length <= 1"
                @click="removeItem($index)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 8px">
          <el-button type="primary" text @click="addItem">
            <el-icon><Plus /></el-icon>
            添加分录
          </el-button>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 使用模板对话框 -->
    <el-dialog
      v-model="applyDialogVisible"
      title="使用模板创建凭证"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item label="凭证日期" required>
          <el-date-picker
            v-model="applyForm.voucher_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="凭证摘要">
          <el-input v-model="applyForm.summary" placeholder="凭证摘要" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">分录明细（可修改金额）</el-divider>
      <el-table :data="applyForm.items" border stripe size="small">
        <el-table-column label="科目代码" width="120">
          <template #default="{ row }">
            {{ row.account_code }}
          </template>
        </el-table-column>
        <el-table-column label="科目名称" width="120">
          <template #default="{ row }">
            {{ row.account_name }}
          </template>
        </el-table-column>
        <el-table-column label="借方金额" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.debit_amount"
              :min="0"
              :precision="2"
              :controls="false"
              style="width: 110px"
            />
          </template>
        </el-table-column>
        <el-table-column label="贷方金额" width="140">
          <template #default="{ row }">
            <el-input-number
              v-model="row.credit_amount"
              :min="0"
              :precision="2"
              :controls="false"
              style="width: 110px"
            />
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="140">
          <template #default="{ row }">
            {{ row.description }}
          </template>
        </el-table-column>
      </el-table>

      <div class="apply-totals">
        <span>借方合计：<strong>{{ applyTotalDebit.toFixed(2) }}</strong></span>
        <span>贷方合计：<strong>{{ applyTotalCredit.toFixed(2) }}</strong></span>
        <span :class="{ unbalanced: !applyBalanced }">
          差额：<strong>{{ Math.abs(applyTotalDebit - applyTotalCredit).toFixed(2) }}</strong>
        </span>
        <el-tag v-if="!applyBalanced" type="danger" size="small">借贷不平衡</el-tag>
        <el-tag v-else-if="applyTotalDebit > 0" type="success" size="small">借贷平衡</el-tag>
      </div>

      <template #footer>
        <el-button @click="applyDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="applying"
          :disabled="!applyBalanced || applyTotalDebit === 0"
          @click="handleApply"
        >
          创建凭证
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTemplates, getTemplate, createTemplate, updateTemplate, deleteTemplate, applyTemplate } from '@/api/voucherTemplate'
import request from '@/api/request'
import { ElMessage } from 'element-plus'

const router = useRouter()

// ===== 状态 =====

const loading = ref(false)
const saving = ref(false)
const applying = ref(false)
const templates = ref([])
const categoryFilter = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const accountOptions = ref([])

// 模板表单
const form = reactive({
  name: '',
  description: '',
  category: '其他',
  items: [
    { account_code: '', account_name: '', description: '', debit_amount: 0, credit_amount: 0, sort_order: 0 }
  ]
})

// 应用模板表单
const applyDialogVisible = ref(false)
const applyTemplateId = ref(null)
const applyForm = reactive({
  voucher_date: '',
  summary: '',
  items: []
})

// ===== 计算属性 =====

const applyTotalDebit = computed(() => {
  return applyForm.items.reduce((sum, item) => sum + (item.debit_amount || 0), 0)
})

const applyTotalCredit = computed(() => {
  return applyForm.items.reduce((sum, item) => sum + (item.credit_amount || 0), 0)
})

const applyBalanced = computed(() => {
  return Math.abs(applyTotalDebit.value - applyTotalCredit.value) < 0.01
})

// ===== 生命周期 =====

onMounted(async () => {
  await loadAccounts()
  await loadTemplates()
})

// ===== 数据加载 =====

async function loadAccounts() {
  try {
    const res = await request.get('/vouchers/accounts')
    accountOptions.value = res.data.accounts || []
  } catch (error) {
    accountOptions.value = []
  }
}

async function loadTemplates() {
  loading.value = true
  try {
    const params = {}
    if (categoryFilter.value) {
      params.category = categoryFilter.value
    }
    const res = await getTemplates(params)
    templates.value = res.data.templates || []
  } catch (error) {
    ElMessage.error('加载模板列表失败')
  } finally {
    loading.value = false
  }
}

// ===== 对话框操作 =====

function openCreateDialog() {
  isEdit.value = false
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

async function openEditDialog(tpl) {
  isEdit.value = true
  editId.value = tpl.id
  try {
    const res = await getTemplate(tpl.id)
    const data = res.data
    form.name = data.name
    form.description = data.description || ''
    form.category = data.category
    form.items = data.items.map(item => ({
      account_code: item.account_code,
      account_name: item.account_name,
      description: item.description,
      debit_amount: item.debit_amount,
      credit_amount: item.credit_amount,
      sort_order: item.sort_order || 0
    }))
    if (form.items.length === 0) {
      form.items.push({ account_code: '', account_name: '', description: '', debit_amount: 0, credit_amount: 0, sort_order: 0 })
    }
  } catch (error) {
    ElMessage.error('加载模板详情失败')
    return
  }
  dialogVisible.value = true
}

function openApplyDialog(tpl) {
  applyTemplateId.value = tpl.id
  applyForm.voucher_date = ''
  applyForm.summary = ''
  // 加载模板详情获取分录
  getTemplate(tpl.id).then(res => {
    applyForm.items = res.data.items.map(item => ({
      account_code: item.account_code,
      account_name: item.account_name,
      description: item.description,
      debit_amount: item.debit_amount,
      credit_amount: item.credit_amount
    }))
  }).catch(() => {
    ElMessage.error('加载模板详情失败')
  })
  applyDialogVisible.value = true
}

function resetForm() {
  form.name = ''
  form.description = ''
  form.category = '其他'
  form.items = [
    { account_code: '', account_name: '', description: '', debit_amount: 0, credit_amount: 0, sort_order: 0 }
  ]
}

// ===== 分录操作 =====

function addItem() {
  form.items.push({
    account_code: '',
    account_name: '',
    description: '',
    debit_amount: 0,
    credit_amount: 0,
    sort_order: form.items.length
  })
}

function removeItem(index) {
  form.items.splice(index, 1)
}

function onItemAccountChange(index, accountCode) {
  const account = accountOptions.value.find(a => a.code === accountCode)
  if (account) {
    form.items[index].account_name = account.name
  }
}

// ===== 保存 =====

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入模板名称')
    return
  }
  const validItems = form.items.filter(i => i.account_code)
  if (validItems.length === 0) {
    ElMessage.warning('请至少添加一条分录')
    return
  }

  saving.value = true
  try {
    const data = {
      name: form.name,
      description: form.description || null,
      category: form.category,
      items: validItems.map((item, index) => ({
        account_code: item.account_code,
        account_name: item.account_name,
        description: item.description || '',
        debit_amount: item.debit_amount || 0,
        credit_amount: item.credit_amount || 0,
        sort_order: index
      }))
    }

    if (isEdit.value) {
      await updateTemplate(editId.value, data)
      ElMessage.success('模板已更新')
    } else {
      await createTemplate(data)
      ElMessage.success('模板已创建')
    }
    dialogVisible.value = false
    await loadTemplates()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// ===== 删除 =====

async function handleDelete(id) {
  try {
    await deleteTemplate(id)
    ElMessage.success('模板已删除')
    await loadTemplates()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

// ===== 应用模板 =====

async function handleApply() {
  if (!applyForm.voucher_date) {
    ElMessage.warning('请选择凭证日期')
    return
  }
  if (!applyBalanced.value) {
    ElMessage.warning('借贷不平衡，请调整金额')
    return
  }

  applying.value = true
  try {
    const data = {
      voucher_date: applyForm.voucher_date,
      summary: applyForm.summary || undefined,
      amount_overrides: applyForm.items.map(item => ({
        account_code: item.account_code,
        debit_amount: item.debit_amount,
        credit_amount: item.credit_amount
      }))
    }
    const res = await applyTemplate(applyTemplateId.value, data)
    ElMessage.success(`凭证 ${res.data.voucher_no} 已创建`)
    applyDialogVisible.value = false
    router.push(`/voucher/create?id=${res.data.id}`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建凭证失败')
  } finally {
    applying.value = false
  }
}

// ===== 工具方法 =====

function getCategoryType(category) {
  const types = { '收入': 'success', '支出': 'danger', '转账': 'warning', '其他': 'info' }
  return types[category] || 'info'
}
</script>

<style scoped>
.voucher-template {
  max-width: 1200px;
}

/* 分类筛选 */
.category-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

/* 模板卡片网格 */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.template-card {
  transition: transform 0.2s;
}

.template-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.card-body {
  min-height: 60px;
}

.card-desc {
  color: #909399;
  font-size: 13px;
  margin: 0 0 12px;
  line-height: 1.5;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #909399;
  font-size: 13px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-footer {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

/* 应用模板合计 */
.apply-totals {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  margin-top: 12px;
  padding: 10px 16px;
  background-color: #f5f7fa;
  border-radius: 6px;
  font-size: 14px;
}

.apply-totals .unbalanced {
  color: #f56c6c;
}

.apply-totals strong {
  font-family: 'Courier New', monospace;
}
</style>