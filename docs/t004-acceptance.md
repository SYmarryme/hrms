# T-004 独立验收记录

状态：**T-004 未通过；当前 CloudStudio 公网入口 Cookie 兼容性 BLOCKED**。
最新用户证据：FastAPI/Vite 的 Path=/api/v1/poc/、SameSite=Lax，在 Chromium 响应与存储中
变为 Path=/、SameSite=None，并被发到范围外；报告包含 EDGE_SET_COOKIE_TRANSFORM。
据此阻断当前入口，不再把问题归为前端统计；不等于所有 CloudStudio 入口永久不支持。
见[脱敏证据](evidence/t004-cookie-transform-summary.json)及[平台结论/官方资料/直连对比](t004-platform-compatibility.md)。
2026-10-25 用户回传 `b7237e7b10bc0385228113fe282039c9e92d3476` 的浏览器结果：
https/same_origin/cookie_received/cookie_hidden_from_js_inside_path 为 true，
cookie_outside_path=true，browser_result=FAIL。这里只登记用户回传摘要，不补造运行日志。
后续用户回传 `10c34dd49863ecc87dd3b25b3036cc4ca7e961a7`：原 7 项回归通过、退出 0；
真实浏览器仍 FAIL，独立本次名称 inside=1/outside=1、legacy=false、实际路径核对 true。
该阶段已排除旧固定名称干扰；本次最新属性对比进一步定位到 Vite 之后的响应链转换。
本轮新增分层属性/路径/次数诊断与真实 Chromium 网络测试，原 7 项测试文件保留不变。
原 7 项于 10c34dd 用户回传通过；上轮 Chromium 已有失败证据。
用户现已确认 CloudStudio 本机/公网 A/B 完成：本机 Path=/api/v1/poc/、SameSite=Lax，
当前公网 Path=/、SameSite=None，结果 **BLOCKED_CURRENT_PUBLIC_ENTRY**，边界 **AFTER_LOOPBACK_VITE**。
仅指当前入口；没有指认内部具体组件或证明全部 CloudStudio 入口有同样问题。
新增 8 项比较判定单元测试未获单独回传，仍 NOT_RUN；其余未逐项回传不补造结果。
暂停改写 Cookie 实现/统计；[官方支持说明](cloudstudio-support-issue.md)已准备但未发送。
最新用户回传：[SQLite 重启与端口脱敏摘要](evidence/t004-restart-isolation-summary.json)。
SQLite 基线退出 0，原回执/哈希已独立保存，用户确认实际停止并重启工作空间，
使用原回执及原哈希运行 after，T004_RESTART_EXIT_CODE=0、AFTER_RESTART_EXIT_CODE=0。
按原 after 分支语义登记数据库部分 **USER_REPORTED_PASS**，完整 CONTENT_MATCH 日志仍 **PENDING_REVIEW**。
这不是 Codex 已读取原始日志或独立重跑的结论。实际运行提交、时间未提供，不用交付提交冒充。
8000 本机隔离 USER_REPORTED_PASS；Edge 无痕受限端口跳转 CloudStudio 登录页仅作观测，
外部隔离 INCOMPLETE，不能据此判定后端无独立路由。
前置 T-001～T-003 已于 2026-10-25 获用户确认通过。
验收不得只依据脚本退出 0；每项须记录真实脚本提交及实际服务提交，不能把新 HEAD 冒充仍运行的旧服务。
SQLite 重启前后项目 HEAD 必须一致；未重启服务时可独立使用新端口脚本收集原服务的证据。

| 编号 | 断言/所需证据 | 当前状态 |
|---|---|---|
| T004-01 | 独立安装真实 Python/Node/npm/依赖版本，setup 退出码和候选锁 | PENDING_EVIDENCE（未回传完整版本/锁证据） |
| T004-02 | Vue/健康检查可运行（用户回传）；完整浏览器 Cookie 断言受当前入口属性改写阻断 | PARTIAL；完整浏览器 BLOCKED |
| T004-03 | 证书验证开启的 HTTPS 脚本通过，健康响应 commit 与实际服务一致 | PENDING_EVIDENCE |
| T004-04 | 伪造 Forwarded/X-Forwarded-* 经代理被清除/替换；直连 Uvicorn 不据伪造头更改 scheme | PENDING_EVIDENCE |
| T004-05 | Chromium EDGE_SET_COOKIE_TRANSFORM + 用户 A/B 确认 AFTER_LOOPBACK_VITE | BLOCKED_CURRENT_PUBLIC_ENTRY（当前入口；其他入口未证实） |
| T004-06 | 仅 3000 平台公网映射；8000 loopback；外部无独立 API 入口 | PARTIAL：本机 USER_REPORTED_PASS；外部 INCOMPLETE（无痕登录跳转不足以通过） |
| T004-07 | Vite 只服务隔离前端，外部对已存在的无敏感 canary 的 /@fs 请求被拒绝 | PENDING_EVIDENCE |
| T004-08 | SQLite prepare、重启前 verify；原回执/哈希独立保存 | USER_REPORTED_PASS；基线完整输出待核对 |
| T004-09 | 实际停止并重启 CloudStudio 工作空间 | USER_REPORTED_PASS（用户明确确认；具体时间/操作记录未附） |
| T004-10 | 原库标记/摘要、WAL、FK/integrity；恢复后同源/浏览器 | PARTIAL：数据库 USER_REPORTED_PASS / CONTENT_MATCH 日志待核对；恢复后浏览器未验收且 Cookie BLOCKED |
| T004-11 | 脱敏退出码/证据、安装锁、平台限制与失败项回传 | PARTIAL：已收到本次摘要，完整脱敏核对/剩余项证据未齐 |

`USER_REPORTED_PASS` 表示按用户明确回传及原脚本语义登记通过，不能写成已独立审核全部产物。
`PENDING_EVIDENCE` 不断言用户从未执行，只表示本记录没有足够逐项证据。
完整日志核对须确认原 before/after 的 action、BASELINE_READY/CONTENT_MATCH、logical_content=MATCH、
integrity=ok、prepared_commit 与重启前 HEAD 一致，且对应同一次原回执；回执哈希仅私下核对不公开。
参照[仅输出安全字段的查看命令](t004-remaining-acceptance.md#最新回传后的日志核对)复核已有产物，
不得为了补记录重新 prepare 或还原数据库；若完整日志不支持摘要，回退对应数据库状态并排查。

**不能自动证明的项**：脚本从工作空间自身访问公网域名不等于独立外网验证；
`ss` 监听 loopback 不等于平台没有二次端口映射；只重启应用不等于工作空间暂停/重启；
SQLite verify 的 PASS 仅说明当前内容吻合，重启事实另需人工证据。
本轮重启包装脚本改用 CONTENT_MATCH 表述，只核对原回执 SHA-256 和原库，不能自动证明 UI 重启。
T004-10 数据库部分与恢复后浏览器部分分开收证；Cookie 仍 BLOCKED 时不得将整行或整个 T-004 标为 PASS。
诊断 Cookie 不是真实登录/CSRF/权限测试；这些属于后续已批准任务。

目录或网络能力不足时标记 BLOCKED/FAIL 并留证，不能清空库重建后称持久化通过，
也不能关闭 Secure、放宽 Host 到任意域名、暴露 8000 或添加跳过认证开关来消除失败。
不能持久时阻塞正式公网交付并提出方案；工作空间休眠/时限不冒充 24 小时在线。
T-004 全部验收前 M00 Gate 保持未通过，M01 与业务模块未开始。
