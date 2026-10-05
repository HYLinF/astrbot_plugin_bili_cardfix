"""biliVideo 卡片识别补丁（AstrBot 插件入口）。

不改动 astrbot_plugin_biliVideo 任何源文件；通过运行时 monkey-patch
恢复其对新版 QQ B站小卡片的自动识别，并自带热重载自愈。

- 加载时尝试应用补丁；
- 每条消息到达时调用 ``ensure_applied()`` 自愈（热重载冲掉补丁后自动重挂）；
- 提供 ``/卡片补丁状态`` 命令查看生效情况与自检结果。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .cardfix import patch as cardfix_patch


class BiliCardFixPlugin(Star):
    """biliVideo 卡片识别补丁插件。"""

    def __init__(self, context: Context) -> None:
        super().__init__(context)
        applied = cardfix_patch.ensure_applied()
        if applied:
            logger.info("biliVideo 卡片识别补丁已生效")
        else:
            logger.info(
                "biliVideo 卡片识别补丁暂未生效（biliVideo 可能尚未加载，"
                "收到下一条消息时会自动重试）"
            )

    @filter.command("卡片补丁状态", alias={"cardfix", "卡片修复状态"})
    async def cmd_status(self, event: AstrMessageEvent) -> AsyncIterator[object]:
        """查看补丁生效情况与自检结果。"""
        applied = cardfix_patch.ensure_applied()
        check = cardfix_patch.self_check()
        lines = [
            "📌 biliVideo 卡片识别补丁",
            f"状态: {'✅ 已生效' if applied else '⚠️ 未生效（biliVideo 未加载？）'}",
            "自检:",
        ]
        for name, ok in check["samples"].items():
            lines.append(f"  - {name}: {'✅' if ok else '❌'}")
        yield event.plain_result("\n".join(lines))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_message(self, event: AstrMessageEvent) -> None:
        """自愈钩子：每条消息确保补丁在位；不产出任何回复。

        本函数只保证补丁存在，识别与回复仍由 biliVideo 插件完成。
        """
        cardfix_patch.ensure_applied()
