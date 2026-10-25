# T-004 Cookie 路径检查排查与重测

状态：**未通过；修复与新增回归测试待 CloudStudio 执行**。
用户回传基线为 `b7237e7b10bc0385228113fe282039c9e92d3476`：HTTPS/同源/范围内接收/
范围内 JS 不可读均 true，但范围外接收也为 true，因此 browser_result=FAIL。
未收到实际 Set-Cookie 属性或浏览器逐跳请求证据，不将猜测写成已证实的云端根因。

## 代码可确认的结论

- 后端声明 `Secure; HttpOnly; SameSite=Lax; Path=/api/v1/poc/`，未设置 Domain。
- 外侧路由确为 `/api/v1/poc-outside/cookie-check`，与 `/api/v1/poc/` 不匹配。
- Vite 无路径 rewrite、Cookie Path rewrite 或 Cookie 注入；现有安全配置无需放宽。
- 旧检查只判断固定名称 `hrms_t004_probe` 的固定值。请求 Cookie 不含 Path 元数据，
  同名不同 Path 的历史 Cookie 可以共存，不能把服务器收到同名值归因于本次新设置的 Cookie。
- 旧前端 fetch 默认跟随重定向，且只检查最终 origin；重定向到范围内路径也可能被误报为范围外接收。

以上是确定存在的检测歧义，不等于已经证明 CloudStudio 上是历史 Cookie 或重定向。
Path 匹配及 Cookie 请求不携带 Path 的规则见 [RFC 6265 §5.1.4 / §4.2.2](https://www.rfc-editor.org/rfc/rfc6265)。

## 修复边界与诊断判据

每次浏览器点击/HTTPS 探针生成新的 32 个十六进制字符组成的诊断 ID，名称为 `hrms_t004_probe_<ID>`。
该 ID/固定值只是无权限实验标记，不是认证凭据。所有 Cookie 端点必须提供合法的 `probe_id`。
安全属性、原 Path 和 600 秒期限不变，不删除或改写用户已有 Cookie，不加认证绕过。

前端禁止重定向，校验最终完整 URL；后端返回实际静态路由路径、本次名称是否出现及次数、
旧固定名称是否存在。后端不返回任何 Cookie 名称/值/原始请求头；页面和探针不输出 ID 或 Cookie 内容。
同名重复不折叠成成功：范围内要求恰好 1 个正确标记，范围外要求本次名称出现次数为 0，
即使值不同，范围外出现本次名称也失败。浏览器仍在 Path 内的 iframe 验证本次 HttpOnly 标记不可读。

重测结果的含义：

| 观察 | 结论 |
|---|---|
| 本次 outside=false、count=0，legacy_cookie_outside_path=true | 已收到旧固定名称，但新标记未越界；支持旧 Cookie 干扰的归因 |
| 本次 outside=false、count=0，legacy=false | 新标记隔离通过；不能反推旧故障的唯一原因 |
| 重定向或 observed_path 不符 | 目标路径未被可靠测试，失败；排查平台重定向/重写，不能算 Cookie Path 通过 |
| 本次 outside=true 或 count>0 | 仍是实际异常，继续 FAIL；对比 DevTools 中新标记的 Path/Domain 属性与外侧请求是否携带该名称 |
| 同名 count>1 | 存在同名歧义，失败；不要用字典最后一个值认定成功 |

`legacy_cookie_outside_path` 是旧标记的诊断结果，不是当前独立标记的验收条件。
不以“清空全部 Cookie 后页面不报错”替代证据，也不强制把 outside 改成 false。

## CloudStudio 更新与重测

1. 在旧 `start_t004.sh` 前台终端 Ctrl+C 停止该次两个进程，保留旧版 FAIL 证据。
2. 更新代码并核对本轮交付的新 commit，然后重新 setup。源文件副本/提交约束要求新建环境，
   不可复用旧前端副本，不向原 `.venv` 安装项目依赖。

```bash
git pull --ff-only origin main
git rev-parse HEAD
T004_BASE_PYTHON="$PWD/.venv/bin/python" bash scripts/m00/setup_t004.sh
```

3. 使用 setup 打印的**新目录**和原实际 HTTPS origin：

```bash
export T004_ENV_DIR='<新打印的绝对 T004_ENV_DIR>'
export T004_ORIGIN='https://<实际3000映射主机名>'
bash scripts/m00/test_t004_cookies.sh "$T004_ENV_DIR" &&
bash scripts/m00/start_t004.sh "$T004_ENV_DIR" "$T004_ORIGIN"
```

回归测试使用已声明的 FastAPI/Starlette 加标准库 unittest，无新依赖，无网络请求/真实 Cookie/数据库。
预期 **7 tests / OK / T004_COOKIE_TEST_EXIT_CODE=0**。覆盖：安全属性、干净客户端路径隔离、
旧宽 Path Cookie 重现旧误判、不同运行互不混淆、同名重复、错误值仍判存在、iframe 绑定本次标记。
当前这些测试未在 Windows 或 CloudStudio 执行，不能把补充测试文件当作已通过。

4. 另开终端，设置相同两个变量，执行：

```bash
python3 scripts/m00/t004_probe.py --local --origin http://127.0.0.1:8000 --commit "$(git rev-parse HEAD)"
python3 scripts/m00/t004_probe.py --origin "$T004_ORIGIN" --commit "$(git rev-parse HEAD)" \
  --outside-canary "$T004_ENV_DIR/outside-canary.txt"
```

分别保存退出码，均须 0。浏览器从独立外网打开原 HTTPS 地址并强制刷新，确认页面 commit 为新版本，
再次点击按钮。要求原断言保持：https=true、same_origin=true、cookie_received=true、
cookie_outside_path=false、cookie_hidden_from_js_inside_path=true、browser_result=PASS；
并新增 request_paths_verified=true、cookie_inside_name_count=1、cookie_outside_name_count=0。

若仍失败，只回传脱敏布尔值/次数、实际路由、HTTP 状态/是否重定向及新标记的属性摘要；
不要复制原始 Cookie/Set-Cookie、值、认证头或其他站点 Cookie。先不要改变代理信任或安全属性。
所有运行日志放被忽略的 `var/m00/t004-cookie-tests.*` / `t004-probe.*`。
T-004 全部通过仍需原验收表的其他公网/端口/工作空间重启证据及用户确认。
