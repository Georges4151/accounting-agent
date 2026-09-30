<template>
  <div class="aging-analysis">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>账龄分析表</span>
          <div class="header-actions">
            <el-button type="primary" @click="loadData" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选区 -->
      <div class="filter-bar">
        <el-radio-group v-model="filters.reconciliation_type" @change="handleFilterChange" size="small">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="ar">应收</el-radio-button>
          <el-radio-button value="ap">应付</el-radio-button>
        </el-radio-group>
        <el-select
          v-model="filters.party_type"
          placeholder="往来方类型"
          clearable
          style="width: 130px; margin-left: 12px"
          @change="handleFilterChange"
        >
          <el-option label="客户" value="customer" />
          <el-option label="供应商" value="supplier" />
        </el-select>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading && summary.length === 0" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <!-- 空数据 -->
      <el-empty
        v-else-if="!loading && summary.length === 0"
        description="暂无账龄分析数据，请先创建应收应付记录"
      />

      <template v-else>
        <!-- 图表区 -->
        <div class="charts-row">
          <div class="chart-card">
            <div class="chart-title">账龄分布（柱状图）</div>
            <v-chart :option="barChartOption" style="height: 350px" autoresize />
          </div>
          <div class="chart-card">
            <div class="chart-title">账龄占比（饼图）</div>
            <v-chart :option="pieChartOption" style="height: 350px" autoresize />
          </div>
        </div>

        <!-- 汇总表 -->
        <div class="section-title">账龄汇总</div>
        <el-table :data="summary" stripe size="small" style="margin-top: 12px">
          <el-table-column prop="label" label="账龄区间" width="140" />
          <el-table-column prop="amount" label="金额" width="180" align="right">
            <template #default="{ row }">
              <span class="amount-cell">{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="percentage" label="占比" width="120" align="right">
            <template #default="{ row }">
              <span>{{ row.percentage }}%</span>
            </template>
          </el-table-column>
          <el-table-column label="占比进度条" min-width="200">
            <template #default="{ row }">
              <el-progress
                :percentage="row.percentage"
                :color="getProgressColor(row.percentage)"
                :stroke-width="16"
              />
            </template>
          </el-table-column>
        </el-table>

        <!-- 明细表 -->
        <div class="section-title" style="margin-top: 24px">往来方明细</div>
        <el-table :data="items" stripe style="margin-top: 12px">
          <el-table-column prop="party_type" label="类别" width="80">
            <template #default="{ row }">
              {{ row.party_type === 'customer' ? '客户' : '供应商' }}
            </template>
          </el-table-column>
          <el-table-column prop="party_name" label="名称" min-width="140" />
          <el-table-column prop="amount" label="合计金额" width="130" align="right">
            <template #default="{ row }">
              <span class="amount-cell">{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="aging_0_30" label="30天内" width="120" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.aging_0_30 > 0 }">
                {{ formatMoney(row.aging_0_30) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="aging_30_60" label="30-60天" width="120" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.aging_30_60 > 0 }">
                {{ formatMoney(row.aging_30_60) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="aging_60_90" label="60-90天" width="120" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.aging_60_90 > 0 }">
                {{ formatMoney(row.aging_60_90) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="aging_90_180" label="90-180天" width="120" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.aging_90_180 > 0 }">
                {{ formatMoney(row.aging_90_180) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="aging_180_365" label="180-365天" width="120" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.aging_180_365 > 0 }">
                {{ formatMoney(row.aging_180_365) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="aging_365_plus" label="1年以上" width="120" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.aging_365_plus > 0 }">
                {{ formatMoney(row.aging_365_plus) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useBookStore } from '@/stores/book'
import { getAgingAnalysis } from '@/api/reconciliation'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const bookStore = useBookStore()

// ===== 状态 =====
const loading = ref(false)
const summary = ref([])
const items = ref([])

const filters = reactive({
  reconciliation_type: '',
  party_type: '',
})

// ===== 生命周期 =====
onMounted(() => {
  loadData()
})

// ===== 数据加载 =====
async function loadData() {
  const bookId = bookStore.currentBookId
  if (!bookId) {
    ElMessage.warning('请先选择账套')
    return
  }

  loading.value = true
  try {
    const params = { book_id: bookId }
    if (filters.reconciliation_type) params.reconciliation_type = filters.reconciliation_type
    if (filters.party_type) params.party_type = filters.party_type

    const res = await getAgingAnalysis(params)
    summary.value = res.data.summary || []
    items.value = res.data.items || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载账龄分析数据失败')
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  loadData()
}

// ===== 图表 =====
const barChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => {
      const p = params[0]
      return `${p.name}<br/>金额: ¥${formatMoney(p.value)}`
    },
  },
  grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
  xAxis: {
    type: 'category',
    data: summary.value.map(s => s.label),
    axisLabel: { rotate: 30 },
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      formatter: (val) => {
        if (val >= 10000) return (val / 10000).toFixed(0) + '万'
        return val
      },
    },
  },
  series: [{
    type: 'bar',
    data: summary.value.map(s => s.amount),
    itemStyle: {
      color: (params) => {
        const colors = ['#91cc75', '#73c0de', '#5470c6', '#ee6666', '#fac858', '#fc8452']
        return colors[params.dataIndex % colors.length]
      },
    },
  }],
}))

const pieChartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: ¥{c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    left: 'left',
    top: 'center',
  },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    center: ['55%', '50%'],
    avoidLabelOverlap: false,
    itemStyle: {
      borderRadius: 4,
      borderColor: '#fff',
      borderWidth: 2,
    },
    label: {
      show: true,
      formatter: '{b}\n{d}%',
    },
    data: summary.value
      .filter(s => s.amount > 0)
      .map(s => ({ name: s.label, value: s.amount })),
    color: ['#91cc75', '#73c0de', '#5470c6', '#ee6666', '#fac858', '#fc8452'],
  }],
}))

// ===== 辅助函数 =====
function formatMoney(val) {
  if (val === null || val === undefined) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function getProgressColor(pct) {
  if (pct > 50) return '#f56c6c'
  if (pct > 30) return '#e6a23c'
  return '#409eff'
}
</script>

<style scoped>
.aging-analysis {
  max-width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.loading-container {
  padding: 20px 0;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.chart-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  padding-bottom: 8px;
  border-bottom: 2px solid #409eff;
}

.amount-cell {
  font-family: 'Courier New', monospace;
  font-weight: 500;
}

.text-danger {
  color: #f56c6c;
}

@media (max-width: 768px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}
</style>