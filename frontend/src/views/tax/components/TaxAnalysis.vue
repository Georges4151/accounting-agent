<template>
  <div class="tax-analysis">
    <!-- 年份选择 -->
    <div class="toolbar">
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
    </div>

    <!-- 关键指标卡片 -->
    <el-row :gutter="20" v-if="analysisData">
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">年度总税负</div>
          <div class="metric-value">{{ formatNum(analysisData.total_year_tax) }}</div>
          <div class="metric-sub">合计应纳税额</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">年度总收入</div>
          <div class="metric-value">{{ formatNum(analysisData.total_year_revenue) }}</div>
          <div class="metric-sub">营业收入合计</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">实际税负率</div>
          <div class="metric-value" :class="rateClass(analysisData.year_effective_rate)">
            {{ (analysisData.year_effective_rate * 100).toFixed(2) }}%
          </div>
          <div class="metric-sub">行业平均: {{ (analysisData.industry_average_rate * 100).toFixed(2) }}%</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-label">税种数量</div>
          <div class="metric-value">{{ analysisData.tax_type_breakdown?.length || 0 }}</div>
          <div class="metric-sub">涉及税种</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="20" v-if="analysisData" style="margin-top: 20px">
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

    <!-- 税种明细表 -->
    <el-card shadow="hover" v-if="analysisData && analysisData.tax_type_breakdown?.length" style="margin-top: 20px">
      <template #header>
        <span class="chart-title">税种明细</span>
      </template>
      <el-table :data="analysisData.tax_type_breakdown" stripe border>
        <el-table-column prop="tax_type" label="税种" width="150" />
        <el-table-column label="税额" align="right">
          <template #default="{ row }">
            {{ formatNum(row.amount) }}
          </template>
        </el-table-column>
        <el-table-column label="占比" align="right">
          <template #default="{ row }">
            {{ calcPercent(row.amount) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-if="!analysisData" description="请选择年份查看税负分析" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { getTaxAnalysis } from '@/api/tax'

const selectedYear = ref(new Date().getFullYear().toString())
const analysisData = ref(null)

const lineChartRef = ref(null)
const pieChartRef = ref(null)
let lineChart = null
let pieChart = null

function formatNum(val) {
  if (val == null) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function rateClass(rate) {
  if (rate > 0.05) return 'text-danger'
  if (rate > 0.03) return 'text-warning'
  return 'text-success'
}

function calcPercent(amount) {
  if (!analysisData.value) return '0.00%'
  const total = analysisData.value.total_year_tax
  if (!total) return '0.00%'
  return ((amount / total) * 100).toFixed(2) + '%'
}

async function fetchAnalysis() {
  try {
    const res = await getTaxAnalysis(parseInt(selectedYear.value))
    analysisData.value = res.data
    await nextTick()
    renderCharts()
  } catch (e) {
    // handled by interceptor
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
    const months = data.monthly.map(m => m.period.substring(5))
    lineChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: function(params) {
          let html = params[0].axisValue + '月<br/>'
          params.forEach(p => {
            html += `${p.marker} ${p.seriesName}: ${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}<br/>`
          })
          return html
        }
      },
      legend: { data: ['应纳税额', '税负率'], bottom: 0 },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
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
            formatter: v => (v / 10000).toFixed(1) + '万'
          }
        },
        {
          type: 'value',
          name: '税负率',
          axisLabel: { formatter: v => (v * 100).toFixed(1) + '%' }
        }
      ],
      series: [
        {
          name: '应纳税额',
          type: 'line',
          data: data.monthly.map(m => m.total_tax),
          smooth: true,
          itemStyle: { color: '#409eff' },
          areaStyle: { color: 'rgba(64,158,255,0.1)' },
        },
        {
          name: '税负率',
          type: 'line',
          yAxisIndex: 1,
          data: data.monthly.map(m => m.effective_rate),
          smooth: true,
          itemStyle: { color: '#67c23a' },
          lineStyle: { type: 'dashed' },
        }
      ]
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
        formatter: '{b}: {c} ({d}%)'
      },
      legend: { orient: 'vertical', right: 10, top: 'center' },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['40%', '50%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 14, fontWeight: 'bold' }
          },
          data: (data.tax_type_breakdown || []).map(item => ({
            name: item.tax_type,
            value: item.amount,
          })),
        }
      ]
    }, true)
  }
}

// 窗口大小变化时重绘
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
  padding: 8px 0;
}
.toolbar {
  margin-bottom: 16px;
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
.text-danger {
  color: #f56c6c;
}
.text-warning {
  color: #e6a23c;
}
.text-success {
  color: #67c23a;
}
.chart-title {
  font-weight: 600;
  font-size: 15px;
}
</style>