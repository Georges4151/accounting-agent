<template>
  <div class="tax-manage">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 税务计算 -->
      <el-tab-pane label="税务计算" name="calculate">
        <TaxCalculate />
      </el-tab-pane>

      <!-- 申报记录 -->
      <el-tab-pane label="申报记录" name="records">
        <TaxRecords />
      </el-tab-pane>

      <!-- 税负分析 -->
      <el-tab-pane label="税负分析" name="analysis">
        <TaxAnalysis />
      </el-tab-pane>

      <!-- 截止提醒 -->
      <el-tab-pane label="截止提醒" name="deadlines">
        <TaxDeadlines />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import TaxCalculate from './components/TaxCalculate.vue'
import TaxRecords from './components/TaxRecords.vue'
import TaxAnalysis from './components/TaxAnalysis.vue'
import TaxDeadlines from './components/TaxDeadlines.vue'

const activeTab = ref('calculate')
</script>

<style scoped>
.tax-manage {
  height: 100%;
}
</style>