# -*- coding: utf-8 -*-
"""阶段A 后端可观测底座：失败原因码、登录三态、截图、堆栈、URL、风控识别。

设计原则：
- 本模块只做“观测/记录”，绝不改变任何投递动作（定位/点击/翻页/发送）。
- 任何截图/取 URL/取文本的异常都必须 try 兜底，绝不抛出、绝不影响主投递。
- 风控只检测不绕过：命中特征只返回标志位，不做任何自动滑动/填验证码动作。
"""
import os
import re
import time
import traceback
from typing import Optional, Tuple


class ReasonCode:
    """失败原因码（机器可读，对齐诊断报告 6.1）"""
    BROWSER_CONNECT_FAIL = "BROWSER_CONNECT_FAIL"
    NOT_LOGGED_IN = "NOT_LOGGED_IN"
    LOGIN_UNKNOWN = "LOGIN_UNKNOWN"
    RISK_CONTROL = "RISK_CONTROL"
    LIST_EMPTY = "LIST_EMPTY"
    CARD_SELECTOR_FAIL = "CARD_SELECTOR_FAIL"
    APPLY_BTN_NOT_FOUND = "APPLY_BTN_NOT_FOUND"
    CHAT_BTN_NOT_FOUND = "CHAT_BTN_NOT_FOUND"
    BTN_CLICK_FAIL = "BTN_CLICK_FAIL"
    PAGE_DISCONNECTED = "PAGE_DISCONNECTED"
    OBJECT_TYPE_ERROR = "OBJECT_TYPE_ERROR"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    SUCCESS = "SUCCESS"
    UNKNOWN = "UNKNOWN"


class ErrorStage:
    """失败阶段枚举"""
    CONNECT = "connect"
    CHECK_LOGIN = "check_login"
    LIST = "list"
    PARSE = "parse"
    OPEN_DETAIL = "open_detail"
    CLICK_CHAT = "click_chat"
    DIALOG = "dialog"
    INPUT = "input"
    SEND = "send"
    CLOSE = "close"
    UNKNOWN = "unknown"  # 任意未捕获异常（无法定位阶段）


class LoginState:
    """登录三态（check_login 返回值）"""
    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    LOGIN_UNKNOWN = "unknown"
    RISK_CONTROL = "risk_control"  # 命中风控/安全验证页


# 风控特征（只检测，不绕过）
# 注意：URL 强信号只取 verify/geetest/captcha/security；
# 不单独取 "passport" —— 智联/猎聘的正常登录域就是 passport.*，
# 会把"未登录"误判成风控。Boss 极验真实 URL 含 /web/passport/zp/verify.html，仍命中 verify。
_RISK_URL_KEYWORDS = ("verify", "geetest", "captcha", "security")
_RISK_TEXT_KEYWORDS = (
    "安全验证", "滑块", "验证码", "访问频繁", "操作频繁",
    "账号异常", "访问验证", "请按住滑块",
)


def safe_page_url(page) -> str:
    """安全取当前页 URL，失败返回空串。"""
    if page is None:
        return ""
    try:
        url = getattr(page, "url", None)
        return str(url) if url else ""
    except Exception:
        return ""


def short_traceback(exc: Optional[BaseException] = None, limit: int = 1000) -> str:
    """返回截断到 <=limit 字符的堆栈字符串。

    exc 为 None 时取当前异常上下文（traceback.format_exc）。
    保留尾部（最贴近失败点与异常信息）。
    """
    try:
        if exc is None:
            s = traceback.format_exc()
        else:
            s = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        s = s.strip()
        if not s or s == "None":
            return ""
        return s[-limit:] if len(s) > limit else s
    except Exception:
        return ""


def sanitize_tag(tag: str) -> str:
    """把目录/文件名标识清洗为安全字符（只允许 字母数字 下划线 连字符）。"""
    try:
        s = re.sub(r"[^A-Za-z0-9_\-]", "_", str(tag or ""))
        s = re.sub(r"_+", "_", s).strip("_")
        return s or "stage"
    except Exception:
        return "stage"


