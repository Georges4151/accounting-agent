<template>
  <!-- 录入凭证页面 - Excel式交互 -->
  <div class="voucher-create">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ isEdit ? '编辑凭证' : '录入凭证' }}</span>
          <div class="header-actions">
            <span v-if="lastAutoSaveTime" class="auto-save-status">
              <el-icon v-if="isAutoSaving" class="is-loading"><Loading /></el-icon>
              <el-icon v-else><CircleCheck /></el-icon>
              {{ isAutoSaving ? '自动保存中...' : `已自动保存 ${lastAutoSaveTime}` }}
            </span>
            <el-button @click="openTemplateSelector">
              <el-icon><Files /></el-icon>
              从模板创建
            </el-button>
            <el-button @click="handleAiGenerate" :loading="aiGenerating">
              <el-icon><MagicStick /></el-icon>
              AI 生成
            </el-button>
            <el-button type="primary" @click="handleSave" :loading="saving">
              <el-icon><Document /></el-icon>
              保存草稿
            </el-button>
            <el-button type="success" @click="handleSubmit" :loading="submitting">
              <el-icon><Select /></el-icon>
              提交审核
            </el-button>
          </div>
        </div>
      </template>

      <!-- 键盘快捷键提示 -->
      <el-alert
        title="键盘操作: Tab 跳下一格 | Enter 新行/下一行 | 方向键 导航 | 在表格区域 Ctrl+V 从Excel粘贴"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      />

      <!-- 凭证基本信息 -->
      <el-form :model="voucherForm" label-width="80px" class="voucher-info-form">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="凭证字">
              <el-select v-model="voucherForm.voucher_type" style="width: 100%">
                <el-option label="记" value="记" />
                <el-option label="转" value="转" />
                <el-option label="收" value="收" />
                <el-option label="付" value="付" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="日期">
              <el-date-picker
                v-model="voucherForm.voucher_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="摘要">
              <div style="display: flex; gap: 8px; width: 100%">
                <el-input
                  v-model="voucherForm.summary"
                  placeholder="凭证摘要"
                  clearable
                  style="flex: 1"
                  @keydown.enter.prevent="focusFirstEntryCell"
                />
                <el-button
                  type="primary"
                  :loading="suggesting"
                  :disabled="!voucherForm.summary.trim()"
                  @click="handleAiSuggest"
                >
                  <el-icon><MagicStick /></el-icon>
                  AI建议科目
                </el-button>
              </div>
              <div v-if="suggestionResult" class="suggestion-tip">
                <el-tag type="success" size="small" effect="plain">
                  推荐: {{ suggestionResult.account_code }} {{ suggestionResult.account_name }}
                  ({{ (suggestionResult.confidence * 100).toFixed(0) }}%)
                </el-tag>
                <span class="suggestion-reason">{{ suggestionResult.reason }}</span>
                <el-button type="primary" size="small" text @click="applySuggestion">应用</el-button>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <!-- 分录明细表 - Excel式交互 -->
      <div class="entry-table-wrapper" @paste="handlePaste">
        <el-table
          :data="entries"
          border
          stripe
          style="width: 100%; margin-top: 16px"
          row-key="__rowKey"
        >
          <el-table-column label="#" width="40" align="center">
            <template #default="{ $index }">
              <span class="row-number">{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="科目代码" width="220">
            <template #default="{ row, $index }">
              <el-tree-select
                v-model="row.account_code"
                :data="accountTreeData"
                :render-after-expand="false"
                :filter-node-method="filterAccountNode"
                filterable
                clearable
                check-strictly
                placeholder="选择科目"
                style="width: 100%"
                :props="{ value: 'code', label: 'label', children: 'children' }"
                @change="(val) => { onAccountChange($index, val); clearRowSuggestion($index); markDirty(); }"
                @keydown="(e) => handleCellKeydown(e, $index, 'account_code')"
                @visible-change="(visible) => { if (!visible) afterCellEdit($index, 'account_code'); }"
                :ref="(el) => setCellRef($index, 'account_code', el)"
              />
            </template>
          </el-table-column>
          <el-table-column label="科目名称" width="150">
            <template #default="{ row }">
              <span class="account-name-display">{{ row.account_name || '--' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="借方金额" width="180">
            <template #default="{ row, $index }">
              <el-input-number
                v-model="row.debit_amount"
                :min="0"
                :precision="2"
                :controls="false"
                placeholder="0.00"
                style="width: 140px"
                @change="() => { recalculateTotals(); markDirty(); }"
                @keydown="(e) => handleCellKeydown(e, $index, 'debit_amount')"
                :ref="(el) => setCellRef($index, 'debit_amount', el)"
              />
            </template>
          </el-table-column>
          <el-table-column label="贷方金额" width="180">
            <template #default="{ row, $index }">
              <el-input-number
                v-model="row.credit_amount"
                :min="0"
                :precision="2"
                :controls="false"
                placeholder="0.00"
                style="width: 140px"
                @change="() => { recalculateTotals(); markDirty(); }"
                @keydown="(e) => handleCellKeydown(e, $index, 'credit_amount')"
                :ref="(el) => setCellRef($index, 'credit_amount', el)"
              />
            </template>
          </el-table-column>
          <el-table-column label="现金流量" width="100" align="center">
            <template #default="{ row, $index }">
              <el-select
                v-model="row.cash_flow_tag"
                placeholder="标记"
                clearable
                size="small"
                style="width: 90px"
                @change="markDirty"
                @keydown="(e) => handleCellKeydown(e, $index, 'cash_flow_tag')"
              >
                <el-option label="经营" value="operating" />
                <el-option label="投资" value="investing" />
                <el-option label="筹资" value="financing" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="辅助核算" width="90" align="center">
            <template #default="{ row, $index }">
              <el-popover
                placement="bottom"
                :width="300"
                trigger="click"
                :visible="auxPopoverIndex === $index"
                @show="openAuxPopover($index)"
                @hide="auxPopoverIndex = -1"
              >
                <template #reference>
                  <el-button
                    size="small"
                    :type="row.auxiliary_accounting && Object.keys(row.auxiliary_accounting).length > 0 ? 'primary' : 'default'"
                    text
                  >
                    <el-icon><Setting /></el-icon>
                  </el-button>
                </template>
                <el-form :model="auxForm" label-width="70px" size="small">
                  <el-form-item label="客户">
                    <el-input v-model="auxForm.customer" placeholder="客户名称" clearable />
                  </el-form-item>
                  <el-form-item label="供应商">
                    <el-input v-model="auxForm.supplier" placeholder="供应商名称" clearable />
                  </el-form-item>
                  <el-form-item label="部门">
                    <el-input v-model="auxForm.department" placeholder="部门名称" clearable />
                  </el-form-item>
                  <el-form-item label="项目">
                    <el-input v-model="auxForm.project" placeholder="项目名称" clearable />
                  </el-form-item>
                  <el-form-item label="员工">
                    <el-input v-model="auxForm.employee" placeholder="员工姓名" clearable />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" size="small" @click="applyAuxiliary($index)">应用</el-button>
                    <el-button size="small" @click="auxPopoverIndex = -1">取消</el-button>
                  </el-form-item>
                </el-form>
              </el-popover>
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="250">
            <template #default="{ row, $index }">
              <div class="summary-cell">
                <el-input
                  v-model="row.summary"
                  placeholder="分录摘要"
                  clearable
                  @change="markDirty"
                  @input="(val) => onSummaryInput($index, val)"
                  @focus="() => onSummaryFocus($index)"
                  @keydown="(e) => handleCellKeydown(e, $index, 'summary')"
                  :ref="(el) => setCellRef($index, 'summary', el)"
                />
                <!-- AI 科目建议标签 -->
                <div v-if="rowSuggestions[$index] && !row.account_code" class="ai-row-suggestion">
                  <el-icon v-if="suggestingRow === $index" class="is-loading"><Loading /></el-icon>
                  <el-icon v-else><MagicStick /></el-icon>
                  <span class="suggestion-text">
                    {{ rowSuggestions[$index].account_code }} {{ rowSuggestions[$index].account_name }}
                  </span>
                  <el-button type="primary" size="small" text @click="applyRowSuggestion($index)">
                    选这个
                  </el-button>
                </div>
                <!-- AI 摘要建议标签 -->
                <div v-if="summarySuggestions[$index] && summarySuggestions[$index].length > 0" class="ai-summary-suggestions">
                  <div class="summary-suggest-header">
                    <el-icon><MagicStick /></el-icon>
                    <span>AI 摘要建议</span>
                  </div>
                  <div class="summary-suggest-chips">
                    <el-tag
                      v-for="(item, si) in summarySuggestions[$index]"
                      :key="si"
                      :type="si === 0 ? 'primary' : 'info'"
                      size="small"
                      effect="plain"
                      class="summary-suggest-chip"
                      @click="applySummarySuggestion($index, item.summary)"
                    >
                      {{ item.summary }}
                      <span class="chip-count">({{ item.usage_count }}次)</span>
                    </el-tag>
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ $index }">
              <el-button
                text
                type="danger"
                size="small"
                :disabled="entries.length <= 1"
                @click="removeEntry($index)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 添加分录行按钮 -->
      <div style="margin-top: 12px; display: flex; gap: 8px; align-items: center">
        <el-button type="primary" text @click="addEntryAndFocus">
          <el-icon><Plus /></el-icon>
          添加分录行 (Enter)
        </el-button>
        <el-button text @click="handlePasteFromClipboard">
          <el-icon><DocumentCopy /></el-icon>
          从剪贴板粘贴
        </el-button>
        <span class="shortcut-hint">在表格区域按 Ctrl+V 可直接粘贴Excel数据</span>
      </div>

      <!-- 合计信息 - 实时借贷平衡检查 -->
      <div class="totals-bar" :class="{ 'totals-bar--unbalanced': !isBalanced && (totalDebit > 0 || totalCredit > 0), 'totals-bar--balanced': isBalanced && totalDebit > 0 }">
        <div class="total-item">
          <span class="total-label">借方合计：</span>
          <span class="total-value debit">{{ formatMoney(totalDebit) }}</span>
        </div>
        <div class="total-item">
          <span class="total-label">贷方合计：</span>
          <span class="total-value credit">{{ formatMoney(totalCredit) }}</span>
        </div>
        <div class="total-item">
          <span class="total-label">差额：</span>
          <span class="total-value" :class="{ unbalanced: !isBalanced }">
            {{ formatMoney(Math.abs(totalDebit - totalCredit)) }}
          </span>
          <el-tag
            v-if="!isBalanced && (totalDebit > 0 || totalCredit > 0)"
            type="danger"
            size="small"
            effect="dark"
            class="balance-warning-tag"
          >
            借贷不平衡
          </el-tag>
          <el-tag
            v-else-if="isBalanced && totalDebit > 0"
            type="success"
            size="small"
            effect="dark"
          >
            借贷平衡
          </el-tag>
        </div>
      </div>

      <!-- 不平衡时显示醒目提示 -->
      <el-alert
        v-if="!isBalanced && (totalDebit > 0 || totalCredit > 0)"
        :title="`借贷不平衡！借方 ${formatMoney(totalDebit)} ≠ 贷方 ${formatMoney(totalCredit)}，差额 ${formatMoney(Math.abs(totalDebit - totalCredit))}`"
        type="error"
        :closable="false"
        show-icon
        style="margin-top: 12px"
      />

      <!-- 附件区域 -->
      <el-divider />
      <div class="attachment-section">
        <div class="attachment-header">
          <span class="attachment-title">
            <el-icon><Paperclip /></el-icon>
            附件
          </span>
          <span class="attachment-hint">支持 jpg/png/gif/pdf/doc/docx/xlsx 文件，单个文件不超过10MB</span>
        </div>

        <!-- 上传区域 -->
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="20"
          :on-change="handleAttachmentChange"
          :on-exceed="handleAttachmentExceed"
          :on-remove="handleAttachmentRemove"
          :file-list="pendingFiles"
          :before-upload="beforeAttachmentUpload"
          accept=".jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.xlsx,.xls"
          drag
          multiple
          action="#"
          class="attachment-upload"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            将文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              文件大小限制：10MB，支持图片预览
            </div>
          </template>
        </el-upload>

        <!-- 已上传附件列表 -->
        <div v-if="existingAttachments.length > 0" class="attachment-list">
          <div class="attachment-list-header">
            <span>已上传附件 ({{ existingAttachments.length }})</span>
          </div>
          <div class="attachment-items">
            <div
              v-for="(att, index) in existingAttachments"
              :key="att.filename"
              class="attachment-item"
            >
              <!-- 图片预览 -->
              <div class="attachment-preview">
                <el-image
                  v-if="isImageFile(att.filename)"
                  :src="getAttachmentUrl(route.query.id, att.filename)"
                  :preview-src-list="[getAttachmentUrl(route.query.id, att.filename)]"
                  fit="cover"
                  class="attachment-thumb"
                >
                  <template #error>
                    <el-icon :size="32"><PictureFilled /></el-icon>
                  </template>
                </el-image>
                <el-icon v-else :size="32" :color="getFileIconColor(att.filename)">
                  <Document />
                </el-icon>
              </div>
              <!-- 文件信息 -->
              <div class="attachment-info">
                <span class="attachment-name" :title="att.filename">
                  <el-link type="primary" :underline="false" @click="handleDownloadAttachment(att.filename)">
                    {{ att.filename }}
                  </el-link>
                </span>
                <span class="attachment-meta">
                  {{ formatFileSize(att.size) }}
                  <span v-if="att.uploaded_at"> · {{ formatUploadTime(att.uploaded_at) }}</span>
                </span>
              </div>
              <!-- 删除按钮 -->
              <el-button
                type="danger"
                text
                size="small"
                :loading="deletingAttachment === att.filename"
                @click="handleDeleteExistingAttachment(att.filename, index)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <el-empty v-else-if="!isEdit" description="暂无附件，请上传" :image-size="40" />
      </div>
    </el-card>

    <!-- AI 生成对话框 -->
    <el-dialog v-model="aiDialogVisible" title="AI 智能生成凭证" width="600px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="自然语言描述">
          <el-input
            v-model="aiDescription"
            type="textarea"
            :rows="4"
            placeholder="例如：1月15日从银行提取现金5000元，销售商品收入10000元已存入银行..."
          />
        </el-form-item>
        <el-form-item label="凭证日期">
          <el-date-picker
            v-model="aiDate"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiGenerating" @click="executeAiGenerate">生成凭证</el-button>
      </template>
    </el-dialog>

    <!-- 模板选择器对话框 -->
    <el-dialog v-model="templateDialogVisible" title="从模板创建凭证" width="800px" :close-on-click-modal="false">
      <el-radio-group v-model="templateCategoryFilter" size="small" style="margin-bottom: 16px" @change="loadTemplateList">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="收入">收入</el-radio-button>
        <el-radio-button value="支出">支出</el-radio-button>
        <el-radio-button value="转账">转账</el-radio-button>
        <el-radio-button value="其他">其他</el-radio-button>
      </el-radio-group>
      <div v-loading="templateLoading" class="template-selector-grid">
        <div
          v-for="tpl in templateList"
          :key="tpl.id"
          class="template-selector-item"
          @click="applyTemplateToForm(tpl)"
        >
          <div class="tpl-name">{{ tpl.name }}</div>
          <div class="tpl-desc">{{ tpl.description || '暂无描述' }}</div>
          <div class="tpl-meta">
            <el-tag size="small" :type="getTemplateCategoryType(tpl.category)">{{ tpl.category }}</el-tag>
            <span>{{ tpl.item_count }} 条分录</span>
          </div>
        </div>
        <el-empty v-if="!templateLoading && templateList.length === 0" description="暂无模板" />
      </div>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getVoucher, createVoucher, updateVoucher, submitVoucher, aiGenerateVoucher, uploadAttachments, getAttachments, deleteAttachment, getAttachmentUrl, downloadAttachment } from '@/api/voucher'
import { getTemplates, getTemplate } from '@/api/voucherTemplate'
import request from '@/api/request'
import { useAmountMask } from '@/composables/useAmountMask'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { formatAmount } = useAmountMask()

// ===== 常量 =====

// 可编辑的列（按Tab导航顺序）
const EDITABLE_COLS = ['account_code', 'debit_amount', 'credit_amount', 'cash_flow_tag', 'summary']

// 自动保存防抖延迟（毫秒）
const AUTO_SAVE_DELAY = 3000

// ===== 状态 =====

const isEdit = computed(() => !!route.query.id)
const saving = ref(false)
const submitting = ref(false)

// 凭证表单
const voucherForm = reactive({
  voucher_type: '记',
  voucher_date: '',
  summary: ''
})

// 分录列表 - 每行添加唯一 key
let rowKeyCounter = 0
function createEntry(data = {}) {
  return {
    __rowKey: ++rowKeyCounter,
    account_code: data.account_code || '',
    account_name: data.account_name || '',
    debit_amount: data.debit_amount || 0,
    credit_amount: data.credit_amount || 0,
    cash_flow_tag: data.cash_flow_tag || '',
    auxiliary_accounting: data.auxiliary_accounting || null,
    summary: data.summary || ''
  }
}

const entries = ref([createEntry()])

// 科目选项
const accountOptions = ref([])
const accountTreeData = ref([])

// 构建树形数据的label（含层级缩进）
function buildTreeLabels(tree, depth = 0) {
  const prefix = depth > 0 ? '\u00A0\u00A0'.repeat(depth) + '\u2514 ' : ''
  return tree.map(node => ({
    ...node,
    label: `${prefix}${node.code} ${node.name}`,
    children: node.children ? buildTreeLabels(node.children, depth + 1) : []
  }))
}

// 树形筛选
function filterAccountNode(value, data) {
  if (!value) return true
  const label = `${data.code} ${data.name}`.toLowerCase()
  return label.includes(value.toLowerCase())
}

// 页面加载状态
const pageLoading = ref(false)

// ===== Excel式交互：单元格引用管理 =====

const cellRefs = {}

function setCellRef(rowIndex, colKey, el) {
  if (el) {
    cellRefs[`${rowIndex}-${colKey}`] = el
  }
}

function getCellRef(rowIndex, colKey) {
  return cellRefs[`${rowIndex}-${colKey}`]
}

function focusCell(rowIndex, colKey) {
  nextTick(() => {
    const el = getCellRef(rowIndex, colKey)
    if (el) {
      // Element Plus 组件暴露 focus 方法
      if (typeof el.focus === 'function') {
        el.focus()
      } else if (el.$el) {
        // 兼容不同版本
        const input = el.$el.querySelector('input')
        if (input) input.focus()
      }
    }
  })
}

function focusNextCell(rowIndex, colIdx) {
  const nextColIdx = colIdx + 1
  if (nextColIdx < EDITABLE_COLS.length) {
    focusCell(rowIndex, EDITABLE_COLS[nextColIdx])
  } else if (rowIndex < entries.value.length - 1) {
    focusCell(rowIndex + 1, EDITABLE_COLS[0])
  }
}

function focusPrevCell(rowIndex, colIdx) {
  const prevColIdx = colIdx - 1
  if (prevColIdx >= 0) {
    focusCell(rowIndex, EDITABLE_COLS[prevColIdx])
  } else if (rowIndex > 0) {
    focusCell(rowIndex - 1, EDITABLE_COLS[EDITABLE_COLS.length - 1])
  }
}

function focusFirstEntryCell() {
  focusCell(0, 'account_code')
}

// ===== Excel式交互：键盘导航 =====

function handleCellKeydown(e, rowIndex, colKey) {
  const colIdx = EDITABLE_COLS.indexOf(colKey)

  switch (e.key) {
    case 'Tab':
      e.preventDefault()
      if (e.shiftKey) {
        focusPrevCell(rowIndex, colIdx)
      } else {
        focusNextCell(rowIndex, colIdx)
      }
      break
    case 'Enter':
      // 对于 el-select，Enter 键用于选择选项，不拦截（除非下拉已关闭）
      if (colKey === 'account_code') {
        // el-select 的 Enter 在 filterable 模式下用于选择，不拦截
        // 让 el-select 自己处理
        return
      }
      e.preventDefault()
      if (rowIndex === entries.value.length - 1) {
        // 最后一行：添加新行并聚焦新行的同一列
        addEntry()
        nextTick(() => {
          focusCell(entries.value.length - 1, colKey)
        })
      } else {
        // 跳转到下一行同一列
        focusCell(rowIndex + 1, colKey)
      }
      break
    case 'ArrowUp':
      if (rowIndex > 0) {
        e.preventDefault()
        focusCell(rowIndex - 1, colIdx)
      }
      break
    case 'ArrowDown':
      if (rowIndex < entries.value.length - 1) {
        e.preventDefault()
        focusCell(rowIndex + 1, colIdx)
      }
      break
    case 'ArrowLeft':
      // 光标在输入框开头时才跳转到上一格
      if (colKey === 'summary' || colKey === 'debit_amount' || colKey === 'credit_amount') {
        const input = e.target
        if (input.selectionStart === 0) {
          e.preventDefault()
          focusPrevCell(rowIndex, colIdx)
        }
      }
      break
    case 'ArrowRight':
      // 光标在输入框末尾时才跳转到下一格
      if (colKey === 'summary' || colKey === 'debit_amount' || colKey === 'credit_amount') {
        const input = e.target
        if (input.selectionStart === input.value.length) {
          e.preventDefault()
          focusNextCell(rowIndex, colIdx)
        }
      }
      break
    case 'Escape':
      e.target.blur()
      break
  }
}

// 单元格编辑完成后触发
function afterCellEdit(rowIndex, colKey) {
  // 科目选择完成后，自动跳转到借方金额
  if (colKey === 'account_code') {
    nextTick(() => {
      focusCell(rowIndex, 'debit_amount')
    })
  }
}

// ===== Excel式交互：粘贴 =====

async function handlePaste(e) {
  const clipboardData = e.clipboardData
  if (!clipboardData) return

  const text = clipboardData.getData('text/plain')
  if (!text || !text.trim()) return

  // 检测是否为表格数据（包含制表符或换行符）
  if (!text.includes('\t') && !text.includes('\n')) return

  e.preventDefault()
  parseAndFillFromClipboard(text)
}

async function handlePasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText()
    if (!text || !text.trim()) {
      ElMessage.warning('剪贴板为空')
      return
    }
    parseAndFillFromClipboard(text)
  } catch {
    ElMessage.warning('无法读取剪贴板，请使用 Ctrl+V 在表格区域粘贴')
  }
}

