"""biliVideo 卡片识别补丁核心（深模块：对外只暴露 ensure_applied / is_applied / self_check）。

背景
----
astrbot_plugin_biliVideo 从 v2.0 起重构了自动识别链路（GitHub commit c429d05），
删除了 v1 版本中「从消息组件字符串里用正则兜底提取 B 站链接」的逻辑，仅保留对
JSON 卡片中 ``"qqdocurl"`` 键的匹配。

QQ 当前发送的 B 站分享卡片（新版小程序卡片）不含 ``qqdocurl`` 键，链接位于
``url`` / ``jumpUrl`` 字段，因此 v2 插件无法识别这类卡片（线上日志表现为
收到 ``[ComponentType.Json]`` 消息但无任何响应）。

方案
----
不修改 biliVideo 任何源文件。以 monkey-patch 方式，在运行时包装
``data.plugins.astrbot_plugin_biliVideo.bilivideo.handlers.auto_detect.parse_event``：

1. 先调用原始 parse_event 得到 MessageContext；
2. 若消息包含 JSON 卡片组件（``ctx.json_card_text`` 非空）且文本中没有链接，
   用兜底正则（b23.tv 短链 / bilibili.com/video 长链 / qqdocurl）从组件字符串中
   提取链接并注入 ``ctx.plain_text``；
3. 插件后续的 ``_resolve_bvid`` 文本提取链路无需改动，自然生效。

自愈
----
AstrBot 热重载 biliVideo 插件时会重新加载其模块，已应用的补丁可能被冲掉。
main.py 在每条消息到达时调用 ``ensure_applied()`` 确保补丁始终在位：
- 若 ``parse_event`` 已是本补丁的包装版本（带 ``__wrapped__`` 标记）则跳过；
- 否则重新 apply（幂等，重复调用安全）。

设计原则（参考 mattpocock/skills：small / composable / deep module）
- 对外只暴露三个函数，解析细节全部封装在本模块内，main.py 保持薄入口；
- apply 幂等、自检内置，任何异常都不会让消息处理崩溃。
"""

from __future__ import annotations

import importlib
import logging
import re
from typing import Any

logger = logging.getLogger("astrbot_plugin_bili_cardfix")

# biliVideo 插件在 AstrBot 中的模块路径（AstrBot 以 data.plugins.<name> 加载插件）。
TARGET_MODULE = (
    "data.plugins.astrbot_plugin_biliVideo.bilivideo.handlers.auto_detect"
)

# ─────────────────────────── 兜底提取正则 ───────────────────────────
# 与 v1 版本能力对齐：不管卡片 JSON 以何种键名承载链接，都能从组件字符串中捞出来。

_QQDOC_RE = re.compile(r'"qqdocurl"\s*:\s*"(https?://[^"]+)"')
_SHORT_RE = re.compile(
    r"https?://(?:b23\.tv|bili2233\.cn|bili22\.cn|bili23\.cn|bili33\.cn)/\S{1,256}",
    re.IGNORECASE,
)
_LONG_RE = re.compile(
    r"https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9/?=&_.\-]+",
    re.IGNORECASE,
)

# bilibili 短链 / 官方域名，用于判定提取结果是否是 B 站链接。
_BILI_HOST_SUFFIXES = (
    "bilibili.com",
    "b23.tv",
    "bili2233.cn",
    "bili22.cn",
    "bili23.cn",
    "bili33.cn",
)

# 聊天/组件字符串中常见的尾随符号（引用、逗号、括号、标点等）。
_TRAILING_URL_CHARS = "\"'`}>]),，。）、）！!？?；;：:"


# ─────────────────────────── 纯函数提取 ───────────────────────────


