<template>
  <div class="tax-summary">
    <!-- 期间选择 -->
    <el-card shadow="never" class="toolbar-card">
      <el-form :inline="true" size="default">
        <el-form-item label="汇总期间">
          <el-date-picker
            v-model="period"
            type="month"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
            @change="fetchSummary"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchSummary">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 汇总卡片 -->
    <el-row :gutter="16" v-if="summaryData" v-loading="loading" style="margin-top: 16px">
      <el-col
        v-for="(card, idx) in summaryCards"
        :key="idx"
        :xs="24" :sm="12" :md="8" :lg="6"
        style="margin-bottom: 16px"
      >
        <el-card shadow="hover" class="summary-card">
          <div class="card-header">
            <span class="card-tax-type">{{ card.tax_type }}</span>
            <el-tag :type="statusTagType(card.status)" size="small">
              {{ statusLabel(card.status) }}
            </el-tag>
          </div>
          <div class="card-body">
            <div class="card-line">
              <span class="card-label">应纳税额</span>
              <span class="card-value value-primary">{{ formatMoney(card.tax_amount) }}</span>
            </div>
            <div class="card-line">
              <span class="card-label">已缴纳</span>
              <span class="card-value value-success">{{ formatMoney(card.paid_amount) }}</span>
            </div>
            <div class="card-line">
              <span class="card-label">未缴纳</span>
              <span class="card-value" :class="card.remaining_amount > 0 ? 'value-danger' : 'value-success'">
                {{ formatMoney(card.remaining_amount) }}
              </span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16" v-if="summaryData" style="margin-top: 0">
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header>
            <span class="chart-title">各税种应纳税额占比</span>
          </template>
          <div ref="pieChartRef" style="height: 360px"></div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header>
            <span class="chart-title">缴纳状态</span>
          </template>
          <div ref="barChartRef" style="height: 360px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 空状态 -->
    <el-empty v-if="!loading && !summaryData" description="请选择期间查看税务汇总" :image-size="80" style="margin-top: 60px" />
    <el-empty v-if="!loading && summaryData && summaryCards.length === 0" description="该期间暂无税务数据" :image-size="80" style="margin-top: 60px" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getTaxSummary } from '@/api/tax'

const period = ref(getCurrentMonth())
const loading = ref(false)
const summaryData = ref(null)

const pieChartRef = ref(null)
const barChartRef = ref(null)
let pieChart = null
let barChart = null

function getCurrentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function formatMoney(val) {
  if (val == null || val === '') return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function statusTagType(status) {
  const map = { pending: 'info', calculated: '', paid: 'success', overdue: 'danger' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { pending: '待计算', calculated: '已计算', paid: '已缴纳', overdue: '逾期' }
  return map[status] || status
}

const summaryCards = computed(() => {
  if (!summaryData.value) return []
  const items = summaryData.value.items || []
  return items.map(item => ({
    tax_type: item.tax_type,
    tax_amount: item.tax_amount || 0,
    paid_amount: item.paid_amount || 0,
    remaining_amount: item.remaining_amount || 0,
    status: item.status || 'pending',
  }))
})

async function fetchSummary() {
  if (!period.value) return
  loading.value = true
  try {
    const res = await getTaxSummary(period.value)
    summaryData.value = res.data
    await nextTick()
    renderCharts()
  } catch (e) {
    summaryData.value = null
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (!summaryData.value) return
  const items = summaryCards.value
  if (items.length === 0) return

  // 饼图：各税种税额占比
  if (pieChartRef.value) {
    if (!pieChart) {
      pieChart = echarts.init(pieChartRef.value)
    }
    const pieData = items
      .filter(item => item.tax_amount > 0)
      .map(item => ({
        name: item.tax_type,
        value: item.tax_amount,
      }))
    pieChart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
      },
      series: [
        {
          type: 'pie',
          radius: ['45%', '72%'],
          center: ['40%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 14, fontWeight: 'bold' },
          },
          data: pieData.length > 0 ? pieData : [{ name: '无数据', value: 0 }],
        },
      ],
    }, true)
  }

  // 柱状图：已缴 vs 未缴
  if (barChartRef.value) {
    if (!barChart) {
      barChart = echarts.init(barChartRef.value)
    }
    const taxTypes = items.map(i => i.tax_type)
    const paidData = items.map(i => i.paid_amount || 0)
    const unpaidData = items.map(i => i.remaining_amount || 0)

    barChart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
      },
      legend: {
        data: ['已缴纳', '未缴纳'],
        bottom: 0,
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: taxTypes,
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: v => (v / 10000).toFixed(1) + '万',
        },
      },
      series: [
        {
          name: '已缴纳',
          type: 'bar',
          stack: 'total',
          data: paidData,
          itemStyle: { color: '#67c23a' },
          barWidth: '40%',
        },
        {
          name: '未缴纳',
          type: 'bar',
          stack: 'total',
          data: unpaidData,
          itemStyle: { color: '#f56c6c' },
        },
      ],
    }, true)
  }
}

function handleResize() {
  pieChart?.resize()
  barChart?.resize()
}

onMounted(() => {
  fetchSummary()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChart?.dispose()
  barChart?.dispose()
})
</script>

<style scoped>
.tax-summary {
  max-width: 1400px;
}

.toolbar-card {
  margin-bottom: 0;
}

.summary-card {
  border-radius: 8px;
}

.summary-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
}

.card-tax-type {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.card-label {
  font-size: 13px;
  color: #909399;
}

.card-value {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  font-size: 15px;
}

.value-primary { color: #409eff; }
.value-success { color: #67c23a; }
.value-danger { color: #f56c6c; }

.chart-title {
  font-weight: 600;
  font-size: 15px;
}
</style>