def capture_failure(page, run_id, tag: str, reason_code: str,
                    settings_data_dir=None) -> str:
    """失败截图：存到 data_dir/screenshots/{run_id}/{tag}_{reason}_{ts}.png。

    返回相对 data_dir 的正斜线路径（如 screenshots/3/xxx.png）；
    任何异常都 try 兜底返回空串，绝不抛出。
    """
    try:
        if page is None:
            return ""
        # 取数据目录
        if settings_data_dir is None:
            from app.config import settings
            settings_data_dir = settings.data_dir
        run_dir = os.path.join(str(settings_data_dir), "screenshots", str(run_id))
        os.makedirs(run_dir, exist_ok=True)

        safe_tag = sanitize_tag(tag)
        safe_reason = sanitize_tag(reason_code)
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_tag}_{safe_reason}_{ts}.png"
        filepath = os.path.join(run_dir, filename)

        get_screenshot = getattr(page, "get_screenshot", None)
        if get_screenshot is None:
            print(f"[observability] page 无 get_screenshot 方法，跳过截图 run={run_id}")
            return ""

        # DrissionPage 4.1.0.0: get_screenshot(path=目录, name=文件名)
        get_screenshot(path=run_dir, name=filename)

        # 返回相对 data_dir 的正斜线路径
        rel = os.path.relpath(filepath, str(settings_data_dir)).replace(os.sep, "/")
        return rel
    except Exception as e:
        print(f"[observability] 截图失败(已降级) run={run_id}: {e}")
        return ""


def classify_message(message: str) -> str:
    """把自由文本失败消息归类为 reason_code（用于零改动给其余平台自动归类）。

    命中顺序按特异性从高到低。
    """
    if not message:
        return ReasonCode.UNKNOWN
    m = str(message)
    low = m.lower()
    try:
        # 对象类型错误（历史残留 to_tab / tab_ids / has no attribute）
        if "to_tab" in low or "tab_ids" in low or "has no attribute" in low:
            return ReasonCode.OBJECT_TYPE_ERROR
        # 页面连接断开
        if "连接已断开" in m or "与页面的连接已断开" in m or "disconnect" in low:
            return ReasonCode.PAGE_DISCONNECTED
        # 投递按钮未找到
        if "未找到投递按钮" in m or "未找到申请按钮" in m:
            return ReasonCode.APPLY_BTN_NOT_FOUND
        # 沟通按钮未找到
        if "未找到立即沟通按钮" in m or "未找到沟通按钮" in m:
            return ReasonCode.CHAT_BTN_NOT_FOUND
        # 按钮点击失败
        if "点击失败" in m:
            return ReasonCode.BTN_CLICK_FAIL
        # 已沟通过/已投递/已申请
        if "已沟通" in m or "已投递" in m or "已申请" in m:
            return ReasonCode.ALREADY_APPLIED
    except Exception:
        return ReasonCode.UNKNOWN
    return ReasonCode.UNKNOWN


def detect_risk_control(page) -> Tuple[bool, str]:
    """风控特征识别（只检测，不绕过）。

    返回 (是否命中, 命中特征描述)。取 html/text 必须 try 兜底。
    """
    try:
        url = safe_page_url(page)
        low_url = url.lower()
        for kw in _RISK_URL_KEYWORDS:
            if kw in low_url:
                return True, f"url:{kw}"

        # 取页面文本（多来源兜底）
        text = ""
        try:
            text = getattr(page, "html", "") or ""
        except Exception:
            text = ""
        if not text:
            try:
                text = page.run_js("return document.body.innerText") or ""
            except Exception:
                text = ""
        if not text:
            try:
                text = getattr(page, "text", "") or ""
            except Exception:
                text = ""

        for kw in _RISK_TEXT_KEYWORDS:
            if kw in text:
                return True, f"text:{kw}"
    except Exception as e:
        print(f"[observability] 风控识别异常(已降级): {e}")
    return False, ""
