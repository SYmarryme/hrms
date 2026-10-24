# M00 待实测验收记录

CloudStudio 未执行；以下全为 `NOT_RUN`，不得因本地提交/推送更新为 PASS。
原交接包验收清单保留原文，本文件仅作公开的本批跟踪入口。

| 条目 | 待取得的证据 | CloudStudio 状态 |
|---|---|---|
| SYNC-01 | 实际导入分支、commit 与交付报告一致 | NOT_RUN |
| T001-01 | 私有资料 SHA-256 脚本真实输出 | NOT_RUN |
| T001-02/03 | 基线、版本、Git 可追溯；批准源文档未更改 | NOT_RUN |
| T002-01 | Ubuntu 工具链真实版本、命令和退出码 | NOT_RUN |
| T002-02 | 安装日志、校准 lock、全新 venv 重放 | NOT_RUN |
| T002-03 | 无密钥模板和云端 git check-ignore 实测 | NOT_RUN |
| T003-01 | 两连接文件库 FK、WAL、busy_timeout | NOT_RUN |
| T003-02 | 写锁、CAS、NULL/唯一、同事故与跨事故竞争 | NOT_RUN |
| T003-03 | 故障注入回滚、FK/完整性检查 | NOT_RUN |
| T003-04 | Alembic 从零/重复升级、batch 失败及 DDL 局限 | NOT_RUN |
| T003-05 | 在线备份、独立目录恢复、拒绝坏库与覆盖 | NOT_RUN |

T-004：`NOT_STARTED`。生产信任与部署：未配置、未验证。
本地文件准备、静态核验与 Git 同步回执另记 `var/m00/`，不混入云端测试结果。
只有用户收到真实云端证据并明确验收后，才可变更任务验收状态。
