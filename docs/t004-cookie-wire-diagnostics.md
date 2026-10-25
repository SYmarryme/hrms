# T-004：真实浏览器与代理的 Cookie Path 分层诊断

**未通过；本轮代码、8 项新增分类测试和 Chromium 自动化尚未在 CloudStudio 执行。**
用户已回传 `10c34dd49863ecc87dd3b25b3036cc4ca7e961a7` 的原 7 项回归通过、退出 0，
但真实页面 outside_name_count=1、inside_name_count=1、legacy=false、request_paths_verified=true，
因此不能再用旧固定名称干扰解释本次失败。原 7 项回归及其执行脚本原样保留。
单元测试只覆盖应用与模拟客户端；它们没有经过浏览器和 CloudStudio HTTPS 代理。

## 观察边界，不改写 Cookie

本轮不猜测或自动修正 CloudStudio 的配置，不修改 Path/Secure/HttpOnly/SameSite、Host 白名单、
原有转发信任策略或已验收 M00 锁文件。诊断仅记录本次无权限标记的名称、URL 路径、次数及安全属性。
名称包含随机诊断 ID，但不是认证凭据。不会返回/写入 Cookie 值或原始 Cookie/Set-Cookie。

| 位置 | 采集方式 | 安全输出 |
|---|---|---|
| FastAPI 发出响应 | 从实际 Response Set-Cookie 提取白名单属性 | name/path/secure/httpOnly/sameSite/domain_present |
| Vite 收到请求 | 代理之前的 middleware 捕获 | ingress_path、当前名称出现次数 |
| Vite 发向后端 | proxyReq 观察发送路径及 Cookie 名称 | outgoing_path、次数；通过覆盖式诊断头传给后端 |
| 后端收到请求 | 原始 Cookie 字段只计名称、不返回值 | backend_path、cookie_name、backend_count |
| Vite 收到响应 | proxyRes 提取当前名称的 Set-Cookie 属性 | x-t004-vite-set-cookie 元数据；不改写 Set-Cookie 本身 |
| HTTPS 客户端/Chromium 收到响应 | urllib / CDP responseReceivedExtraInfo | 响应 Cookie 的白名单属性 |
| Chromium 实际发出请求 | CDP requestWillBeSentExtraInfo | URL 路径、名称次数、关联 Cookie 的生效路径及阻止标志 |
| Chromium 存储 | 仅投影目标 Cookie 的属性 | 名称、Path、Secure、HttpOnly、SameSite；丢弃 value |

浏览器页面在 `cookie_path_diagnostics` 显示前四个应用/代理边界。浏览器 JS 不能读取 HttpOnly Cookie
的实际请求头或 Set-Cookie，这两处由 Chromium CDP 补齐；不会用后端返回的次数冒充浏览器发包证据。
事件先转为脱敏结构再保存，支持 ExtraInfo 先于普通事件到达；缺失、重定向、重复或不一致均失败。
重定向离开已知路径时也禁止把多个 hop 合并。API JSON 响应由自动化独立读取后立即脱敏，
与页面显示及页面复制的诊断字段分开比较，不能用页面自己的计数证明后端计数。
不启用 HAR、trace、video、storage_state、个人浏览器 profile 或 TLS 证书忽略。
临时浏览器目录、二进制、依赖及报告全部位于被忽略的 `var/m00/`。

## CloudStudio 操作

先在旧服务终端 Ctrl+C，保留 `10c34dd` 的失败记录。更新并确认本轮报告的新提交后：

```bash
git pull --ff-only origin main
git rev-parse HEAD
T004_BASE_PYTHON="$PWD/.venv/bin/python" bash scripts/m00/setup_t004.sh
```

使用新 setup 输出的目录，保留原实际 HTTPS 主机：

```bash
export T004_ENV_DIR='<新输出的绝对目录>'
export T004_ORIGIN='https://<原3000映射主机名>'
bash scripts/m00/test_t004_cookies.sh "$T004_ENV_DIR" &&
bash scripts/m00/start_t004.sh "$T004_ENV_DIR" "$T004_ORIGIN"
```

原 7 项测试仍须 7 tests / OK / 退出 0。服务保持前台运行。
另开终端设置相同两个变量，先运行便于快速定位响应转换的普通 HTTPS 探针：

```bash
python3 scripts/m00/t004_probe.py --origin "$T004_ORIGIN" --commit "$(git rev-parse HEAD)" \
  --outside-canary "$T004_ENV_DIR/outside-canary.txt"
printf 'HTTPS_PROBE_COMMAND_EXIT_CODE=%s\n' "$?"
```

即使它失败，`var/m00/t004-probe.*/result.json` 的 `cookie_observation.set_cookie` 也会保留
backend / vite / https_received 三层属性，未写任何值。不要因失败而跳过真实浏览器诊断：

```bash
bash scripts/m00/test_t004_browser.sh "$T004_ENV_DIR" "$T004_ORIGIN"
printf 'BROWSER_COMMAND_EXIT_CODE=%s\n' "$?"
```

