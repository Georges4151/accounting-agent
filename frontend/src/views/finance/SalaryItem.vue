<template>
  <div class="salary-item">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>工资项目管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加项目
          </el-button>
        </div>
      </template>

      <el-alert
        title="工资项目分为收入项（基本工资、加班费、奖金等）和扣除项（社保、公积金、个税等），系统将据此自动计算实发工资"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="4" animated />
      </div>

      <el-empty v-else-if="items.length === 0" description="暂无工资项目，请添加" />

      <el-table v-else :data="items" border stripe row-key="id">
        <el-table-column label="排序" width="80" align="center">
          <template #default="{ row }">
            <el-button-group>
              <el-button
                size="small"
                :disabled="row.sort_order <= 0"
                @click="moveItem(row, -1)"
              >
                <el-icon><ArrowUp /></el-icon>
              </el-button>
              <el-button
                size="small"
                @click="moveItem(row, 1)"
              >
                <el-icon><ArrowDown /></el-icon>
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="序号" width="60" align="center" />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="item_type" label="项目类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.item_type === 'income' ? 'success' : 'danger'">
              {{ row.item_type === 'income' ? '收入项' : '扣除项' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="formula" label="计算公式" min-width="200">
          <template #default="{ row }">
            <span v-if="row.formula">{{ row.formula }}</span>
            <el-tag v-else type="info" size="small">手动录入</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑工资项目' : '添加工资项目'"
      width="520px"
      :close-on-click-modal="false"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="如: 基本工资、加班费、社保" />
        </el-form-item>
        <el-form-item label="项目类型" prop="item_type">
          <el-radio-group v-model="form.item_type">
            <el-radio value="income">收入项</el-radio>
            <el-radio value="deduction">扣除项</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="计算公式">
          <el-input
            v-model="form.formula"
            type="textarea"
            :rows="3"
            placeholder="可选，如: 基本工资 * 0.08（社保个人部分）"
          />
        </el-form-item>
        <el-form-item label="排序序号" prop="sort_order">
          <el-input-number v-model="form.sort_order" :min="0" :step="1" />
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
import { getSalaryItems, createSalaryItem, updateSalaryItem, deleteSalaryItem } from '@/api/payroll'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const items = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '',
  item_type: 'income',
  formula: '',
  sort_order: 0
})

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  item_type: [{ required: true, message: '请选择项目类型', trigger: 'change' }]
}

onMounted(() => {
  loadItems()
})

async function loadItems() {
  loading.value = true
  try {
    const res = await getSalaryItems()
    items.value = res.data.items || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载工资项目失败')
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
  form.name = row.name
  form.item_type = row.item_type
  form.formula = row.formula || ''
  form.sort_order = row.sort_order
  dialogVisible.value = true
}

function resetForm() {
  form.name = ''
  form.item_type = 'income'
  form.formula = ''
  form.sort_order = 0
  formRef.value?.resetFields()
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateSalaryItem(editId.value, {
        name: form.name,
        item_type: form.item_type,
        formula: form.formula || null,
        sort_order: form.sort_order
      })
      ElMessage.success('项目更新成功')
    } else {
      await createSalaryItem({
        name: form.name,
        item_type: form.item_type,
        formula: form.formula || null,
        sort_order: form.sort_order
      })
      ElMessage.success('项目添加成功')
    }
    dialogVisible.value = false
    await loadItems()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除工资项目 "${row.name}" 吗？`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteSalaryItem(row.id)
    ElMessage.success('删除成功')
    await loadItems()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

async function moveItem(row, direction) {
  const newOrder = row.sort_order + direction
  if (newOrder < 0) return
  try {
    await updateSalaryItem(row.id, { sort_order: newOrder })
    await loadItems()
  } catch (error) {
    ElMessage.error('排序失败')
  }
}
</script>

<style scoped>
.salary-item {
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