# 图文教程截图来源

这些 JPEG 是 **2026-10-21 实际操作 AstrBot 后台时取得的原始页面截图**，没有用绘图、拼接或生成界面代替实操。

- 环境：独立的 AstrBot **4.29.1 / Python 3.12** 容器，使用 [兼容性说明](../../COMPATIBILITY.md) 中固定的官方镜像。
- 数据：使用教学账号、示例「机器人测试群」「小助手」，没有真实聊天、微信登录态、模型密钥或生产令牌。`MIMICWX_API_TOKEN` 是环境变量名称，截图不含它的值。
- 安装：初装 0.1.0 时通过后台「从链接安装」读取本项目 GitHub 仓库。实跑发现列表表单类型问题后发布 0.1.1；后台更新因 GitHub 下载断开而失败，随后以固定提交 [`192586a`](https://github.com/JulyEnd404/astrbot_plugin_whalebridge/commit/192586a0c07b52757e7f1799713c0d952615c571) 的源码手动更新插件目录并重启。更新后的画面仍是实际 AstrBot 界面。
- 表单验证：在 0.1.1 后台创建平台、填写并保存；核对落盘的 `groups`、`mention_names` 为列表，数值及布尔字段类型正确，并用插件的 `settings_from()` 验证通过。已部署 `main.py` 的 SHA-256 与该提交相同：`118baefa1d9e2a021313a2052adb6a0d6264d1d29a96f8616a90379000e229a7`。
- 运行验证：同一固定 AstrBot 镜像内的 **25 项隔离测试全部通过**，测试只使用合成数据。
- 边界：教学微信平台始终保持停用；截图中的 `http://mimicwx:8899` 是地址格式示例，没有连接真实 MimicWX。模型截图只打开了空白配置表单，没有配置密钥或调用模型。**安装、配置保存、隔离测试不等于真实微信端到端验收**；读者仍须按 [教程第七步](../../INSTALL.md#第七步实际验收) 在自己有权使用的账号与测试群验收。

| 文件 | 实际画面 |
| --- | --- |
| [01](01-astrbot-login.jpg) | 干净教学实例的登录页，输入框为空 |
| [02](02-dashboard-sections.jpg) | 欢迎页与「机器人」「模型提供商」等导航入口 |
| [03](03-install-from-github.jpg) | 从公开 GitHub 链接安装插件的弹窗 |
| [04](04-plugin-installed.jpg) | 修复后的 0.1.1 已加载插件卡片 |
| [05](05-select-mimicwx.jpg) | 创建机器人时实际的 `mimicwx` 类别选项 |
| [06](06-platform-connection.jpg) | 0.1.1 平台表单的 API 地址及令牌环境变量名 |
| [07](07-platform-lists.jpg) | 精确会话及 @ 昵称列表、匿名策略与轮询设置 |
| [08](08-platform-saved.jpg) | 已实际保存、保持停用的教学平台 |
| [09](09-model-provider-entry.jpg) | 「模型提供商」的独立入口 |
| [10](10-model-api-fields.jpg) | 模型提供商的 API Key 与 API Base URL 字段，密钥为空 |

页面中的服务名、群名和昵称请换成自己的设置；不要照抄教学配置后直接启用。
