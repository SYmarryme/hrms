# HRMS

企业员工管理系统的 M00 准备仓库，包含 T-001～T-003 的基线记录、
Ubuntu 环境检查和 SQLite/Alembic 独立实验，以及 T-004 的隔离健康检查夹具与测试脚本。
没有实现员工、考勤、工资业务；T-004 尚未实际执行，也没有完成应用部署。

用户已回传原提交 `954bfb341d638e62bf8243073b03f30850ae2d81` 的云端结果：
T-001 哈希 7/7 MATCH、环境检查退出 0、SQLite PoC 13/13 通过。
2026-10-25 用户确认全新环境重放及本批检查全部通过，**T-001～T-003 已验收 PASS**。
验收代码基线：`8d427017e0f91f7c3aa23dd20fefcd8d4e34284a`，证据来源与边界见[验收记录](docs/acceptance.md)。
T-004 将独立准备并验收，实际运行仍为 `NOT_RUN`；不代表 M00 Gate 或部署完成。

**下一步：[T-004 CloudStudio 执行指令](docs/t004-execution.md)**。
包含独立环境安装、前端 3000 同源代理到 loopback 8000、HTTPS/转发头/Cookie 检查、
浏览器与平台端口证据，以及 SQLite 跨工作空间暂停/重启持久化。
所有 T-004 安装、启动和运行项均为 `NOT_RUN`，见[独立验收表](docs/t004-acceptance.md)。
新依赖仅装入 `var/m00/t004-env.<随机后缀>`，不改变已通过的 M00 环境或锁文件。

依赖已按该次真实 `pip freeze --all` 固定，未调整已验证版本。
在 CloudStudio Ubuntu 项目根目录更新后运行：

```bash
git pull --ff-only origin main
git rev-parse HEAD
M00_REPLAY_PYTHON="$PWD/.venv/bin/python" bash scripts/m00/replay_dependencies.sh
replay_rc=$?
printf 'REPLAY_COMMAND_EXIT_CODE=%s\n' "$replay_rc"
```

这里 `.venv/bin/python` 只提供已验证的 Python 3.11.1 解释器，脚本不会向原 `.venv`
安装包。每次在 `var/m00/replay.<随机后缀>/venv` 创建独立的新环境，固定引导工具、
安装项目依赖、运行 `pip check`、核对全部 13 个包，再重跑 13 项 PoC 并核对 JUnit。
日志、环境和数据库均在被忽略的 `var/m00/` 下。详见[依赖重放与通过判据](docs/m00-replay.md)。

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
