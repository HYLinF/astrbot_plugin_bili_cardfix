"""补丁核心逻辑测试。

运行方式（容器内）：
    docker exec -i astrbot bash -c "cd /AstrBot/data/plugins/astrbot_plugin_bili_cardfix && python3 -m pytest tests/ -q"
或直接：
    docker exec -i astrbot python3 /AstrBot/data/plugins/astrbot_plugin_bili_cardfix/tests/test_patch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让补丁包可被导入（容器内 sys.path 已有 /AstrBot）
PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from cardfix.patch import extract_bili_url  # noqa: E402


def _simulate_component_str(card_json: str) -> str:
    """模拟 AstrBot Json 组件 str() 输出（pydantic repr，卡片 JSON 嵌套为字符串）。"""
    return f"type=<ComponentType.Json: 'Json'> data={{'data': '{card_json}'}}"


# 老版 structmsg 卡片（含 qqdocurl）
CARD_OLD = (
    '{"app": "com.tencent.structmsg", "desc": "【测试】标题", '
    '"meta": {"news": {"tag": "哔哩哔哩", "jumpUrl": "https://b23.tv/abcDEFg", '
    '"qqdocurl": "https://b23.tv/abcDEFg"}}, "view": "news"}'
)
# 新版小程序卡片（无 qqdocurl，链接在 url 字段）
CARD_NEW = (
    '{"app": "com.tencent.mini.app", "desc": "哔哩哔哩", '
    '"meta": {"mini_app": {"appid": "1111153846", "title": "标题", '
    '"url": "https://b23.tv/abcDEFg", "preview": "http://x/p.jpg"}}, '
    '"prompt": "[QQ小程序] 哔哩哔哩"}'
)
# bilibili.com 长链卡片
CARD_LONG = (
    '{"app": "com.tencent.structmsg", "desc": "视频", '
    '"meta": {"news": {"qqdocurl": "https://www.bilibili.com/video/BV1WWHv6FE82"}}}'
)
# 无关卡片（不应误报）
CARD_NOISE = '{"app": "com.tencent.structmsg", "desc": "无关分享", "meta": {"news": {"title": "xxx"}}}'


def test_extract_old_structmsg():
    url = extract_bili_url(_simulate_component_str(CARD_OLD))
    assert url == "https://b23.tv/abcDEFg", url


def test_extract_new_miniapp():
    url = extract_bili_url(_simulate_component_str(CARD_NEW))
    assert url == "https://b23.tv/abcDEFg", url


def test_extract_long_url():
    url = extract_bili_url(_simulate_component_str(CARD_LONG))
    assert url == "https://www.bilibili.com/video/BV1WWHv6FE82", url


def test_no_false_positive():
    assert extract_bili_url(_simulate_component_str(CARD_NOISE)) is None


def test_clean_trailing_chars():
    # 组件 repr 中 URL 后可能残留引号/大括号
    text = 'some text https://b23.tv/abcDEFg", }, tail'
    assert extract_bili_url(text) == "https://b23.tv/abcDEFg"


def test_rejects_non_bili_domain():
    text = 'https://example.com/abc'
    assert extract_bili_url(text) is None


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'-' * 40}\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
