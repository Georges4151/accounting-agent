<template>
  <div class="currency-list">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>币种管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加币种
          </el-button>
        </div>
      </template>

      <el-alert
        title="本位币只能有一个，设置为本位币的币种将作为系统的基准货币"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="4" animated />
      </div>

      <el-empty v-else-if="currencies.length === 0" description="暂无币种数据，请添加币种" />

      <el-table v-else :data="currencies" border stripe style="width: 100%">
        <el-table-column prop="code" label="币种代码" width="120" />
        <el-table-column prop="name" label="币种名称" width="150" />
        <el-table-column prop="symbol" label="货币符号" width="100" />
        <el-table-column prop="is_base" label="本位币" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_base" type="success" effect="dark">本位币</el-tag>
            <el-tag v-else type="info">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button
              v-if="!row.is_base"
              type="danger"
              link
              size="small"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑币种' : '添加币种'"
      width="480px"
      :close-on-click-modal="false"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="币种代码" prop="code">
          <el-input
            v-model="form.code"
            placeholder="如: CNY, USD, EUR"
            :disabled="isEdit"
            style="text-transform: uppercase"
          />
        </el-form-item>
        <el-form-item label="币种名称" prop="name">
          <el-input v-model="form.name" placeholder="如: 人民币, 美元, 欧元" />
        </el-form-item>
        <el-form-item label="货币符号" prop="symbol">
          <el-input v-model="form.symbol" placeholder="如: ¥, $" />
        </el-form-item>
        <el-form-item label="本位币" prop="is_base">
          <el-switch v-model="form.is_base" active-text="设为默认本位币" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio value="active">启用</el-radio>
            <el-radio value="inactive">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEdit ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getCurrencies, createCurrency, updateCurrency, deleteCurrency } from '@/api/currency'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const currencies = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)

const form = reactive({
  code: '',
  name: '',
  symbol: '',
  is_base: false,
  status: 'active'
})

const rules = {
  code: [{ required: true, message: '请输入币种代码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入币种名称', trigger: 'blur' }],
  symbol: [{ required: true, message: '请输入货币符号', trigger: 'blur' }]
}

onMounted(() => {
  loadCurrencies()
})

async function loadCurrencies() {
  loading.value = true
  try {
    const res = await getCurrencies()
    currencies.value = res.data.items || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载币种列表失败')
  } finally {
    loading.value = false
  }
}

function handleAdd() {
  isEdit.value = false
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row) {
  isEdit.value = true
  editId.value = row.id
  form.code = row.code
  form.name = row.name
  form.symbol = row.symbol
  form.is_base = row.is_base
  form.status = row.status
  dialogVisible.value = true
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.symbol = ''
  form.is_base = false
  form.status = 'active'
  formRef.value?.resetFields()
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateCurrency(editId.value, {
        code: form.code,
        name: form.name,
        symbol: form.symbol,
        is_base: form.is_base,
        status: form.status
      })
      ElMessage.success('币种更新成功')
    } else {
      await createCurrency({
        code: form.code,
        name: form.name,
        symbol: form.symbol,
        is_base: form.is_base,
        status: form.status
      })
      ElMessage.success('币种添加成功')
    }
    dialogVisible.value = false
    await loadCurrencies()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除币种 "${row.name}" (${row.code}) 吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteCurrency(row.id)
    ElMessage.success('删除成功')
    await loadCurrencies()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}
</script>

<style scoped>
.currency-list {
  max-width: 900px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.loading-container {
  padding: 20px 0;
}
</style>