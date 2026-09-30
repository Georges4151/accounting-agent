<template>
  <div class="invoice-manage">
    <!-- 上传区域 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>发票录入</span>
        </div>
      </template>

      <div class="upload-area">
        <!-- 票据类型选择 -->
        <div class="upload-type-selector">
          <span class="type-label">票据类型：</span>
          <el-radio-group v-model="docType" size="default">
            <el-radio-button value="invoice">发票</el-radio-button>
            <el-radio-button value="bank_receipt">银行回单</el-radio-button>
            <el-radio-button value="expense_report">费用报销单</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 拍照上传 -->
        <div class="upload-actions">
          <el-button type="primary" size="large" @click="openCameraDialog">
            <el-icon><Camera /></el-icon>
            拍照上传
          </el-button>

          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-exceed="handleUploadExceed"
            :on-change="handleFileChange"
            :accept="acceptFileTypes"
            :show-file-list="false"
            drag
            class="drag-upload"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将发票图片拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 JPG、PNG、BMP、WebP、PDF 格式，单个文件不超过 20MB
              </div>
            </template>
          </el-upload>
        </div>

        <!-- 待上传预览 -->
        <div v-if="uploadFile" class="upload-preview">
          <div class="preview-info">
            <el-icon><PictureFilled /></el-icon>
            <span>{{ uploadFile.name }}</span>
            <span class="preview-size">{{ formatFileSize(uploadFile.size) }}</span>
          </div>
          <div class="preview-actions">
            <el-button @click="clearUpload">取消</el-button>
            <el-button type="primary" @click="handleUpload" :loading="uploadLoading">
              <el-icon><Upload /></el-icon>
              上传并识别
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 发票列表 -->
    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>发票列表</span>
          <div class="card-header-right">
            <el-select
              v-model="filterStatus"
              placeholder="全部状态"
              clearable
              style="width: 160px"
              @change="loadInvoices"
            >
              <el-option label="待识别" value="pending" />
              <el-option label="已识别" value="recognized" />
              <el-option label="已确认" value="verified" />
              <el-option label="已归档" value="archived" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table
        :data="invoiceList"
        v-loading="tableLoading"
        border
        stripe
        style="width: 100%"
      >
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="票据类型" width="110">
          <template #default="{ row }">
            <el-tag :type="docTypeTagType(row.doc_type)" size="small" effect="plain">
              {{ docTypeLabel(row.doc_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发票类型" width="130">
          <template #default="{ row }">
            <span>{{ row.invoice_type || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="invoice_number" label="发票号码" width="140" show-overflow-tooltip />
        <el-table-column label="开票日期" width="110">
          <template #default="{ row }">
            <span>{{ row.invoice_date || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="价税合计" width="130" align="right">
          <template #default="{ row }">
            <span class="amount-text" v-if="row.total_amount">
              ¥{{ formatAmount(row.total_amount) }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="销售方" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.seller_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">
            <span>{{ row.created_at ? formatTime(row.created_at) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              text
              type="primary"
              size="small"
              @click="handleRecognize(row)"
              :loading="recognizingId === row.id"
            >
              <el-icon><View /></el-icon>
              AI 识别
            </el-button>
            <el-button
              text
              type="primary"
              size="small"
              @click="openDetailDialog(row)"
            >
              <el-icon><Edit /></el-icon>
              {{ row.status === 'pending' ? '手动填写' : '查看/编辑' }}
            </el-button>
            <el-button
              v-if="['recognized', 'verified'].includes(row.status) && !row.voucher_id"
              text
              type="success"
              size="small"
              @click="handleGenerateVoucher(row)"
              :loading="generatingId === row.id"
            >
              <el-icon><DocumentAdd /></el-icon>
              生成凭证
            </el-button>
            <el-button
              v-if="row.voucher_id"
              text
              type="info"
              size="small"
              @click="goToVoucher(row.voucher_id)"
            >
              <el-icon><Link /></el-icon>
              查看凭证
            </el-button>
            <el-popconfirm
              title="确定要删除该发票吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!tableLoading && invoiceList.length === 0"
        description="暂无发票，请上传"
        :image-size="80"
      />

      <div class="pagination-wrapper" v-if="total > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadInvoices"
          @current-change="loadInvoices"
        />
      </div>
    </el-card>

    <!-- 发票详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="发票详情"
      width="800px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-if="currentInvoice" class="invoice-detail">
        <!-- 原始票据图片 -->
        <div class="detail-image" v-if="currentInvoice.id">
          <el-image
            v-if="invoiceImageUrl"
            :src="invoiceImageUrl"
            fit="contain"
            style="max-height: 300px; width: 100%"
            :preview-src-list="[invoiceImageUrl]"
            :preview-teleported="true"
          >
            <template #error>
              <div class="image-error">
                <el-icon><PictureFilled /></el-icon>
                <span>加载失败</span>
              </div>
            </template>
          </el-image>
          <div v-else-if="invoiceImageLoading" class="image-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
          <div v-else-if="invoiceImageError" class="image-error">
            <el-icon><WarningFilled /></el-icon>
            <span>{{ invoiceImageError }}</span>
          </div>
          <div v-else-if="currentInvoice.image_available" class="image-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
          <div v-else class="image-error">
            <el-icon><PictureFilled /></el-icon>
            <span>暂无原始票据</span>
          </div>
        </div>

        <el-form :model="editForm" label-width="120px" class="detail-form">
          <!-- 发票：发票类型+发票号码 -->
          <el-row :gutter="16" v-if="editForm.doc_type === 'invoice'">
            <el-col :span="12">
              <el-form-item label="发票类型">
                <el-select v-model="editForm.invoice_type" placeholder="请选择" style="width: 100%">
                  <el-option label="增值税专用发票" value="增值税专用发票" />
                  <el-option label="增值税普通发票" value="增值税普通发票" />
                  <el-option label="电子发票" value="电子发票" />
                  <el-option label="其他" value="其他" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="发票号码">
                <el-input v-model="editForm.invoice_number" placeholder="发票号码" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="docLabels.dateLabel">
                <el-date-picker
                  v-model="editForm.invoice_date"
                  type="date"
                  placeholder="选择日期"
                  style="width: 100%"
                  value-format="YYYY-MM-DD"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="docLabels.numberLabel">
                <el-input v-model="editForm.invoice_number" :placeholder="docLabels.numberLabel" />
              </el-form-item>
            </el-col>
          </el-row>

          <!-- 发票代码（仅发票模式） -->
          <el-row :gutter="16" v-if="editForm.doc_type === 'invoice'">
            <el-col :span="12">
              <el-form-item label="发票代码">
                <el-input v-model="editForm.invoice_code" placeholder="发票代码" />
              </el-form-item>
            </el-col>
          </el-row>

          <!-- 银行回单：回单类型 -->
          <el-row :gutter="16" v-if="editForm.doc_type === 'bank_receipt'">
            <el-col :span="12">
              <el-form-item label="回单类型">
                <el-input v-model="editForm.invoice_type" placeholder="转账/收款/付款" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="摘要">
                <el-input v-model="editForm.remark" placeholder="交易摘要" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-divider content-position="left">金额信息</el-divider>

          <el-row :gutter="16">
            <el-col :span="8" v-if="editForm.doc_type === 'invoice'">
              <el-form-item label="金额（不含税）">
                <el-input-number
                  v-model="editForm.amount"
                  :precision="2"
                  :min="0"
                  style="width: 100%"
                  controls-position="right"
                />
              </el-form-item>
            </el-col>
            <el-col :span="8" v-if="editForm.doc_type === 'invoice'">
              <el-form-item label="税额">
                <el-input-number
                  v-model="editForm.tax_amount"
                  :precision="2"
                  :min="0"
                  style="width: 100%"
                  controls-position="right"
                />
              </el-form-item>
            </el-col>
            <el-col :span="editForm.doc_type === 'invoice' ? 8 : 24">
              <el-form-item :label="docLabels.amountLabel">
                <el-input-number
                  v-model="editForm.total_amount"
                  :precision="2"
                  :min="0"
                  style="width: 100%"
                  controls-position="right"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <!-- 银行回单：交易金额 -->
          <el-row :gutter="16" v-if="editForm.doc_type === 'bank_receipt'">
            <el-col :span="12">
              <el-form-item label="交易金额">
                <el-input-number
                  v-model="editForm.total_amount"
                  :precision="2"
                  :min="0"
                  style="width: 100%"
                  controls-position="right"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-divider content-position="left">{{ docLabels.partiesLabel }}</el-divider>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="docLabels.party1Label">
                <el-input v-model="editForm.seller_name" :placeholder="docLabels.party1Label" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item :label="docLabels.party1SubLabel">
                <el-input v-model="editForm.seller_tax_id" :placeholder="docLabels.party1SubLabel" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item :label="docLabels.party2Label">
                <el-input v-model="editForm.buyer_name" :placeholder="docLabels.party2Label" />
              </el-form-item>
            </el-col>
            <el-col :span="12" v-if="docLabels.party2SubLabel">
              <el-form-item :label="docLabels.party2SubLabel">
                <el-input v-model="editForm.buyer_tax_id" :placeholder="docLabels.party2SubLabel" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-divider content-position="left" v-if="editForm.items && editForm.items.length > 0">明细信息</el-divider>

          <el-table
            v-if="editForm.items && editForm.items.length > 0"
            :data="editForm.items"
            border
            size="small"
            style="width: 100%"
          >
            <el-table-column prop="name" :label="docLabels.itemNameLabel" />
            <el-table-column v-if="editForm.doc_type === 'invoice'" prop="quantity" label="数量" width="80" />
            <el-table-column v-if="editForm.doc_type === 'invoice'" prop="price" label="单价" width="120">
              <template #default="{ row: item }">
                ¥{{ formatAmount(item.price) }}
              </template>
            </el-table-column>
            <el-table-column prop="amount" label="金额" width="120">
              <template #default="{ row: item }">
                ¥{{ formatAmount(item.amount) }}
              </template>
            </el-table-column>
            <el-table-column v-if="editForm.doc_type === 'expense_report'" prop="remark" label="备注" min-width="120" />
          </el-table>

          <!-- 银行回单：额外信息 -->
          <template v-if="editForm.doc_type === 'bank_receipt' && editForm.details">
            <el-divider content-position="left">银行信息</el-divider>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="银行名称">{{ editForm.details.bank_name }}</el-descriptions-item>
              <el-descriptions-item label="手续费">{{ editForm.details.fee || '0.00' }}</el-descriptions-item>
              <el-descriptions-item label="付款方账号">{{ editForm.details.payer_account }}</el-descriptions-item>
              <el-descriptions-item label="收款方账号">{{ editForm.details.payee_account }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <!-- AI 识别错误提示 -->
          <el-alert
            v-if="editForm._parse_error"
            type="warning"
            :closable="false"
            show-icon
            style="margin-top: 12px"
          >
            <template #title>
              {{ editForm._parse_error }}
            </template>
          </el-alert>

          <!-- 原始识别文本 -->
          <el-form-item
            v-if="editForm.extracted_text"
            label="识别原文"
            style="margin-top: 12px"
          >
            <el-input
              :model-value="editForm.extracted_text"
              type="textarea"
              :rows="4"
              readonly
            />
          </el-form-item>

          <el-form-item label="备注" style="margin-top: 12px">
            <el-input
              v-model="editForm.remark"
              type="textarea"
              :rows="2"
              placeholder="备注信息"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="detailVisible = false">取消</el-button>
        <el-button
          v-if="currentInvoice && currentInvoice.status === 'pending'"
          type="warning"
          @click="handleRecognizeInDialog"
          :loading="recognizingId === currentInvoice?.id"
        >
          <el-icon><View /></el-icon>
          AI 识别
        </el-button>
        <el-button type="primary" @click="handleSaveInvoice" :loading="saveLoading">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 拍照弹窗 -->
    <el-dialog
      v-model="cameraVisible"
      title="拍照上传"
      width="720px"
      :close-on-click-modal="false"
      @close="closeCameraDialog"
      destroy-on-close
    >
      <div class="camera-dialog">
        <!-- 摄像头选择 -->
        <div class="camera-selector" v-if="cameras.length > 1">
          <span class="camera-selector-label">选择摄像头：</span>
          <el-select v-model="selectedCameraId" placeholder="请选择摄像头" style="width: 280px" @change="switchCamera">
            <el-option
              v-for="cam in cameras"
              :key="cam.deviceId"
              :label="cam.label"
              :value="cam.deviceId"
            />
          </el-select>
        </div>

        <!-- 视频预览 / 拍照结果 -->
        <div class="camera-preview-wrapper">
          <video
            v-show="!capturedImage"
            ref="videoRef"
            class="camera-video"
            autoplay
            playsinline
            muted
          />
          <img
            v-if="capturedImage"
            :src="capturedImage"
            class="camera-result"
            alt="拍照结果"
          />
          <div v-if="cameraLoading" class="camera-loading">
            <el-icon class="is-loading" :size="40"><Loading /></el-icon>
            <span>正在启动摄像头...</span>
          </div>
          <div v-if="cameraError" class="camera-error">
            <el-icon :size="40"><WarningFilled /></el-icon>
            <span>{{ cameraError }}</span>
            <el-button @click="initCamera">重试</el-button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="camera-actions">
          <template v-if="!capturedImage">
            <el-button @click="closeCameraDialog">取消</el-button>
            <el-button type="primary" @click="capturePhoto" :disabled="!cameraReady">
              <el-icon><Camera /></el-icon>
              拍照
            </el-button>
          </template>
          <template v-else>
            <el-button @click="retakePhoto">重新拍照</el-button>
            <el-button type="primary" @click="confirmPhoto">
              <el-icon><Check /></el-icon>
              确认使用
            </el-button>
          </template>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  uploadInvoice,
  recognizeInvoice,
  getInvoiceList,
  getInvoiceDetail,
  updateInvoice,
  deleteInvoice,
  generateVoucherFromInvoice
} from '@/api/invoice'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

// ===== 上传 =====
const uploadRef = ref(null)
const uploadFile = ref(null)
const uploadLoading = ref(false)
const acceptFileTypes = '.jpg,.jpeg,.png,.bmp,.webp,.pdf'
const docType = ref('invoice')

// 根据票据类型动态返回表单标签
const docLabels = computed(() => {
  const dt = editForm.doc_type || 'invoice'
  if (dt === 'bank_receipt') {
    return {
      dateLabel: '交易日期',
      numberLabel: '交易流水号',
      amountLabel: '交易金额',
      partiesLabel: '交易双方',
      party1Label: '付款方名称',
      party1SubLabel: '付款方账号',
      party2Label: '收款方名称',
      party2SubLabel: '收款方账号',
      itemNameLabel: '项目',
    }
  } else if (dt === 'expense_report') {
    return {
      dateLabel: '报销日期',
      numberLabel: '报销单编号',
      amountLabel: '报销总额',
      partiesLabel: '人员信息',
      party1Label: '申请人',
      party1SubLabel: '部门',
      party2Label: '审批人',
      party2SubLabel: '',  // 空字符串 → v-if 隐藏
      itemNameLabel: '费用项目',
    }
  }
  // 发票
  return {
    dateLabel: '开票日期',
    numberLabel: '发票号码',
    amountLabel: '价税合计',
    partiesLabel: '交易双方',
    party1Label: '销售方名称',
    party1SubLabel: '销售方税号',
    party2Label: '购买方名称',
    party2SubLabel: '购买方税号',
    itemNameLabel: '商品名称',
  }
})

// ===== 摄像头 =====
const cameraVisible = ref(false)
const videoRef = ref(null)
const cameras = ref([])
const selectedCameraId = ref('')
const cameraLoading = ref(false)
const cameraError = ref('')
const cameraReady = ref(false)
const capturedImage = ref(null)
let cameraStream = null

// ===== 列表 =====
const invoiceList = ref([])
const tableLoading = ref(false)
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const recognizingId = ref(null)
const generatingId = ref(null)

// ===== 详情弹窗 =====
const detailVisible = ref(false)
const currentInvoice = ref(null)
const invoiceImageUrl = ref('')
const invoiceImageLoading = ref(false)
const invoiceImageError = ref('')
const saveLoading = ref(false)
const editForm = reactive({
  invoice_type: '',
  invoice_number: '',
  invoice_code: '',
  invoice_date: null,
  amount: null,
  tax_amount: null,
  total_amount: null,
  seller_name: '',
  seller_tax_id: '',
  buyer_name: '',
  buyer_tax_id: '',
  items: [],
  remark: '',
  doc_type: 'invoice',
  details: null
})

onMounted(() => {
  loadInvoices()
})

// 关闭弹窗时释放 blob URL
watch(detailVisible, (val) => {
  if (!val) {
    if (invoiceImageUrl.value && invoiceImageUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(invoiceImageUrl.value)
    }
    invoiceImageUrl.value = ''
    invoiceImageLoading.value = false
    invoiceImageError.value = ''
  }
})

// ===== 摄像头方法 =====

/** 枚举可用摄像头设备 */
async function getCameras() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    cameras.value = devices.filter(d => d.kind === 'videoinput')
    if (cameras.value.length > 0 && !selectedCameraId.value) {
      selectedCameraId.value = cameras.value[0].deviceId
    }
  } catch {
    cameras.value = []
  }
}

/** 启动摄像头 */
async function initCamera() {
  cameraLoading.value = true
  cameraError.value = ''
  cameraReady.value = false
  capturedImage.value = null

  try {
    await getCameras()
    const deviceId = selectedCameraId.value
    const constraints = {
      video: deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'environment' },
      audio: false,
    }
    cameraStream = await navigator.mediaDevices.getUserMedia(constraints)
    if (videoRef.value) {
      videoRef.value.srcObject = cameraStream
      await videoRef.value.play()
      cameraReady.value = true
    }
  } catch (err) {
    if (err.name === 'NotAllowedError') {
      cameraError.value = '摄像头权限被拒绝，请在浏览器设置中允许访问摄像头'
    } else if (err.name === 'NotFoundError') {
      cameraError.value = '未检测到摄像头设备'
    } else {
      cameraError.value = '摄像头启动失败：' + (err.message || '未知错误')
    }
  } finally {
    cameraLoading.value = false
  }
}

/** 切换摄像头 */
async function switchCamera() {
  stopCamera()
  await initCamera()
}

/** 拍照 */
function capturePhoto() {
  if (!videoRef.value || !cameraReady.value) return
  const video = videoRef.value
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  const ctx = canvas.getContext('2d')
  ctx.drawImage(video, 0, 0)
  capturedImage.value = canvas.toDataURL('image/jpeg', 0.9)
  stopCamera()
  cameraReady.value = false
}

/** 重新拍照 */
async function retakePhoto() {
  capturedImage.value = null
  await initCamera()
}

/** 确认使用照片 */
function confirmPhoto() {
  if (!capturedImage.value) return
  // 将 base64 转为 File 对象
  const arr = capturedImage.value.split(',')
  const mime = arr[0].match(/:(.*?);/)[1]
  const bstr = atob(arr[1])
  const n = bstr.length
  const u8arr = new Uint8Array(n)
  for (let i = 0; i < n; i++) {
    u8arr[i] = bstr.charCodeAt(i)
  }
  const filename = `camera_${Date.now()}.jpg`
  const file = new File([u8arr], filename, { type: mime })
  uploadFile.value = file
  cameraVisible.value = false
}

/** 停止摄像头 */
function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop())
    cameraStream = null
  }
}

/** 打开拍照弹窗 */
async function openCameraDialog() {
  cameraVisible.value = true
  // 等待 DOM 更新后再初始化摄像头
  await new Promise(resolve => setTimeout(resolve, 100))
  await initCamera()
}

/** 关闭拍照弹窗 */
function closeCameraDialog() {
  stopCamera()
  cameraVisible.value = false
  cameraReady.value = false
  capturedImage.value = null
  cameraError.value = ''
}

// 组件卸载时释放摄像头
onUnmounted(() => {
  stopCamera()
})

// ===== 上传方法 =====

function handleFileChange(file) {
  uploadFile.value = file.raw || null
}

function handleUploadExceed() {
  ElMessage.warning('请先移除当前文件再上传')
  uploadFile.value = null
}

function clearUpload() {
  uploadFile.value = null
  uploadRef.value?.clearFiles()
}

async function handleUpload() {
  if (!uploadFile.value) {
    ElMessage.warning('请选择票据图片')
    return
  }

  uploadLoading.value = true
  try {
    const res = await uploadInvoice(uploadFile.value, docType.value)
    const invoiceId = res.data?.id
    ElMessage.success('票据上传成功，正在 AI 识别...')

    // 自动识别
    if (invoiceId) {
      try {
        const recRes = await recognizeInvoice(invoiceId, docType.value)
        ElMessage.success('票据识别完成')
        currentInvoice.value = recRes.data?.invoice
        fillEditForm(currentInvoice.value)
        detailVisible.value = true
        loadInvoiceImage(invoiceId)
      } catch (e) {
        if (e.response?.status === 409) {
          uploadFile.value = null
          return
        }
        ElMessage.warning('AI 识别失败，请手动填写票据信息')
        currentInvoice.value = { id: invoiceId, status: 'pending', doc_type: docType.value }
        fillEditForm(currentInvoice.value)
        detailVisible.value = true
        loadInvoiceImage(invoiceId)
      }
    }

    clearUpload()
    loadInvoices()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploadLoading.value = false
  }
}

// ===== 列表方法 =====

async function loadInvoices() {
  tableLoading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    const res = await getInvoiceList(params)
    const data = res.data
    invoiceList.value = data.invoices || []
    total.value = data.total || 0
  } catch (error) {
    ElMessage.error('加载发票列表失败')
  } finally {
    tableLoading.value = false
  }
}

// ===== 识别方法 =====

async function handleRecognize(row) {
  recognizingId.value = row.id
  try {
    const res = await recognizeInvoice(row.id, row.doc_type || 'invoice')
    ElMessage.success('票据识别完成')
    Object.assign(row, res.data?.invoice || {})
    loadInvoices()
  } catch (error) {
    if (error.response?.status !== 409) {
      ElMessage.error(error.response?.data?.detail || '识别失败')
    }
  } finally {
    recognizingId.value = null
  }
}

async function handleRecognizeInDialog() {
  if (!currentInvoice.value) return
  recognizingId.value = currentInvoice.value.id
  try {
    const res = await recognizeInvoice(currentInvoice.value.id, currentInvoice.value.doc_type || 'invoice')
    ElMessage.success('票据识别完成')
    currentInvoice.value = res.data?.invoice
    fillEditForm(currentInvoice.value)
  } catch (error) {
    if (error.response?.status !== 409) {
      ElMessage.error(error.response?.data?.detail || '识别失败')
    }
  } finally {
    recognizingId.value = null
  }
}

// ===== 详情弹窗 =====

async function openDetailDialog(row) {
  try {
    const res = await getInvoiceDetail(row.id)
    currentInvoice.value = res.data
    fillEditForm(currentInvoice.value)
    detailVisible.value = true
    loadInvoiceImage(row.id)
  } catch (error) {
    ElMessage.error('获取发票详情失败')
  }
}

function fillEditForm(invoice) {
  if (!invoice) return
  const dt = invoice.doc_type || 'invoice'
  const details = invoice.details || {}

  editForm.doc_type = dt
  editForm.details = details

  if (dt === 'bank_receipt') {
    // 银行回单：从 details 读取
    editForm.invoice_type = details.receipt_type || invoice.invoice_type || ''
    editForm.invoice_number = details.transaction_id || invoice.invoice_number || ''
    editForm.invoice_code = ''
    editForm.invoice_date = details.transaction_date || invoice.invoice_date || null
    editForm.amount = details.amount ?? invoice.amount ?? null
    editForm.tax_amount = null
    editForm.total_amount = details.amount ?? invoice.total_amount ?? null
    editForm.seller_name = details.payer_name || invoice.seller_name || ''
    editForm.seller_tax_id = details.payer_account || invoice.seller_tax_id || ''
    editForm.buyer_name = details.payee_name || invoice.buyer_name || ''
    editForm.buyer_tax_id = details.payee_account || invoice.buyer_tax_id || ''
    editForm.items = []
    editForm.remark = details.summary || invoice.remark || ''
  } else if (dt === 'expense_report') {
    // 费用报销单：从 details 读取
    editForm.invoice_type = ''
    editForm.invoice_number = details.report_no || invoice.invoice_number || ''
    editForm.invoice_code = ''
    editForm.invoice_date = details.report_date || invoice.invoice_date || null
    editForm.amount = null
    editForm.tax_amount = null
    editForm.total_amount = details.total_amount ?? invoice.total_amount ?? null
    editForm.seller_name = details.applicant || invoice.seller_name || ''
    editForm.seller_tax_id = details.department || invoice.seller_tax_id || ''
    editForm.buyer_name = details.approver || invoice.buyer_name || ''
    editForm.buyer_tax_id = ''
    editForm.items = details.items || invoice.items || []
    editForm.remark = details.reason || invoice.remark || ''
  } else {
    // 发票
    editForm.invoice_type = invoice.invoice_type || ''
    editForm.invoice_number = invoice.invoice_number || ''
    editForm.invoice_code = invoice.invoice_code || ''
    editForm.invoice_date = invoice.invoice_date || null
    editForm.amount = invoice.amount ?? null
    editForm.tax_amount = invoice.tax_amount ?? null
    editForm.total_amount = invoice.total_amount ?? null
    editForm.seller_name = invoice.seller_name || ''
    editForm.seller_tax_id = invoice.seller_tax_id || ''
    editForm.buyer_name = invoice.buyer_name || ''
    editForm.buyer_tax_id = invoice.buyer_tax_id || ''
    editForm.items = invoice.items || []
    editForm.remark = invoice.remark || ''
  }

  editForm._parse_error = invoice._parse_error || ''
  editForm.extracted_text = invoice.extracted_text || ''
}

async function handleSaveInvoice() {
  if (!currentInvoice.value) return

  saveLoading.value = true
  try {
    const data = { ...editForm }
    if (data.invoice_date === '') data.invoice_date = null
    const res = await updateInvoice(currentInvoice.value.id, data)
    ElMessage.success('发票信息已保存')
    currentInvoice.value = res.data?.invoice
    detailVisible.value = false
    loadInvoices()
  } catch (error) {
    // 409 重复发票已在拦截器中以 warning 提示，此处不再重复提示
    if (error.response?.status !== 409) {
      ElMessage.error(error.response?.data?.detail || '保存失败')
    }
  } finally {
    saveLoading.value = false
  }
}

// ===== 生成凭证 =====

async function handleGenerateVoucher(row) {
  try {
    await ElMessageBox.confirm(
      '确定要基于该发票自动生成凭证吗？',
      '确认生成凭证',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }

  generatingId.value = row.id
  try {
    const res = await generateVoucherFromInvoice(row.id)
    ElMessage.success(`凭证生成成功，凭证号：${res.data?.voucher_no}`)
    row.voucher_id = res.data?.voucher_id
    row.status = 'archived'
    loadInvoices()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '生成凭证失败')
  } finally {
    generatingId.value = null
  }
}

function goToVoucher(voucherId) {
  router.push({ name: 'VoucherList', query: { highlight: voucherId } })
}

// ===== 删除 =====

async function handleDelete(row) {
  try {
    await deleteInvoice(row.id)
    ElMessage.success('发票已删除')
    loadInvoices()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

// ===== 工具函数 =====

function statusLabel(status) {
  const map = {
    pending: '待识别',
    recognized: '已识别',
    verified: '已确认',
    archived: '已归档'
  }
  return map[status] || status
}

function statusTagType(status) {
  const map = {
    pending: 'warning',
    recognized: 'primary',
    verified: 'success',
    archived: 'info'
  }
  return map[status] || 'info'
}

function docTypeLabel(docType) {
  const map = {
    invoice: '发票',
    bank_receipt: '银行回单',
    expense_report: '费用报销单'
  }
  return map[docType] || docType || '-'
}

function docTypeTagType(docType) {
  const map = {
    invoice: '',
    bank_receipt: 'warning',
    expense_report: 'success'
  }
  return map[docType] || 'info'
}

function formatAmount(val) {
  if (val == null) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatFileSize(bytes) {
  if (bytes == null) return '-'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  try {
    const date = new Date(timeStr)
    const y = date.getFullYear()
    const M = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    const h = String(date.getHours()).padStart(2, '0')
    const m = String(date.getMinutes()).padStart(2, '0')
    const s = String(date.getSeconds()).padStart(2, '0')
    return `${y}-${M}-${d} ${h}:${m}:${s}`
  } catch {
    return timeStr
  }
}

async function loadInvoiceImage(invoiceId) {
  if (!invoiceId) {
    invoiceImageUrl.value = ''
    invoiceImageError.value = ''
    return
  }
  invoiceImageLoading.value = true
  invoiceImageUrl.value = ''
  invoiceImageError.value = ''
  try {
    const token = useAuthStore().accessToken
    const resp = await fetch(`/api/invoices/${invoiceId}/image`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (resp.ok) {
      const blob = await resp.blob()
      // 释放旧 blob URL
      if (invoiceImageUrl.value && invoiceImageUrl.value.startsWith('blob:')) {
        URL.revokeObjectURL(invoiceImageUrl.value)
      }
      invoiceImageUrl.value = URL.createObjectURL(blob)
    } else if (resp.status === 404) {
      invoiceImageError.value = '原始票据图片不存在'
    } else {
      invoiceImageError.value = `加载失败 (${resp.status})`
    }
  } catch {
    invoiceImageError.value = '网络错误，加载失败'
    invoiceImageUrl.value = ''
  } finally {
    invoiceImageLoading.value = false
  }
}
</script>

<style scoped>
.invoice-manage {
  max-width: 1400px;
}

.section-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.card-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 上传区域 */
.upload-area {
  padding: 4px 0;
}

.upload-type-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.type-label {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  white-space: nowrap;
}

.upload-actions {
  display: flex;
  align-items: flex-start;
  gap: 24px;
}

.drag-upload {
  flex: 1;
}

.upload-preview {
  margin-top: 16px;
  padding: 12px 16px;
  background-color: #f5f7fa;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #303133;
}

.preview-size {
  color: #909399;
  font-size: 13px;
}

.preview-actions {
  display: flex;
  gap: 8px;
}

/* 表格 */
.amount-text {
  font-weight: 600;
  color: #e6a23c;
  font-family: 'Courier New', monospace;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* 详情弹窗 */
.invoice-detail {
  max-height: 60vh;
  overflow-y: auto;
}

.detail-image {
  margin-bottom: 16px;
  background-color: #f5f7fa;
  border-radius: 8px;
  padding: 8px;
  display: flex;
  justify-content: center;
}

.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #c0c4cc;
  font-size: 14px;
  gap: 8px;
}

.image-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
  font-size: 14px;
  gap: 8px;
}

.detail-form {
  margin-top: 4px;
}

:deep(.el-upload-dragger) {
  padding: 30px 20px;
}

/* 拍照弹窗 */
.camera-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.camera-selector {
  display: flex;
  align-items: center;
  gap: 12px;
}

.camera-selector-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

.camera-preview-wrapper {
  width: 100%;
  min-height: 360px;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.camera-video {
  width: 100%;
  max-height: 480px;
  display: block;
}

.camera-result {
  width: 100%;
  max-height: 480px;
  object-fit: contain;
  display: block;
}

.camera-loading,
.camera-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #c0c4cc;
  font-size: 14px;
  padding: 40px;
}

.camera-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
}
</style>