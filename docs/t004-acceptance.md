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
新[8000/重启验收指令与脚本](t004-remaining-acceptance.md)仅文件准备，云端仍 NOT_RUN。
前置 T-001～T-003 已于 2026-10-25 获用户确认通过。
验收不得只依据脚本退出 0；每项须记录真实脚本提交及实际服务提交，不能把新 HEAD 冒充仍运行的旧服务。
SQLite 重启前后项目 HEAD 必须一致；未重启服务时可独立使用新端口脚本收集原服务的证据。

| 编号 | 断言/所需证据 | 当前状态 |
|---|---|---|
| T004-01 | 独立安装真实 Python/Node/npm/依赖版本，setup 退出码和候选锁 | NOT_RUN |
| T004-02 | Vue/健康检查可运行，但完整浏览器 Cookie 断言受当前入口属性改写阻断 | BLOCKED（依赖当前入口） |
| T004-03 | 证书验证开启的 HTTPS 脚本通过，健康响应 commit 与本次交付一致 | NOT_RUN |
| T004-04 | 伪造 Forwarded/X-Forwarded-* 经代理被清除/替换；直连 Uvicorn 不据伪造头更改 scheme | NOT_RUN |
| T004-05 | Chromium EDGE_SET_COOKIE_TRANSFORM + 用户 A/B 确认 AFTER_LOOPBACK_VITE | BLOCKED_CURRENT_PUBLIC_ENTRY（当前入口；其他入口未证实） |
| T004-06 | 仅 3000 平台公网映射；8000 本机 loopback；从外部网络核对平台未提供可独立访问的 API 入口 | NOT_RUN |
| T004-07 | Vite 只服务隔离前端，外部对已存在的无敏感 canary 的 /@fs 请求被拒绝 | NOT_RUN |
| T004-08 | SQLite prepare、重启前 verify 通过；下载独立回执保存 | NOT_RUN |
| T004-09 | CloudStudio UI 实际暂停/恢复或完整重启工作空间，记录操作时间/截图/实际限制 | NOT_RUN |
| T004-10 | 重启后同路径、同标记和逻辑摘要 MATCH，FK/integrity 通过；重启后同源/浏览器复测 | NOT_RUN |
| T004-11 | 脱敏日志、退出码、安装锁、平台限制与失败项回传，由用户决定验收 | NOT_RUN |

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
