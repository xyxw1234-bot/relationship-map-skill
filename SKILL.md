---
name: relationship-map-installer
description: Use when a user sends the official Relationship Map capability package link or asks to install or update 人脉地图. Install the declared plugin package first, then expose the bundled durable Skill; never claim persistence if the vault tools are unavailable.
version: 3.0.0
author: Node Engine
license: MIT
metadata:
  hermes:
    tags: [relationship-map, installer, relationship-assets]
    related_skills: []
---

# 人脉地图能力包安装入口

当用户明确要求安装、更新人脉地图，或发送本仓库链接时，读取仓库根目录 `INSTALL.md` 并执行其中的安装契约。

安装目标是仓库内的 `relationship_map_plugin` 能力包，而不是只复制本文件。安装必须同时获得：

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
