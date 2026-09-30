"""
发票识别服务
使用 Ollama Vision 多模态模型从发票图片中提取结构化信息
"""
import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

# 发票识别 Prompt
_INVOICE_RECOGNITION_PROMPT = """你是一个发票识别助手。请从这张发票图片中提取信息，只返回 JSON，不要任何其他文字。

图片是中文发票，请仔细阅读图片中的中文文字，提取以下字段：

- invoice_type: 发票类型（增值税专用发票/增值税普通发票/电子发票/其他）
- invoice_number: 发票号码（右上角，通常8位或10位数字）
- invoice_code: 发票代码（左上角，通常12位数字）
- invoice_date: 开票日期，格式 YYYY-MM-DD
- amount: 不含税金额（金额栏"合计"行，纯数字）
- tax_amount: 税额（税额栏"合计"行，纯数字）
- total_amount: 价税合计（大写金额旁边的小写数字，纯数字）
- seller_name: 销售方名称
- seller_tax_id: 销售方纳税人识别号
- buyer_name: 购买方名称
- buyer_tax_id: 购买方纳税人识别号
- items: 货物明细，格式 [{"name":"商品名","quantity":1,"price":100,"amount":100}]

规则：无法识别的字段用 ""，金额用纯数字（如 1000.00），不要编造数据。

返回示例：
{"invoice_type":"增值税普通发票","invoice_number":"12345678","invoice_code":"123456789012","invoice_date":"2024-01-15","amount":1000.00,"tax_amount":130.00,"total_amount":1130.00,"seller_name":"XX公司","seller_tax_id":"","buyer_name":"YY公司","buyer_tax_id":"","items":[{"name":"服务费","quantity":1,"price":1000.00,"amount":1000.00}]}"""

# 银行回单识别 Prompt
_BANK_RECEIPT_PROMPT = """你是一个银行回单识别助手。请从这张银行回单图片中提取信息，只返回 JSON，不要任何其他文字。

图片是中文银行回单，请仔细阅读图片中的中文文字，提取以下字段：

- receipt_type: 回单类型（转账/收款/付款/其他）
- bank_name: 银行名称
- transaction_date: 交易日期，格式 YYYY-MM-DD
- amount: 交易金额（纯数字）
- payer_name: 付款方名称
- payer_account: 付款方账号
- payee_name: 收款方名称
- payee_account: 收款方账号
- transaction_id: 交易流水号
- summary: 摘要/用途
- fee: 手续费（纯数字，无则为0）

规则：无法识别的字段用 ""，金额用纯数字，不要编造数据。

返回示例：
{"receipt_type":"转账","bank_name":"中国工商银行","transaction_date":"2024-01-15","amount":10000.00,"payer_name":"XX公司","payer_account":"6217000000000000001","payee_name":"YY公司","payee_account":"6217000000000000002","transaction_id":"20240115000001","summary":"货款","fee":0.00}"""

# 费用报销单识别 Prompt
_EXPENSE_REPORT_PROMPT = """你是一个费用报销单识别助手。请从这张报销单图片中提取信息，只返回 JSON，不要任何其他文字。

图片是中文费用报销单，请仔细阅读图片中的中文文字，提取以下字段：

- report_no: 报销单编号
- report_date: 报销日期，格式 YYYY-MM-DD
- applicant: 申请人姓名
- department: 部门
- items: 费用明细，格式 [{"name":"费用项目","amount":100.00,"remark":""}]
- total_amount: 报销总额（大写金额旁边的小写数字，纯数字）
- reason: 报销事由
- approver: 审批人

规则：无法识别的字段用 ""，金额用纯数字，不要编造数据。

返回示例：
{"report_no":"BX-2024-001","report_date":"2024-01-15","applicant":"张三","department":"技术部","items":[{"name":"差旅费","amount":500.00,"remark":"北京出差"},{"name":"办公用品","amount":200.00,"remark":"购买纸张"}],"total_amount":700.00,"reason":"1月差旅及办公费用","approver":"李四"}"""


