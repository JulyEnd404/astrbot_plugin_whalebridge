# 参与贡献

先阅读README、DISCLAIMER和SECURITY。请只使用合成消息与测试图片，不提交真实账号、群聊、token或登录数据。

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt ruff==0.17.1
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m ruff check .
```

本机没有AstrBot时，纯逻辑测试照常运行，原生测试会跳过。CI另外使用固定AstrBot镜像执行原生接口测试，禁止连接真实微信或模型服务。

新增配置必须给出关闭/安全默认值及文档；不得将模型文本变成任意发送目标或系统命令。更改消息ID、匿名策略或平台ID命名空间时，要说明对历史、白名单及记忆归属的影响。

提交前检查`git diff --cached`与全部待发布文件。不要把开发环境、旧部署目录、模型凭据或服务器备份整体拷进本仓库。
