<template>
  <div class="tax-calculate">
    <!-- 期间选择 -->
    <div class="toolbar">
      <el-form :inline="true" :model="form" size="default">
        <el-form-item label="所属期间">
          <el-date-picker
            v-model="form.period"
            type="month"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="calculateAll">一键计算全部税种</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 计算结果卡片 -->
    <el-row :gutter="20" v-if="results.length">
      <el-col :span="12" v-for="(item, idx) in results" :key="idx" style="margin-bottom: 20px">
        <el-card :class="['result-card', item.has_data ? '' : 'no-data']" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="tax-type-label">{{ item.tax_type }}</span>
              <el-tag :type="item.has_data ? 'success' : 'info'" size="small">
                {{ item.has_data ? '已计算' : '无数据' }}
              </el-tag>
            </div>
          </template>
          <div class="card-body" v-if="item.has_data">
            <div class="calc-line" v-if="item.tax_type === '增值税'">
              <span>销项税额</span>
              <span class="amount">{{ formatNum(item.output_tax) }}</span>
            </div>
            <div class="calc-line" v-if="item.tax_type === '增值税'">
              <span>进项税额</span>
              <span class="amount deduction">{{ formatNum(item.input_tax) }}</span>
            </div>
            <div class="calc-line" v-if="item.tax_type === '企业所得税'">
              <span>利润总额</span>
              <span class="amount">{{ formatNum(item.profit) }}</span>
            </div>
            <div class="calc-line" v-if="item.tax_type === '附加税' && item.breakdown">
              <span>城建税 (7%)</span>
              <span class="amount">{{ formatNum(item.breakdown['城建税(7%)']) }}</span>
            </div>
            <div class="calc-line" v-if="item.tax_type === '附加税' && item.breakdown">
              <span>教育费附加 (3%)</span>
              <span class="amount">{{ formatNum(item.breakdown['教育费附加(3%)']) }}</span>
            </div>
            <div class="calc-line" v-if="item.tax_type === '附加税' && item.breakdown">
              <span>地方教育附加 (2%)</span>
              <span class="amount">{{ formatNum(item.breakdown['地方教育附加(2%)']) }}</span>
            </div>
            <el-divider />
            <div class="calc-line total">
              <span>应纳{{ item.tax_type }}</span>
              <span class="amount" :class="{ negative: item.tax_amount < 0 }">{{ formatNum(item.tax_amount) }}</span>
            </div>
            <div class="calc-line meta">
              <span>税率</span>
              <span>{{ (item.tax_rate * 100).toFixed(2) }}%</span>
            </div>
            <div class="calc-line meta">
              <span>计税基数</span>
              <span>{{ formatNum(item.taxable_amount) }}</span>
            </div>
            <div class="actions">
              <el-button type="primary" size="small" @click="handlePay(item)">确认申报</el-button>
              <el-button size="small" @click="handleAdjust(item)">手动调整</el-button>
            </div>
          </div>
          <div class="card-body" v-else>
            <el-empty description="该期间无相关凭证数据" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 空状态 -->
    <el-empty v-if="!results.length" :description="'请选择期间并点击「一键计算」开始计算税费'" />

    <!-- 手动调整对话框 -->
    <el-dialog v-model="adjustVisible" title="手动调整税额" width="500px">
      <el-form :model="adjustForm" label-width="120px">
        <el-form-item label="税种">
          <el-input :model-value="adjustForm.tax_type" disabled />
        </el-form-item>
        <el-form-item label="计税基数">
          <el-input-number v-model="adjustForm.taxable_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="税率">
          <el-input-number v-model="adjustForm.tax_rate" :precision="4" :min="0" :max="1" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="应纳税额">
          <el-input-number v-model="adjustForm.tax_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="adjustForm.notes" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdjust">确认调整</el-button>
      </template>
    </el-dialog>

    <!-- 确认申报对话框 -->
    <el-dialog v-model="payVisible" title="确认申报" width="400px">
      <el-form :model="payForm" label-width="100px">
        <el-form-item label="税种">
          <span>{{ payForm.tax_type }}</span>
        </el-form-item>
        <el-form-item label="应纳税额">
          <span class="amount">{{ formatNum(payForm.tax_amount) }}</span>
        </el-form-item>
        <el-form-item label="实缴金额">
          <el-input-number v-model="payForm.paid_amount" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="缴纳日期">
          <el-date-picker v-model="payForm.paid_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPay">确认缴纳</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { calculateTax, payTax, updateTaxRecord } from '@/api/tax'

