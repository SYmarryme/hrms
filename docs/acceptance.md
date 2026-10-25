# M00 验收记录

初次文件准备时 CloudStudio 全部为 `NOT_RUN`。现用户回传原提交
`954bfb341d638e62bf8243073b03f30850ae2d81` 的 T-001 7/7 MATCH、环境检查退出 0、
SQLite PoC 13/13 通过（退出 0）。以下 `USER_REPORTED` 仅记录用户回传，
不表示本轮在 Windows 执行或重新核查了完整云端日志。
2026-10-25 用户明确确认“已经全部通过”，批准 T-001～T-003 验收。
验收代码基线为上轮交付 `8d427017e0f91f7c3aa23dd20fefcd8d4e34284a`：
包含两份精确锁、新虚拟环境重放、pip check、13 包版本比对及 13 项 SQLite PoC。
状态改为 **PASS（用户确认验收）**，不表示 Codex 在 Windows 运行了这些测试。
原始云端日志未附在此次确认消息中，也不补造日志路径、运行时间或截图。
原交接包验收清单保留原文，本文件仅作公开的本批跟踪入口。

| 条目 | 待取得的证据 | CloudStudio 状态 |
|---|---|---|
| SYNC-01 | 原提交与依赖重放交付基线可追溯；用户确认 | PASS |
| T001-01 | 用户回传 7/7 MATCH、退出 0 | PASS |
| T001-02/03 | 基线、版本、Git 可追溯；批准源文档未更改；用户确认 | PASS |
| T002-01 | Ubuntu 24.04.3 x86_64 / Python 3.11.1 / ENV_EXIT_CODE=0 | PASS |
| T002-02 | 精确锁、新环境安装、pip check、完整版本核对及 PoC 重放；用户确认全部通过 | PASS |
| T002-03 | 无密钥模板、Git 忽略边界；用户确认本批验收 | PASS |
| T003-01～05 | 原环境及新锁环境 13 项 SQLite PoC；用户确认全部通过 | PASS |

T-004：当前公网入口 **BLOCKED**。用户回传 FastAPI/Vite 严格的 Path/SameSite 在 Chromium 侧
变为 / 和 None（EDGE_SET_COOKIE_TRANSFORM）；阻断 T004-05 及完整浏览器验收。
用户进一步回传直连 A/B：BLOCKED_CURRENT_PUBLIC_ENTRY，边界 AFTER_LOOPBACK_VITE；
不等于所有平台入口永久不支持。官方透传方法仍未获证实，Cookie 测试逻辑暂停改写。
原 7 项回归通过不解除该阻断；详见平台兼容性结论及 CR-DEPLOY-COOKIE-001 未批准草案。
最新用户确认：SQLite 基线退出 0、原回执/哈希独立保存、实际停止并重启工作空间，
原回执 after 验证 T004_RESTART_EXIT_CODE=0、AFTER_RESTART_EXIT_CODE=0。
数据库持久化登记 USER_REPORTED_PASS，完整 CONTENT_MATCH 日志仍待核对；不代表恢复后浏览器验收通过。
8000 本机监听限制和非公开配置 PASS（用户回传），无痕访问登录拦截已有实测证据。
已登录所有者可在 IDE 的 8000 预览直达 FastAPI（根路径正常 HTTP 404），故无独立预览入口断言不满足；
整体外部隔离 INCOMPLETE/BLOCKED。该受认证预览不直接认定为匿名公开漏洞。
详见 [最新验收表](t004-acceptance.md)及[安全日志核对/剩余步骤](t004-remaining-acceptance.md)。
官方支持说明仅准备未代发，正式部署架构未更换；T-004 仍未通过。
T-001～T-003 通过不等于整个 M00 Gate 通过。生产信任与部署：未配置、未验证。
本地文件准备、静态核验与 Git 同步回执另记 `var/m00/`，不混入云端测试结果。
只有用户收到真实云端证据并明确验收后，才可变更任务验收状态。
