<template>
  <div class="tax-analysis">
    <!-- 年份选择 -->
    <el-card shadow="never" class="toolbar-card">
      <el-form :inline="true" size="default">
        <el-form-item label="分析年份">
          <el-date-picker
            v-model="selectedYear"
            type="year"
            placeholder="选择年份"
            format="YYYY"
            value-format="YYYY"
            @change="fetchAnalysis"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchAnalysis">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 关键指标卡片 -->
    <el-row :gutter="16" v-if="analysisData" v-loading="loading" style="margin-top: 16px">
      <el-col :xs="12" :sm="6" style="margin-bottom: 16px">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">年度总税负</div>
          <div class="metric-value value-primary">{{ formatMoney(analysisData.total_year_tax) }}</div>
          <div class="metric-sub">合计应纳税额</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" style="margin-bottom: 16px">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">年度总收入</div>
          <div class="metric-value">{{ formatMoney(analysisData.total_year_revenue) }}</div>
          <div class="metric-sub">营业收入合计</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" style="margin-bottom: 16px">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">实际税负率</div>
          <div class="metric-value" :class="rateClass(analysisData.year_effective_rate)">
            {{ formatRate(analysisData.year_effective_rate) }}
          </div>
          <div class="metric-sub">
            行业平均: {{ formatRate(analysisData.industry_average_rate) }}
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6" style="margin-bottom: 16px">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">涉及税种</div>
          <div class="metric-value">{{ analysisData.tax_type_breakdown?.length || 0 }}</div>
          <div class="metric-sub">个税种</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16" v-if="analysisData" style="margin-top: 0">
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header>
            <span class="chart-title">月度税负趋势</span>
          </template>
          <div ref="lineChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header>
            <span class="chart-title">税种构成</span>
          </template>
          <div ref="pieChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 税负率明细表 -->
    <el-card
      shadow="hover"
      v-if="analysisData && analysisData.tax_type_breakdown?.length"
      style="margin-top: 16px"
    >
      <template #header>
        <span class="chart-title">各税种税负率</span>
      </template>
      <el-table :data="taxTypeTableData" stripe border>
        <el-table-column prop="tax_type" label="税种" width="150" />
        <el-table-column label="年度税额" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.amount) }}
          </template>
        </el-table-column>
        <el-table-column label="占总税负比" align="right" width="120">
          <template #default="{ row }">
            {{ row.percent }}%
          </template>
        </el-table-column>
        <el-table-column label="税负率" align="right" width="120">
          <template #default="{ row }">
            {{ formatRate(row.burden_rate) }}
          </template>
        </el-table-column>
        <el-table-column label="法定税率" align="right" width="120">
          <template #default="{ row }">
            {{ row.statutory_rate ? (row.statutory_rate * 100).toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="税负率对比" align="center" width="140">
          <template #default="{ row }">
            <el-tag
              v-if="row.burden_rate != null && row.statutory_rate != null"
              :type="row.burden_rate > row.statutory_rate ? 'danger' : row.burden_rate < row.statutory_rate * 0.8 ? 'warning' : 'success'"
              size="small"
            >
              {{ row.burden_rate > row.statutory_rate ? '偏高' : row.burden_rate < row.statutory_rate * 0.8 ? '偏低' : '正常' }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 空状态 -->
    <el-empty v-if="!loading && !analysisData" description="请选择年份查看税负分析" :image-size="80" style="margin-top: 60px" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getTaxAnalysis } from '@/api/tax'

const selectedYear = ref(new Date().getFullYear().toString())
const analysisData = ref(null)
const loading = ref(false)

const lineChartRef = ref(null)
const pieChartRef = ref(null)
let lineChart = null
let pieChart = null

// 法定税率映射
const STATUTORY_RATES = {
  '增值税': 0.13,
  '企业所得税': 0.25,
  '附加税': 0.12,
  '印花税': 0.001,
  '其他': null,
}

function formatMoney(val) {
  if (val == null || val === '') return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatRate(rate) {
  if (rate == null) return '-'
  return (rate * 100).toFixed(2) + '%'
}

function rateClass(rate) {
  if (rate == null) return ''
  if (rate > 0.05) return 'value-danger'
  if (rate > 0.03) return 'value-warning'
  return 'value-success'
}

const taxTypeTableData = computed(() => {
  if (!analysisData.value) return []
  const breakdown = analysisData.value.tax_type_breakdown || []
  const total = analysisData.value.total_year_tax || 0
  const revenue = analysisData.value.total_year_revenue || 0
  return breakdown.map(item => ({
    tax_type: item.tax_type,
    amount: item.amount || 0,
    percent: total > 0 ? ((item.amount / total) * 100).toFixed(2) : '0.00',
    burden_rate: revenue > 0 ? (item.amount / revenue) : null,
    statutory_rate: STATUTORY_RATES[item.tax_type] ?? null,
  }))
})

async function fetchAnalysis() {
  if (!selectedYear.value) return
  loading.value = true
  try {
    const res = await getTaxAnalysis(parseInt(selectedYear.value))
    analysisData.value = res.data
    await nextTick()
    renderCharts()
  } catch (e) {
    analysisData.value = null
  } finally {
    loading.value = false
  }
}

function renderCharts() {
  if (!analysisData.value) return

  const data = analysisData.value

  // 月度趋势折线图
  if (lineChartRef.value) {
    if (!lineChart) {
      lineChart = echarts.init(lineChartRef.value)
    }
    const months = (data.monthly || []).map(m => m.period ? m.period.substring(5) : '')
    lineChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: function (params) {
          let html = params[0].axisValue + '月<br/>'
          params.forEach(p => {
            html += `${p.marker} ${p.seriesName}: ${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}<br/>`
          })
          return html
        },
      },
      legend: {
        data: ['应纳税额', '税负率'],
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
        data: months,
        name: '月份',
      },
      yAxis: [
        {
          type: 'value',
          name: '税额 (元)',
          axisLabel: {
            formatter: v => (v / 10000).toFixed(1) + '万',
          },
        },
        {
          type: 'value',
          name: '税负率',
          axisLabel: {
            formatter: v => (v * 100).toFixed(1) + '%',
          },
        },
      ],
      series: [
        {
          name: '应纳税额',
          type: 'line',
          data: (data.monthly || []).map(m => m.total_tax),
          smooth: true,
          itemStyle: { color: '#409eff' },
          areaStyle: { color: 'rgba(64,158,255,0.1)' },
        },
        {
          name: '税负率',
          type: 'line',
          yAxisIndex: 1,
          data: (data.monthly || []).map(m => m.effective_rate),
          smooth: true,
          itemStyle: { color: '#67c23a' },
          lineStyle: { type: 'dashed' },
        },
      ],
    }, true)
  }

  // 税种构成饼图
  if (pieChartRef.value) {
    if (!pieChart) {
      pieChart = echarts.init(pieChartRef.value)
    }
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
          radius: ['40%', '70%'],
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
          data: (data.tax_type_breakdown || []).map(item => ({
            name: item.tax_type,
            value: item.amount,
          })),
        },
      ],
    }, true)
  }
}

function handleResize() {
  lineChart?.resize()
  pieChart?.resize()
}

onMounted(() => {
  fetchAnalysis()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  lineChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.tax-analysis {
  max-width: 1400px;
}

.toolbar-card {
  margin-bottom: 0;
}

.metric-card {
  text-align: center;
}

.metric-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  color: #303133;
}

.metric-sub {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}

.value-primary { color: #409eff; }
.value-success { color: #67c23a; }
.value-warning { color: #e6a23c; }
.value-danger { color: #f56c6c; }

.chart-title {
  font-weight: 600;
  font-size: 15px;
}
</style>