# 安装与使用教程

**先安装并运行 AstrBot，并配置好能完成普通对话的模型，再安装本插件。** 没有 AstrBot，单独下载本仓库不能启动微信机器人。请先读 [README 风险警告](../README.md) 和 [完整免责声明](../DISCLAIMER.md)。

## 第一步：确认准备条件

- 已运行的 AstrBot；本版原生接口基线为 `4.29.1`，Python `3.12`。
- 你有权操作的 Linux 微信账号，已在你控制的环境中登录。
- 独立部署、具备下述 HTTP 接口的 MimicWX 服务。请参考 [上游固定版本](https://github.com/wx-11/MimicWX-Linux/tree/a42a3eec4e6efa2d023915e980e9af7d5fcf9439) 及 [兼容性说明](COMPATIBILITY.md)。不要盲用最新分支或混用 OneBot 模式。
- 机器人已加入一个取得适当授权、无同名歧义的测试群；部署者已完成必要的参与者告知和权限评估。

本插件不安装微信、不提取数据库密钥、不处理扫码登录，也不附带模型密钥或免费额度。上游安装脚本、镜像权限和账号授权需要你另外核验。

## 第二步：先确认 MimicWX 接口

本插件期望：

| 接口 | 用途 | 是否消费消息 |
| --- | --- | --- |
| `GET /status` | 返回 `{"status":"已登录", ...}` | 否 |
| `GET /listen` | 返回已监听会话名称数组 | 否 |
| `POST /listen` | 用 `{"who":"精确会话名称"}` 添加监听 | 否，但会操作微信窗口 |
| `GET /listen/messages` | 返回 `{会话名称: [消息...]}` | **是，取走待处理消息** |
| `POST /send` | `{"to":"会话名称","text":"文字"}` | 执行发送 |
| `POST /send_image` | `{"to":"会话名称","file":"原始Base64","name":"image.gif"}` | 执行发送 |

发送返回至少包含 `sent: true/false`，通常还带 `verified`。消息结构见 [架构与接口](ARCHITECTURE.md)。

**不要在机器人运行时手动调用 `/listen/messages` 做测试，也不要再启动第二个监听程序。** 可以使用下面的只读检查工具；它只调用 `/status` 和 `/listen`，不发送或消费消息。

在安全环境内设置 `MIMICWX_API_TOKEN`，不要把值发到聊天、Issue 或公共命令记录中，然后运行：

```sh
python tools/check_transport.py --url http://127.0.0.1:8899
```

令牌应与 MimicWX 配置中的 token 一致。启用 token 认证，不要使用公开、弱口令或他人的接口。

## 第三步：让 AstrBot 所在环境连到接口

- 两者是同一宿主机上的普通进程：可使用 `http://127.0.0.1:8899`。
- AstrBot 在容器内：这里的 `127.0.0.1` 指 AstrBot 容器自身，不是宿主机或另一个容器。
- 两者在 Docker 中：推荐只把 AstrBot 服务接入 MimicWX 所在的现有私有网络，使用该网络内的服务名，例如 `http://mimicwx:8899`。

[Docker 扩展示例](../examples/compose.astrbot.override.yaml) 只是在**你原有 AstrBot Compose**上增加环境变量和已有网络，不负责创建 MimicWX。检查服务名、网络名，合并时保留原有卷、其他网络和设置，先备份配置及数据。

`.env.example` 只含占位符。复制到你私有的部署目录并填写，确保不提交 Git。`MIMICWX_API_TOKEN` 必须注入 **AstrBot 进程/容器**；仅在自己电脑的终端设置，不会自动传进云端容器。

不要为图方便发布 API、VNC 或管理端口到公网。跨不可信网络使用有效 HTTPS 和访问控制，不要关闭证书校验。

## 第四步：安装插件

在 AstrBot 管理面板进入“插件”，选择从链接安装：

```text
https://github.com/JulyEnd404/astrbot_plugin_whalebridge
```

检查依赖安装及插件加载状态，然后重启 AstrBot 一次，让新增平台出现在消息平台选择列表中。仅安装插件不会自动登录微信或启用通道。

开发者也可将仓库放到 AstrBot 的 `data/plugins/astrbot_plugin_whalebridge/` 中，按 AstrBot 官方文档安装依赖并重启。

## 第五步：添加消息平台

在 AstrBot 的“消息平台 / 机器人”页新增 **鲸桥 WhaleBridge（实验性微信通道）**。这是平台配置，不是在插件页随意新增一份 JSON。

| 参数 | 说明 |
| --- | --- |
| `id` | 例如 `whalebridge-wechat`；使用后不要随意更改，会影响会话及去重数据命名空间 |
| `enable` | 默认关闭；完成配置和风险评估后自行开启 |
| `risk_acknowledged` | 阅读风险后显式设为 `true`；它不能替代法律授权 |
| `api_url` | MimicWX 的 HTTP(S) origin；不得附带账号、密码、路径、查询参数或 fragment |
| `api_token_env` | 推荐 `MIMICWX_API_TOKEN`；填写环境变量**名称**，不是令牌值 |
| `api_token` | 仅在清空 `api_token_env` 后用作备用；不建议直接存真实令牌 |
| `groups` | 精确会话名称列表；最多30个，先只填一个授权测试群 |
| `self_name` | 机器人当前微信显示名 |
| `mention_names` | 群内 @ 机器人时出现的昵称列表；先使用实际显示名 |
| `unknown_sender_policy` | 默认 `mention_only`；其他选项的限制见下文 |
| `poll_interval` | 1–30秒，默认2秒 |
| `discard_startup_backlog` | 默认 `true`，启动跳过积压；这也可能丢掉启动过程中的新消息 |

无真实凭据的完整样例见 [examples/platform.json](../examples/platform.json)。如果通过配置文件维护，应在停止 AstrBot 并备份后，将该对象合并进全局 `data/cmd_config.json` 的 `platform` 数组，**保留已有平台**，然后再启动。不同 profile 中的同名 `platform` 不是本插件的生效入口。

### 身份不明时怎么处理

- `drop`：丢弃所有无法识别发言者的消息。
- `mention_only`：默认。只接收明确 @；每条消息使用不同匿名标识，不保证按人续聊。
- `group`：允许身份未知消息参与群话题，共用一个匿名群标识。所有身份未知者在技术上会被当成同一主体，**不能**做可靠个人记忆、管理员识别或只回应最初呼叫者。

三个选项都不能修复真实微信 ID 的缺失。同名显示名也可能串人。启用任何个人记忆插件前必须单独核验；未知身份标记不会强制第三方插件停止存储。

## 第六步：绑定模型、人设和核心白名单

本插件只收发消息。模型、人设、上下文和回答风格在 AstrBot 中配置；可为该通道/群绑定自己的配置文件和人格。不要照搬别人的真实账号、群名单或模型登录数据。

群标识根据名称的 UTF-8 字节生成。运行：

```sh
python tools/group_ids.py '机器人测试群'
```

将输出的 `group_id` 加到你启用的 AstrBot 核心 `platform_settings.id_whitelist`。不要为了连通而关闭全局白名单。若要按通道绑定配置，使用工具输出的 `unified_msg_origin`。

如果另外安装群聊增强插件，应按该插件说明，把同一个 `group_id` 加进它的允许群列表，核对唤醒词、概率、分段和数据保存行为。QQ专属的戳一戳、群管理或协议组件不保证在微信可用。本仓库不自动安装或改写其他插件，也不保证它们会尊重隐私标记。

## 第七步：实际验收

1. 确认日志没有持续通道错误，`health.json` 中配置会话数与可用会话数一致。
2. 从另一个有权参与测试的账号，在测试群准确 @ 机器人，发送一句普通问题。
3. 核对它只回复到预期会话，内容、人设和发言者识别符合预期。
4. 再测试一张本地图片和可选动态 GIF；不要用隐私图片或敏感信息验收。
5. 只有确认风险及行为后再增加会话。不要同时有两个相同显示名的目标。

群改名会产生新的哈希标识，相应白名单、profile 路由和历史隔离需要人工重新核验，不要假定会自动继承。

## 数据、停止与升级

每个平台ID对应数据目录 `data/plugin_data/astrbot_plugin_whalebridge/instance_<哈希>/`，含 `bridge.sqlite3` 和只含计数/状态的 `health.json`。去重记录保留约7天，发言摘要保留约5分钟；上游与其他插件的正文和日志不由本插件控制。

在 AstrBot 停用或删除该平台配置可以停止本通道；这不保证会停止其他消费者或删除其他组件保存的数据。不要通过删除去重库来解决重复回复，这可能引发旧消息再次处理。

升级前备份私有配置、插件数据和已登录客户端数据，阅读变更；先在测试环境验证，再选择是否更新。插件与客户端升级均不保证免扫码、不断线或不丢消息。不要为了升级这个插件盲目删除微信登录卷。

故障排查见 [FAQ](FAQ.md)。
