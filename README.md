# HRMS

企业员工管理系统的 M00 初始准备仓库，目前仅包含 T-001～T-003 的基线记录、
Ubuntu 环境检查和 SQLite/Alembic 独立实验脚本。没有实现员工、考勤、工资业务，
没有执行 T-004，也没有部署应用。

**所有 CloudStudio 运行测试：`NOT_RUN`。**

- [项目基线与批准版本](docs/baseline.md)
- [CloudStudio 安装、运行与回传说明](docs/cloudstudio-m00.md)
- [待实测验收记录](docs/acceptance.md)
- [依赖校准与锁定策略](requirements/README.md)

CloudStudio 从 GitHub 导入 `SYmarryme/hrms`，分支选择 `main`，先核对
`git rev-parse HEAD`，然后按执行说明操作。本仓库公开代码无需设计资料即可运行
环境检查和独立数据库 PoC；文档哈希核验另需私下传入原始交接资料。

公开内容限代码、空配置模板、脚本、批准文档版本/哈希索引和非敏感操作说明。
完整设计/交接包位于本地 `handoff/hrms-m00/`，不随公开仓库分发。
ZIP、`.env`、密钥/凭证、真实企业/员工资料、数据库/WAL/SHM、日志、备份和
`var/` 中所有实验产物禁止提交。不要使用 `git add -f` 绕过忽略规则。
后续由 Codex 检查变更、提交并推送，不使用强制推送。
