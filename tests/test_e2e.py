"""端到端模拟验证：补丁后 biliVideo 能否识别新版小程序卡片（只读模拟）。"""
import asyncio
import json
import sys

sys.path.insert(0, "/tmp/astrbot_plugin_bili_cardfix")

# 1. 加载补丁并应用
from cardfix import patch as cardfix_patch

assert cardfix_patch.ensure_applied(), "补丁应用失败"
print("1) 补丁已应用:", cardfix_patch.is_applied())

# 2. 构造真实形态的 OneBot Event（新版小程序卡片，无 qqdocurl）
card = {
    "app": "com.tencent.mini.app",
    "desc": "哔哩哔哩",
    "meta": {"mini_app": {"appid": "1111153846", "title": "测试视频",
        "url": "https://b23.tv/abcDEFg", "preview": "http://x/p.jpg"}},
    "prompt": "[QQ小程序] 哔哩哔哩",
}
card_json = json.dumps(card, ensure_ascii=False)
event_payload = {
    "post_type": "message", "message_type": "group",
    "self_id": 3326727370, "group_id": 605753039, "user_id": 2849904642,
    "message": [{"type": "json", "data": {"data": card_json}}],
    "raw_message": f"[CQ:json,data={card_json}]",
    "font": 14, "sender": {"user_id": 2849904642, "nickname": "寒", "card": "寒"},
}

# 3. 用 AstrBot 组件构造事件替身
from astrbot.core.message.components import Json

comp = Json(data={"data": card_json})

class FakeMsgObj:
    raw_message = event_payload
    message = [comp]

class FakeEvent:
    message_str = ""
    message_obj = FakeMsgObj()

# 4. 调用补丁后的 parse_event
import data.plugins.astrbot_plugin_biliVideo.bilivideo.handlers.auto_detect as ad

ctx = ad.parse_event(FakeEvent())
print("2) parse_event 后 plain_text:", repr(ctx.plain_text))
assert "b23.tv" in ctx.plain_text, "plain_text 未注入链接！"

# 5. 跑 _resolve_bvid 全链路（短链跳转用 stub）
class FakeHttp:
    @staticmethod
    async def follow_redirect(url):
        print("   follow_redirect:", url)
        return "https://www.bilibili.com/video/BV1WWHv6FE82"

class FakeServices:
    http_client = FakeHttp()

async def main():
    bvid = await ad._resolve_bvid(FakeServices(), ctx, allow_full_text=not ctx.is_reply)
    print("3) _resolve_bvid 结果:", bvid)
    assert bvid == "BV1WWHv6FE82", f"未识别到 BV: {bvid}"
    print("\n✅ 端到端验证通过：新版小程序卡片 → 补丁后成功解析出 BV")

asyncio.run(main())
