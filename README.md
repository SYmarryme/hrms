# HRMS 课程 MVP v1.0

当前提供 Vue 3 + TypeScript + Vite 前端、FastAPI、SQLite/SQLAlchemy/Alembic 后端。
课程范围包括部门、职位、员工及 CSV/XLSX 导入导出、考勤、请假、月薪、统计看板、账号管理与四角色授权。
全部使用真实数据库和后端权限；没有公开注册、默认密码或 DEMO_MODE 绕过。

本轮以用户提供的课程实施规格为准，不要求实现企业蓝图的54表/162接口/95任务。
保留既有登录、部门、M00证据和私有文档；CloudStudio不再是前置条件。
会话仍为不透明 Bearer，浏览器仅保存在模块私有内存；刷新和新标签页重新登录。
绝对30天、空闲24小时、每账号最多5会话，密码重置/停用/退出由服务器撤销。

## Windows 最少命令（PowerShell，项目根目录）

需要 Python 3.12、Node 22.12+（本轮实际使用 Python3.12.7 / Node24.18）和可选的已安装 Microsoft Edge。

```powershell
python scripts/local.py setup
python scripts/local.py test
# 先清除其他数据库配置；以下入口只接受命名隔离演示库
Remove-Item Env:HRMS_DATABASE_PATH,Env:HRMS_PUBLIC_ORIGIN -ErrorAction SilentlyContinue
python scripts/local.py demo --name class-one
python scripts/local.py start --name class-one
```

创建时交互输入四个不同的12～128位密码；账号为 fixture-admin、fixture-hr、fixture-manager、fixture-employee。
浏览器打开 **http://127.0.0.1:3000**。后端仅127.0.0.1:8000；前端本地入口也仅回环，所有API走相对路径同源代理。
启动只读取 `var/course-demo/class-one/app.sqlite3` 及其完成标记；原 `var/hrms/app.sqlite3` 和 CloudStudio 库不参与本地初始化。
同名目录存在即拒绝重建，包括失败的半成品；使用另一个名称重试，不会清空或覆盖。
Ctrl+C停止后可重新运行同一 `start` 命令验证持久化。
切回旧运行方式时停止本地演示，恢复原终端配置和原入口；**不要将演示文件复制到原库，也不要将原库交给 demo 命令**。

完整操作和实际测试结果见[课程运行与验收说明](docs/course-mvp.md)。
真实 Edge 自动端到端测试（每次新建独立虚构库，先停止手工演示以释放端口）：

```powershell
var/mvp/venv/Scripts/python.exe scripts/e2e_local.py
```

原企业版操作说明保留为历史资料，不应将其首次HR建制阻断流程用于课程虚构库。
课程数据库增量版本 `course_0003`：保留13张既有表，增加6张课程表，不重写原身份或审计数据。
本地脚本不会自动迁移旧业务库。所有运行文件、测试库、日志及下载文件都留在 Git 忽略目录。

以下为 **M00历史记录**；保留真实PASS/FAIL/BLOCKED，不再作为本批功能开发的前置条件。

企业员工管理系统的 M00 准备仓库，包含 T-001～T-003 的基线记录、
Ubuntu 环境检查和 SQLite/Alembic 独立实验，以及 T-004 的隔离健康检查夹具与测试脚本。
没有实现员工、考勤、工资业务；当前 CloudStudio 公网入口改写 Cookie 属性，T-004 对应项 BLOCKED，部署尚未验收。

用户已回传原提交 `954bfb341d638e62bf8243073b03f30850ae2d81` 的云端结果：
T-001 哈希 7/7 MATCH、环境检查退出 0、SQLite PoC 13/13 通过。
2026-10-25 用户确认全新环境重放及本批检查全部通过，**T-001～T-003 已验收 PASS**。
验收代码基线：`8d427017e0f91f7c3aa23dd20fefcd8d4e34284a`，证据来源与边界见[验收记录](docs/acceptance.md)。
T-004 独立验收，当前入口 Cookie 兼容性 BLOCKED，M00 Gate 未通过。

**独立 PoC 已通过：[Bearer Token 三项兼容性验证](docs/t004-bearer.md)**。
Edge 在 3000 公网 HTTPS 页面验证正确/缺失/错误合成 Token 分别为 200/401/401；
代码 8d3f7ec9e25208ad2b5219045e21bb3339ffa0ed 已获用户回传 Windows Edge 公网 PASS，
Bearer 自动回归 7 项通过、退出 0。Token 只临时在内存使用、不输出原文，
不追踪 Authorization 中间处理，不改变 Cookie/正式认证方案；T-004 继续 BLOCKED。
用户已指示暂不继续研究关闭 8000 所有者预览入口。本轮不新增 start.sh，继续用既有 setup/start。
正式认证架构变更仅准备本地设计影响分析，尚未批准；不修改七份已批准文档或实现正式登录。

**既有阻断：[平台兼容性结论与直连 Vite/公网对比](docs/t004-platform-compatibility.md)**。
用户证据已表明 Path=/api/v1/poc/、SameSite=Lax 在 Vite 之后变为 /、None；
不再重写前端检测或放宽属性。官方公开文档未找到透传控制项，平台全局能力尚待官方确认。
用户已确认本机/公网 A/B 为 BLOCKED_CURRENT_PUBLIC_ENTRY，异常边界 AFTER_LOOPBACK_VITE；
仅限当前入口，不能推断所有 CloudStudio 入口相同。暂停继续改写 Cookie 测试逻辑。
已准备[官方支持技术问题说明](docs/cloudstudio-support-issue.md)，尚未代发。
部署入口调整仅是[未批准 CR 草案](docs/cr-deploy-cookie-001.md)，不修改批准设计或自动迁移。

**既有记录：[8000 外部隔离与 SQLite 工作空间重启验收](docs/t004-remaining-acceptance.md)**。
SQLite 实际工作空间重启与原回执 after 已获用户回传退出 0，数据库部分 USER_REPORTED_PASS，
完整 CONTENT_MATCH 日志仍待核对。8000 本机监听限制与非公开配置用户回传通过，未登录访问被要求认证；
已登录所有者仍能通过 IDE 预览直达后端，故“无独立入口”不满足，整体外部隔离 INCOMPLETE/BLOCKED。
这不是匿名公开漏洞结论。彻底禁用 8000 预览且保留内部代理的官方配置尚未确认，见[平台能力边界](docs/t004-platform-compatibility.md#8000-独立预览入口的能力边界)。
无需重建已完成的数据库基线或改写 Cookie 测试。
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
