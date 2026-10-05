# astrbot_plugin_bili_cardfix

为 [astrbot_plugin_biliVideo](https://github.com/storyAura/astrbot_plugin_biliVideo) 恢复**新版 QQ B站小卡片**自动识别的运行时补丁。

**不改动原插件任何源码**；biliVideo 升级后补丁自动适配；热重载后自动自愈。

## 问题背景

biliVideo 从 v2.0 起重构了自动识别链路（GitHub commit `c429d05`），删除了 v1 版本中
「从消息组件字符串里用正则兜底提取 B 站链接」的逻辑，仅保留对 JSON 卡片中
`"qqdocurl"` 键的匹配。

QQ 当前发送的 B 站分享卡片（新版小程序卡片）**不含 `qqdocurl` 键**，链接位于
`url` / `jumpUrl` 字段。因此 v2 插件无法识别这类卡片——表现为群里收到
`[ComponentType.Json]` 消息但机器人无任何响应；而纯文本链接一切正常。

排查证据（服务器实测）：

| 输入 | v1（2.0 前） | v2（当前 v2.1.0） |
| --- | --- | --- |
| 纯文本链接 | ✅ | ✅ |
| 老版 structmsg 卡片（含 qqdocurl） | ✅ | ✅ |
| 新版小程序卡片（无 qqdocurl） | ✅ | ❌ |

## 方案

以 monkey-patch 方式，在运行时包装 biliVideo 的
`bilivideo.handlers.auto_detect.parse_event`：

1. 调用原始 `parse_event` 得到消息上下文；
2. 若消息含 JSON 卡片组件，用兜底正则（`b23.tv` 短链 / `bilibili.com/video` 长链 /
   `qqdocurl`）从组件字符串中提取链接，注入 `plain_text`；
3. 插件后续的链接提取链路无需改动，自然生效。

等效恢复 v1 的兜底能力，且不侵入插件内部逻辑。

## 自愈

AstrBot 热重载 biliVideo 插件时会重新加载其模块，补丁可能被冲掉。
本插件在**每条消息到达时**调用 `ensure_applied()`：

- `parse_event` 已是补丁版本（带 `__wrapped__` 标记）→ 跳过；
- 被冲掉 → 重新应用（幂等）。

无需手动干预，重启机器人或热重载任意插件后自动恢复。

## 安装

```bash
# 将插件目录放到 AstrBot 插件目录
cp -r astrbot_plugin_bili_cardfix /AstrBot/data/plugins/
# 重启 AstrBot 使插件被扫描加载（或 WebUI 重载）
docker restart astrbot
```

## 使用

无需配置。在群里发 B站小卡片即可自动识别。

可选命令：

- `/卡片补丁状态`（别名 `/cardfix`）——查看补丁是否生效及自检结果。

## 测试

```bash
docker exec -i astrbot python3 /AstrBot/data/plugins/astrbot_plugin_bili_cardfix/tests/test_patch.py
```

## 卸载 / 停用

在 AstrBot WebUI 停用本插件即可；biliVideo 恢复为原行为，不受任何影响。

## 致谢与灵感来源

- 兜底提取逻辑对齐 biliVideo **v1.0.5a**（`main.py` 中 `on_all_message` 的
  `str(comp)` 正则兜底），该版本小卡片识别正常。
- 代码结构参考 [mattpocock/skills](https://github.com/mattpocock/skills) 的工程规范：
  小而易适配、深模块（薄入口 + 封装细节）、内置自检反馈回路、防御式错误处理。
- 插件骨架遵循 [AstrBot 官方插件开发指南](https://docs.astrbot.app/dev/star/plugin-new)。
