# -*- coding: utf-8 -*-
"""
图片 / PDF 课表交给大模型识别（不依赖 OCR 库）。

  · 图片（png/jpg/webp/bmp）：PIL 校正方向、缩到长边 ≤1600px，以 OpenAI 视觉格式
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}} 发送；
  · PDF：先用 pypdf 提取文字（文字版 PDF 任何模型都能识别）；提不出有效文字（扫描件）时
    用 pypdfium2 把前 2 页渲染成图片，再按图片发送。

模型输出的每一门课都会重新校验（节次在节次表内、周次在学期内、课程名非空），结果与文件导入的预览格式一致。
"""

import base64
import dataclasses
import io
import json
import re
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.llm import LlmError, ModelConfig
from app.core import timeutil
from app.core.errors import ApiError
from app.models import User
from app.services import import_common, schedule

MAX_SIDE = 1600
MAX_PIXELS = 40_000_000
MAX_PDF_PAGES_TEXT = 4
MAX_PDF_PAGES_IMAGE = 2
MAX_TEXT_CHARS = 12000
MAX_COURSES = 200
VISION_TIMEOUT = 85
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

NO_VISION_MESSAGE = ("当前模型不支持图片识别，请在 AI 设置中添加支持视觉的模型（如 通义千问 qwen-vl、GLM-4V、GPT-4o），"
                     "或上传文字版 PDF")
# 已知的纯文本模型：直接提示，省一次必然失败的请求
_TEXT_ONLY = re.compile(r"^(?:deepseek-(?:chat|reasoner|coder)|moonshot-v1-\d+k|kimi-k2|glm-4-(?:flash|plus|air)|"
                        r"qwen-(?:plus|turbo|max|long))(?:[-_.].*)?$", re.I)
_VISION_HINT = re.compile(r"(?:vl|vision|4v|4o|omni|gemini|claude|gpt-4\.1|gpt-5|llava|pixtral|minicpm-v|qvq)", re.I)
_NO_VISION_WORDS = ("image", "vision", "multimodal", "multi-modal", "image_url", "content type", "unknown variant",
                    "not support", "unsupported", "图片", "图像", "视觉", "多模态")

SYSTEM_PROMPT = """你是课程表识别助手。用户会给你一张课表截图/照片，或从 PDF 提取的课表文字。
请找出课表里的每一门课，只输出一个 JSON 对象，不要输出任何解释：
{"courses": [{"course_name": "高等数学", "teacher": "张三", "classroom": "A101", "day_of_week": 1,
  "start_period": 1, "end_period": 2, "week_text": "1-16周(单)", "weeks": [1,3,5]}],
 "semester_start": "YYYY-MM-DD", "total_weeks": 18}
规则：
1. day_of_week：星期一=1 … 星期日=7，按课程所在的列判断；start_period / end_period 是第几节（整数），按所在的行判断。
2. week_text 写周次（如 "1-16周"、"2-16周(双)"、"1-3,18周"），单双周必须写成 "(单)"/"(双)"；weeks 为对应的完整周次整数列表。课表没写周次时两者都省略。
3. 同一门课在不同星期或不同节次上课时，拆成多条；同一格里叠放多门课时，逐门输出。
4. 教师、教室看不清就填空字符串；看不清课程名的格子不要输出；不要编造课表上没有的课。
5. semester_start、total_weeks 只有课表上明确写出时才输出，否则省略。"""


# ---------------------------------------------------------------- 文件预处理
def _open_image(content: bytes):
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(content))
        if image.width * image.height > MAX_PIXELS:
            raise ApiError(422, "图片分辨率过大，请截图后再上传")
        image.load()
        return ImageOps.exif_transpose(image)
    except ApiError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise ApiError(415, "暂只支持 png / jpg / webp 图片或 PDF 文件") from None


def _image_part(image) -> dict:
    from PIL import Image

    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}


def _meaningful(text: str) -> bool:
    """提取到的 PDF 文字是否像一张课表（扫描件通常提不出字，或只有页码）。"""
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 30:
        return False
    keywords = ("星期", "周一", "周二", "节", "课程", "Monday", "Mon", "Tuesday", "Period", "Course")
    return any(word in text for word in keywords)


