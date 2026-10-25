# CloudStudio 官方支持技术问题说明（待用户提交，NOT_SENT）

主题：当前工作空间公网 HTTPS 预览入口改变应用 Set-Cookie Path / SameSite，导致路径隔离失效。

## 事实、范围与影响

用户已在 CloudStudio 完成真实 Chromium 和直连/公网 A/B 对比，报告
`BLOCKED_CURRENT_PUBLIC_ENTRY`、`AFTER_LOOPBACK_VITE`。公开脱敏摘要在
[证据记录](evidence/t004-cookie-transform-summary.json)。没有公开原始响应头或 Cookie 值。

| 观察点 | Path | SameSite |
|---|---|---|
| FastAPI 本机响应 | `/api/v1/poc/` | `Lax` |
| 工作空间 loopback Vite :3000 响应 | `/api/v1/poc/` | `Lax` |
| 当前公网 HTTPS 入口响应 | `/` | `None` |
| Chromium 响应观察和存储 | `/` | `None` |

Chromium 在 `/api/v1/poc-outside/cookie-check` 确实发送该诊断名称的 Cookie，范围外次数为 1，
预期 0。诊断为每轮唯一名称，已排除旧名称 Cookie 干扰，且实际请求路径已核对。
Cookie 是无权限合成实验标记，不是生产会话。客户端遵循了被改宽的属性，不能将其归为前端计数错误。
目前只定位到本机 Vite 之后的链路；不能指认厂商具体内部组件，也不能推断所有区域/版本/入口都有相同问题。

安全契约要求 Secure、HttpOnly、SameSite=Lax、Path=/api/v1/poc/；不接受放宽属性作为解决办法。
当前入口阻断 Cookie 隔离与完整浏览器验收。T-001～T-003 不受影响，尚未部署 HRMS 业务/生产认证。

## 最小复现（仅在用户自己的工作空间执行）

1. 后端固定监听 `127.0.0.1:8000`，Vite 监听 3000，仅 `/api/` 同源转发，不重写路径或 Cookie。
   保持精确 Host 白名单。使用当前实际的 3000 HTTPS 入口，保留服务运行。
2. 在项目根目录设置原有 `T004_ORIGIN`，将服务启动记录中的真实 40 位提交填入
   `T004_SERVICE_COMMIT`；脚本提交与运行中服务提交可以不同，不能用刚拉取的 HEAD 冒充服务提交。
3. 执行现有 A/B 脚本（不需要重新安装/改写 Cookie 代码）：

```bash
python3 -B scripts/m00/compare_t004_entry.py \
  --origin "$T004_ORIGIN" --service-commit "$T004_SERVICE_COMMIT"
printf 'COMPARE_COMMAND_EXIT_CODE=%s\n' "$?"
```

报告在忽略目录 `var/m00/t004-compat.*/result.json`；只提供经过人工审阅的属性投影。
本机请求带正常的已批准 Host，公网请求校验 TLS，拒绝重定向，不携带/保存 Cookie jar 或认证凭证。
预期路径/SameSite 一致；实际公网变宽时报告上述 BLOCKED/边界，退出 1，这是故障证据而非脚本执行成功证明。
真实 Chromium 复现材料只提交脱敏 URL 路径、名称次数、安全属性与诊断分类，不导出 HAR、Cookie 存储或原始网络头。

## 请官方确认

1. HTTPS 预览网关或嵌入预览是否会改写应用 Set-Cookie 的 Path、SameSite？触发条件和适用入口/区域/版本是什么？
2. 是否存在正式支持的原样透传配置/访问模式/入口？请给出准确配置键、文档、适用版本及回滚方式。
3. 能否同时保留 Secure、HttpOnly、SameSite=Lax、窄 Path、精确 Vite Host 校验，且只映射 3000、8000 仅本机？
4. 若推荐 start.sh / `.vscode/preview.yml`，请说明它为何改变响应处理链，以及如何验证没有 Cookie 属性重写；仅启动命令不同是否有效？
5. 如当前入口不支持该契约，请明确能力边界及其他受支持入口；不要以关闭安全属性或暴露后端端口替代修复。

公开官方资料核查日期：2026-10-25。
[运行配置文档](https://cloud.tencent.com/document/product/1039/131766)列出启动/预览端口字段，
未公开说明上述 Cookie 透传开关；[端口插件](https://ide.cloud.tencent.com/docs/guide/code_editing/productivity_plugin/port-plug/)
说明访问范围与分享入口。这不证明内部不存在配置，需要官方确认。

## 仅在官方私密工单补充的上下文

填写实际产品版本/套餐、区域、工作空间标识、当前入口类型/访问模式、浏览器版本、采集时间及时区、
运行服务提交与脚本提交、工单要求的已脱敏报告。以上未在本次用户摘要中给全，不补造。
工作空间标识/完整入口地址仅在官方私密渠道填写；本公开文件不填写真实值。
不附凭证、Cookie 值、`.env`、七份设计文档、数据库、备份或原始日志。
本文件是可提交说明，Codex 没有代发工单、邮件或其他消息。

## start.sh / preview.yml 独立对照提案（未执行）

当前不新增或替换启动配置，不更换正式部署架构。如用户决定试验，先取得课程原始示例/官方说明并评审：

| 条件 | A 基线 | B 候选 |
|---|---|---|
| 服务代码/依赖、区域、账号、浏览器、入口访问模式 | 固定并记录 | 与 A 相同 |
| Secure/HttpOnly/SameSite/Path、Host 白名单、后端 loopback | 保持原要求 | 与 A 相同 |
| 唯一变量 | 当前启动/预览方式 | 官方/课程支持的 start.sh 或 preview.yml 启动方式；一次只改一项 |
| 证据 | 已有本机/公网属性对比与 Chromium 失败 | 同样的 A/B 和真实 Chromium 原断言，另记录实际入口是否改变 |

只有官方或课程原始配置具体可审查时才写候选文件，固定 3000，不能自动换端口或公开 8000。
若实际入口也变化，作为额外变量单独说明，不能把改善归因于脚本名称。
B 仍改写则保留 BLOCKED；B 看似正常也须完整原浏览器断言通过且用户验收，不能凭启动成功解除阻断。
试验完成回到 A 并保留双方脱敏证据。此提案不是已批准部署变更，也没有假定能修复网关。
