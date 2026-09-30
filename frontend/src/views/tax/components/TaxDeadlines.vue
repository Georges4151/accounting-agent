<template>
  <div class="tax-deadlines">
    <el-row :gutter="20">
      <!-- 左侧：截止提醒列表 -->
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-title-row">
              <span class="chart-title">即将到期的申报</span>
              <el-button type="primary" size="small" @click="fetchDeadlines">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>

          <el-table :data="deadlines" v-loading="loading" stripe>
            <el-table-column label="序号" type="index" width="60" />
            <el-table-column prop="tax_type" label="税种" width="120" />
            <el-table-column prop="period" label="所属期间" width="100" />
            <el-table-column label="截止日期" width="120">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.days_left <= 3 }">
                  {{ row.deadline_date }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="剩余天数" width="100" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="row.days_left <= 3 ? 'danger' : row.days_left <= 7 ? 'warning' : 'success'"
                  size="small"
                >
                  {{ row.days_left }} 天
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="税额" width="130" align="right">
              <template #default="{ row }">
                <span v-if="row.tax_amount != null">
                  {{ formatNum(row.tax_amount) }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="未缴金额" width="130" align="right">
              <template #default="{ row }">
                <span v-if="row.remaining_amount != null" class="text-danger">
                  {{ formatNum(row.remaining_amount) }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.source === 'deadline' ? 'info' : 'warning'">
                  {{ row.source === 'deadline' ? '提醒' : '记录' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!deadlines.length && !loading" description="暂无即将到期的申报" :image-size="80" />
        </el-card>
      </el-col>

      <!-- 右侧：添加提醒表单 -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span class="chart-title">添加截止提醒</span>
          </template>
          <el-form :model="addForm" label-width="100px" size="default">
            <el-form-item label="税种" required>
              <el-select v-model="addForm.tax_type" placeholder="选择税种" style="width: 100%">
                <el-option label="增值税" value="增值税" />
                <el-option label="企业所得税" value="企业所得税" />
                <el-option label="附加税" value="附加税" />
                <el-option label="印花税" value="印花税" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
            <el-form-item label="截止日期" required>
              <el-date-picker
                v-model="addForm.deadline_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="所属期间" required>
              <el-date-picker
                v-model="addForm.period"
                type="month"
                placeholder="选择月份"
                format="YYYY-MM"
                value-format="YYYY-MM"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="提前提醒">
              <el-input-number v-model="addForm.reminder_days" :min="1" :max="30" style="width: 100%" />
              <span style="margin-left: 8px; color: #909399; font-size: 12px">天</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleAdd" :loading="adding" style="width: 100%">
                添加提醒
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 逾期记录提示 -->
        <el-card shadow="hover" style="margin-top: 16px" v-if="overdueRecords.length">
          <template #header>
            <span class="chart-title" style="color: #f56c6c">
              <el-icon><WarningFilled /></el-icon> 逾期记录
            </span>
          </template>
          <div v-for="item in overdueRecords" :key="item.id" class="overdue-item">
            <el-tag type="danger" size="small">{{ item.tax_type }}</el-tag>
            <span class="overdue-period">{{ item.tax_period }}</span>
            <span class="overdue-amount">{{ formatNum(item.remaining_amount) }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTaxDeadlines, addTaxDeadline, getTaxRecords } from '@/api/tax'

const deadlines = ref([])
const loading = ref(false)
const adding = ref(false)
const overdueRecords = ref([])

const addForm = reactive({
  tax_type: '增值税',
  deadline_date: '',
  period: '',
  reminder_days: 7,
})

function formatNum(val) {
  if (val == null) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function fetchDeadlines() {
  loading.value = true
  try {
    const res = await getTaxDeadlines()
    deadlines.value = res.data.items || []
  } catch (e) {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

async function fetchOverdue() {
  try {
    const res = await getTaxRecords({ status: 'overdue', page_size: 50 })
    overdueRecords.value = res.data.items || []
  } catch (e) {
    // handled by interceptor
  }
}

async function handleAdd() {
  if (!addForm.tax_type || !addForm.deadline_date || !addForm.period) {
    ElMessage.warning('请填写完整信息')
    return
  }
  adding.value = true
  try {
    await addTaxDeadline({
      tax_type: addForm.tax_type,
      deadline_date: addForm.deadline_date,
      period: addForm.period,
      reminder_days: addForm.reminder_days,
    })
    ElMessage.success('添加成功')
    addForm.deadline_date = ''
    addForm.period = ''
    fetchDeadlines()
  } catch (e) {
    // handled by interceptor
  } finally {
    adding.value = false
  }
}

onMounted(() => {
  fetchDeadlines()
  fetchOverdue()
})
</script>

<style scoped>
.tax-deadlines {
  padding: 8px 0;
}
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chart-title {
  font-weight: 600;
  font-size: 15px;
}
.text-danger {
  color: #f56c6c;
  font-weight: 600;
}
.overdue-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.overdue-item:last-child {
  border-bottom: none;
}
.overdue-period {
  font-size: 13px;
  color: #606266;
}
.overdue-amount {
  font-weight: 600;
  color: #f56c6c;
  font-family: 'Courier New', monospace;
}
</style>