def _pdf_text(content: bytes) -> Tuple[str, int]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ApiError(422, "PDF 已加密，请先解除密码再上传")
        pages = reader.pages[:MAX_PDF_PAGES_TEXT]
        chunks = []
        for page in pages:
            try:
                chunks.append(page.extract_text(extraction_mode="layout") or "")
            except Exception:  # noqa: BLE001 - 版式模式对个别 PDF 会失败，退回普通模式
                chunks.append(page.extract_text() or "")
        page_count = len(reader.pages)
    except ApiError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError):
        raise ApiError(422, "PDF 文件已损坏或无法读取") from None
    text = "\n\n".join(chunk for chunk in chunks if chunk)
    # 版式模式会用大量空格对齐列：压缩过长的空白，保留相对位置
    text = re.sub(r" {6,}", "      ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_TEXT_CHARS], page_count


def _pdf_images(content: bytes) -> List[dict]:
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(content)
    except Exception:  # noqa: BLE001 - pdfium 抛出的异常类型不固定
        raise ApiError(422, "PDF 文件已损坏或无法读取") from None
    try:
        parts = []
        for index in range(min(len(document), MAX_PDF_PAGES_IMAGE)):
            page = document[index]
            width, height = page.get_size()
            scale = max(0.5, min(3.0, MAX_SIDE / max(width, height, 1)))
            parts.append(_image_part(page.render(scale=scale).to_pil()))
        return parts
    finally:
        document.close()


def _prepare(filename: str, content: bytes) -> Tuple[str, Optional[str], List[dict]]:
    """返回 (来源 image/pdf-text/pdf-image, PDF 文字, 图片 content parts)。"""
    if content[:5] == b"%PDF-":
        text, _ = _pdf_text(content)
        if _meaningful(text):
            return "pdf-text", text, []
        parts = _pdf_images(content)
        if not parts:
            raise ApiError(422, "PDF 里没有页面")
        return "pdf-image", None, parts
    return "image", None, [_image_part(_open_image(content))]


# ---------------------------------------------------------------- 模型调用
def supports_vision_guess(config: ModelConfig) -> bool:
    model = (config.model or "").strip()
    if _VISION_HINT.search(model):
        return True
    return not _TEXT_ONLY.match(model)


def _is_vision_error(error: LlmError) -> bool:
    """带图片的请求被拒（400/415/422），或 404 且提到图片/视觉，按"模型不支持图片"处理。"""
    if error.status in (400, 415, 422):
        return True
    message = (error.message or "").lower()
    return error.status == 404 and any(word in message for word in _NO_VISION_WORDS)


def _messages(user: User, text: Optional[str], parts: List[dict]) -> List[dict]:
    periods = schedule.period_times(user)
    context = (f"本校每天共 {len(periods)} 节课，节次时间："
               + "，".join(f"第{i}节 {p['start']}-{p['end']}" for i, p in enumerate(periods, start=1))
               + f"。本学期共 {int(user.total_weeks or 20)} 周。")
    if text is not None:
        content = f"{context}\n以下是从 PDF 课表提取的文字（用空格保持了列的位置）：\n\n{text}"
        return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": f"{context}\n请识别这张课表。"}, *parts]}]


def _call(config: ModelConfig, messages: List[dict], with_images: bool) -> str:
    config = dataclasses.replace(config, timeout=max(config.timeout, VISION_TIMEOUT))
    try:
        # 不少视觉模型不支持 response_format，图片请求直接靠提示词约束 JSON
        return llm.chat(config, messages, json_mode=not with_images, temperature=0)
    except LlmError as error:
        if with_images and _is_vision_error(error):
            raise ApiError(422, NO_VISION_MESSAGE, {"detail": error.message}) from None
        raise ApiError(502, f"模型识别失败：{error.message}") from None


def parse_model_output(reply: str) -> dict:
    """解析模型 JSON；输出被截断时尽量抢救出完整的课程对象。"""
    try:
        data = llm.extract_json(reply)
        if isinstance(data.get("courses"), list):
            return data
    except LlmError:
        data = {}
    salvaged = []
    for match in re.finditer(r"\{[^{}]*\"course_name\"[^{}]*\}", reply or ""):
        try:
            salvaged.append(json.loads(match.group(0)))
        except ValueError:
            continue
    if salvaged:
        return {"courses": salvaged, **{k: v for k, v in data.items() if k in ("semester_start", "total_weeks")}}
    raise ApiError(502, "模型没有返回可识别的课表，请换一张更清晰的图片或重试")


# ---------------------------------------------------------------- 入口
def _merge_weeks(weeks, week_text) -> Optional[list]:
    """
    模型同时给了 weeks 列表和 week_text 时以 week_text 为准（列表常被省略成 [1,2]）；
    例外：week_text 没写单双周、而列表恰好是其中的单/双周（模型把 "2-16 even" 写成了 "2-16周"）。
    """
    parsed = schedule.parse_week_text(str(week_text or ""), import_common.MAX_WEEKS) if week_text else []
    if not parsed:
        return weeks
    if isinstance(weeks, list) and len(weeks) >= 2 and not re.search(r"[单双]", str(week_text)):
        try:
            numbers = sorted({int(w) for w in weeks})
        except (TypeError, ValueError):
            return parsed
        same_parity = len({n % 2 for n in numbers}) == 1
        if same_parity and set(numbers) <= set(parsed) and numbers == [n for n in parsed if n % 2 == numbers[0] % 2]:
            return numbers
    return parsed


def _normalize(data: dict, user: User) -> Tuple[List[dict], List[dict], int, Optional[str]]:
    base_total = int(user.total_weeks or 20)
    detected = data.get("total_weeks")
    detected = detected if isinstance(detected, int) and 1 <= detected <= import_common.MAX_WEEKS else None
    raw_items = [item for item in data.get("courses", []) if isinstance(item, dict)][:MAX_COURSES]

    # 先按最宽的 30 周校验，再根据实际出现的最大周次确定学期总周数
    staged, skipped = [], []
    for index, item in enumerate(raw_items, start=1):
        item = dict(item)
        item["weeks"] = _merge_weeks(item.get("weeks"), item.get("week_text"))
        if not item.get("weeks") and not str(item.get("week_text") or "").strip():
            item["weeks"] = list(range(1, (detected or base_total) + 1))
        course, reason = import_common.normalize_course(item, user, import_common.MAX_WEEKS)
        if course is None:
            skipped.append({"name": str(item.get("course_name") or f"第 {index} 条")[:60], "reason": reason})
        else:
            staged.append(course)
    total = detected or import_common.widen_total_weeks(staged, base_total)

    courses, seen = [], set()
    for course in staged:
        if course["weeks"][-1] > total:
            skipped.append({"name": course["course_name"][:60], "reason": f"周次超出学期（共 {total} 周）"})
            continue
        key = (course["course_name"], course["day_of_week"], course["start_period"], course["end_period"],
               tuple(course["weeks"]))
        if key not in seen:
            seen.add(key)
            courses.append(course)

    start = data.get("semester_start")
    start = start if isinstance(start, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) else None
    if start and timeutil.parse_date(start) is None:
        start = None
    return courses, skipped, total, start


def recognize_timetable(db: Session, user: User, config: ModelConfig, filename: str, content: bytes) -> dict:
    source, text, parts = _prepare(filename, content)
    if parts and not supports_vision_guess(config):
        raise ApiError(422, NO_VISION_MESSAGE)
    reply = _call(config, _messages(user, text, parts), with_images=bool(parts))
    courses, skipped, total, semester_start = _normalize(parse_model_output(reply), user)
    if not courses:
        raise ApiError(422, "没有识别出任何课程，请换一张更清晰、完整的课表图片", {"skipped": skipped})
    return import_common.build_preview(
        db, user, file_name=filename or None, fmt="ai", courses=courses, skipped=skipped,
        semester=None, semester_start=semester_start, total_weeks=total,
        source=source, model=f"{config.name} · {config.model}",
    )
