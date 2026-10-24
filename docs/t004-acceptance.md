# T-004 独立验收记录

状态：**文件已准备；实际运行全部 NOT_RUN；T-004 未通过验收**。
前置 T-001～T-003 已于 2026-10-25 获用户确认通过。
验收不得只依据脚本退出 0；以下每项须有相同代码提交对应的真实证据。

| 编号 | 断言/所需证据 | 当前状态 |
|---|---|---|
| T004-01 | 独立安装真实 Python/Node/npm/依赖版本，setup 退出码和候选锁 | NOT_RUN |
| T004-02 | 外部网络浏览器打开实际 HTTPS URL，Vue 页面成功渲染，同源 fetch 无 localhost:8000 | NOT_RUN |
| T004-03 | 证书验证开启的 HTTPS 脚本通过，健康响应 commit 与本次交付一致 | NOT_RUN |
| T004-04 | 伪造 Forwarded/X-Forwarded-* 经代理被清除/替换；直连 Uvicorn 不据伪造头更改 scheme | NOT_RUN |
| T004-05 | Set-Cookie Secure/HttpOnly/SameSite=Lax/Path=/api/v1/poc/，无 Domain；浏览器确认接收/路径排除/JS 不可读 | NOT_RUN |
| T004-06 | 仅 3000 平台公网映射；8000 本机 loopback；从外部网络核对平台未提供可独立访问的 API 入口 | NOT_RUN |
| T004-07 | Vite 只服务隔离前端，外部对已存在的无敏感 canary 的 /@fs 请求被拒绝 | NOT_RUN |
| T004-08 | SQLite prepare、重启前 verify 通过；下载独立回执保存 | NOT_RUN |
| T004-09 | CloudStudio UI 实际暂停/恢复或完整重启工作空间，记录操作时间/截图/实际限制 | NOT_RUN |
| T004-10 | 重启后同路径、同标记和逻辑摘要 MATCH，FK/integrity 通过；重启后同源/浏览器复测 | NOT_RUN |
| T004-11 | 脱敏日志、退出码、安装锁、平台限制与失败项回传，由用户决定验收 | NOT_RUN |

**不能自动证明的项**：脚本从工作空间自身访问公网域名不等于独立外网验证；
`ss` 监听 loopback 不等于平台没有二次端口映射；只重启应用不等于工作空间暂停/重启；
SQLite verify 的 PASS 仅说明当前内容吻合，重启事实另需人工证据。
诊断 Cookie 不是真实登录/CSRF/权限测试；这些属于后续已批准任务。

目录或网络能力不足时标记 BLOCKED/FAIL 并留证，不能清空库重建后称持久化通过，
也不能关闭 Secure、放宽 Host 到任意域名、暴露 8000 或添加跳过认证开关来消除失败。
不能持久时阻塞正式公网交付并提出方案；工作空间休眠/时限不冒充 24 小时在线。
T-004 全部验收前 M00 Gate 保持未通过，M01 与业务模块未开始。
