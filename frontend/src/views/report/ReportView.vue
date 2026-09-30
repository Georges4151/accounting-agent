<template>
  <div class="report-view">
    <!-- 报表标题和操作栏 -->
    <el-card class="report-header-card" shadow="never">
      <div class="report-header">
        <div class="report-title-area">
          <h2>{{ currentReport.label }}</h2>
          <p class="report-desc">{{ currentReport.description }}</p>
        </div>
        <div class="report-actions">
          <el-date-picker
            v-model="reportPeriod"
            type="month"
            placeholder="选择月份"
            value-format="YYYY-MM"
            @change="handlePeriodChange"
            style="width: 160px"
          />
          <el-button type="primary" @click="handleExportCSV" :loading="exporting">
            <el-icon><Download /></el-icon>
            导出 CSV
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 报表类型标签页 -->
    <el-card class="report-tabs-card" shadow="never" style="margin-top: 16px">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange" type="border-card">
        <el-tab-pane
          v-for="tab in reportTabs"
          :key="tab.key"
          :label="tab.label"
          :name="tab.key"
        />
      </el-tabs>
    </el-card>

    <!-- DEBUG: 数据状态 -->
    <el-card v-if="true" style="margin-top: 16px; background: #f0f9eb;">
      <div style="font-size: 12px; color: #67c23a;">
        <div>activeTab: {{ activeTab }}</div>
        <div>reportPeriod: {{ reportPeriod }}</div>
        <div>loading: {{ loading }}</div>
        <div>balanceSheetData: {{ balanceSheetData ? '有数据(total_assets=' + balanceSheetData.total_assets + ')' : 'null' }}</div>
        <div>incomeStatementData: {{ incomeStatementData ? '有数据' : 'null' }}</div>
        <div>cashFlowData: {{ cashFlowData ? '有数据' : 'null' }}</div>
        <div>ledgerData: {{ ledgerData ? '有数据' : 'null' }}</div>
        <div>trialBalanceData: {{ trialBalanceData ? '有数据' : 'null' }}</div>
        <div>trialBalanceSummaryData: {{ trialBalanceSummaryData ? '有数据' : 'null' }}</div>
        <div>comparisonData: {{ comparisonData ? '有数据' : 'null' }}</div>
        <div>summaryCards count: {{ summaryCards.length }}</div>
        <div>balanceSheetTableData count: {{ balanceSheetTableData.length }}</div>
        <div>incomeStatementTableData count: {{ incomeStatementTableData.length }}</div>
        <div>cashFlowTableData count: {{ cashFlowTableData.length }}</div>
        <div>ledgerTableData count: {{ ledgerTableData.length }}</div>
      </div>
    </el-card>

    <!-- 汇总卡片 -->
    <el-row :gutter="16" class="summary-row" v-if="summaryCards.length > 0" v-loading="loading">
      <el-col
        v-for="card in summaryCards"
        :key="card.label"
        :xs="24" :sm="12" :md="6"
        style="margin-top: 16px"
      >
        <el-card shadow="hover" class="summary-card">
          <div class="summary-card-content">
            <div class="summary-label">{{ card.label }}</div>
            <div class="summary-value" :class="card.valueClass">
              {{ formatMoney(card.value) }}
            </div>
            <div v-if="card.change !== null" class="summary-change">
              <span :class="card.change >= 0 ? 'change-up' : 'change-down'">
                <el-icon v-if="card.change > 0"><CaretTop /></el-icon>
                <el-icon v-else-if="card.change < 0"><CaretBottom /></el-icon>
                {{ formatPercent(card.change) }}
              </span>
              <span class="change-label">较上期</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 多期间对比视图（资产负债表 / 利润表） -->
    <el-card
      v-if="showComparison"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <div class="card-header">
          <span class="card-title">多期间对比</span>
          <el-tag type="info" size="small">{{ comparisonPeriods[0] }} vs {{ comparisonPeriods[1] }} vs {{ comparisonPeriods[2] }}</el-tag>
        </div>
      </template>
      <el-table :data="comparisonTableData" border stripe style="width: 100%" :row-class-name="comparisonRowClass">
        <el-table-column prop="label" label="指标" min-width="160" />
        <el-table-column :label="comparisonPeriods[0]" align="right" min-width="140">
          <template #default="{ row }">
            {{ formatMoney(row.current) }}
          </template>
        </el-table-column>
        <el-table-column :label="comparisonPeriods[1]" align="right" min-width="140">
          <template #default="{ row }">
            {{ formatMoney(row.prev) }}
          </template>
        </el-table-column>
        <el-table-column :label="comparisonPeriods[2]" align="right" min-width="140">
          <template #default="{ row }">
            {{ formatMoney(row.lastYear) }}
          </template>
        </el-table-column>
        <el-table-column label="环比变化" align="right" min-width="120">
          <template #default="{ row }">
            <span v-if="row.prevChange !== null" :class="row.prevChange >= 0 ? 'change-up' : 'change-down'">
              {{ formatMoney(row.prevChange) }}
            </span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="环比变化率" align="right" min-width="100">
          <template #default="{ row }">
            <span v-if="row.prevChangePct !== null" :class="row.prevChangePct >= 0 ? 'change-up' : 'change-down'">
              {{ formatPercent(row.prevChangePct) }}
            </span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="同比变化" align="right" min-width="120">
          <template #default="{ row }">
            <span v-if="row.yoyChange !== null" :class="row.yoyChange >= 0 ? 'change-up' : 'change-down'">
              {{ formatMoney(row.yoyChange) }}
            </span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="同比变化率" align="right" min-width="100">
          <template #default="{ row }">
            <span v-if="row.yoyChangePct !== null" :class="row.yoyChangePct >= 0 ? 'change-up' : 'change-down'">
              {{ formatPercent(row.yoyChangePct) }}
            </span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 明细报表（资产负债表） -->
    <el-card
      v-if="activeTab === 'balance-sheet'"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <span class="card-title">资产负债表明细</span>
      </template>
      <el-table
        :data="balanceSheetTableData"
        border stripe style="width: 100%"
        :span-method="balanceSheetSpanMethod"
        :row-class-name="tableRowClassName"
      >
        <el-table-column prop="account_name" label="项目" min-width="200" />
        <el-table-column prop="line_no" label="行次" width="80" align="center" />
        <el-table-column prop="ending_balance" label="期末余额" width="180" align="right">
          <template #default="{ row }">
            <span v-if="row.is_section"></span>
            <span v-else :class="{ 'total-amount': row.is_total }">
              {{ formatMoney(row.ending_balance) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="beginning_balance" label="期初余额" width="180" align="right">
          <template #default="{ row }">
            <span v-if="row.is_section"></span>
            <span v-else>
              {{ formatMoney(row.beginning_balance) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && balanceSheetTableData.length === 0" description="暂无数据" :image-size="80" />
    </el-card>

    <!-- 明细报表（利润表） -->
    <el-card
      v-if="activeTab === 'income-statement'"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <span class="card-title">利润表明细</span>
      </template>
      <el-table
        :data="incomeStatementTableData"
        border stripe style="width: 100%"
        :row-class-name="tableRowClassName"
      >
        <el-table-column prop="account_name" label="项目" min-width="200" />
        <el-table-column prop="line_no" label="行次" width="80" align="center" />
        <el-table-column prop="current_amount" label="本期金额" width="180" align="right">
          <template #default="{ row }">
            <span v-if="row.is_section"></span>
            <span v-else :class="{ 'total-amount': row.is_total }">
              {{ formatMoney(row.current_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="cumulative_amount" label="本年累计金额" width="180" align="right">
          <template #default="{ row }">
            <span v-if="row.is_section"></span>
            <span v-else>
              {{ formatMoney(row.cumulative_amount) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && incomeStatementTableData.length === 0" description="暂无数据" :image-size="80" />
    </el-card>

    <!-- 明细报表（现金流量表） -->
    <el-card
      v-if="activeTab === 'cash-flow'"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <span class="card-title">现金流量表明细</span>
      </template>
      <el-table
        :data="cashFlowTableData"
        border stripe style="width: 100%"
        :row-class-name="tableRowClassName"
      >
        <el-table-column prop="account_name" label="项目" min-width="240" />
        <el-table-column prop="line_no" label="行次" width="80" align="center" />
        <el-table-column prop="amount" label="本期金额" width="180" align="right">
          <template #default="{ row }">
            <span v-if="row.is_section"></span>
            <span v-else>
              {{ formatMoney(row.amount) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && cashFlowTableData.length === 0" description="暂无数据" :image-size="80" />
    </el-card>

    <!-- 明细报表（科目余额表） -->
    <el-card
      v-if="activeTab === 'account-ledger'"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <span class="card-title">科目余额表明细</span>
      </template>
      <el-table :data="ledgerTableData" border stripe style="width: 100%" max-height="600">
        <el-table-column prop="account_code" label="科目代码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="160" />
        <el-table-column prop="beginning_debit" label="期初借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.beginning_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="beginning_credit" label="期初贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.beginning_credit) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_debit" label="本期借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_credit" label="本期贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_credit) }}
          </template>
        </el-table-column>
        <el-table-column prop="ending_debit" label="期末借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.ending_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="ending_credit" label="期末贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.ending_credit) }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && ledgerTableData.length === 0" description="暂无数据" :image-size="80" />
    </el-card>

    <!-- 明细报表（科目余额表v2） -->
    <el-card
      v-if="activeTab === 'trial-balance'"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <span class="card-title">科目余额表明细</span>
      </template>
      <el-table :data="trialBalanceTableData" border stripe style="width: 100%" max-height="600">
        <el-table-column prop="account_code" label="科目代码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="160" />
        <el-table-column prop="account_type" label="科目类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="accountTypeTag(row.account_type)">
              {{ accountTypeLabel(row.account_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="balance_direction" label="余额方向" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.balance_direction === 'debit' ? 'primary' : 'success'">
              {{ row.balance_direction === 'debit' ? '借' : '贷' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="beginning_debit" label="期初借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.beginning_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="beginning_credit" label="期初贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.beginning_credit) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_debit" label="本期借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_credit" label="本期贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_credit) }}
          </template>
        </el-table-column>
        <el-table-column prop="ending_debit" label="期末借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.ending_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="ending_credit" label="期末贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.ending_credit) }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && trialBalanceTableData.length === 0" description="暂无数据" :image-size="80" />
    </el-card>

    <!-- 明细报表（试算平衡表） -->
    <el-card
      v-if="activeTab === 'trial-balance-summary'"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <div class="card-header">
          <span class="card-title">试算平衡表明细</span>
          <el-tag
            :type="(trialBalanceSummaryData?.balance_check?.is_balanced) ? 'success' : 'danger'"
            size="large"
          >
            {{ (trialBalanceSummaryData?.balance_check?.is_balanced) ? '✓ 试算平衡' : '✗ 试算不平衡' }}
          </el-tag>
        </div>
      </template>
      <el-table :data="trialBalanceSummaryTableData" border stripe style="width: 100%" max-height="600">
        <el-table-column prop="account_code" label="科目代码" width="120" />
        <el-table-column prop="account_name" label="科目名称" min-width="160" />
        <el-table-column prop="account_type" label="科目类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="accountTypeTag(row.account_type)">
              {{ accountTypeLabel(row.account_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="balance_direction" label="余额方向" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.balance_direction === 'debit' ? 'primary' : 'success'">
              {{ row.balance_direction === 'debit' ? '借' : '贷' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="beginning_debit" label="期初借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.beginning_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="beginning_credit" label="期初贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.beginning_credit) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_debit" label="本期借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="current_credit" label="本期贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.current_credit) }}
          </template>
        </el-table-column>
        <el-table-column prop="ending_debit" label="期末借方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.ending_debit) }}
          </template>
        </el-table-column>
        <el-table-column prop="ending_credit" label="期末贷方" width="140" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.ending_credit) }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && trialBalanceSummaryTableData.length === 0" description="暂无数据" :image-size="80" />
    </el-card>

    <!-- 财务指标分析 -->
    <el-card
      v-if="activeTab === 'financial-ratios'"
      class="report-content-card"
      shadow="never"
      style="margin-top: 16px"
      v-loading="loading"
    >
      <template #header>
        <span class="card-title">财务指标分析</span>
      </template>

      <!-- 指标卡片 -->
      <el-row :gutter="16" v-if="financialRatiosTableData.length > 0">
        <el-col
          v-for="ratio in financialRatiosTableData"
          :key="ratio.name"
          :xs="24" :sm="12" :md="8" :lg="6"
          style="margin-bottom: 16px"
        >
          <el-card shadow="hover" class="ratio-card">
            <div class="ratio-header">
              <span class="ratio-name">{{ ratio.name }}</span>
              <el-tag
                :type="ratioStatusTag(ratio.status)"
                size="small"
                effect="plain"
              >
                {{ ratioStatusLabel(ratio.status) }}
              </el-tag>
            </div>
            <div class="ratio-value" :class="'ratio-' + ratio.status">
              {{ ratio.value != null ? formatRatioValue(ratio.value, ratio.unit) : '--' }}
            </div>
            <div class="ratio-formula">{{ ratio.formula }}</div>
            <div class="ratio-reference">参考值: {{ ratio.reference }}</div>
            <div class="ratio-desc">{{ ratio.description }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="!loading && financialRatiosTableData.length === 0" description="暂无数据" :image-size="80" />

      <!-- 基础数据摘要 -->
      <el-card v-if="financialRatiosData?.summary" shadow="never" style="margin-top: 16px" class="ratio-summary-card">
        <template #header>
          <span style="font-weight: 600; font-size: 14px;">基础数据摘要</span>
        </template>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="流动资产">
            {{ formatMoney(financialRatiosData.summary.current_assets) }}
          </el-descriptions-item>
          <el-descriptions-item label="存货">
            {{ formatMoney(financialRatiosData.summary.inventory) }}
          </el-descriptions-item>
          <el-descriptions-item label="流动负债">
            {{ formatMoney(financialRatiosData.summary.current_liabilities) }}
          </el-descriptions-item>
          <el-descriptions-item label="资产总额">
            {{ formatMoney(financialRatiosData.summary.total_assets) }}
          </el-descriptions-item>
          <el-descriptions-item label="负债总额">
            {{ formatMoney(financialRatiosData.summary.total_liabilities) }}
          </el-descriptions-item>
          <el-descriptions-item label="所有者权益">
            {{ formatMoney(financialRatiosData.summary.total_equity) }}
          </el-descriptions-item>
          <el-descriptions-item label="营业收入">
            {{ formatMoney(financialRatiosData.summary.total_revenue) }}
          </el-descriptions-item>
          <el-descriptions-item label="成本费用">
            {{ formatMoney(financialRatiosData.summary.total_cost) }}
          </el-descriptions-item>
          <el-descriptions-item label="净利润">
            <span :class="financialRatiosData.summary.net_profit >= 0 ? 'change-up' : 'change-down'">
              {{ formatMoney(financialRatiosData.summary.net_profit) }}
            </span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getBalanceSheet,
  getIncomeStatement,
  getCashFlow,
  getAccountLedger,
  getTrialBalance,
  getTrialBalanceSummary,
  getComparison,
  getFinancialRatios,
  exportReport
} from '@/api/report'
import { useAmountMask } from '@/composables/useAmountMask'
import { ElMessage } from 'element-plus'

const { formatAmount } = useAmountMask()

const route = useRoute()
const router = useRouter()

// ===== 报表类型配置 =====

const reportTabs = [
  { key: 'balance-sheet', label: '资产负债表', description: '反映企业在某一特定日期的财务状况' },
  { key: 'income-statement', label: '利润表', description: '反映企业在一定会计期间的经营成果' },
  { key: 'cash-flow', label: '现金流量表', description: '反映企业在一定会计期间现金和现金等价物的流入和流出' },
  { key: 'account-ledger', label: '科目余额表', description: '反映各会计科目在本期的发生额和余额情况' },
  { key: 'trial-balance', label: '科目余额表(新)', description: '反映各会计科目在本期的发生额和余额情况（含科目类型和余额方向）' },
  { key: 'trial-balance-summary', label: '试算平衡表', description: '汇总所有科目余额，检查借贷是否平衡' },
  { key: 'financial-ratios', label: '财务指标', description: '财务比率分析，包括偿债能力、盈利能力、运营效率等指标' }
]

const activeTab = ref('balance-sheet')

const currentReport = computed(() => {
  return reportTabs.find(t => t.key === activeTab.value) || reportTabs[0]
})

// ===== 期间选择 =====

const reportPeriod = ref(getCurrentMonth())

function getCurrentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function getPreviousMonth(period) {
  const [y, m] = period.split('-').map(Number)
  if (m === 1) return `${y - 1}-12`
  return `${y}-${String(m - 1).padStart(2, '0')}`
}

function getLastYearMonth(period) {
  const [y, m] = period.split('-')
  return `${Number(y) - 1}-${m}`
}

// ===== 对比期间 =====

const comparisonPeriods = computed(() => {
  const current = reportPeriod.value
  const prev = getPreviousMonth(current)
  const lastYear = getLastYearMonth(current)
  return [current, prev, lastYear]
})

// ===== 状态 =====

const loading = ref(false)
const exporting = ref(false)

// 报表数据
const balanceSheetData = ref(null)
const incomeStatementData = ref(null)
const cashFlowData = ref(null)
const ledgerData = ref(null)
const trialBalanceData = ref(null)
const trialBalanceSummaryData = ref(null)
const comparisonData = ref(null)
const financialRatiosData = ref(null)

// ===== 是否显示对比视图 =====

const showComparison = computed(() => {
  return ['balance-sheet', 'income-statement'].includes(activeTab.value)
})

// ===== 汇总卡片 =====

const summaryCards = computed(() => {
  const cards = []

  if (activeTab.value === 'balance-sheet' && comparisonData.value) {
    const periods = comparisonData.value.periods || []
    const current = periods[0] || {}
    const prev = periods[1] || {}

    const calcChange = (cur, prv) => {
      if (prv == null || prv === 0) return null
      return cur - prv
    }
    const calcChangePct = (cur, prv) => {
      if (prv == null || prv === 0) return null
      return ((cur - prv) / Math.abs(prv)) * 100
    }

    cards.push({
      label: '资产总计',
      value: current.total_assets ?? 0,
      change: prev ? calcChangePct(current.total_assets, prev.total_assets) : null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '负债合计',
      value: current.total_liabilities ?? 0,
      change: prev ? calcChangePct(current.total_liabilities, prev.total_liabilities) : null,
      valueClass: 'value-warning'
    })
    cards.push({
      label: '所有者权益',
      value: current.total_equity ?? 0,
      change: prev ? calcChangePct(current.total_equity, prev.total_equity) : null,
      valueClass: 'value-success'
    })
    cards.push({
      label: '负债和权益总计',
      value: current.total_liabilities_and_equity ?? 0,
      change: null,
      valueClass: 'value-info'
    })
  } else if (activeTab.value === 'income-statement' && comparisonData.value) {
    const periods = comparisonData.value.periods || []
    const current = periods[0] || {}
    const prev = periods[1] || {}

    const calcChangePct = (cur, prv) => {
      if (prv == null || prv === 0) return null
      return ((cur - prv) / Math.abs(prv)) * 100
    }

    cards.push({
      label: '营业收入',
      value: current.total_revenue ?? 0,
      change: prev ? calcChangePct(current.total_revenue, prev.total_revenue) : null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '营业费用',
      value: current.total_expenses ?? 0,
      change: prev ? calcChangePct(current.total_expenses, prev.total_expenses) : null,
      valueClass: 'value-danger'
    })
    cards.push({
      label: '净利润',
      value: current.net_profit ?? 0,
      change: prev ? calcChangePct(current.net_profit, prev.net_profit) : null,
      valueClass: (current.net_profit ?? 0) >= 0 ? 'value-success' : 'value-danger'
    })
    cards.push({
      label: '利润率',
      value: current.total_revenue ? ((current.net_profit / current.total_revenue) * 100) : 0,
      suffix: '%',
      change: null,
      valueClass: 'value-info'
    })
  } else if (activeTab.value === 'cash-flow' && cashFlowData.value) {
    const data = cashFlowData.value
    cards.push({
      label: '经营现金流净额',
      value: data.operating?.net ?? 0,
      change: null,
      valueClass: (data.operating?.net ?? 0) >= 0 ? 'value-success' : 'value-danger'
    })
    cards.push({
      label: '投资现金流净额',
      value: data.investing?.net ?? 0,
      change: null,
      valueClass: (data.investing?.net ?? 0) >= 0 ? 'value-success' : 'value-danger'
    })
    cards.push({
      label: '筹资现金流净额',
      value: data.financing?.net ?? 0,
      change: null,
      valueClass: (data.financing?.net ?? 0) >= 0 ? 'value-success' : 'value-danger'
    })
    cards.push({
      label: '现金净增加额',
      value: data.net_cash_flow ?? 0,
      change: null,
      valueClass: 'value-primary'
    })
  } else if (activeTab.value === 'account-ledger' && ledgerData.value) {
    const items = ledgerData.value.items || []
    const totalDebit = items.reduce((s, i) => s + (i.current_debit || 0), 0)
    const totalCredit = items.reduce((s, i) => s + (i.current_credit || 0), 0)
    cards.push({
      label: '本期借方合计',
      value: totalDebit,
      change: null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '本期贷方合计',
      value: totalCredit,
      change: null,
      valueClass: 'value-success'
    })
    cards.push({
      label: '借贷差额',
      value: totalDebit - totalCredit,
      change: null,
      valueClass: (totalDebit - totalCredit) === 0 ? 'value-success' : 'value-danger'
    })
    cards.push({
      label: '科目数量',
      value: items.length,
      change: null,
      valueClass: 'value-info'
    })
  } else if (activeTab.value === 'trial-balance' && trialBalanceData.value) {
    const items = trialBalanceData.value.items || []
    const totalCurrentDebit = items.reduce((s, i) => s + (i.current_debit || 0), 0)
    const totalCurrentCredit = items.reduce((s, i) => s + (i.current_credit || 0), 0)
    const totalEndingDebit = items.reduce((s, i) => s + (i.ending_debit || 0), 0)
    const totalEndingCredit = items.reduce((s, i) => s + (i.ending_credit || 0), 0)
    cards.push({
      label: '本期借方合计',
      value: totalCurrentDebit,
      change: null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '本期贷方合计',
      value: totalCurrentCredit,
      change: null,
      valueClass: 'value-success'
    })
    cards.push({
      label: '期末借方合计',
      value: totalEndingDebit,
      change: null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '期末贷方合计',
      value: totalEndingCredit,
      change: null,
      valueClass: 'value-success'
    })
  } else if (activeTab.value === 'trial-balance-summary' && trialBalanceSummaryData.value) {
    const summary = trialBalanceSummaryData.value.summary || {}
    const check = trialBalanceSummaryData.value.balance_check || {}
    const items = trialBalanceSummaryData.value.items || []
    cards.push({
      label: '期初借方合计',
      value: summary.total_beginning_debit ?? 0,
      change: null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '期初贷方合计',
      value: summary.total_beginning_credit ?? 0,
      change: null,
      valueClass: 'value-success'
    })
    cards.push({
      label: '本期借方合计',
      value: summary.total_current_debit ?? 0,
      change: null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '本期贷方合计',
      value: summary.total_current_credit ?? 0,
      change: null,
      valueClass: 'value-success'
    })
    cards.push({
      label: '期末借方合计',
      value: summary.total_ending_debit ?? 0,
      change: null,
      valueClass: 'value-primary'
    })
    cards.push({
      label: '期末贷方合计',
      value: summary.total_ending_credit ?? 0,
      change: null,
      valueClass: 'value-success'
    })
    cards.push({
      label: '借贷差额',
      value: check.ending_diff ?? 0,
      change: null,
      valueClass: Math.abs(check.ending_diff ?? 0) < 0.01 ? 'value-success' : 'value-danger'
    })
    cards.push({
      label: '科目数量',
      value: items.length,
      change: null,
      valueClass: 'value-info'
    })
  }

  return cards
})

// ===== 对比表格数据 =====

const comparisonTableData = computed(() => {
  if (!comparisonData.value) return []
  const periods = comparisonData.value.periods || []
  const current = periods[0] || {}
  const prev = periods[1] || {}
  const lastYear = periods[2] || {}

  const calcChange = (cur, prv) => {
    if (prv == null) return null
    return cur - prv
  }
  const calcChangePct = (cur, prv) => {
    if (prv == null || prv === 0) return null
    return ((cur - prv) / Math.abs(prv)) * 100
  }

  const rows = []

  if (comparisonData.value.report_type === 'balance-sheet') {
    const metrics = [
      { label: '资产总计', cur: current.total_assets, prev: prev.total_assets, ly: lastYear.total_assets },
      { label: '负债合计', cur: current.total_liabilities, prev: prev.total_liabilities, ly: lastYear.total_liabilities },
      { label: '所有者权益', cur: current.total_equity, prev: prev.total_equity, ly: lastYear.total_equity },
      { label: '负债和权益总计', cur: current.total_liabilities_and_equity, prev: prev.total_liabilities_and_equity, ly: lastYear.total_liabilities_and_equity },
    ]
    for (const m of metrics) {
      rows.push({
        label: m.label,
        current: m.cur ?? 0,
        prev: m.prev ?? null,
        lastYear: m.ly ?? null,
        prevChange: m.prev != null ? calcChange(m.cur, m.prev) : null,
        prevChangePct: m.prev != null ? calcChangePct(m.cur, m.prev) : null,
        yoyChange: m.ly != null ? calcChange(m.cur, m.ly) : null,
        yoyChangePct: m.ly != null ? calcChangePct(m.cur, m.ly) : null,
      })
    }
  } else if (comparisonData.value.report_type === 'income-statement') {
    const metrics = [
      { label: '营业收入', cur: current.total_revenue, prev: prev.total_revenue, ly: lastYear.total_revenue },
      { label: '营业费用', cur: current.total_expenses, prev: prev.total_expenses, ly: lastYear.total_expenses },
      { label: '净利润', cur: current.net_profit, prev: prev.net_profit, ly: lastYear.net_profit },
    ]
    for (const m of metrics) {
      rows.push({
        label: m.label,
        current: m.cur ?? 0,
        prev: m.prev ?? null,
        lastYear: m.ly ?? null,
        prevChange: m.prev != null ? calcChange(m.cur, m.prev) : null,
        prevChangePct: m.prev != null ? calcChangePct(m.cur, m.prev) : null,
        yoyChange: m.ly != null ? calcChange(m.cur, m.ly) : null,
        yoyChangePct: m.ly != null ? calcChangePct(m.cur, m.ly) : null,
      })
    }
  }

  return rows
})

// ===== 明细表格数据 =====

const balanceSheetTableData = computed(() => {
  if (!balanceSheetData.value) return []
  return transformBalanceSheet(balanceSheetData.value)
})

const incomeStatementTableData = computed(() => {
  if (!incomeStatementData.value) return []
  return transformIncomeStatement(incomeStatementData.value)
})

const cashFlowTableData = computed(() => {
  if (!cashFlowData.value) return []
  return transformCashFlow(cashFlowData.value)
})

const ledgerTableData = computed(() => {
  if (!ledgerData.value) return []
  return ledgerData.value.items || []
})

const trialBalanceTableData = computed(() => {
  if (!trialBalanceData.value) return []
  return trialBalanceData.value.items || []
})

const trialBalanceSummaryTableData = computed(() => {
  if (!trialBalanceSummaryData.value) return []
  return trialBalanceSummaryData.value.items || []
})

const financialRatiosTableData = computed(() => {
  if (!financialRatiosData.value) return []
  return financialRatiosData.value.ratios || []
})

// ===== 初始化 =====

onMounted(() => {
  if (route.params.type) {
    const validTabs = reportTabs.map(t => t.key)
    if (validTabs.includes(route.params.type)) {
      activeTab.value = route.params.type
    }
  }
  loadAllData()
})

watch(() => route.params.type, (newType) => {
  if (newType && reportTabs.some(t => t.key === newType)) {
    activeTab.value = newType
    loadAllData()
  }
})

// ===== 事件处理 =====

function handleTabChange(tabKey) {
  if (tabKey !== route.params.type) {
    router.replace({ name: 'ReportView', params: { type: tabKey } })
  }
}

function handlePeriodChange() {
  loadAllData()
}

// ===== 数据加载 =====

async function loadAllData() {
  loading.value = true
  try {
    const period = reportPeriod.value
    const params = { period }

    console.log('[ReportView] loadAllData start, tab:', activeTab.value, 'period:', period)

    // 根据当前报表类型加载对应数据
    const promises = []

    if (activeTab.value === 'balance-sheet') {
      promises.push(
        getBalanceSheet(params).then(res => {
          console.log('[ReportView] balanceSheet response:', res.data)
          balanceSheetData.value = res.data
          console.log('[ReportView] balanceSheetData set:', balanceSheetData.value)
        }).catch(err => {
          console.error('[ReportView] balanceSheet error:', err)
        }),
        loadComparison('balance-sheet')
      )
    } else if (activeTab.value === 'income-statement') {
      promises.push(
        getIncomeStatement(params).then(res => {
          console.log('[ReportView] incomeStatement response:', res.data)
          incomeStatementData.value = res.data
        }).catch(err => {
          console.error('[ReportView] incomeStatement error:', err)
        }),
        loadComparison('income-statement')
      )
    } else if (activeTab.value === 'cash-flow') {
      promises.push(
        getCashFlow(params).then(res => {
          console.log('[ReportView] cashFlow response:', res.data)
          cashFlowData.value = res.data
        }).catch(err => {
          console.error('[ReportView] cashFlow error:', err)
        })
      )
    } else if (activeTab.value === 'account-ledger') {
      promises.push(
        getAccountLedger(params).then(res => {
          console.log('[ReportView] ledger response:', res.data)
          ledgerData.value = res.data
        }).catch(err => {
          console.error('[ReportView] ledger error:', err)
        })
      )
    } else if (activeTab.value === 'trial-balance') {
      promises.push(
        getTrialBalance(params).then(res => {
          console.log('[ReportView] trialBalance response:', res.data)
          trialBalanceData.value = res.data
        }).catch(err => {
          console.error('[ReportView] trialBalance error:', err)
        })
      )
    } else if (activeTab.value === 'trial-balance-summary') {
      promises.push(
        getTrialBalanceSummary(params).then(res => {
          console.log('[ReportView] trialBalanceSummary response:', res.data)
          trialBalanceSummaryData.value = res.data
        }).catch(err => {
          console.error('[ReportView] trialBalanceSummary error:', err)
        })
      )
    } else if (activeTab.value === 'financial-ratios') {
      promises.push(
        getFinancialRatios(params).then(res => {
          console.log('[ReportView] financialRatios response:', res.data)
          financialRatiosData.value = res.data
        }).catch(err => {
          console.error('[ReportView] financialRatios error:', err)
        })
      )
    }

    await Promise.all(promises)
    console.log('[ReportView] loadAllData done, balanceSheetData:', balanceSheetData.value, 'comparisonData:', comparisonData.value)
  } catch (error) {
    console.error('[ReportView] loadAllData error:', error)
    ElMessage.error('加载报表数据失败')
  } finally {
    loading.value = false
  }
}

async function loadComparison(reportType) {
  try {
    const periods = comparisonPeriods.value.join(',')
    console.log('[ReportView] loadComparison start, type:', reportType, 'periods:', periods)
    const res = await getComparison(reportType, periods, 'monthly')
    console.log('[ReportView] loadComparison response:', res.data)
    comparisonData.value = res.data
  } catch (error) {
    console.error('[ReportView] loadComparison error:', error)
    comparisonData.value = null
  }
}

// ===== 数据转换 =====

function transformBalanceSheet(data) {
  if (!data) return []
  const rows = []
  let lineNo = 0

  rows.push({ account_name: '资产', is_section: true, line_no: '', ending_balance: '', beginning_balance: '' })
  for (const item of (data.assets || [])) {
    lineNo++
    rows.push({
      account_name: item.account_name,
      account_code: item.account_code,
      line_no: lineNo,
      ending_balance: item.ending_balance,
      beginning_balance: item.beginning_balance ?? null
    })
  }
  rows.push({ account_name: '资产总计', is_total: true, line_no: '', ending_balance: data.total_assets, beginning_balance: null })

  rows.push({ account_name: '负债', is_section: true, line_no: '', ending_balance: '', beginning_balance: '' })
  for (const item of (data.liabilities || [])) {
    lineNo++
    rows.push({
      account_name: item.account_name,
      account_code: item.account_code,
      line_no: lineNo,
      ending_balance: item.ending_balance,
      beginning_balance: item.beginning_balance ?? null
    })
  }
  rows.push({ account_name: '负债合计', is_total: true, line_no: '', ending_balance: data.total_liabilities, beginning_balance: null })

  rows.push({ account_name: '所有者权益', is_section: true, line_no: '', ending_balance: '', beginning_balance: '' })
  for (const item of (data.equity || [])) {
    lineNo++
    rows.push({
      account_name: item.account_name,
      account_code: item.account_code,
      line_no: lineNo,
      ending_balance: item.ending_balance,
      beginning_balance: item.beginning_balance ?? null
    })
  }
  rows.push({ account_name: '所有者权益合计', is_total: true, line_no: '', ending_balance: data.total_equity, beginning_balance: null })

  rows.push({ account_name: '负债和所有者权益总计', is_total: true, is_grand_total: true, line_no: '', ending_balance: data.total_liabilities_and_equity, beginning_balance: null })

  return rows
}

function transformIncomeStatement(data) {
  if (!data) return []
  const rows = []
  let lineNo = 0

  rows.push({ account_name: '一、营业收入', is_section: true, line_no: '', current_amount: '', cumulative_amount: '' })
  for (const item of (data.revenue || [])) {
    lineNo++
    rows.push({
      account_name: item.account_name,
      account_code: item.account_code,
      line_no: lineNo,
      current_amount: item.current_amount,
      cumulative_amount: item.cumulative_amount
    })
  }
  rows.push({ account_name: '营业收入合计', is_total: true, line_no: '', current_amount: data.total_revenue, cumulative_amount: null })

  rows.push({ account_name: '二、营业费用', is_section: true, line_no: '', current_amount: '', cumulative_amount: '' })
  for (const item of (data.expenses || [])) {
    lineNo++
    rows.push({
      account_name: item.account_name,
      account_code: item.account_code,
      line_no: lineNo,
      current_amount: item.current_amount,
      cumulative_amount: item.cumulative_amount
    })
  }
  rows.push({ account_name: '营业费用合计', is_total: true, line_no: '', current_amount: data.total_expenses, cumulative_amount: null })

  rows.push({ account_name: '三、净利润', is_total: true, is_grand_total: true, line_no: '', current_amount: data.net_profit, cumulative_amount: null })

  return rows
}

function transformCashFlow(data) {
  if (!data) return []
  const rows = []
  let lineNo = 0

  const categories = [
    { key: 'operating', label: '一、经营活动产生的现金流量' },
    { key: 'investing', label: '二、投资活动产生的现金流量' },
    { key: 'financing', label: '三、筹资活动产生的现金流量' },
  ]

  for (const cat of categories) {
    const catData = data[cat.key] || {}
    const inflow = catData.inflow || []
    const outflow = catData.outflow || []

    rows.push({ account_name: cat.label, is_section: true, line_no: '', amount: '' })

    if (inflow.length > 0) {
      rows.push({ account_name: '  现金流入小计', is_sub_section: true, line_no: '', amount: '' })
      for (const item of inflow) {
        lineNo++
        const label = item.summary || item.description || item.account_name
        rows.push({
          account_name: `    ${label}`,
          account_code: item.account_code,
          voucher_no: item.voucher_no,
          line_no: lineNo,
          amount: item.amount,
        })
      }
    }

    if (outflow.length > 0) {
      rows.push({ account_name: '  现金流出小计', is_sub_section: true, line_no: '', amount: '' })
      for (const item of outflow) {
        lineNo++
        const label = item.summary || item.description || item.account_name
        rows.push({
          account_name: `    ${label}`,
          account_code: item.account_code,
          voucher_no: item.voucher_no,
          line_no: lineNo,
          amount: -item.amount,
        })
      }
    }

    rows.push({
      account_name: `${cat.label}净额`,
      is_total: true,
      line_no: '',
      amount: catData.net ?? 0,
    })
  }

  rows.push({
    account_name: '现金及现金等价物净增加额',
    is_total: true,
    is_grand_total: true,
    line_no: '',
    amount: data.net_cash_flow ?? 0,
  })

  return rows
}

// ===== 导出 CSV =====

async function handleExportCSV() {
  exporting.value = true
  try {
    const res = await exportReport(activeTab.value, { period: reportPeriod.value })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentReport.value.label}_${reportPeriod.value}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('报表导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// ===== 表格工具方法 =====

function balanceSheetSpanMethod({ row, columnIndex }) {
  if ((row.is_section || row.is_total) && columnIndex === 0) {
    return [1, 4]
  }
  return [1, 1]
}

function tableRowClassName({ row }) {
  if (row.is_section) return 'section-row'
  if (row.is_total) return 'total-row'
  return ''
}

function comparisonRowClass({ rowIndex }) {
  if (rowIndex === 0) return 'comparison-header-row'
  return ''
}

function formatMoney(value) {
  return formatAmount(value)
}

function formatPercent(value) {
  if (value == null || isNaN(value)) return '--'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function accountTypeTag(type) {
  const map = {
    asset: 'primary',
    liability: 'warning',
    equity: 'success',
    revenue: 'info',
    expense: 'danger',
    cost: 'danger'
  }
  return map[type] || 'info'
}

function accountTypeLabel(type) {
  const map = {
    asset: '资产',
    liability: '负债',
    equity: '权益',
    revenue: '收入',
    expense: '费用',
    cost: '成本'
  }
  return map[type] || type
}

function ratioStatusTag(status) {
  const map = { normal: 'success', warning: 'warning', danger: 'danger', unknown: 'info' }
  return map[status] || 'info'
}

function ratioStatusLabel(status) {
  const map = { normal: '正常', warning: '注意', danger: '危险', unknown: '--' }
  return map[status] || '--'
}

function formatRatioValue(value, unit) {
  if (value == null || isNaN(value)) return '--'
  if (unit === '%') return `${value.toFixed(2)}%`
  return value.toFixed(2)
}
</script>

<style scoped>
.report-view {
  max-width: 1200px;
}

.report-header-card {
  margin-bottom: 0;
}

.report-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.report-title-area h2 {
  font-size: 20px;
  color: #303133;
  margin-bottom: 4px;
}

.report-desc {
  font-size: 13px;
  color: #909399;
}

.report-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.report-tabs-card {
  padding: 0;
}

.report-tabs-card :deep(.el-card__body) {
  padding: 0;
}

.report-tabs-card :deep(.el-tabs--border-card) {
  border: none;
  box-shadow: none;
}

/* 汇总卡片 */
.summary-row {
  margin-top: 0;
}

.summary-card {
  cursor: default;
}

.summary-card-content {
  text-align: center;
  padding: 4px 0;
}

.summary-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  margin-bottom: 6px;
}

.value-primary { color: #409eff; }
.value-success { color: #67c23a; }
.value-warning { color: #e6a23c; }
.value-danger { color: #f56c6c; }
.value-info { color: #909399; }

.summary-change {
  font-size: 12px;
}

.change-up {
  color: #f56c6c;
  font-weight: 600;
}

.change-down {
  color: #67c23a;
  font-weight: 600;
}

.change-label {
  color: #c0c4cc;
  margin-left: 4px;
}

.text-muted {
  color: #c0c4cc;
}

/* 内容卡片 */
.report-content-card {
  min-height: 200px;
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

/* 表格行样式 */
:deep(.section-row) {
  background-color: #f5f7fa;
  font-weight: 600;
}

:deep(.total-row) {
  background-color: #fafafa;
  font-weight: 600;
}

:deep(.total-row td) {
  border-top: 2px solid #909399 !important;
}

:deep(.comparison-header-row) {
  background-color: #ecf5ff;
}

.total-amount {
  font-weight: 700;
  color: #303133;
}

/* 财务指标卡片 */
.ratio-card {
  cursor: default;
  height: 180px;
}

.ratio-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.ratio-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.ratio-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.ratio-value {
  font-size: 28px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  margin-bottom: 6px;
}

.ratio-normal { color: #67c23a; }
.ratio-warning { color: #e6a23c; }
.ratio-danger { color: #f56c6c; }
.ratio-unknown { color: #909399; }

.ratio-formula {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}

.ratio-reference {
  font-size: 11px;
  color: #c0c4cc;
  margin-bottom: 2px;
}

.ratio-desc {
  font-size: 11px;
  color: #909399;
}

.ratio-summary-card {
  background-color: #fafafa;
}
</style>