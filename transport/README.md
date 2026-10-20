# 可选：保留 GIF 动画的剪贴板修复

先完成 AstrBot 和 MimicWX 的文字收发，再决定是否需要这个补丁。它不是 AstrBot 插件文件，应只放在 **MimicWX 容器内**，不要覆盖宿主机或 AstrBot 的 xclip。

部分 Linux 微信把 `image/gif` 剪贴板内容当静态图片。本目录的包装脚本仅对 MimicWX 的 `xclip -selection … -t image/gif -i 文件` 调用改为 `text/uri-list` 文件粘贴，其余参数原样交给 `/usr/bin/xclip`。MimicWX 发送目录里的文件名应由服务生成；不要将不可信路径直接传入脚本。

依赖：基础镜像已有 `/usr/bin/xclip`，`PATH` 中 `/usr/local/bin` 排在 `/usr/bin` 前，微信允许从该临时路径粘贴文件。没有这些条件时请勿直接套用。

可从**你已经核验的不可变基础镜像**构建派生镜像：

```sh
docker build --build-arg MIMICWX_IMAGE='你的镜像仓库@sha256:实际摘要' -t mimicwx-gif-local ./transport
```

这不是可直接照抄的镜像地址。只替换 MimicWX 的镜像配置，保留已有登录数据卷、私有网络、认证和其他必要配置；先在独立测试环境构建、运行并确认手机收到的 GIF 会动。不要为了安装补丁删除登录卷或增加容器权限。

回退：改回原 MimicWX 镜像并重建其容器，保留数据卷。脚本不会改变 AstrBot 本体。不同微信版本可能仍展平 GIF；该办法不保证动画、透明度、色彩或最终送达。

本目录包装脚本为本项目自有 MIT 代码；不分发微信、基础镜像或表情包素材。相关许可、平台规则及账号风险仍须独立评估，见 [DISCLAIMER](../DISCLAIMER.md)。
