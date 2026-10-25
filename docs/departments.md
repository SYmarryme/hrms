# 部门管理：第二批正式功能

本批新增功能、迁移和自动化测试的 CloudStudio 运行结果均为 **NOT_RUN**。
上一批 `ba59a4d0850df897d768ed7f36b2e308941db7d5` 登录闭环已由用户回传安装、迁移、初始化、
`scripts/core/test.sh` 退出0及 Edge HTTPS 登录/主页/退出/刷新重新登录通过；不据此宣称本批通过。

- 登录用户可搜索、分页、查看部门及非敏感直属/子树在职人数。没有员工姓名或人员明细。
- 新增/编辑只允许当前有效、绑定在职员工的 HR。单独 ADMIN、EMPLOYEE、MANAGER 均无部门写权限。
  本批仅实现批准的 HR 写入路径；不凭角色名称推导未落地的专项组织授权。
- 沿用 departments 字段和父 FK；“启用/停用”在接口中映射为 ACTIVE/DISABLED，不新增业务状态。
  code 唯一，层级不成环，启用部门的祖先链须启用；停用不得留下启用子树或在职归属。
- 授权引用表尚未在当前13表中落地；如果数据库出现新授权表，本版保守拒绝停用/改父级，
  后续模块须先补齐对应有效授权判断，不能声称已经完成未来授权模块的测试。
- GET 详情返回强 ETag `"vN"`；PATCH 必须携带该详情的 If-Match，缺失428、过期412。
  详情只返回本部门持久字段，动态上级名称/人数在列表中展示为快照，不纳入详情强ETag。
  请求ID通过响应头返回；写响应另含request_id，不伪造覆盖动态响应体的强ETag。
  数据写入、成功审计与脱敏 Outbox 事实同事务。Outbox 投递器本批未开发。
- **没有 DELETE 接口或物理删除按钮**。原批准接口只提供启停，不能把本次“增删改查”理解为删除历史。
- 前端继续使用相对 /api、原请求模块私有内存 Bearer；没有浏览器持久化认证数据。

## 安全增量迁移

`departments_0002` 在 `identity_0001` 后增加部门状态守卫、父节点索引与首次HR成功审计部分唯一索引。
不改冻结 schema_v1、不新增表、不重建/删除既有身份和员工资料；已有未知部门状态会中止迁移。
`scripts/core/migrate.sh` 先保存私有一致性备份到忽略的 var/core，再升级并检查版本/FK。
迁移错误时检查该目录下日志，不自动恢复备份或重置管理员。

## 首位独立 HR：严格员工前置

用户已批准独立HR受控CLI；按照安全设计 §7.3.1，该账号必须绑定不同的有效 employee_id。
CLI 校验现有ADMIN密码、实时ADMIN角色、独立新账号、有效在职员工及部门/岗位/任职期，
再以普通角色授予写入 assigned_by=操作者、bootstrap_origin=false 和来源审计，同事务提交。
首次HR历史或成功标记存在就拒绝重跑；不用于失权恢复，不创建 CEO、主管或薪酬专项许可。
该普通HR角色授予不要求先建立CEO根任命；当前阻断来自员工/任职事实，而不是CEO功能。

**仅执行登录基线初始化时的前置阻断**：这些脚本只建立首位ADMIN，不产生员工与在职归属；
尚未读取你的云端业务库，不能假定已有合格员工。
Spec FR-EMP-01/FR-LIFE-01 要求部门岗位一致、合法入职状态流转及生效事实；本批尚无批准入职执行链。
因此不能仅给新档案填写 ACTIVE 就声称完成有效入职，也不能给 PRE_HIRE 或 employee_id=NULL 授予正式HR。
CLI 本版只支持绑定已经依法建立且满足检查的员工；缺少时返回 `HR_EMPLOYMENT_PREREQUISITE`，不留半个账号或伪造员工。
用户允许“最小员工初始化”的前提是满足全部必要约束；当前未具备该前提，故未增加绕过入职的员工创建开关。
需先完成合法的初始组织/既有在职资料导入或入职前置方案，再进行真实HR页面写入验收；这不等于重启T-004调查。

## CloudStudio 最少命令

先 Ctrl+C 停止正式启动器，项目根目录逐条执行，退出0才继续；本批无新增依赖，不重建管理员：
如使用过自定义 HRMS_DATABASE_PATH，必须保留同一配置再执行迁移和启动。

```bash
git pull --ff-only origin main
bash scripts/core/migrate.sh
bash scripts/core/test.sh
```

仅当已有满足上述条件、尚未绑定账号的独立员工时：

```bash
read -r -p '现有ADMIN账号: ' HRMS_ADMIN_USERNAME
read -r -p '新的独立HR账号: ' HRMS_HR_USERNAME
read -r -p '已有效入职的独立员工UUID: ' HRMS_HR_EMPLOYEE_ID
var/core/venv/bin/python -m backend.cli init-hr --operator "$HRMS_ADMIN_USERNAME" --username "$HRMS_HR_USERNAME" --employee-id "$HRMS_HR_EMPLOYEE_ID"
```

现有ADMIN密码与HR新密码均终端不回显；无默认值，不传命令参数/环境变量，不粘贴日志或HAR。
没有合格员工时停止初始化，保留明确阻断；不要人工INSERT、改员工状态或给ADMIN自己加HR来绕过。

```bash
read -r -p '实际3000 HTTPS origin: ' HRMS_PUBLIC_ORIGIN
export HRMS_PUBLIC_ORIGIN
bash scripts/core/start.sh
```

人工验收：ADMIN登录→主页→部门列表只读；具备合法HR后新增、名称/编号搜索、分页、详情、改名、
上下级调整、启停及冲突提示；两标签分别重新登录，编辑同一版本应有一方412，重新读取后再编辑。
无Token401、无HR写403、重复编号409、环/有效在职引用409、缺If-Match428由自动化用例验证。
测试脚本同时保留上一批全部登录回归、前端类型检查和构建；以真实退出码与输出为准。
静态清点共定义59项后端用例（含参数化）与16项前端用例，其中本批新增35项后端、10项前端；
这些数量不是通过结果，实际收集和运行仍待CloudStudio执行。
日志/报告/备份只在 var/core，禁止提交；没有任何云端截图、日志或测试结果被编造。
