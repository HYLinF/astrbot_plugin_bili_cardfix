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

> 前置要求：你的 AstrBot 已能正常运行，且已安装
> [astrbot_plugin_biliVideo](https://github.com/storyAura/astrbot_plugin_biliVideo)
>（本插件是它的补丁，不依赖它就无法工作）。

### 第一步：获取插件源码

任选一种方式：

**方式 A：git clone（推荐）**

```bash
git clone https://github.com/HYLinF/astrbot_plugin_bili_cardfix.git
```

**方式 B：下载 ZIP**

打开仓库页面 → 绿色 **Code** 按钮 → **Download ZIP** → 解压。
注意：ZIP 解压出来的文件夹名会带分支后缀（如 `astrbot_plugin_bili_cardfix-main`），
建议重命名为 `astrbot_plugin_bili_cardfix`，方便后续操作与识别。

### 第二步：找到你的 AstrBot 插件目录

插件目录就是 AstrBot 的 `data/plugins/` 目录，位置取决于你的部署方式：

| 部署方式 | 插件目录位置 |
| --- | --- |
| Docker（soulter/astrbot 镜像） | 容器内固定为 `/AstrBot/data/plugins/` |
| 本机直接运行（pip / 源码启动） | AstrBot 程序目录下的 `data/plugins/`（如 `D:\AstrBot\data\plugins\`、`/root/AstrBot/data/plugins/`） |

Docker 部署时，先确认容器是否挂载了宿主机目录（挂载了就直接往宿主机对应路径放文件，更方便）：

```bash
docker inspect astrbot | grep -A 5 '"Mounts"'
# 如果看到 /AstrBot 或 data 目录的挂载映射，记下宿主机路径
```

### 第三步：把插件放进插件目录

最终效果是插件目录下出现 `astrbot_plugin_bili_cardfix/main.py`。

**情况 1：本机直接运行**

把整个 `astrbot_plugin_bili_cardfix` 文件夹复制到插件目录。

```bash
# Linux / macOS
cp -r astrbot_plugin_bili_cardfix /root/AstrBot/data/plugins/

# Windows（PowerShell），假设 AstrBot 装在 D:\AstrBot
Copy-Item -Recurse astrbot_plugin_bili_cardfix D:\AstrBot\data\plugins\
```

**情况 2：Docker，且插件目录挂载了宿主机路径**

直接把文件夹复制到宿主机对应的挂载路径（参照第二步查到的 Mounts）。

**情况 3：Docker，未挂载插件目录**

用 `docker cp` 把文件夹拷进容器，并修正权限：

```bash
docker cp astrbot_plugin_bili_cardfix astrbot:/AstrBot/data/plugins/
docker exec astrbot chmod -R a+rX /AstrBot/data/plugins/astrbot_plugin_bili_cardfix
```

> ⚠️ 无论哪种方式，请确认复制后**插件目录里没有嵌套重复**，即路径是
> `<插件目录>/astrbot_plugin_bili_cardfix/main.py`，而不是
> `<插件目录>/astrbot_plugin_bili_cardfix/astrbot_plugin_bili_cardfix/main.py`。

### 第四步：重启 AstrBot 加载插件

```bash
# Docker
docker restart astrbot

# 本机运行：重启 AstrBot 进程，或 WebUI → 插件管理 → 重载
```

重启期间机器人会短暂离线（约 30~60 秒），属正常现象。
重启后 AstrBot 会自动扫描 `data/plugins/` 目录并加载新插件。

### 第五步：验证安装成功

1. **看日志**（Docker：`docker logs astrbot`；本机：看控制台输出），应出现：

   ```
   biliVideo 卡片识别补丁已生效
   ```

   如果出现的是 `暂未生效`，说明 biliVideo 还没加载完，收到下一条群消息时会自动重试，无需处理。

2. **群内自检**：给机器人发 `/卡片补丁状态`（别名 `/cardfix`），应显示：

   ```
   📌 biliVideo 卡片识别补丁
   状态: ✅ 已生效
   自检: ...（三项全部 ✅）
   ```

3. **实测**：往群里发一个 B站视频的小卡片（不是纯文本链接），机器人应自动回复视频信息（封面、UP主、播放量等）。若纯文本链接正常、卡片无响应，说明补丁未生效，按下面「常见问题」排查。

### 常见问题（FAQ）

| 现象 | 原因与处理 |
| --- | --- |
| 日志/命令显示 `暂未生效` | biliVideo 尚未加载。重启后等 1 分钟再试，或手动发一条消息触发自愈 |
| 插件目录已放好但没被加载 | 确认目录下有 `main.py`；重启而非仅热重载；检查权限（见第三步） |
| 复制后多了一层同名目录 | 参考第三步的警告，把外层多余目录删掉，只保留 `astrbot_plugin_bili_cardfix/main.py` |
| 之前装过旧版补丁 | 先删除旧插件目录再安装新版本，避免重复补丁 |

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