function parseAndFillFromClipboard(text) {
  const lines = text.trim().split(/\r?\n/).filter(line => line.trim())
  if (lines.length === 0) return

  // 解析每一行
  const parsedRows = lines.map(line => {
    const cols = line.split('\t')
    return {
      account_code: (cols[0] || '').trim(),
      account_name: (cols[1] || '').trim(),
      debit_amount: parseFloat(cols[2]) || 0,
      credit_amount: parseFloat(cols[3]) || 0,
      summary: (cols[4] || '').trim()
    }
  })

  // 过滤掉看起来像表头的行（科目代码不包含数字）
  const dataRows = parsedRows.filter(row => {
    return row.account_code && /\d/.test(row.account_code)
  })

  if (dataRows.length === 0) {
    // 尝试宽松匹配：如果第一列看起来像科目代码
    const allRows = parsedRows.filter(row => row.account_code)
    if (allRows.length === 0) {
      ElMessage.warning('未识别到有效的科目数据，请确保第一列为科目代码')
      return
    }
    // 第一行可能是表头，跳过
    const skipHeader = !/\d/.test(allRows[0].account_code)
    const rows = skipHeader ? allRows.slice(1) : allRows
    fillEntriesFromPaste(rows)
  } else {
    fillEntriesFromPaste(dataRows)
  }
}

