import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

// Ephemeral test credentials supplied to this child process only; never a default password.
const credentials: Record<string,string> = JSON.parse(process.env.HRMS_E2E_PASSWORDS || '{}');
async function login(page: Page, role: string) {
  await page.goto('/login');
  await page.getByLabel('账号', { exact:true }).fill('fixture-' + role);
  await page.getByLabel('密码', { exact:true }).fill(credentials[role]);
  await page.getByRole('button', { name:'登录', exact:true }).click();
  await expect(page.getByRole('heading', { name:'系统主页' })).toBeVisible();
}
async function logout(page: Page) {
  await navigate(page,'/');await page.getByRole('button', {name:'退出登录',exact:true}).click();
  await expect(page.getByRole('heading', {name:'登录'})).toBeVisible();
}
async function navigate(page: Page, destination: string) {
  const links:Record<string,string>={'/':'工作台','/departments':'部门管理','/positions':'职位管理','/employees':'员工档案','/attendance':'考勤管理','/leaves':'请假管理','/approvals':'直属部门审批','/salaries':'薪资管理','/dashboard':'数据看板'};
  await page.getByRole('navigation',{name:'业务菜单'}).getByRole('link',{name:links[destination],exact:true}).click();
}

test('real Edge course chain: ADMIN → HR organization/files → EMPLOYEE leave → MANAGER decision → salary/dashboard', async ({page}) => {
  test.skip(!credentials.admin, 'Run through scripts/e2e_local.py to allocate an isolated database');
  await login(page,'admin');
  await page.getByRole('navigation',{name:'业务菜单'}).getByRole('link',{name:'用户管理与审计',exact:true}).click();
  await expect(page.getByRole('cell',{name:'fixture-hr',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'创建账号',exact:true}).click();
  await page.getByLabel('账号',{exact:true}).fill('fixture-extra-admin');
  await page.getByLabel('初始密码',{exact:true}).fill(credentials.admin+'A');
  await page.getByLabel('EMPLOYEE',{exact:true}).uncheck();await page.getByLabel('ADMIN',{exact:true}).check();
  await page.getByRole('button',{name:'保存账号',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('保存');
  const extra=page.getByRole('row').filter({has:page.getByRole('cell',{name:'fixture-extra-admin',exact:true})});
  await extra.getByRole('button',{name:'编辑 / 角色 / 停用',exact:true}).click();
  await page.getByLabel('状态',{exact:true}).selectOption('DISABLED');await page.getByRole('button',{name:'保存账号',exact:true}).click();
  await expect(extra.getByRole('cell',{name:'停用',exact:true})).toBeVisible();
  await logout(page);

  await login(page,'hr');
  await navigate(page,'/departments');await page.getByRole('button',{name:'新增部门',exact:true}).click();
  await page.getByLabel('部门编号',{exact:true}).fill('E2E-DEPT');await page.getByLabel('部门名称',{exact:true}).fill('[虚构]Edge部门');
  await page.getByRole('button',{name:'保存部门',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('成功');
  await navigate(page,'/positions');await page.getByRole('button',{name:'新增职位',exact:true}).click();
  await page.getByLabel('编码',{exact:true}).fill('E2E-POS');await page.getByLabel('名称',{exact:true}).fill('[虚构]Edge岗位');
  await page.getByLabel('职级',{exact:true}).last().fill('G2');await page.getByLabel('所属部门',{exact:true}).selectOption({label:'[虚构]Edge部门'});
  await page.getByRole('button',{name:'保存职位',exact:true}).click();await expect(page.getByRole('status')).toContainText('保存');
  await navigate(page,'/employees');await page.getByRole('button',{name:'新增员工',exact:true}).click();
  await page.getByLabel('工号',{exact:true}).fill('E2E-EMP');await page.getByLabel('姓名',{exact:true}).fill('[虚构]Edge员工');
  await page.getByLabel('部门',{exact:true}).last().selectOption({label:'[虚构]Edge部门'});
  await page.getByLabel('职位',{exact:true}).selectOption({label:'[虚构]Edge岗位 · G2'});
  await page.getByLabel('入职日期',{exact:true}).fill('2026-01-01');
  await page.getByRole('button',{name:'保存员工',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'员工档案已保存'})).toBeVisible();
  const employeeRow=page.getByRole('row').filter({hasText:'E2E-EMP'});
  await employeeRow.getByRole('button',{name:'编辑',exact:true}).click();await page.getByLabel('姓名',{exact:true}).fill('[虚构]Edge员工改名');
  await page.getByRole('button',{name:'保存员工',exact:true}).click();await expect(employeeRow).toContainText('员工改名');
  await employeeRow.getByRole('button',{name:'调动',exact:true}).click();await page.getByLabel('新部门',{exact:true}).selectOption({label:'[虚构课程]研发部'});
  await page.getByLabel('新职位',{exact:true}).selectOption({label:'[虚构课程]职员'});await page.getByRole('button',{name:'保存员工',exact:true}).click();
  await expect(employeeRow).toContainText('[虚构课程]研发部');
  const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'导出 CSV（当前查询）',exact:true}).click();
  const download=await downloadPromise;const file=await download.path();if(!file)throw new Error('Download not available');
  const content=await fs.readFile(file,'utf8');expect(content).toContain('E2E-EMP');
  const lines=content.trim().split(/\r?\n/);const source=lines.find(line=>line.startsWith('E2E-EMP,'));if(!source)throw new Error('Export row missing');
  const upload=path.resolve('..','var','mvp','e2e-import.csv');
  await fs.writeFile(upload,lines[0]+'\r\n'+source.replace('E2E-EMP','E2E-IMPORT')+'\r\n');
  await page.getByLabel('选择模板文件',{exact:true}).setInputFiles(upload);
  await page.getByRole('button',{name:'预检文件',exact:true}).click();
  await expect(page.getByText('预检有效；正式提交时服务端会重新校验。已写入 0 条。')).toBeVisible();
  await page.getByRole('button',{name:'导入',exact:true}).click();await expect(page.getByRole('status').first()).toContainText('导入');
  page.once('dialog',dialog=>dialog.accept());await employeeRow.getByRole('button',{name:'离职归档',exact:true}).click();await expect(employeeRow).toContainText('已离职');
  await navigate(page,'/positions');const positionRow=page.getByRole('row').filter({hasText:'E2E-POS'});
  await positionRow.getByRole('button',{name:'编辑',exact:true}).click();await page.getByLabel('职位状态',{exact:true}).selectOption('DISABLED');
  await page.getByRole('button',{name:'保存职位',exact:true}).click();await expect(positionRow).toContainText('停用');
  await navigate(page,'/departments');const departmentRow=page.getByRole('row').filter({has:page.getByRole('cell',{name:'E2E-DEPT',exact:true})});
  await departmentRow.getByRole('button',{name:'编辑',exact:true}).click();await page.getByLabel('部门状态',{exact:true}).selectOption('DISABLED');
  await page.getByRole('button',{name:'保存部门',exact:true}).click();await expect(departmentRow.getByRole('cell',{name:'停用',exact:true})).toBeVisible();
  await navigate(page,'/salaries');await page.getByLabel('员工',{exact:true}).last().selectOption({label:'FIXTURE-EMPLOYEE · [虚构课程]employee'});
  await page.getByLabel('月份',{exact:true}).last().fill(new Date().toISOString().slice(0,7));await page.getByLabel('应发总额（元）',{exact:true}).fill('8800.50');
  await page.getByRole('button',{name:'保存薪资',exact:true}).click();await expect(page.getByRole('status')).toContainText('保存');await logout(page);

  await login(page,'employee');await navigate(page,'/attendance');
  const weekday=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',weekday:'short'}).format(new Date());
  const punchResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/attendance/clock-in');
  await page.getByRole('button',{name:'上班打卡',exact:true}).click();
  expect((await punchResponse).status()).toBe(['Sat','Sun'].includes(weekday)?409:200);
  if(!['Sat','Sun'].includes(weekday)){
    await expect(page.getByRole('status').filter({hasText:'上班打卡成功'})).toBeVisible();
    await page.getByRole('button',{name:'下班打卡',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'下班打卡成功'})).toBeVisible();
  } else test.info().annotations.push({type:'NOT_RUN',description:'Weekend: live two-punch path not applicable; backend controlled-clock fixture tests it'});
  await navigate(page,'/leaves');const next=new Date();next.setDate(next.getDate()+1);while([0,6].includes(next.getDay()))next.setDate(next.getDate()+1);
  const day=next.toLocaleDateString('sv-SE');await page.getByLabel('起始日期',{exact:true}).fill(day);await page.getByLabel('结束日期',{exact:true}).fill(day);
  await page.getByLabel('理由',{exact:true}).fill('虚构课程 Edge 请假');await page.getByRole('button',{name:'提交申请',exact:true}).click();
  await expect(page.getByRole('cell',{name:'待审批',exact:true})).toBeVisible();await logout(page);

  await login(page,'manager');await navigate(page,'/approvals');
  await page.getByRole('button',{name:'处理审批',exact:true}).click();await page.getByLabel('审批意见',{exact:true}).fill('虚构课程批准');
  await page.getByRole('button',{name:'批准',exact:true}).click();await expect(page.getByRole('cell',{name:'已批准',exact:true})).toBeVisible();await logout(page);
  await login(page,'employee');await navigate(page,'/leaves');await expect(page.getByRole('cell',{name:'已批准',exact:true})).toBeVisible();
  await navigate(page,'/salaries');await expect(page.getByRole('cell',{name:'8800.50',exact:true})).toBeVisible();
  await page.reload();await expect(page.getByRole('heading',{name:'登录'})).toBeVisible();
  await login(page,'hr');await navigate(page,'/dashboard');await expect(page.getByRole('heading',{name:'近六个月应发总额（仅 HR）',exact:true})).toBeVisible();await expect(page.getByText('8800.50 元',{exact:true})).toBeVisible();
});
