# 鲸桥 WhaleBridge

连接 AstrBot 与微信的开源平台插件，基于已有的 MimicWX HTTP/UI 通道。

[![Checks](https://github.com/JulyEnd404/astrbot_plugin_whalebridge/actions/workflows/ci.yml/badge.svg)](https://github.com/JulyEnd404/astrbot_plugin_whalebridge/actions/workflows/ci.yml)

> **请先安装、运行并配置好 [AstrBot](https://github.com/AstrBotDevs/AstrBot)，再来安装本插件。**
> 本仓库是 AstrBot 的补充平台适配插件，依赖另行部署、已登录且接口兼容的 MimicWX；它不能独立运行，也不会替你安装微信、扫码登录或配置模型。

> [!WARNING]
> **第三方微信自动化可能违反平台协议，触发登录验证、功能限制或封号，也可能造成聊天隐私泄露、误发、重复或漏回。界面自动化和“开源”均不等于安全、官方授权或不会封号。**
> 使用前完整阅读 [风险与免责声明](DISCLAIMER.md) 和 [安全说明](SECURITY.md)。不接受这些风险时，请不要启用。请勿使用重要账号、敏感聊天或依赖此项目处理高风险事务。

WhaleBridge 把 MimicWX 的 HTTP 收发接口转换为 AstrBot 标准群消息事件，让已有的模型、人设、对话、分段和兼容插件继续工作。**不附带模型账号、积分额度、角色卡、群聊增强插件或个人长期记忆系统。**

## 开始使用

1. **先运行 AstrBot**，配置模型，并确认它已经能够完成普通 AI 对话。
2. 自行准备已登录的 Linux 微信和兼容的 MimicWX HTTP 服务。不要假定 MimicWX 最新版、OneBot 模式和本文接口完全相同。
3. 在 AstrBot 的插件管理中，从链接安装：`https://github.com/JulyEnd404/astrbot_plugin_whalebridge`。
4. 重启 AstrBot，在“消息平台 / 机器人”中添加 **鲸桥 WhaleBridge（实验性微信通道）**。
5. 填入私有 API 地址、令牌环境变量、机器人昵称和精确会话白名单；阅读免责声明后自行确认风险，再启用。
6. 只在一个经授权的测试群中验收文字，再验收图片。确认行为符合预期后再扩大范围。

**完整操作步骤、Docker 网络、参数、白名单和验收方法见 [安装与使用教程](docs/INSTALL.md)。** 插件页安装成功不等于微信已接通。

## 能做什么

| 能力 | 当前行为 |
| --- | --- |
| 接收消息 | 约每 2 秒轮询兼容 HTTP 通道；只接收配置的精确会话名称 |
| 输入 @ | 将文本中对配置昵称的 @ 转为 AstrBot `At` 组件；受微信界面信息限制 |
| 发文字、图片 | 文字，以及本地/内联 PNG、JPEG、GIF；超大图片适当压缩 |
| 动态表情 | 可传 GIF；某些 Linux 微信需要 [可选剪贴板补丁](transport/README.md) 才保留动画 |
| 群上下文 | 交给 AstrBot 和已安装插件处理，群标识由名称生成 |
| 启动与去重 | 默认跳过启动积压，保存消息去重及短期发言摘要；不能保证不丢消息或恰好发送一次 |
| 失败处理 | 不自动重试不确定的发送；一个会话不可用时，其余可用会话继续轮询 |

## 不能保证的事

- **无法得到稳定微信账号 ID。** 能读到的发送者也只是显示名；同名、改名和界面信息缺失都会影响身份判断。
- **不支持收到图片的真正视觉理解**，也不支持语音、文件接收、可靠的原生引用回复或原生 @ 他人。
- 默认 `unknown_sender_policy=mention_only`：身份未知时只接收明确 @，为每条消息分配不同匿名标识，不保证按人续聊。
- 可选 `group` 模式会把身份未知者视作同一个匿名群身份；它**不能**支持可靠个人记忆或“只回应最初呼叫者”。请勿与按人长期记忆一起使用。
- `_disable_personal_memory` 只是供其他插件识别的标记。第三方插件未主动遵守时，仍可能存储消息；本插件不能替它们保证隐私。
- 一套 MimicWX 只能有一个消费 `/listen/messages` 的程序。本插件阻止同一进程中重复的相同 API 地址配置，但不能阻止其他进程抢读。
- 对话内容可能经过 AstrBot、其他插件、日志系统和你配置的模型服务。本插件的摘要库不存正文，不代表整套系统不存正文。

## 主要文件

| 文件 | 用途 |
| --- | --- |
| [`main.py`](main.py) | 注册 AstrBot 平台、轮询、标准事件转换和发送 |
| [`config.py`](config.py) | 配置校验、环境变量取令牌和风险确认 |
| [`codec.py`](codec.py) | 会话/消息标识、身份降级、去重和防回声 |
| [`media.py`](media.py) | 图片格式、体积与解码资源限制、GIF 压缩 |
| [`examples/`](examples/) | 无真实凭据的配置样例和 Docker 网络扩展示例 |
| [`tools/`](tools/) | 生成群标识、只读检查兼容接口 |
| [`transport/`](transport/) | 可选 GIF 剪贴板修复，运行在 MimicWX 环境内 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 如何与 AstrBot 及 MimicWX 连接 |
| [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) | 版本与测试边界、上游兼容补丁 |
| [`docs/SOURCE_MAP.md`](docs/SOURCE_MAP.md) | 文件整理结果、原部署边界和开源来源 |
| [`tests/`](tests/) | 纯逻辑和原生 AstrBot 环境的隔离验证 |

## 版本与验证

- 公共版 `0.1.0` 为实验性版本。原生接口测试基线：AstrBot `4.29.1`、Python `3.12`、MimicWX `0.4.0` HTTP 接口形状。
- 不承诺与 MimicWX 所有分支、最新微信或全部 AstrBot 插件兼容；发布测试不包含任何人的真实账号、群聊或登录态。
- [兼容性说明](docs/COMPATIBILITY.md) 区分原部署的实测记录、公开版隔离测试和未验证部分。

本仓库自有代码按 [MIT](LICENSE) 许可。AstrBot、MimicWX、微信及依赖各自的许可和服务条款仍须独立遵守。作者与腾讯、微信、AstrBot、MimicWX 项目没有官方隶属或授权背书关系。
