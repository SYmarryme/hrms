# HRMS

企业员工管理系统的 M00 准备仓库，包含 T-001～T-003 的基线记录、
Ubuntu 环境检查和 SQLite/Alembic 独立实验，以及 T-004 的隔离健康检查夹具与测试脚本。
没有实现员工、考勤、工资业务；当前 CloudStudio 公网入口改写 Cookie 属性，T-004 对应项 BLOCKED，部署尚未验收。

用户已回传原提交 `954bfb341d638e62bf8243073b03f30850ae2d81` 的云端结果：
T-001 哈希 7/7 MATCH、环境检查退出 0、SQLite PoC 13/13 通过。
2026-10-25 用户确认全新环境重放及本批检查全部通过，**T-001～T-003 已验收 PASS**。
验收代码基线：`8d427017e0f91f7c3aa23dd20fefcd8d4e34284a`，证据来源与边界见[验收记录](docs/acceptance.md)。
T-004 独立验收，当前入口 Cookie 兼容性 BLOCKED，M00 Gate 未通过。

**优先：[平台兼容性结论与直连 Vite/公网对比](docs/t004-platform-compatibility.md)**。
用户证据已表明 Path=/api/v1/poc/、SameSite=Lax 在 Vite 之后变为 /、None；
不再重写前端检测或放宽属性。官方公开文档未找到透传控制项，平台全局能力尚待官方确认。
用户已确认本机/公网 A/B 为 BLOCKED_CURRENT_PUBLIC_ENTRY，异常边界 AFTER_LOOPBACK_VITE；
仅限当前入口，不能推断所有 CloudStudio 入口相同。暂停继续改写 Cookie 测试逻辑。
已准备[官方支持技术问题说明](docs/cloudstudio-support-issue.md)，尚未代发。
部署入口调整仅是[未批准 CR 草案](docs/cr-deploy-cookie-001.md)，不修改批准设计或自动迁移。

**下一步：[8000 外部隔离与 SQLite 工作空间重启验收](docs/t004-remaining-acceptance.md)**。
SQLite 实际工作空间重启与原回执 after 已获用户回传退出 0，数据库部分 USER_REPORTED_PASS，
完整 CONTENT_MATCH 日志仍待核对。8000 本机检查用户回传通过；无痕跳登录页不足以通过外部隔离。
该说明包含安全日志核对命令与仍需补充的外部浏览器/平台证据，无需重建已完成的数据库基线。
两项通过不会解除当前 Cookie 阻断或自动通过 T-004，不更换正式部署架构。
课程 start.sh/preview.yml 只准备了独立对照提案，未实施，也未假定可以修复 Cookie 改写。

[原 T-004 CloudStudio 执行指令](docs/t004-execution.md)
包含独立环境安装、前端 3000 同源代理到 loopback 8000、HTTPS/转发头/Cookie 检查、
浏览器与平台端口证据，以及 SQLite 跨工作空间暂停/重启持久化。
`10c34dd` 的原 7 项回归已获用户回传通过，但真实浏览器仍 outside=1，因此 T-004 未通过。
上一轮[真实浏览器分层诊断](docs/t004-cookie-wire-diagnostics.md)已收到属性转换证据。
保留全部旧 Cookie 测试和安全要求；实际 A/B 已回传阻断，新增 8 项比较单元测试未单独回传仍 NOT_RUN，
见[独立验收表](docs/t004-acceptance.md)。
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
