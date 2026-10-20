# 文件整理与来源

本仓库把原来散落在部署项目中的微信接入整理成独立 AstrBot 插件。公开版只负责微信通道，不是原服务器的完整备份。

| 部分 | 主要文件 | 与原系统的关系 |
| --- | --- | --- |
| 核心接入 | `main.py` | 独立的 AstrBot 平台注册、事件接入与发送 |
| 配置与身份 | `config.py`、`codec.py` | 公开配置校验、名称路由、身份降级和持久去重 |
| 图片 | `media.py` | 从原接入需求整理出的体积/解码限制与 GIF 处理 |
| 运维辅助 | `tools/`、`examples/` | 无真实账号和令牌的独立样例；检查工具不发消息、不消费消息 |
| GIF 可选补丁 | `transport/` | 本项目编写的 xclip 包装脚本和派生镜像模板 |
| 上游 UI 可选补丁 | `patches/` | 基于固定 MimicWX 源码的增量修改，非完整上游分发 |
| 文档和测试 | `docs/`、`tests/`、`.github/` | 为公开版新增，以合成数据验证 |

不分发：微信二进制、登录数据、聊天数据库、服务器访问文件、实际会话名单、私人角色/记忆、模型密钥、WorkBuddy/CodeBuddy 登录或额度桥接、QQ 专用发言限制插件、第三方群聊增强插件与表情包素材。

用户自己在 AstrBot 中配置模型、人设、上下文和兼容的群聊增强功能。仅装本插件，不会自动复制原部署的聊天风格或全部功能。

## 开源项目与许可

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)：提供插件与平台接口。本仓库通过接口连接，不分发 AstrBot 核心；其代码许可独立适用。
- [MimicWX-Linux 固定来源](https://github.com/wx-11/MimicWX-Linux/tree/a42a3eec4e6efa2d023915e980e9af7d5fcf9439)：提供 HTTP/UI 传输。该提交的 [Cargo.toml](https://github.com/wx-11/MimicWX-Linux/blob/a42a3eec4e6efa2d023915e980e9af7d5fcf9439/Cargo.toml) 和 README 声明 MIT；该提交根目录没有独立 LICENSE 文件。补丁中的上游上下文仍归原作者和贡献者所有，不将其冒称为本项目原创。参见 [第三方来源告知](../patches/NOTICE.md)。
- aiohttp、Pillow 及其传递依赖：由安装环境取得，各自许可独立适用。

本项目自有代码按 [MIT](../LICENSE) 许可。许可证不授予微信官方授权，也不免除服务协议、隐私和其他法律义务。不要把上游宣传中的“零风险”当作本项目承诺。
