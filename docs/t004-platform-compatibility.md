# T-004 平台兼容性结论与受控复核

2026-10-25 结论：**当前实测的 CloudStudio 公网预览入口不符合批准的 Cookie 安全契约，
T004-05 与依赖该入口的完整浏览器验收标记 BLOCKED；T-004/M00 Gate 不通过。**
该判断基于用户提供的实际 Chromium 报告，不是“单元测试通过所以平台兼容”。
不等于已经证明所有 CloudStudio 版本/区域/入口都永久不支持，也不把检索不到文档当作不可能的证明。

## 已知事实与结论边界

脱敏证据见 [用户回传摘要](evidence/t004-cookie-transform-summary.json)：

| 观察点 | Path | SameSite |
|---|---|---|
| FastAPI 实际响应 | /api/v1/poc/ | Lax |
| Vite 响应观察 | /api/v1/poc/ | Lax |
| Chromium 收到 | / | None |
| Chromium 存储 | / | None |

浏览器在 `/api/v1/poc-outside/cookie-check` 发送该 Cookie，报告 FAIL/EDGE_SET_COOKIE_TRANSFORM。
据此定位为 **Vite 之后至浏览器收到响应之间发生属性转换**；浏览器在按变宽后的有效范围发送，
不是前端计数造成，也不是浏览器违背原本仍有效的窄 Path。
用户随后确认已在 CloudStudio 完成独立 A/B：loopback FastAPI/Vite 严格，当前公网响应变宽，
结果 `BLOCKED_CURRENT_PUBLIC_ENTRY`、边界 `AFTER_LOOPBACK_VITE`。
这进一步定位到本机 Vite 之后，但仍不能指认 CloudStudio 内部的具体代理组件。
原报告的实际采集时间、原始日志路径等未提供，本仓库不补造。

## 官方配置核查（2026-10-25）

仅把厂商产品文档作为配置依据：

