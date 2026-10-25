# T-004 CloudStudio 执行指令

本页为 CloudStudio 操作说明；Windows 不安装或运行项目。
最新结论：当前公网入口 Cookie 属性改写，T004-05/完整浏览器验收 BLOCKED。
先阅读[平台兼容性与直连 A/B 对比](t004-platform-compatibility.md)，不要循环重写应用 Cookie 代码。
以下安装/启动/全流程保留作历史步骤及今后平台入口正式变更后的复测说明。
用户已确认既有服务 A/B 为 BLOCKED_CURRENT_PUBLIC_ENTRY / AFTER_LOOPBACK_VITE。
当前改按[8000 外部隔离与 SQLite 工作空间重启](t004-remaining-acceptance.md)继续独立验收，
不再重写 Cookie 检测或反复重装应用/浏览器；[官方支持说明](cloudstudio-support-issue.md)仅准备未发送。
未收到逐项证据的其他项目仍待验证，T-004 未通过。
T-001～T-003 已获用户验收，代码基线见 `docs/acceptance.md`。
本任务按正式 T-004 准备临时 Vue/TypeScript/Vite + FastAPI GET-only 健康夹具，
不是 HRMS 应用骨架，不接入员工、工资、正式认证或生产数据库。

操作前：项目根目录 `git pull --ff-only origin main`，再执行 `git rev-parse HEAD`，
核对本轮交付报告提交号。更新失败或提交不符先停止修正。
本说明中的 `<...>` 均需替换；所有退出码必须保留。不要输入凭证或带 Token 的 URL。

## 1. 隔离安装

```bash
T004_BASE_PYTHON="$PWD/.venv/bin/python" bash scripts/m00/setup_t004.sh
setup_rc=$?
printf 'SETUP_COMMAND_EXIT_CODE=%s\n' "$setup_rc"
```

预期 `T004_SETUP_EXIT_CODE=0`，并打印 `T004_ENV_DIR=/绝对路径/var/m00/t004-env.<随机后缀>`。
复制该路径供下文使用。脚本在新目录中建独立 venv，复制**仅公开的四份前端源文件**，
在副本里安装 npm 包。原 `.venv`、已验收的 M00 锁、项目源目录不被安装步骤修改。
新 FastAPI/Uvicorn/Vue/Vite 依赖尚未云端验证，版本范围是候选声明，不是假锁。
保存真实 `python.freeze.txt`、`node-version.txt`、`npm-version.txt`、`npm-tree.txt`、
`frontend/package-lock.json` 和 `setup.log`，云端回传后再校准并公开固化锁文件。
不把此新环境误用为原 M00 的严格 13 包重放环境。