def _is_bili_url(url: str) -> bool:
    """判断一个 URL 的域名是否属于 B 站（含官方短链域名）。"""
    if not url:
        return False
    try:
        import urllib.parse

        host = (urllib.parse.urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return any(host == d or host.endswith("." + d) for d in _BILI_HOST_SUFFIXES)


def _clean_url(url: str) -> str:
    """去掉 URL 前后聊天符号 / 组件 repr 残留的字符。"""
    return (url or "").strip().strip("<>").rstrip(_TRAILING_URL_CHARS)


def extract_bili_url(text: str) -> str | None:
    """从任意文本（pydantic repr / CQ 码 / JSON 字符串）中提取第一个 B 站链接。

    按优先级依次尝试：
    1. ``"qqdocurl"`` 键（v2 原有能力，保留）；
    2. b23.tv 等官方短链；
    3. bilibili.com/video 长链。
    """
    if not text:
        return None

    m = _QQDOC_RE.search(text)
    if m and _is_bili_url(m.group(1)):
        return m.group(1)

    m = _SHORT_RE.search(text)
    if m:
        url = _clean_url(m.group(0))
        if url:
            return url

    m = _LONG_RE.search(text)
    if m:
        url = _clean_url(m.group(0))
        if url:
            return url

    return None


# ─────────────────────────── patch 应用 ───────────────────────────


def _load_target() -> Any:
    """获取 biliVideo 的 auto_detect 模块（始终取 sys.modules 中的当前对象）。"""
    return importlib.import_module(TARGET_MODULE)


def _make_wrapper(original: Any) -> Any:
    """构造 parse_event 的包装版本：解析卡片链接并注入 plain_text。"""

    def wrapper(event: Any) -> Any:
        ctx = original(event)
        # 无卡片组件，或文本里已经有链接时不做干预。
        if not getattr(ctx, "json_card_text", None):
            return ctx
        if extract_bili_url(getattr(ctx, "plain_text", "")):
            return ctx
        url = extract_bili_url(ctx.json_card_text)
        if url:
            ctx.plain_text = f"{ctx.plain_text} {url}".strip()
        return ctx

    # 保留原函数元信息；__wrapped__ 同时作为「已补丁」的自愈标记。
    wrapper.__name__ = original.__name__
    wrapper.__module__ = original.__module__
    wrapper.__qualname__ = original.__qualname__
    wrapper.__doc__ = original.__doc__
    wrapper.__wrapped__ = original
    return wrapper


def is_applied() -> bool:
    """当前 biliVideo 的 parse_event 是否已被本补丁包装。"""
    try:
        target = _load_target()
    except (ImportError, ModuleNotFoundError):
        return False
    fn = getattr(target, "parse_event", None)
    return fn is not None and getattr(fn, "__wrapped__", None) is not None


def apply() -> bool:
    """对当前 biliVideo 模块应用补丁。幂等：已补丁则跳过。"""
    if is_applied():
        return True
    target = _load_target()
    original = getattr(target, "parse_event", None)
    if original is None:
        logger.warning("未找到 parse_event，跳过补丁（biliVideo 可能未加载）")
        return False
    setattr(target, "parse_event", _make_wrapper(original))
    logger.info("biliVideo 卡片识别补丁已应用")
    return True


def ensure_applied() -> bool:
    """确保补丁在位；不在位则重新应用。任何异常都不抛出，避免影响消息处理。"""
    try:
        if is_applied():
            return True
        return apply()
    except (ImportError, ModuleNotFoundError):
        # biliVideo 尚未被加载，等下一次消息到达时自愈。
        logger.debug("biliVideo 模块尚不可用，补丁延迟到下次消息时应用")
        return False
    except Exception:  # pragma: no cover - 防御：补丁失败不影响消息流
        logger.exception("biliVideo 卡片识别补丁应用失败")
        return False


# ─────────────────────────── 自检 ───────────────────────────


def self_check() -> dict:
    """用真实形态的卡片样本验证提取能力，返回明细（供状态命令展示）。"""
    # 样本1：老版 structmsg 新闻卡片（含 qqdocurl）——v2 原本应能识别
    card_old = (
        '{"app": "com.tencent.structmsg", "desc": "【测试】标题", '
        '"meta": {"news": {"tag": "哔哩哔哩", "jumpUrl": "https://b23.tv/abcDEFg", '
        '"qqdocurl": "https://b23.tv/abcDEFg"}}, "view": "news"}'
    )
    # 样本2：新版小程序卡片（无 qqdocurl，链接在 url 字段）——v2 识别失败的形态
    card_new = (
        '{"app": "com.tencent.mini.app", "desc": "哔哩哔哩", '
        '"meta": {"mini_app": {"appid": "1111153846", "title": "标题", '
        '"url": "https://b23.tv/abcDEFg", "preview": "http://x/p.jpg"}}, '
        '"prompt": "[QQ小程序] 哔哩哔哩"}'
    )
    # 样本3：无关卡片（不应误报）
    card_noise = '{"app": "com.tencent.structmsg", "desc": "无关分享", "meta": {"news": {"title": "xxx"}}}'

    def _simulate_component_str(card_json: str) -> str:
        # 模拟 AstrBot Json 组件 str() 的形态（pydantic repr，卡片 JSON 以字符串嵌套）
        return f"type=<ComponentType.Json: 'Json'> data={{'data': '{card_json}'}}"

    results = {
        "老版structmsg(含qqdocurl)": bool(extract_bili_url(_simulate_component_str(card_old))),
        "新版小程序(无qqdocurl)": bool(extract_bili_url(_simulate_component_str(card_new))),
        "无关卡片(不应误报)": not extract_bili_url(_simulate_component_str(card_noise)),
    }
    return {"applied": is_applied(), "samples": results}