该脚本在单独随机目录创建测试 venv，安装候选 Playwright 与 Chromium，执行 8 项分类回归，再从真实
HTTPS 页面点击原检查按钮；不使用路由 mock、Cookie 注入或模拟请求代替 Chromium 网络栈。
不会向原 `.venv` / T-004 服务 venv 安装 Playwright，也不自动安装系统包。
脚本打印 `T004_BROWSER_ARTIFACTS`。查看该目录下 `result.json`、`exit-code.txt` 和 `run.log`。
安装候选快照保留 `python.freeze.txt`，未云端测试前不声称新依赖已锁定或通过。

Linux 缺少 Chromium 系统依赖时，运行会非零退出，不算测试通过。
若有云端管理权限，可明确执行 Playwright 官方的 `install-deps chromium`（使用上述测试目录的 Python），
安装后重跑；无权限则标 BLOCKED 并回传错误类别。脚本不自动 sudo、不修改系统 TLS。
如果新浏览器被平台登录/访问控制拦住，保持未完成；不导入真实登录 Cookie、不关闭认证、不绕过平台。
真实页面在用户的浏览器仍须手工确认 PASS，自动化结果不代替 T-004 其他端口/持久化验收。

## 如何区分三种情况

`result.json` 的 `requests` 逐条记录发 Cookie、范围内、范围外、iframe 四个路径；
`browser_count` 来自 CDP 的实际发包，`boundary.proxy` 来自 Vite，`boundary.backend_count` 来自后端。
`backend_set_cookie` / `vite_set_cookie` / 发 Cookie 请求的 `response_cookies` / `stored_cookies`
分别是四个响应/存储观察点。`findings` 只报告发现的差异，不伪造唯一根因。

| 证据组合 | findings / 判断 |
|---|---|
| FastAPI 已经不是严格 Path/安全属性 | BACKEND_COOKIE_ATTRIBUTES_MISMATCH：应用发出即错误 |
| FastAPI 严格，Vite 响应属性变化 | BACKEND_TO_VITE_COOKIE_TRANSFORM：应用到 Vite 响应链发生变化 |
| Vite 仍严格，浏览器收到的 Set-Cookie Path 变宽或 Domain/安全属性变化 | EDGE_SET_COOKIE_TRANSFORM：Vite 之后的 HTTPS 层转换；浏览器可能是在遵守变宽后的生效范围 |
| 检查/iframe 响应另发了本次标记 | COOKIE_REISSUED_AFTER_ISSUANCE：不能只检查首次 Set-Cookie |
| 浏览器发包次数 0，Vite 收到 1 | EDGE_REQUEST_COOKIE_TRANSFORM：不能归责浏览器越界 |
| 浏览器路径与 Vite ingress 不同，或 ingress/outgoing 不同 | EDGE_REQUEST_PATH_TRANSFORM / VITE_REQUEST_PATH_TRANSFORM |
| Vite ingress/outgoing 次数不同 | VITE_REQUEST_COOKIE_TRANSFORM |
| Vite outgoing 与后端次数不符 | VITE_TO_BACKEND_OR_COUNTER_MISMATCH：还不能区分中间转换与后端计数问题 |
| 全部传输次数为 0，页面报 1 | FRONTEND_COUNTER_MISMATCH：检测层不一致 |
| 浏览器确实发了 1，且 CDP 当时关联的未阻止 Cookie Path 仍严格，响应链也未变 | BROWSER_SENT_STRICT_PATH_COOKIE_OUTSIDE_PATH：真实浏览器边界异常证据 |
| 浏览器发了 1，但关联生效 Path 已变宽 | BROWSER_SENT_COOKIE_WITH_DIFFERENT_EFFECTIVE_PATH：不是浏览器违背原 Path 的证据，先追查响应/存储转换 |
| 任一关键边界缺失 | INCOMPLETE_* / MISSING_*：未确定，禁止 PASS |

如果确认是平台重写 Set-Cookie，应用无法靠把断言改成宽 Path 解决。须使用平台支持且保留原路径的
映射配置/入口，或回报环境阻塞并提出受控代理方案；本轮不自动改变未知平台策略或放宽验收。

自动化只在：源提交一致、四条实际路径/请求证据齐全、属性链严格、存储范围严格、浏览器范围内 1/
范围外 0、各代理计数一致、页面 browser_result=PASS 时返回 0；任一异常保留 FAIL。
请回传脱敏 result.json、退出码和浏览器页面诊断 JSON；不要回传整个日志目录/临时 profile、
Cookie 值、原始 CDP 消息、原始 Cookie/Set-Cookie、凭证或数据库。

参考：[Playwright CDPSession](https://playwright.dev/python/docs/api/class-cdpsession)、
[BrowserContext](https://playwright.dev/python/docs/api/class-browsercontext)、
[Chromium Network 协议](https://chromedevtools.github.io/devtools-protocol/tot/Network/)、
[Vite server 选项](https://vite.dev/config/server-options)。