class InvoiceService:
    """发票识别服务"""

    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".pdf"}

    # 默认使用的 Ollama 视觉模型（按优先级排列，前面的优先）
    DEFAULT_VISION_MODELS = [
        "qwen3-vl:4b",
        "qwen2.5vl:7b-q4_K_M",
        "qwen2.5vl:7b",
        "minicpm-v:8b",
        "llava:latest",
        "llava:13b",
        "llava-phi3:latest",
        "bakllava:latest",
    ]

    def __init__(self):
        self._upload_dir = Path("uploads/invoices")
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        self._vision_model: str | None = None

    def save_uploaded_file(self, file_data: bytes, filename: str) -> str:
        """保存上传的发票图片，返回相对路径"""
        import time
        timestamp = int(time.time() * 1000)
        safe_name = f"{int(Path(filename).stem.encode('utf-8').hex(), 16) % 1000000}_{timestamp}{Path(filename).suffix}"
        file_path = self._upload_dir / safe_name
        file_path.write_bytes(file_data)
        return str(file_path)

    def _image_to_base64(self, image_path: str) -> str:
        """将图片文件转为 base64 编码"""
        full_path = Path(image_path)
        if not full_path.is_absolute():
            full_path = Path.cwd() / full_path

        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    async def _get_available_vision_models(self) -> list[str]:
        """获取所有已安装的视觉模型（按优先级排序）"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                check_resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if check_resp.status_code == 200:
                    installed = {m["name"] for m in check_resp.json().get("models", [])}
                    available = []
                    for candidate in self.DEFAULT_VISION_MODELS:
                        base = candidate.split(":")[0]
                        for im in installed:
                            if im == candidate or im.startswith(base + ":"):
                                if im not in available:
                                    available.append(im)
                    if not available:
                        raise RuntimeError(
                            "未找到可用的视觉模型。请安装以下任一模型:\n"
                            + "\n".join(f"  ollama pull {m}" for m in self.DEFAULT_VISION_MODELS[:3])
                        )
                    return available
                raise RuntimeError("无法获取 Ollama 模型列表")
            except httpx.ConnectError:
                raise RuntimeError("Ollama 服务未启动，请先启动 Ollama")

    async def recognize_invoice(self, image_path: str) -> dict:
        """
        使用 Ollama Vision 模型识别发票

        Args:
            image_path: 发票图片路径

        Returns:
            识别结果字典，包含发票所有字段

        Raises:
            RuntimeError: 所有视觉模型均不可用或识别失败
        """
        image_b64 = self._image_to_base64(image_path)

        # 优先使用配置指定的模型
        if settings.INVOICE_VISION_MODEL:
            models_to_try = [settings.INVOICE_VISION_MODEL]
            logger.info(f"使用配置的发票识别模型: {settings.INVOICE_VISION_MODEL}")
        else:
            models_to_try = await self._get_available_vision_models()
            logger.info(f"自动检测到视觉模型: {models_to_try}")

        last_error = ""
        for vision_model in models_to_try:
            logger.info(f"尝试视觉模型: {vision_model}")

            # 判断是否为思考模型（qwen3 系列输出在 thinking 字段）
            is_thinking_model = "qwen3" in vision_model.lower()

            gen_payload = {
                "model": vision_model,
                "prompt": _INVOICE_RECOGNITION_PROMPT,
                "images": [image_b64],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 4096,
                },
            }

            # 思考模型需要使用 think 参数控制思考深度
            if is_thinking_model:
                gen_payload["think"] = "low"

            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json=gen_payload,
                )

            if response.status_code == 200:
                result = response.json()
                # 读取 response 字段（非思考模型）
                raw_text = result.get("response", "")
                # 思考模型：输出在 thinking 字段，response 为空
                if not raw_text:
                    raw_text = result.get("thinking", "")

                if not raw_text:
                    logger.warning(f"模型 {vision_model} 返回了空内容，尝试下一个")
                    last_error = f"模型 {vision_model} 返回了空内容"
                    continue

                logger.info(f"模型 {vision_model} 原始返回(前500字符): {raw_text[:500]}")

                parsed = self._parse_invoice_json(raw_text)
                parsed["extracted_raw_text"] = raw_text
                self._vision_model = vision_model
                logger.info(f"发票识别成功，使用模型: {vision_model}")
                return parsed

            error_text = response.text[:300]
            if "memory" in error_text.lower() or "requires more" in error_text.lower():
                logger.warning(f"模型 {vision_model} 内存不足，尝试下一个")
                last_error = error_text
                continue
            else:
                last_error = f"HTTP {response.status_code}: {error_text}"
                logger.error(f"模型 {vision_model} 调用失败: {last_error}")
                continue

        raise RuntimeError(
            "所有视觉模型均不可用。请安装视觉模型:\n"
            "  ollama pull qwen3-vl:4b\n"
            f"最后错误: {last_error}"
        )

    def _parse_invoice_json(self, raw_text: str) -> dict:
        """从模型返回的文本中提取 JSON"""
        cleaned = raw_text.strip()

        # 尝试移除 markdown 代码块包装
        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', cleaned)
        if code_block:
            cleaned = code_block.group(1).strip()

        # 尝试直接解析
        try:
            result = json.loads(cleaned)
            return self._ensure_fields(result)
        except json.JSONDecodeError:
            pass

        # 尝试提取第一个 JSON 对象
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return self._ensure_fields(result)
            except json.JSONDecodeError:
                pass

        # 尝试修复常见 JSON 问题（缺少引号、尾部逗号等）
        try:
            fixed = re.sub(r'(?<=\{|\,)\s*(\w+)\s*:', r'"\1":', cleaned)
            fixed = re.sub(r',\s*\}', '}', fixed)
            result = json.loads(fixed)
            return self._ensure_fields(result)
        except (json.JSONDecodeError, Exception):
            pass

        logger.warning(f"无法解析模型返回的 JSON, raw_text前200字符: {raw_text[:200]}")

        # 返回部分结果，保留原始文本供用户查看
        return {
            "invoice_type": "",
            "invoice_number": "",
            "invoice_code": "",
            "invoice_date": "",
            "amount": 0,
            "tax_amount": 0,
            "total_amount": 0,
            "seller_name": "",
            "seller_tax_id": "",
            "buyer_name": "",
            "buyer_tax_id": "",
            "items": [],
            "extracted_raw_text": raw_text,
            "_parse_error": "模型返回格式异常，请手动填写或重试",
        }

    def _ensure_fields(self, data: dict) -> dict:
        """确保返回结果包含所有必要字段"""
        defaults = self._empty_result()
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        return data

    def _empty_result(self) -> dict:
        """返回空结果结构（发票）"""
        return {
            "invoice_type": "",
            "invoice_number": "",
            "invoice_code": "",
            "invoice_date": "",
            "amount": 0,
            "tax_amount": 0,
            "total_amount": 0,
            "seller_name": "",
            "seller_tax_id": "",
            "buyer_name": "",
            "buyer_tax_id": "",
            "items": [],
            "extracted_raw_text": "",
        }

    # ========== 银行回单识别 ==========

    async def recognize_bank_receipt(self, image_path: str) -> dict:
        """
        使用 Ollama Vision 模型识别银行回单

        Args:
            image_path: 银行回单图片路径

        Returns:
            识别结果字典
        """
        return await self._recognize_with_prompt(
            image_path, _BANK_RECEIPT_PROMPT, self._parse_bank_receipt_json
        )

    def _parse_bank_receipt_json(self, raw_text: str) -> dict:
        """从模型返回的文本中提取银行回单 JSON"""
        return self._parse_generic_json(raw_text, self._empty_bank_receipt_result())

    def _ensure_bank_receipt_fields(self, data: dict) -> dict:
        defaults = self._empty_bank_receipt_result()
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        return data

    def _empty_bank_receipt_result(self) -> dict:
        return {
            "receipt_type": "",
            "bank_name": "",
            "transaction_date": "",
            "amount": 0,
            "payer_name": "",
            "payer_account": "",
            "payee_name": "",
            "payee_account": "",
            "transaction_id": "",
            "summary": "",
            "fee": 0,
            "extracted_raw_text": "",
        }

    # ========== 费用报销单识别 ==========

    async def recognize_expense_report(self, image_path: str) -> dict:
        """
        使用 Ollama Vision 模型识别费用报销单

        Args:
            image_path: 费用报销单图片路径

        Returns:
            识别结果字典
        """
        return await self._recognize_with_prompt(
            image_path, _EXPENSE_REPORT_PROMPT, self._parse_expense_report_json
        )

    def _parse_expense_report_json(self, raw_text: str) -> dict:
        """从模型返回的文本中提取费用报销单 JSON"""
        return self._parse_generic_json(raw_text, self._empty_expense_report_result())

    def _ensure_expense_report_fields(self, data: dict) -> dict:
        defaults = self._empty_expense_report_result()
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        return data

    def _empty_expense_report_result(self) -> dict:
        return {
            "report_no": "",
            "report_date": "",
            "applicant": "",
            "department": "",
            "items": [],
            "total_amount": 0,
            "reason": "",
            "approver": "",
            "extracted_raw_text": "",
        }

    # ========== 通用识别入口 ==========

    async def recognize_document(self, image_path: str, doc_type: str) -> dict:
        """
        通用票据识别入口，根据 doc_type 调用不同识别方法

        Args:
            image_path: 票据图片路径
            doc_type: 票据类型 (invoice / bank_receipt / expense_report)

        Returns:
            识别结果字典
        """
        if doc_type == "bank_receipt":
            return await self.recognize_bank_receipt(image_path)
        elif doc_type == "expense_report":
            return await self.recognize_expense_report(image_path)
        else:
            return await self.recognize_invoice(image_path)

    # ========== 通用识别核心方法 ==========

    async def _recognize_with_prompt(self, image_path: str, prompt: str, parse_func) -> dict:
        """通用识别核心方法，使用指定 prompt 调用视觉模型"""
        image_b64 = self._image_to_base64(image_path)

        if settings.INVOICE_VISION_MODEL:
            models_to_try = [settings.INVOICE_VISION_MODEL]
            logger.info(f"使用配置的识别模型: {settings.INVOICE_VISION_MODEL}")
        else:
            models_to_try = await self._get_available_vision_models()
            logger.info(f"自动检测到视觉模型: {models_to_try}")

        last_error = ""
        for vision_model in models_to_try:
            logger.info(f"尝试视觉模型: {vision_model}")

            is_thinking_model = "qwen3" in vision_model.lower()

            gen_payload = {
                "model": vision_model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 4096,
                },
            }
            if is_thinking_model:
                gen_payload["think"] = "low"

            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json=gen_payload,
                )

            if response.status_code == 200:
                result = response.json()
                raw_text = result.get("response", "")
                if not raw_text:
                    raw_text = result.get("thinking", "")

                if not raw_text:
                    logger.warning(f"模型 {vision_model} 返回了空内容，尝试下一个")
                    last_error = f"模型 {vision_model} 返回了空内容"
                    continue

                logger.info(f"模型 {vision_model} 原始返回(前500字符): {raw_text[:500]}")

                parsed = parse_func(raw_text)
                parsed["extracted_raw_text"] = raw_text
                self._vision_model = vision_model
                logger.info(f"票据识别成功，使用模型: {vision_model}")
                return parsed

            error_text = response.text[:300]
            if "memory" in error_text.lower() or "requires more" in error_text.lower():
                logger.warning(f"模型 {vision_model} 内存不足，尝试下一个")
                last_error = error_text
                continue
            else:
                last_error = f"HTTP {response.status_code}: {error_text}"
                logger.error(f"模型 {vision_model} 调用失败: {last_error}")
                continue

        raise RuntimeError(
            "所有视觉模型均不可用。请安装视觉模型:\n"
            "  ollama pull qwen3-vl:4b\n"
            f"最后错误: {last_error}"
        )

    def _parse_generic_json(self, raw_text: str, empty_result: dict) -> dict:
        """通用 JSON 解析器，从模型返回的文本中提取 JSON"""
        cleaned = raw_text.strip()

        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', cleaned)
        if code_block:
            cleaned = code_block.group(1).strip()

        try:
            result = json.loads(cleaned)
            return self._ensure_generic_fields(result, empty_result)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return self._ensure_generic_fields(result, empty_result)
            except json.JSONDecodeError:
                pass

        try:
            fixed = re.sub(r'(?<=\{|\,)\s*(\w+)\s*:', r'"\1":', cleaned)
            fixed = re.sub(r',\s*\}', '}', fixed)
            result = json.loads(fixed)
            return self._ensure_generic_fields(result, empty_result)
        except (json.JSONDecodeError, Exception):
            pass

        logger.warning(f"无法解析模型返回的 JSON, raw_text前200字符: {raw_text[:200]}")

        result = {**empty_result}
        result["extracted_raw_text"] = raw_text
        result["_parse_error"] = "模型返回格式异常，请手动填写或重试"
        return result

    def _ensure_generic_fields(self, data: dict, defaults: dict) -> dict:
        """确保返回结果包含所有必要字段"""
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        return data


# 单例
invoice_service = InvoiceService()