function fillEntriesFromPaste(rows) {
  // 清空现有分录，用粘贴的数据填充
  entries.value = rows.map(row => {
    // 自动匹配科目名称
    const account = accountOptions.value.find(a => a.code === row.account_code)
    return createEntry({
      account_code: row.account_code,
      account_name: account ? account.name : row.account_name,
      debit_amount: row.debit_amount,
      credit_amount: row.credit_amount,
      summary: row.summary || voucherForm.summary
    })
  })

  // 确保至少有一行
  if (entries.value.length === 0) {
    entries.value = [createEntry()]
  }

  markDirty()
  ElMessage.success(`已粘贴 ${entries.value.length} 条分录`)
}

// ===== Excel式交互：自动保存 =====

const isDirty = ref(false)
const isAutoSaving = ref(false)
const lastAutoSaveTime = ref('')
let autoSaveTimer = null

function markDirty() {
  isDirty.value = true
  scheduleAutoSave()
}

function scheduleAutoSave() {
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(performAutoSave, AUTO_SAVE_DELAY)
}

async function performAutoSave() {
  // 需要至少填写了日期或摘要才自动保存
  if (!voucherForm.voucher_date && !voucherForm.summary.trim()) return
  if (!isDirty.value) return

  // 至少需要2条有效分录（借贷记账法），否则等用户填完再保存
  const validCount = entries.value.filter(e => e.account_code).length
  if (validCount < 2) return

  isAutoSaving.value = true
  try {
    const data = buildVoucherData()

    if (isEdit.value) {
      await updateVoucher(route.query.id, data)
    } else {
      const res = await createVoucher(data)
      // 首次保存后更新URL，后续自动保存用 update
      router.replace(`/voucher/create?id=${res.data.id}`)
    }

    isDirty.value = false
    const now = new Date()
    lastAutoSaveTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    // 自动保存失败不弹窗，静默处理
  } finally {
    isAutoSaving.value = false
  }
}