const form = reactive({
  period: new Date().toISOString().slice(0, 7),
})

const results = ref([])
const TAX_TYPES = ['增值税', '企业所得税', '附加税', '印花税']

const adjustVisible = ref(false)
const adjustForm = reactive({
  record_id: null,
  tax_type: '',
  tax_amount: 0,
  taxable_amount: 0,
  tax_rate: 0,
  notes: '',
})

const payVisible = ref(false)
const payForm = reactive({
  record_id: null,
  tax_type: '',
  tax_amount: 0,
  paid_amount: 0,
  paid_date: new Date().toISOString().slice(0, 10),
})

function formatNum(val) {
  if (val == null) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function calculateAll() {
  if (!form.period) {
    ElMessage.warning('请选择所属期间')
    return
  }
  results.value = []
  for (const taxType of TAX_TYPES) {
    try {
      const res = await calculateTax({ tax_type: taxType, period: form.period })
      const detail = res.data.calculation_detail || res.data.data || {}
      results.value.push({
        tax_type: taxType,
        record_id: res.data.record?.id,
        ...detail,
        has_data: detail.has_data !== false,
      })
    } catch (e) {
      results.value.push({ tax_type: taxType, has_data: false, record_id: null })
    }
  }
  ElMessage.success('计算完成')
}

function handleAdjust(item) {
  adjustForm.record_id = item.record_id
  adjustForm.tax_type = item.tax_type
  adjustForm.tax_amount = item.tax_amount || 0
  adjustForm.taxable_amount = item.taxable_amount || 0
  adjustForm.tax_rate = item.tax_rate || 0
  adjustForm.notes = ''
  adjustVisible.value = true
}

async function submitAdjust() {
  if (!adjustForm.record_id) {
    ElMessage.warning('请先计算税费')
    return
  }
  try {
    await updateTaxRecord(adjustForm.record_id, {
      tax_amount: adjustForm.tax_amount,
      taxable_amount: adjustForm.taxable_amount,
      tax_rate: adjustForm.tax_rate,
      notes: adjustForm.notes || null,
    })
    ElMessage.success('调整成功')
    adjustVisible.value = false
    calculateAll()
  } catch (e) {
    // error handled by interceptor
  }
}

function handlePay(item) {
  payForm.record_id = item.record_id
  payForm.tax_type = item.tax_type
  payForm.tax_amount = item.tax_amount || 0
  payForm.paid_amount = item.tax_amount || 0
  payForm.paid_date = new Date().toISOString().slice(0, 10)
  payVisible.value = true
}

async function submitPay() {
  if (!payForm.record_id) {
    ElMessage.warning('请先计算税费')
    return
  }
  try {
    await payTax(payForm.record_id, {
      paid_amount: payForm.paid_amount,
      paid_date: payForm.paid_date || null,
    })
    ElMessage.success('申报成功')
    payVisible.value = false
    calculateAll()
  } catch (e) {
    // error handled by interceptor
  }
}
</script>

<style scoped>
.tax-calculate {
  padding: 8px 0;
}
.toolbar {
  margin-bottom: 16px;
}
.result-card {
  border-radius: 8px;
}
.result-card.no-data {
  opacity: 0.6;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tax-type-label {
  font-weight: 600;
  font-size: 15px;
}
.calc-line {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
}
.calc-line.total {
  font-weight: 700;
  font-size: 16px;
  color: #409eff;
}
.calc-line.meta {
  color: #909399;
  font-size: 13px;
}
.amount {
  font-family: 'Courier New', monospace;
  font-weight: 600;
}
.amount.deduction {
  color: #e6a23c;
}
.amount.negative {
  color: #f56c6c;
}
.actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>