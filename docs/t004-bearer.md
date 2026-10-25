# T-004 独立 Bearer Token 兼容性验证

状态：**PASS（USER_REPORTED），独立 Bearer 公网兼容性 PoC 已获用户实测确认**。
验收代码：`8d3f7ec9e25208ad2b5219045e21bb3339ffa0ed`。
用户在 Windows Edge 经 CloudStudio 3000 公网 HTTPS 页面取得 bearer_result=PASS，
https/edge/same_origin=true，正确/缺失/错误 Token 为 200/401/401；Bearer 自动回归 7 项通过、退出 0。
见[脱敏验收摘要](evidence/t004-bearer-summary.json)。仅登记明确回传结果，不声称 Codex 已查看原始日志或独立重跑，
不补造执行时间/浏览器版本。原 Cookie 7 项在本提交的重跑结果未单独回传，不混作本次 Bearer 7 项通过。
这不是正式登录、XSS、会话撤销或权限测试的通过，也不是认证架构变更批准。
T-004 仍 BLOCKED；原 Cookie 方案/属性及 SQLite 结果不变，8000 所有者预览问题按用户要求暂不继续研究。

## 实验边界与判定

现有页面新增“运行 Bearer 三项检查”按钮，独立于 Cookie 按钮/结果：

| 同一个临时受测端点 | 唯一变化 | 必须收到 |
|---|---|---|
| 正确 Token | 携带本轮随机合成 Bearer | HTTP 200 |
| 无 Token | 不携带 Authorization | HTTP 401 |
| 错误 Token | 携带本轮错误合成 Bearer | HTTP 401 |

三项全部满足且响应属于同一 HRMS Bearer 实验/服务提交，才显示 bearer_result=PASS；任意不符、
网络错误、跳转、准备失败或过期均 FAIL。401 是两个反例的预期成功结果，不用 response.ok 判断它们失败。
三次响应还须 context_active=true，避免 Edge/设备休眠后上下文过期的 401 被误当作两个反例已验证；
该布尔只反映临时实验上下文是否存在，不诊断 Authorization 中间处理。
必须实际使用 Edge；页面同时要求 HTTPS、安全上下文和 Edge 标识，浏览器标识只作实验前置提示，
不作为生产认证依据。通过本实验不代表采用 Bearer 作为正式 HRMS 认证，也不解除 T-004 Gate。

浏览器 Web Crypto 每轮生成随机 Token，只在函数局部内存中使用。首次 POST
`/api/v1/poc/bearer-probes` 只提交 SHA-256 摘要，后端只在内存保留该摘要与有效期，返回不相关随机上下文 ID。
随后三次 GET `/api/v1/poc/bearer-probes/<上下文ID>` 检查 Bearer。
上下文 ID 不是 Token，只有 ID 不能获得 200；URL 中不含 Token 或 Token 摘要。
本项目不返回、记录或保存原始 Token，页面也不显示 Token/摘要/上下文 ID。
最多 64 个上下文，120 秒到期，服务重启即失效；不写文件/数据库/`.env`。

这是公开、无业务权限的合成测试准备端点，调用者可为自己的随机实验 Token 登记摘要；
它不发放真实凭证、不授权任何原有路由，不是登录接口或认证绕过。
原 GET 健康/Cookie 夹具保留，新增的唯一 POST 只建立临时实验摘要。
全部 Bearer fetch 使用同源相对路径、credentials=omit、禁止重定向及请求超时，
不使用 Cookie、localStorage、sessionStorage、URL 参数或持久化缓存保存 Token。
不追踪/比较中间 Authorization 请求头，也不输出是否被删除、改写或截断；只记录终端状态码和固定响应身份。
Vite Host 白名单、3000 监听、8000 loopback、原代理和 Cookie 安全属性均不改动。

## CloudStudio Ubuntu 命令