// 监听表单变化，触发自动保存
watch(
  () => [
    voucherForm.voucher_date,
    voucherForm.summary,
    entries.value.map(e => ({
      code: e.account_code,
      debit: e.debit_amount,
      credit: e.credit_amount,
      summary: e.summary
    }))
  ],
  () => {
    markDirty()
  },
  { deep: true }
)

// ===== 计算属性 =====

const totalDebit = computed(() => {
  return entries.value.reduce((sum, entry) => sum + (entry.debit_amount || 0), 0)
})

const totalCredit = computed(() => {
  return entries.value.reduce((sum, entry) => sum + (entry.credit_amount || 0), 0)
})

const isBalanced = computed(() => {
  return Math.abs(totalDebit.value - totalCredit.value) < 0.01
})

// ===== 生命周期 =====

onMounted(async () => {
  await loadAccounts()
  if (isEdit.value) {
    await loadVoucher(route.query.id)
  } else {
    // 设置默认日期为今天
    if (!voucherForm.voucher_date) {
      const today = new Date()
      voucherForm.voucher_date = today.toISOString().split('T')[0]
    }
  }
})

onBeforeUnmount(() => {
  // 页面离开前执行一次自动保存
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    if (isDirty.value) {
      performAutoSave()
    }
  }
})

// ===== 数据加载 =====

