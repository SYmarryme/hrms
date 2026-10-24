# M00 待实测验收记录

初次文件准备时 CloudStudio 全部为 `NOT_RUN`。现用户回传原提交
`954bfb341d638e62bf8243073b03f30850ae2d81` 的 T-001 7/7 MATCH、环境检查退出 0、
SQLite PoC 13/13 通过（退出 0）。以下 `USER_REPORTED` 仅记录用户回传，
不表示本轮在 Windows 执行或重新核查了完整云端日志。
**T-002 总体仍为 `PARTIAL`，精确锁的全新环境重放为 `NOT_RUN`，不得标记为已通过。**
原交接包验收清单保留原文，本文件仅作公开的本批跟踪入口。

| 条目 | 待取得的证据 | CloudStudio 状态 |
|---|---|---|
| SYNC-01 | 实际导入分支、commit 与交付报告一致 | NOT_RUN |
| T001-01 | 用户回传 7/7 MATCH、退出 0 | USER_REPORTED |
| T001-02/03 | 基线、版本、Git 可追溯；批准源文档未更改 | NOT_RUN |
| T002-01 | 用户回传 Ubuntu 24.04.3 x86_64 / Python 3.11.1 / ENV_EXIT_CODE=0 | USER_REPORTED |
| T002-02 | 两份精确锁已准备；全新 venv 安装、版本核对、13 项 PoC 重放待回传 | NOT_RUN |
| T002-03 | 无密钥模板和云端 git check-ignore 实测 | NOT_RUN |
| T003-01～05 | 用户回传原 PoC 共 13 项通过，POC_EXIT_CODE=0；新锁环境需重跑 | USER_REPORTED |

T-004：`NOT_STARTED`。生产信任与部署：未配置、未验证。
本地文件准备、静态核验与 Git 同步回执另记 `var/m00/`，不混入云端测试结果。
只有用户收到真实云端证据并明确验收后，才可变更任务验收状态。