| 官方资料 | 文档明确支持的内容 | 对本故障的意义 |
|---|---|---|
| [配置运行文件](https://cloud.tencent.com/document/product/1039/131766) | preview.yml 的 port/run/root/autoOpen/autoPreview/mainPort | 未列出 Cookie Path/SameSite 透传或禁用改写参数 |
| [端口与 Web 预览插件](https://ide.cloud.tencent.com/docs/guide/code_editing/productivity_plugin/port-plug/) | 分享链接、公开/仅自己可见、外部浏览器打开 | 可核对入口和调试，但不是 Cookie 属性透传承诺 |
| [URL 访问异常排查](https://cloud.tencent.com/document/product/1039/131818) | 预览 URL 与实际服务端口对应，入口公式 | 可以核对是否使用官方 3000 入口，不能证明其不改 Cookie |
| [其他问题](https://cloud.tencent.com/document/product/1039/131821) | 平台 HTTPS 网关通常转发内部 HTTP，TCP/UDP 不支持、WebSocket 支持 | 不能把内部加 TLS 或 SSH/TCP 隧道视为官方支持的绕行方案 |

**未找到公开、可核验的 Cookie 原样透传开关。没有证据说明这种开关绝不存在；需厂商确认。
当前没有可以诚实称为“官方支持的最小配置修复”的具体配置项。**
不写入猜测性的 preserveCookies/disableCookieRewrite 等键，不使用其他产品的代理参数冒充 CloudStudio 设置。
官方 FAQ 的通用 Vite Host 建议也不覆盖本项目明确要求：本次保留现有精确 Host 白名单与固定端口。
[旧更新日志](https://cloud.tencent.com/document/product/1039/72558)曾提过预览 Cookie 问题，不能当作当前功能保证或配置方法。

最低风险的核对仅为：从 3000 端口卡片复制厂商实际分享链接，在外部浏览器打开，
确认与 `T004_ORIGIN` 一致；不另开 8000、不关闭访问控制、不通过改 Host 或自动端口来换取 PASS。
这个操作不是已证实的修复。若新的官方入口仍改写，保留 BLOCKED。

## 独立对比：127.0.0.1:3000 与公网 HTTPS

本轮只新增测试/文档，**不改变 FastAPI/Vue/Vite 的 Cookie 或统计实现**。
可保留正在运行的上一版服务；拉取新脚本不要求重建服务环境或再安装 Chromium。
脚本提交和服务提交分开记录。`--service-commit` 必须填写原诊断报告中实际运行服务的完整 commit，
不能不加区分地写成更新脚本后的 HEAD。若服务确为上轮交付 17b8eb6：

```bash
git pull --ff-only origin main
python3 scripts/m00/compare_t004_entry.py \
  --origin "$T004_ORIGIN" \
  --service-commit 17b8eb6fa7f18a58dda27a5b4f7c1b4570ded2ea
printf 'COMPARE_COMMAND_EXIT_CODE=%s\n' "$?"
```

`T004_ORIGIN` 是原实际 3000 HTTPS 入口；若另开终端请重新设置。若服务不是 17b8eb6，
替换为真实服务提交。脚本先核验两端 health 的 fixture/commit，再以相同新诊断名称分别 GET Cookie 端点。
本机目标固定 `http://127.0.0.1:3000`；Host 仍是已配置的公网 Host，以正常通过现有白名单，
没有关闭校验。明文 HTTP 仅限工作空间 loopback 观察响应头，不存储/发送 Cookie，不测试认证。
公网 HTTPS 校验证书，拒绝重定向，不携带凭证、不输出原始 Cookie/响应内容。

打印 `T004_COMPAT_EXIT_CODE` 及 `var/m00/t004-compat.<随机后缀>`；查看 `result.json`：

- `loopback_vite_3000.received`：直接收到的 Vite Set-Cookie 安全属性。
- `public_https.received`：经过公网 HTTPS 链路后收到的同名属性。
- `backend` / `vite_metadata`：两端安全投影；不会包含值。
- `comparison.result=BLOCKED_CURRENT_PUBLIC_ENTRY`、`boundary=AFTER_LOOPBACK_VITE`：
  本机严格但公网属性不同，退出 1，将修改进一步限定到本机 Vite 之后的链路。
- `INCOMPLETE`：网络/服务提交/JSON 或缺失/重复 Cookie 等证据不完整，退出 1；不能把这类错误当作属性改写证明。
- `MISSING_VITE_METADATA`：任一端 Vite 观察元数据缺失，不能进一步声称具体改写位于 Vite 之后。
- `LOCAL_APP_OR_VITE_CHAIN`：本机已经不严格，退出 1；不能把本机故障归责平台。
- `PUBLIC_APP_OR_VITE_CHAIN`：公网请求对应的 Vite 观察已经与 FastAPI 不同，不能归到 Vite 之后。
- `ATTRIBUTES_MATCH_FOR_THIS_CLIENT`：当前标准 HTTP 客户端样本匹配，退出 0，**不解除现有 Chromium BLOCKED**。
  如 Chromium 仍被改写，提示与客户端/预览嵌入场景相关的策略，需厂商解释并重跑实际浏览器。

脚本只报告路径、诊断名称、次数/属性及 commit，不保存 Cookie jar、值、原始头或日志。
实际 A/B 比较已由用户确认，结果 BLOCKED_CURRENT_PUBLIC_ENTRY / AFTER_LOOPBACK_VITE。
本仓库只记录脱敏摘要，未收到本次完整运行提交/时间，不补造。
暂停继续改写 Cookie 检测。原 7 项回归及上轮 8 项分类测试保留不变。
新增 8 项纯内存比较判定测试可在云端运行，产物同样放忽略目录：

```bash
mkdir -p var/m00
test_dir="$(mktemp -d "$PWD/var/m00/t004-compat-tests.XXXXXXXX")"
PYTHONPATH="$PWD/scripts/m00" PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s experiments/t004 -p test_entry_compare.py -v > "$test_dir/tests.log" 2>&1
test_rc=$?
printf '%s\n' "$test_rc" > "$test_dir/exit-code.txt"
printf 'COMPARE_UNIT_EXIT_CODE=%s; artifacts=%s\n' "$test_rc" "$test_dir"
```

上述 8 项纯内存比较判定测试在 Windows 未执行，用户未单独回传其结果，仍记 NOT_RUN；
不要把实际 A/B 已完成错误地扩展成所有新增单元测试已通过。

## 给厂商的最小问题清单（仅准备，尚未发送）

附脱敏属性对比及实际产品版本/区域/入口类型，询问：

1. 预览 HTTPS 网关是否会统一改写应用的 Set-Cookie Path 和 SameSite？哪些入口/访问模式受影响？
2. 是否有正式支持并可复现的原样透传选项、控制台设置或其他预览入口？请提供文档和适用版本。
3. 该设置能否保留 Secure、HttpOnly、SameSite=Lax、窄 Path，且仅公开 3000、后端 8000 保持本机？
4. 若当前套餐/区域不支持，是否明确不适合作为依赖这些属性的应用演示/部署入口？

若厂商给出支持的方法，最小改动仅限受控平台入口配置；记录官方说明、前后对比和回滚方式，
然后运行本脚本、原 7 项回归及原真实 Chromium 测试，并由用户确认浏览器 PASS 后才解除阻断。
未授权发送工单/邮件，本轮不会代发。
可直接交给用户填写并提交的完整说明见[官方支持技术问题说明](cloudstudio-support-issue.md)。
最新 SQLite 工作空间重启已获用户回传原回执 after 退出 0，数据库部分 USER_REPORTED_PASS，完整日志待核对；
8000 本机用户回传通过，外部无痕跳登录页仍不足以验收隔离，见[最新独立步骤与判据](t004-remaining-acceptance.md)。
这些独立结果不解除当前入口 Cookie BLOCKED。

当前 Cookie 下一步优先级：由用户向官方提交已有问题说明，补充实际产品版本/区域/入口类型、
运行服务与诊断脚本提交，以及 Path/SameSite 的脱敏 A/B 表；询问当前入口的改写策略和正式透传办法。
SQLite 已完成的重启测试无需为 Cookie 问题重复准备；8000 的拥有者浏览器和平台映射证据继续单独补齐。
官方若提供具体方法，先审阅适用范围和回滚方式，再提出只改入口配置的独立对照，运行原 A/B 与 Chromium 原断言。
没有官方支持的方法前继续 BLOCKED，不新增猜测参数、不修改安全属性、不自动切换正式部署架构。

## 影响范围与部署评估

阻断当前预览入口的 Cookie 属性验收和依赖它的完整浏览器 Gate；未来正式会话、CSRF/SameSite、
同源部署不能凭此入口宣称安全验证完成。T-001～T-003 已验收不受影响，其他独立未测项不伪造结果。
本结论不是说用户数据已经泄露：当前只是无权限合成 Cookie，尚无 HRMS 生产认证/业务部署。

若官方无法提供且复测仍不保持属性，需要调整**部署入口/运行载体**，不调整安全设计。
候选 CR 见 [CR-DEPLOY-COOKIE-001 草案](cr-deploy-cookie-001.md)。优先申请官方受支持透传；
否则评估 CloudStudio 仅作开发/集成环境，独立可控 HTTPS 单入口承载后续验证/部署。
在同一个会改写响应的 CloudStudio 网关后再套一层 Nginx，不能保证消除最后一跳的改写。
未获用户正式确认前不迁移、不购买、不部署、不改七份批准设计。
当前按用户要求暂不更换正式部署架构，也不新增 start.sh/preview.yml；
如需尝试课程启动方式，只按官方支持说明中的独立对照提案另行评审，不假定可修复 Cookie 改写。