async function loadAccounts() {
  try {
    const res = await request.get('/vouchers/accounts')
    accountOptions.value = res.data.accounts || []
  } catch {
    accountOptions.value = [
      { code: '1001', name: '库存现金' },
      { code: '1002', name: '银行存款' },
      { code: '1122', name: '应收账款' },
      { code: '1403', name: '原材料' },
      { code: '1405', name: '库存商品' },
      { code: '1601', name: '固定资产' },
      { code: '2001', name: '短期借款' },
      { code: '2202', name: '应付账款' },
      { code: '4001', name: '实收资本' },
      { code: '5001', name: '主营业务收入' },
      { code: '5401', name: '主营业务成本' },
      { code: '5501', name: '销售费用' },
      { code: '5502', name: '管理费用' },
      { code: '5503', name: '财务费用' },
      { code: '6602', name: '管理费用' },
      { code: '6603', name: '财务费用' }
    ]
  }

  // 加载树形数据
  try {
    const treeRes = await request.get('/vouchers/accounts/tree')
    accountTreeData.value = buildTreeLabels(treeRes.data.tree || [])
  } catch {
    // 降级到平铺数据
    accountTreeData.value = accountOptions.value.map(a => ({
      code: a.code,
      name: a.name,
      label: `${a.code} ${a.name}`,
      children: []
    }))
  }
}

async function loadVoucher(id) {
  pageLoading.value = true
  try {
    const res = await getVoucher(id)
    const data = res.data
    voucherForm.voucher_type = data.voucher_type || '记'
    voucherForm.voucher_date = data.voucher_date
    voucherForm.summary = data.summary
    entries.value = (data.items && data.items.length > 0)
      ? data.items.map(item => createEntry({
          account_code: item.account_code,
          account_name: item.account_name,
          debit_amount: item.debit_amount,
          credit_amount: item.credit_amount,
          cash_flow_tag: item.cash_flow_tag || '',
          auxiliary_accounting: item.auxiliary_accounting || null,
          summary: item.description || ''
        }))
      : [createEntry()]
  } catch {
    ElMessage.error('加载凭证失败')
  } finally {
    pageLoading.value = false
  }
  // 为已有科目的分录行触发摘要建议
  entries.value.forEach((entry, idx) => {
    if (entry.account_code) {
      scheduleSummarySuggestion(idx, '')
    }
  })
  // 加载已有附件
  await loadExistingAttachments(id)
}

// ===== 分录操作 =====

function addEntry() {
  entries.value.push(createEntry())
}

function addEntryAndFocus() {
  addEntry()
  nextTick(() => {
    focusCell(entries.value.length - 1, 'account_code')
  })
}

function removeEntry(index) {
  // 删除前清理该行的 ref
  EDITABLE_COLS.forEach(col => {
    delete cellRefs[`${index}-${col}`]
  })
  entries.value.splice(index, 1)
  recalculateTotals()
  markDirty()
}

function onAccountChange(index, accountCode) {
  const account = accountOptions.value.find(a => a.code === accountCode)
  if (account) {
    entries.value[index].account_name = account.name
  } else {
    entries.value[index].account_name = ''
  }
  // 科目变更后，触发摘要建议
  if (accountCode) {
    scheduleSummarySuggestion(index, '')
  } else {
    delete summarySuggestions[index]
  }
}

function recalculateTotals() {
  // 合计为计算属性，自动更新
}

// ===== 附件管理 =====

const existingAttachments = ref([])       // 已上传的附件列表
const pendingFiles = ref([])              // 待上传的文件列表
const uploadingAttachments = ref(false)   // 是否正在上传
const deletingAttachment = ref(null)      // 正在删除的附件文件名

// 文件类型判断
function isImageFile(filename) {
  const ext = (filename || '').toLowerCase().split('.').pop()
  return ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext)
}

function getFileIconColor(filename) {
  const ext = (filename || '').toLowerCase().split('.').pop()
  const colorMap = {
    pdf: '#e74c3c',
    doc: '#2980b9',
    docx: '#2980b9',
    xls: '#27ae60',
    xlsx: '#27ae60',
  }
  return colorMap[ext] || '#909399'
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatUploadTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// 上传前校验
function beforeAttachmentUpload(file) {
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.warning(`文件 ${file.name} 超过10MB限制`)
    return false
  }
  const allowedExts = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xlsx', 'xls']
  const ext = file.name.split('.').pop().toLowerCase()
  if (!allowedExts.includes(ext)) {
    ElMessage.warning(`文件 ${file.name} 类型不支持`)
    return false
  }
  return true
}

function handleAttachmentChange(file, fileList) {
  pendingFiles.value = fileList
}

function handleAttachmentExceed() {
  ElMessage.warning('附件数量已达上限（20个）')
}

function handleAttachmentRemove(file, fileList) {
  pendingFiles.value = fileList
}