以下保留为日后复测流程，本次仅登记既有通过结果，**无需因文档更新重新 setup/重建服务**。
已验收服务提交是上方 8d3f7ec，不能用本次记录提交替换该运行基线；日后重测应另记实际服务提交。
Bearer 功能初次交付同时新增了前后端代码；日后复测时，setup、服务与实际目标源码提交必须一致，不能混用旧服务。
在旧 start_t004.sh 的前台终端 Ctrl+C，只停止它自己启动的旧测试进程；不要结束其他用户进程。
然后在项目根目录：

```bash
git status --short
git pull --ff-only origin main
git rev-parse HEAD
T004_BASE_PYTHON="$PWD/.venv/bin/python" bash scripts/m00/setup_t004.sh
printf 'SETUP_COMMAND_EXIT_CODE=%s\n' "$?"
```

若已跟踪源码有本地修改或 setup 退出非 0，保留原文件/错误并停止后续步骤，不 reset 或覆盖。
setup 成功后从输出复制新的 T004_ENV_DIR（不能用旧提交环境），运行后端回归：

```bash
read -r -p '本次 setup 输出的 T004_ENV_DIR 绝对目录: ' T004_ENV_DIR
export T004_ENV_DIR
bash scripts/m00/test_t004_bearer.sh "$T004_ENV_DIR"
printf 'BEARER_REGRESSION_COMMAND_EXIT_CODE=%s\n' "$?"
bash scripts/m00/test_t004_cookies.sh "$T004_ENV_DIR"
printf 'COOKIE_REGRESSION_COMMAND_EXIT_CODE=%s\n' "$?"
```

预期新增 7 项 ASGI 回归通过，T004_BEARER_TEST_EXIT_CODE=0；原 7 项 Cookie 回归仍应通过。
Bearer 7 项已于上方提交获用户回传通过；原 Cookie 7 项本提交复测未单独回传，不能据此一并标记通过。
ASGI 回归直接走应用路由/状态码，不代表公网/Edge 验收。产物仅在被忽略的 var/m00 下。

确认两套回归成功后，从 **3000 端口**卡片复制当前公开 HTTPS origin，保持 8000 仅自己可见和本机监听：

```bash
read -r -p '3000 端口公开 HTTPS origin（不带路径/查询）: ' T004_ORIGIN
export T004_ORIGIN
bash scripts/m00/start_t004.sh "$T004_ENV_DIR" "$T004_ORIGIN"
```

该终端保持前台运行。继续使用既有 setup/start，不新增 start.sh，不改 Host 校验或端口访问策略。
未完成安装/启动时不要跳到旧服务页面测试。

## Edge 浏览器验收

1. 用真实 Microsoft Edge，从平台 **3000 公开端口**链接打开 HTTPS 页面，确认显示新增 Bearer 区块。
2. 点击“运行 Bearer 三项检查”；不必点击 Cookie 按钮，也不输入任何 Token。
3. 查看该区块的脱敏 JSON：https=true、edge=true、same_origin=true，
   statuses.correct=200、statuses.missing=401、statuses.wrong=401，bearer_result=PASS。
   commit 必须与本次实际启动的 git rev-parse HEAD 一致。
4. 任一状态码不符、状态为 null 或 bearer_result=FAIL 即未通过。仅回传三项状态、PASS/FAIL 和服务 commit。
   不展开/导出 Authorization、请求体、网络原始头、HAR、Cookie 存储或浏览器调试快照。
5. Cookie 区块可能仍 FAIL/NOT_RUN，不能用 Bearer 结果覆盖它；整个 T-004 仍 BLOCKED。

本轮不调查 Authorization 的具体中间处理；失败只记录结果，不增加逐层头部诊断或放宽规则。
若 public 入口要求平台 Cookie，credentials=omit 可能导致跳转/失败，按真实结果 FAIL，不能回退 Cookie 来强行通过。
重试会生成新 Token 和上下文；刷新/结束本次函数后不持久保存 Token，但不声称能强制擦除浏览器内部所有瞬态字符串。
SQLite 已有重启结果无需重做，不拷贝或提交 DB/回执。Windows 不运行这些项目测试。

参考：[Fetch credentials](https://developer.mozilla.org/en-US/docs/Web/API/Request/credentials)、
[FastAPI 直接返回响应](https://fastapi.tiangolo.com/advanced/response-directly/)。