Node 需满足 Vite 的 `20.19+ / 22.12+` 代际要求；脚本不足则退出，不自行升级系统工具。
没有 `.venv` 时指定现有 Python >=3.11 的路径。安装失败回传真实错误，禁止改旧 M00 版本来适配。
参考 [Vite 环境要求](https://vite.dev/guide/)。

## 2. 配置唯一公网入口并启动

在 CloudStudio 的端口/预览管理面板取得 **3000 端口**的 HTTPS 映射 URL，
只保留这个入口，确认没有 8000 公网映射。记录端口面板截图和实际 URL。
不能取得入口或平台强制暴露后端时标 BLOCKED，回传实际限制，不猜域名或关闭 Host 校验。
用平台实际给出的纯 origin（不带路径、查询、用户名、密码）运行：

```bash
export T004_ENV_DIR='<上一步实际打印的绝对环境目录>'
export T004_ORIGIN='https://<3000映射的实际主机名>'
bash scripts/m00/start_t004.sh "$T004_ENV_DIR" "$T004_ORIGIN"
```

该终端保持前台运行；另开终端测试。Ctrl+C 只清理该次启动的两个子进程。
端口占用时失败，不杀已有服务、不换到另一个端口蒙混通过。保存打印的 `T004_SERVER_LOG_DIR`。
前端 `0.0.0.0:3000`、后端 `127.0.0.1:8000`，启动日志中的 `listeners.txt` 应一致。
源提交变化需重新 setup，避免混用旧前端副本与新后端。
setup/start 均拒绝相关源目录的未提交变更，启动时还核对副本源文件的 Git 哈希；
不能在改动代码后仍用旧提交号作为本次验证证据。

Cookie 检查现要求每次独立 `probe_id`；页面和 HTTPS 探针会自动生成，手工请求不带合法 ID 返回 422。
Path 与安全属性不变，不重写或清空用户已有 Cookie；旧固定名称只做脱敏诊断，不当成本次标记。
前端拒绝重定向并核对最终 URL/后端实际路径，范围外出现本次名称即失败，不能用值不匹配掩盖越界。

转发头策略：Uvicorn `--no-proxy-headers`；Vite 不信任客户端或未知平台的 Forwarded/
X-Forwarded-*，清除后只写操作人配置的 HTTPS origin。因此健康输出的 `transport_scheme`
应仍是 HTTP（工作空间内部一跳），外部 TLS 由 HTTPS 探针/浏览器证实，不能靠请求头自证。
这不推断平台客户端真实 IP，也不是生产多层代理策略。诊断 Cookie 无条件 Secure，
是固定、公开的无权限测试标记，不能用于登录；所有持久化写入仅限下述 CLI。
参考 [FastAPI 代理说明](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)、
[Uvicorn 选项](https://uvicorn.dev/settings/) 与 [Vite Host/文件服务选项](https://vite.dev/config/server-options)。

## 3. 本机、HTTPS 和浏览器检查

另开终端，重新设置 `T004_ORIGIN` 和 `T004_ENV_DIR` 为上述实际值：

```bash
python3 scripts/m00/t004_probe.py --local --origin http://127.0.0.1:8000 --commit "$(git rev-parse HEAD)"
printf 'LOCAL_PROBE_COMMAND_EXIT_CODE=%s\n' "$?"
python3 scripts/m00/t004_probe.py --origin "$T004_ORIGIN" --commit "$(git rev-parse HEAD)" \
  --outside-canary "$T004_ENV_DIR/outside-canary.txt"
printf 'HTTPS_PROBE_COMMAND_EXIT_CODE=%s\n' "$?"
```

两次均应退出 0。HTTPS 探针不跳过证书、不跟随登录重定向，不记录响应原文/Cookie。
断言包括本次 commit、伪造头被替换、Cookie 的 Secure/HttpOnly/SameSite/Path 和路径排除。
`outside-canary.txt` 是 setup 在前端根目录**外**生成的无敏感测试文件；它确实存在，
探针先检查本地文件存在且内容为固定无敏感标记，拼错或缺失时失败；
经 `/@fs/` 请求必须 403/404，不能只凭请求一个不存在的文件证明边界。
未提供 canary 参数时该项仍 NOT_RUN；前端 fs.allow 只允许隔离副本，绝不把仓库根加入允许目录。

再从**工作空间之外的真实浏览器/网络**打开该 HTTPS URL，点击页面按钮，结果应为 PASS：
Vue 实际渲染、fetch 同源、cookie_received=true、cookie_outside_path=false、cookie_hidden_from_js_inside_path=true。
最后一项在 Cookie Path 内的同源 iframe 文档检查，且先确认该文档已收到诊断 Cookie；
不能在 `/` 上读不到 Cookie 就断言 HttpOnly，因为 Path 本身也会阻止它出现。
浏览器 DevTools 的 Network/Application 中核查 Secure、HttpOnly、SameSite=Lax、Path，
不截图/分享其他站点的真实 Cookie。记录当前 commit、验证时间和截图，不能用 curl 代替 Vue 渲染证据。

**8000 负测须独立完成**：保存端口管理面板仅映射 3000 的记录、loopback 监听记录，
并从外部网络检查平台显示/曾配置的 8000 地址不能直接获得 `fixture=hrms-t004` 健康响应。
不要擅自创建 8000 公网映射来测试。如果存在这样的地址且能直接访问，立即删除该映射并复测，
原失败记录保留。仅某次 DNS/网络错误不足以证明未暴露；无平台或外网证据则该项 NOT_RUN/BLOCKED。
自工作空间运行 HTTPS 探针只证明 HTTP 路径，不能替代此独立外网及端口证据。

## 4. SQLite 工作空间重启持久化

选择操作者确认可写的**私有绝对目录**作为数据根；禁止选择正在服务的 frontend 目录或真实业务库。
可先试工作区的忽略目录，但这只是待测候选位置，不预设该位置会持久化：

```bash
mkdir -p var/m00
python3 scripts/m00/t004_persistence.py prepare --data-root "$PWD/var/m00"
printf 'PREPARE_COMMAND_EXIT_CODE=%s\n' "$?"
```

脚本只新建 `hrms-t004.<随机后缀>/marker.sqlite3`，写一行随机合成标记；不覆盖已有库。
打印 `receipt` 的路径，将其设为变量，先做一次基线核验：

```bash
export T004_RECEIPT='<实际打印的 receipt.json 绝对路径>'
python3 scripts/m00/t004_persistence.py verify --receipt "$T004_RECEIPT"
printf 'BEFORE_RESTART_EXIT_CODE=%s\n' "$?"
```

通过后将 receipt.json **下载到本地单独保管**，同时保存真实数据库路径和当前 commit，
不要公开或改写回执。如果工作区整体消失，该独立回执仍应能证明原来预期的内容。
使用 CloudStudio UI **暂停并恢复或完整重启工作空间**，记录实际操作时间与平台状态。
只 Ctrl+C 或重启两个应用进程不算该项完成；不调用任何生产恢复 CLI。

恢复后确认检出同一代码提交；如环境/依赖丢失，可重新 setup 并用新环境重新启动服务，
但**不能重新 prepare 或复制旧库回去充当持久化通过**。使用原回执（需要时从独立本地副本私下上传）运行：

```bash
python3 scripts/m00/t004_persistence.py verify --receipt '<原始回执实际路径>'
printf 'AFTER_RESTART_EXIT_CODE=%s\n' "$?"
```

应退出 0，`logical_content=MATCH`、`integrity=ok`，并重新运行 HTTPS/浏览器检查。
验证缺文件、改标记或完整性错误会退出非零，不自动建库/修复。
负例可传一个不存在的回执路径验证非零；不要破坏实际基线文件做负例。
SQLite verify 的 PASS 不证明重启事件发生过，仍需人工平台证据。
数据消失则记录 FAIL/BLOCKED，并提出持久化目录/存储方案，不能宣布 M00 Gate 通过。

## 5. 回传、退出和清理

每个脚本都有独立 `var/m00/t004-*` 目录（数据库另在所选私有根的新目录中），
保存 JSON/日志/退出码、安装快照、锁与数据库。所有这些运行产物不进公开 Git。
回传本次 commit、真实 URL/时间、各退出码及脱敏报告、浏览器/端口/重启证据、
安装候选锁和平台机时/休眠/端口/访问有效期限制。逐项填写 `t004-acceptance.md` 后由用户验收。
HTTP 200 或某个脚本 PASS 都不代表整项 T-004 通过，更不表示正式上线或持续可用。

结束时在服务前台 Ctrl+C；保留证据。只在核对实际路径与进程已停止后删除**该次**随机实验目录，
不得通配清理、删除 `.venv`/其他实验、清空任何数据根或用 `git clean -fdx`。