// 批量上传待上传的文件
async function uploadPendingAttachments(voucherId) {
  const files = pendingFiles.value.map(f => f.raw).filter(Boolean)
  if (files.length === 0) return

  uploadingAttachments.value = true
  try {
    await uploadAttachments(voucherId, files)
    pendingFiles.value = []
    // 重新加载附件列表
    await loadExistingAttachments(voucherId)
    ElMessage.success(`已上传 ${files.length} 个附件`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '附件上传失败')
  } finally {
    uploadingAttachments.value = false
  }
}

// 加载已有附件
async function loadExistingAttachments(voucherId) {
  try {
    const res = await getAttachments(voucherId)
    existingAttachments.value = res.data.attachments || []
  } catch {
    existingAttachments.value = []
  }
}

// 删除已上传的附件
async function handleDeleteExistingAttachment(filename, index) {
  const voucherId = route.query.id
  if (!voucherId) return

  try {
    await ElMessageBox.confirm(`确定要删除附件"${filename}"吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  deletingAttachment.value = filename
  try {
    await deleteAttachment(voucherId, filename)
    existingAttachments.value.splice(index, 1)
    ElMessage.success('附件已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  } finally {
    deletingAttachment.value = null
  }
}

// 下载附件
function handleDownloadAttachment(filename) {
  const voucherId = route.query.id
  if (!voucherId) return
  downloadAttachment(voucherId, filename)
}

// ===== 保存和提交 =====

async function handleSave() {
  if (!validateForm()) return

  saving.value = true
  try {
    const data = buildVoucherData()

    let voucherId = route.query.id
    if (isEdit.value) {
      await updateVoucher(voucherId, data)
      ElMessage.success('凭证已更新')
    } else {
      const res = await createVoucher(data)
      voucherId = res.data.id
      ElMessage.success('凭证已保存为草稿')
      router.replace(`/voucher/create?id=${voucherId}`)
    }

    // 上传待上传的附件
    if (voucherId && pendingFiles.value.length > 0) {
      await uploadPendingAttachments(voucherId)
    }

    isDirty.value = false
    lastAutoSaveTime.value = ''
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleSubmit() {
  if (!validateForm()) return

  try {
    await ElMessageBox.confirm('确定要提交审核吗？提交后不可修改。', '提交审核', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    submitting.value = true
    let voucherId = route.query.id

    if (isEdit.value) {
      await updateVoucher(voucherId, buildVoucherData())
    } else {
      const res = await createVoucher(buildVoucherData())
      voucherId = res.data.id
    }

    // 上传待上传的附件
    if (voucherId && pendingFiles.value.length > 0) {
      await uploadPendingAttachments(voucherId)
    }

    await submitVoucher(voucherId)
    ElMessage.success('凭证已提交审核')
    router.push('/voucher/list')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '提交失败')
    }
  } finally {
    submitting.value = false
  }
}

function validateForm() {
  if (!voucherForm.voucher_date) {
    ElMessage.warning('请选择凭证日期')
    return false
  }
  if (!voucherForm.summary.trim()) {
    ElMessage.warning('请输入凭证摘要')
    return false
  }
  const validEntries = entries.value.filter(e => e.account_code)
  if (validEntries.length < 2) {
    ElMessage.warning('借贷记账法至少需要2条分录（一借一贷），请补充科目')
    return false
  }
  if (!isBalanced.value) {
    ElMessage.warning('借贷不平衡，请检查金额')
    return false
  }
  return true
}

function buildVoucherData() {
  return {
    voucher_type: voucherForm.voucher_type,
    voucher_date: voucherForm.voucher_date,
    summary: voucherForm.summary,
    items: entries.value
      .filter(e => e.account_code)
      .map(e => ({
        account_code: e.account_code,
        account_name: e.account_name,
        description: e.summary || voucherForm.summary,
        debit_amount: e.debit_amount || 0,
        credit_amount: e.credit_amount || 0,
        cash_flow_tag: e.cash_flow_tag || null,
        auxiliary_accounting: e.auxiliary_accounting || null
      }))
  }
}

// ===== AI 智能建议科目 =====

const suggesting = ref(false)
const suggestionResult = ref(null)
const rowSuggestionTimers = {}  // 每行防抖定时器
const suggestingRow = ref(-1)   // 正在建议的行索引
const rowSuggestions = reactive({})  // 每行AI建议结果: { rowIndex: { account_code, account_name, confidence, reason } }

async function handleAiSuggest() {
  if (!voucherForm.summary.trim()) {
    ElMessage.warning('请先输入凭证摘要')
    return
  }

  suggesting.value = true
  suggestionResult.value = null
  try {
    const res = await request.post('/suggestions/account-code', {
      description: voucherForm.summary,
      amount: totalDebit.value || totalCredit.value || 0
    })
    suggestionResult.value = res.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取科目建议失败')
  } finally {
    suggesting.value = false
  }
}

function applySuggestion() {
  if (!suggestionResult.value) return

  const emptyIndex = entries.value.findIndex(e => !e.account_code)
  if (emptyIndex >= 0) {
    entries.value[emptyIndex].account_code = suggestionResult.value.account_code
    entries.value[emptyIndex].account_name = suggestionResult.value.account_name
  } else {
    entries.value.push(createEntry({
      account_code: suggestionResult.value.account_code,
      account_name: suggestionResult.value.account_name,
      summary: voucherForm.summary
    }))
  }
  ElMessage.success(`已应用科目: ${suggestionResult.value.account_code} ${suggestionResult.value.account_name}`)
  suggestionResult.value = null
  markDirty()
}

/**
 * 自动为指定行触发AI科目建议
 * 用户填写分录摘要后自动推荐科目，供用户选择
 */
function scheduleRowSuggestion(rowIndex) {
  const entry = entries.value[rowIndex]
  if (!entry) return

  // 摘要非空即触发（不强制要求金额）
  const hasSummary = entry.summary && entry.summary.trim()
  if (!hasSummary) return

  // 如果该行已有科目，不再自动建议（用户已手动选择）
  if (entry.account_code) return

  // 防抖：清除之前的定时器
  if (rowSuggestionTimers[rowIndex]) {
    clearTimeout(rowSuggestionTimers[rowIndex])
  }

  rowSuggestionTimers[rowIndex] = setTimeout(() => {
    suggestForRow(rowIndex)
  }, 600)  // 600ms 防抖
}

/**
 * 为指定行执行AI科目建议，结果存入 rowSuggestions 供用户选择
 */
async function suggestForRow(rowIndex) {
  const entry = entries.value[rowIndex]
  if (!entry) return

  const description = entry.summary?.trim()
  if (!description) return

  // 如果用户已在建议期间手动选择了科目，跳过
  if (entry.account_code) {
    delete rowSuggestions[rowIndex]
    return
  }

  const amount = entry.debit_amount || entry.credit_amount || 0

  suggestingRow.value = rowIndex
  try {
    const res = await request.post('/suggestions/account-code', {
      description,
      amount
    })
    const data = res.data

    // 确认行未被修改且未选择科目
    if (entries.value[rowIndex] && !entries.value[rowIndex].account_code) {
      rowSuggestions[rowIndex] = {
        account_code: data.account_code,
        account_name: data.account_name,
        confidence: data.confidence,
        reason: data.reason
      }
    }
  } catch {
    // 自动建议失败静默处理
  } finally {
    suggestingRow.value = -1
  }
}

/**
 * 用户点击建议标签，应用AI推荐的科目
 */
function applyRowSuggestion(rowIndex) {
  const suggestion = rowSuggestions[rowIndex]
  if (!suggestion) return

  entries.value[rowIndex].account_code = suggestion.account_code
  entries.value[rowIndex].account_name = suggestion.account_name
  delete rowSuggestions[rowIndex]
  markDirty()

  // 自动跳转到借方金额
  nextTick(() => {
    focusCell(rowIndex, 'debit_amount')
  })
}

/**
 * 用户手动选择科目后，清除该行的AI科目建议
 */
function clearRowSuggestion(rowIndex) {
  delete rowSuggestions[rowIndex]
}

// ===== AI 摘要建议 =====

const summarySuggestions = reactive({})  // { rowIndex: [{ summary, usage_count, relevance }, ...] }
const summarySuggestTimers = {}  // 每行防抖定时器
const summarySuggestLoading = reactive({})  // { rowIndex: true/false }

/**
 * 科目选择后或摘要输入时，触发摘要建议
 */
function scheduleSummarySuggestion(rowIndex, partialText) {
  if (summarySuggestTimers[rowIndex]) {
    clearTimeout(summarySuggestTimers[rowIndex])
  }
  summarySuggestTimers[rowIndex] = setTimeout(() => {
    fetchSummarySuggestions(rowIndex, partialText)
  }, 400)
}

/**
 * 用户聚焦摘要输入框时触发
 */
function onSummaryFocus(rowIndex) {
  const entry = entries.value[rowIndex]
  if (!entry || !entry.account_code) return
  // 如果已有建议且摘要为空，直接显示
  if (summarySuggestions[rowIndex] && summarySuggestions[rowIndex].length > 0) return
  // 否则请求建议
  scheduleSummarySuggestion(rowIndex, entry.summary || '')
}

/**
 * 用户输入摘要时触发
 */
function onSummaryInput(rowIndex, val) {
  const entry = entries.value[rowIndex]
  if (!entry || !entry.account_code) return
  scheduleSummarySuggestion(rowIndex, val || '')
}

/**
 * 从后端获取摘要建议
 */
async function fetchSummarySuggestions(rowIndex, partialText) {
  const entry = entries.value[rowIndex]
  if (!entry || !entry.account_code) return

  // 如果用户已手动填写了摘要且摘要不在建议列表中，不清除建议
  // 仅当摘要为空或用户正在输入时更新建议

  summarySuggestLoading[rowIndex] = true
  try {
    const res = await request.post('/suggestions/summary', {
      account_code: entry.account_code,
      partial_text: partialText || ''
    })
    const suggestions = res.data.suggestions || []

    // 确认行未被修改
    if (entries.value[rowIndex] && entries.value[rowIndex].account_code === entry.account_code) {
      if (suggestions.length > 0) {
        summarySuggestions[rowIndex] = suggestions
      } else {
        delete summarySuggestions[rowIndex]
      }
    }
  } catch {
    // 静默处理
  } finally {
    summarySuggestLoading[rowIndex] = false
  }
}

/**
 * 用户点击摘要建议，填入摘要
 */
function applySummarySuggestion(rowIndex, summary) {
  entries.value[rowIndex].summary = summary
  delete summarySuggestions[rowIndex]
  markDirty()
  // 自动跳转到借方金额
  nextTick(() => {
    focusCell(rowIndex, 'debit_amount')
  })
}

// 监听分录行变化，自动触发AI建议
watch(
  () => entries.value.map(e => ({
    summary: e.summary,
    debit: e.debit_amount,
    credit: e.credit_amount,
    code: e.account_code
  })),
  (newEntries, oldEntries) => {
    if (!oldEntries) return
    newEntries.forEach((entry, index) => {
      const old = oldEntries[index]
      if (!old) return
      // 摘要变化时触发建议
      if (entry.summary !== old.summary && !entry.code) {
        scheduleRowSuggestion(index)
      }
    })
  },
  { deep: true }
)

// ===== AI 生成凭证 =====

const aiDialogVisible = ref(false)
const aiDescription = ref('')
const aiDate = ref('')
const aiGenerating = ref(false)

function handleAiGenerate() {
  aiDescription.value = ''
  aiDate.value = voucherForm.voucher_date || ''
  aiDialogVisible.value = true
}

async function executeAiGenerate() {
  if (!aiDescription.value.trim()) {
    ElMessage.warning('请输入业务描述')
    return
  }

  aiGenerating.value = true
  try {
    const res = await aiGenerateVoucher({
      description: aiDescription.value,
      voucher_date: aiDate.value || undefined
    })

    const data = res.data
    if (data.voucher_date) voucherForm.voucher_date = data.voucher_date
    if (data.summary) voucherForm.summary = data.summary
    if (data.items && data.items.length > 0) {
      entries.value = data.items.map(e => createEntry({
        account_code: e.account_code || '',
        account_name: e.account_name || '',
        debit_amount: e.debit_amount || 0,
        credit_amount: e.credit_amount || 0,
        summary: e.description || ''
      }))
    }

    ElMessage.success('AI 生成凭证成功，请检查并调整')
    aiDialogVisible.value = false
    markDirty()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || 'AI 生成失败')
  } finally {
    aiGenerating.value = false
  }
}

// ===== 辅助核算弹窗 =====

const auxPopoverIndex = ref(-1)
const auxForm = reactive({
  customer: '',
  supplier: '',
  department: '',
  project: '',
  employee: ''
})

function openAuxPopover(index) {
  const entry = entries.value[index]
  const aux = entry.auxiliary_accounting || {}
  auxForm.customer = aux.customer || ''
  auxForm.supplier = aux.supplier || ''
  auxForm.department = aux.department || ''
  auxForm.project = aux.project || ''
  auxForm.employee = aux.employee || ''
  auxPopoverIndex.value = index
}

function applyAuxiliary(index) {
  const aux = {}
  if (auxForm.customer) aux.customer = auxForm.customer
  if (auxForm.supplier) aux.supplier = auxForm.supplier
  if (auxForm.department) aux.department = auxForm.department
  if (auxForm.project) aux.project = auxForm.project
  if (auxForm.employee) aux.employee = auxForm.employee
  entries.value[index].auxiliary_accounting = Object.keys(aux).length > 0 ? aux : null
  auxPopoverIndex.value = -1
  markDirty()
}

// ===== 模板选择器 =====

const templateDialogVisible = ref(false)
const templateLoading = ref(false)
const templateList = ref([])
const templateCategoryFilter = ref('')

async function openTemplateSelector() {
  templateDialogVisible.value = true
  templateCategoryFilter.value = ''
  await loadTemplateList()
}

async function loadTemplateList() {
  templateLoading.value = true
  try {
    const params = {}
    if (templateCategoryFilter.value) params.category = templateCategoryFilter.value
    const res = await getTemplates(params)
    templateList.value = res.data.templates || []
  } catch {
    ElMessage.error('加载模板列表失败')
  } finally {
    templateLoading.value = false
  }
}

async function applyTemplateToForm(tpl) {
  try {
    const res = await getTemplate(tpl.id)
    const data = res.data
    if (data.items && data.items.length > 0) {
      entries.value = data.items.map(item => createEntry({
        account_code: item.account_code || '',
        account_name: item.account_name || '',
        debit_amount: item.debit_amount || 0,
        credit_amount: item.credit_amount || 0,
        summary: item.description || ''
      }))
      if (data.description && !voucherForm.summary) {
        voucherForm.summary = data.description
      }
    }
    templateDialogVisible.value = false
    ElMessage.success(`已加载模板"${tpl.name}"`)
    markDirty()
  } catch {
    ElMessage.error('加载模板详情失败')
  }
}

function getTemplateCategoryType(category) {
  const types = { '收入': 'success', '支出': 'danger', '转账': 'warning', '其他': 'info' }
  return types[category] || 'info'
}

// ===== 工具方法 =====

function formatMoney(value) {
  return formatAmount(value)
}
</script>

<style scoped>
.voucher-create {
  max-width: 1200px;
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

.auto-save-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
  font-weight: 400;
  margin-right: 8px;
}

.auto-save-status .el-icon {
  font-size: 14px;
}

.voucher-info-form {
  margin-bottom: 0;
}

.voucher-info-form :deep(.el-form-item) {
  margin-bottom: 0;
}

/* 分录表格 */
.entry-table-wrapper {
  position: relative;
}

.entry-table-wrapper :deep(.el-table__body-wrapper) {
  /* 允许表格接收粘贴事件 */
}

.row-number {
  color: #909399;
  font-size: 12px;
  user-select: none;
}

.account-name-display {
  color: #606266;
  font-size: 13px;
}

/* 合计栏 */
.totals-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 24px;
  margin-top: 16px;
  padding: 12px 16px;
  background-color: #f5f7fa;
  border-radius: 6px;
  border: 2px solid transparent;
  transition: all 0.3s ease;
}

.totals-bar--balanced {
  background-color: #f0f9eb;
  border-color: #b3e19d;
}

.totals-bar--unbalanced {
  background-color: #fef0f0;
  border-color: #fab6b6;
  animation: pulse-border 1.5s ease-in-out infinite;
}

@keyframes pulse-border {
  0%, 100% { border-color: #fab6b6; }
  50% { border-color: #f56c6c; }
}

.balance-warning-tag {
  animation: pulse-tag 1s ease-in-out infinite;
}

@keyframes pulse-tag {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.total-item {
  display: flex;
  align-items: center;
}

.total-label {
  font-size: 14px;
  color: #606266;
  margin-right: 8px;
}

.total-value {
  font-size: 16px;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

.total-value.debit {
  color: #409eff;
}

.total-value.credit {
  color: #67c23a;
}

.total-value.unbalanced {
  color: #f56c6c;
}

.shortcut-hint {
  font-size: 12px;
  color: #c0c4cc;
}

/* 模板选择器 */
.template-selector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.template-selector-item {
  padding: 14px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-selector-item:hover {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.tpl-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}

.tpl-desc {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  line-height: 1.4;
}

.tpl-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
}

/* AI 建议提示 */
.suggestion-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
}

.suggestion-reason {
  color: #909399;
  font-size: 12px;
}

/* 分录行AI建议标签 */
.summary-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ai-row-suggestion {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  background: #ecf5ff;
  border: 1px dashed #409eff;
  border-radius: 4px;
  font-size: 12px;
  animation: fadeIn 0.2s ease;
}

.ai-row-suggestion .suggestion-text {
  color: #409eff;
  font-weight: 500;
  flex: 1;
}

.ai-row-suggestion .el-icon {
  font-size: 14px;
  color: #409eff;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* AI 摘要建议 */
.ai-summary-suggestions {
  padding: 4px 6px;
  background: #f0f9eb;
  border: 1px dashed #67c23a;
  border-radius: 4px;
  animation: fadeIn 0.2s ease;
}

.summary-suggest-header {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #67c23a;
  margin-bottom: 4px;
}

.summary-suggest-header .el-icon {
  font-size: 13px;
}

.summary-suggest-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.summary-suggest-chip {
  cursor: pointer;
  transition: all 0.15s;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-suggest-chip:hover {
  transform: scale(1.03);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.summary-suggest-chip .chip-count {
  font-size: 10px;
  opacity: 0.7;
  margin-left: 2px;
}

/* 附件区域 */
.attachment-section {
  margin-top: 0;
}

.attachment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.attachment-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
}

.attachment-hint {
  font-size: 12px;
  color: #909399;
}

.attachment-upload {
  width: 100%;
}

.attachment-list {
  margin-top: 16px;
}

.attachment-list-header {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
}

.attachment-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  transition: background-color 0.2s;
}

.attachment-item:hover {
  background: #ecf5ff;
}

.attachment-preview {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
}

.attachment-thumb {
  width: 48px;
  height: 48px;
}

.attachment-thumb :deep(.el-image__inner) {
  object-fit: cover;
}

.attachment-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.attachment-name {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-meta {
  font-size: 11px;
  color: #909399;
}
</style>