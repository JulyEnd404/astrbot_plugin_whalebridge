# 兼容性与验证边界

**先部署 AstrBot，再接入本插件。** 公开版是实验性 HTTP 平台适配器，不是微信官方 SDK，也不是 MimicWX 全版本适配层。

| 层 | 基线 | 说明 |
| --- | --- | --- |
| AstrBot | 4.29.1 / Python 3.12 | 使用原生 Platform、AstrMessageEvent、MessageChain 和平台注册接口 |
| Python | 3.12、3.13 | 纯逻辑测试基线；以 CI 实际结果为准 |
| HTTP 依赖 | aiohttp 3.14.5+ | 4.x 未验证 |
| 图片依赖 | Pillow 13.0.0+ | 14.x 未验证 |
| MimicWX | 0.4.0 HTTP/UI 接口 | 固定源码提交见下；不是 OneBot 接口，也不保证与最新分支兼容 |
| 微信客户端 | Linux UI/AT-SPI/X11 接入 | 不绑定可普遍保证的微信版本；客户端更新须重新验收 |

AstrBot 原生隔离测试镜像：

```text
soulter/astrbot@sha256:a140a326163ac5f82f62153f033cddeac74e38e4ee1809c6e333e950ff19edc4
```

原部署中的同类接入曾完成文字、分段、GIF 动画和群话题续聊验收。**整理后的公开版有独立的配置校验和更保守的匿名身份默认值，不能把原部署验收当作公开版的真实微信端到端测试。** 公开版测试使用合成消息与生成的图片，不使用真实账号或聊天。

## 可选 MimicWX UI 补丁

基线仓库：[wx-11/MimicWX-Linux](https://github.com/wx-11/MimicWX-Linux/tree/a42a3eec4e6efa2d023915e980e9af7d5fcf9439)。提交：

```text
a42a3eec4e6efa2d023915e980e9af7d5fcf9439
```

[`patches/mimicwx-ui-compat.patch`](../patches/mimicwx-ui-compat.patch) 提供原接入所需的部分 UI 兼容改动：

- 虚拟消息列表按可见节点和内容标识去重，避免列表条数不变时漏掉新消息；启动抑制可见旧消息。
- 对输入框矩形和目标窗口名称做额外检查；仍无法消除同名窗口、焦点竞争及误发风险。
- 在服务的 `main.rs` 中禁用数据库管理器，使用 UI 轮询；轮询间隔改为1秒。

**补丁不修改上游容器的启动脚本。** 上游启动脚本仍可能尝试数据库密钥提取、请求额外权限或使用不适合你的网络暴露设置。禁用服务的数据库管理器不等于整套上游环境不访问数据库；部署者必须另外审查启动脚本和镜像。

它不是最新版通用补丁，不会自动应用，也不安装微信。仅适合能够核对源码、构建和回退的使用者。先在独立工作副本中检出固定提交，再下载本项目并执行：

```sh
# 在固定提交的 MimicWX 源码目录执行；修改下面路径为本仓库的实际位置。
git apply --ignore-space-change --check /path/to/astrbot_plugin_mimicwx/patches/mimicwx-ui-compat.patch
git apply --ignore-space-change /path/to/astrbot_plugin_mimicwx/patches/mimicwx-ui-compat.patch
```

`--ignore-space-change` 用于该上游提交的 CRLF/LF 差异。检查失败时停止，不要强行应用。按上游构建说明生成自己核验的镜像，保留认证、私有网络和登录卷，在测试环境重新验收。回退时使用之前的镜像/备份，不要在有其他本地改动的仓库里盲用破坏性重置。

补丁可应用性测试、两个新增 Rust 模块的单元测试，以及完整 Linux 服务构建/真实微信验收是不同层次；前两者不能代替后者。公共 CI 不承诺完整构建 MimicWX 或执行真实微信登录。来源和许可见 [文件来源说明](SOURCE_MAP.md)。

## 升级范围

`metadata.yaml` 暂限定 AstrBot `>=4.29.1,<4.30`。新版若修改注册、发送或会话接口，先在独立环境运行测试，不能仅扩大版本号范围。MimicWX 若改变 JSON 形状、鉴权或消费语义，也需要重新适配。
