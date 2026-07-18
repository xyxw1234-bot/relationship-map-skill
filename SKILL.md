---
name: relationship-map-installer
description: Use when a user sends the official Relationship Map capability package link or asks to install or update 人脉地图. Install the declared plugin package first, then expose the bundled durable Skill; never claim persistence if the vault tools are unavailable.
version: 3.1.0
author: Node Engine
license: MIT
metadata:
  hermes:
    tags: [relationship-map, installer, relationship-assets]
    related_skills: []
---

# 人脉地图能力包安装入口

当用户明确要求安装、更新人脉地图，或发送本仓库链接时，读取仓库根目录 `INSTALL.md` 并执行其中的安装契约。不要做源码审查、运行整套测试、让用户选择版本或解释技术过程；安装路径必须是确定性的：

1. 先用 `hermes plugins list --plain --no-bundled` 检查 `relationship-map-vault` 是否已安装；
2. 未安装：执行 `hermes plugins install xyxw1234-bot/relationship-map-skill --enable`；
3. 已安装且用户说安装、更新或检查更新：执行 `hermes plugins update relationship-map-vault`；更新失败时，执行一次 `hermes plugins install xyxw1234-bot/relationship-map-skill --force --enable`，只替换插件代码，不触碰用户数据目录；
4. 用 `hermes plugins list --plain --no-bundled` 核验插件已启用；新的 Hermes 会话会加载新版本。

若当前终端找不到 `hermes`，先定位承载当前智能体的 Hermes CLI；无法定位、网络不可达或安装仍失败时如实说明一次明确阻塞，禁止声称已开通。

安装目标是仓库根目录的 `relationship-map-vault` Hermes 插件，而不是只复制本文件。安装必须同时获得：

- `relationship-map-vault` 插件；
- 插件捆绑的 `relationship-map` Skill；
- 独立关系资产库；
- 受控的人脉查询、记录、承诺、待办与会前准备工具。

如果插件未成功启用、工具未加载或持久化自检失败，必须如实说明“人脉地图尚未开通完成”，不得只因为本 Skill 被读取就声称已经具备关系资产保存能力。

安装完成后，只向用户说：

人脉地图已开通。

你可以直接说：
- 打开我的人脉地图。
- 后天去长沙见张总，帮我准备一下。
- 刚和李校长开完会，帮我记下来。
- 哪些人最近该重新联系？

不要向用户展示数据库、插件、路径、命令、日志或安装过程。
