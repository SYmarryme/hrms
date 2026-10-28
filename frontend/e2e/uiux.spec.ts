import { test,expect,type Page } from '@playwright/test';
import path from 'node:path';
const credentials:Record<string,string>=JSON.parse(process.env.HRMS_E2E_PASSWORDS||'{}');
const activated:Record<string,string>={};
const menu=(page:Page)=>page.getByRole('navigation',{name:'业务菜单'});
async function login(page:Page,role:string,username='fixture-'+role){
 test.skip(!credentials[role],'Use the isolated local E2E runner');await page.goto('/login');
 await page.getByLabel('账号',{exact:true}).fill(username);await page.getByLabel('密码',{exact:true}).fill(activated[username]||credentials[role]);
 await page.getByRole('button',{name:'登录',exact:true}).click();
 if(username!=='fixture-'+role&&!activated[username]){
  const dialog=page.getByRole('dialog',{name:'首次登录 · 请修改密码',exact:true});await expect(dialog).toBeVisible();
  await dialog.getByLabel('当前密码：',{exact:true}).fill(credentials[role]);await dialog.getByLabel('新密码：',{exact:true}).fill(credentials[role]+'Activated');await dialog.getByLabel('确认新密码：',{exact:true}).fill(credentials[role]+'Activated');
  await dialog.getByRole('button',{name:'保存新密码',exact:true}).click();await expect(page.getByRole('heading',{name:'登录账号'})).toBeVisible();
  await page.getByLabel('账号',{exact:true}).fill(username);await page.getByLabel('密码',{exact:true}).fill(credentials[role]+'Activated');await page.getByRole('button',{name:'登录',exact:true}).click();
 }
 if(username!=='fixture-'+role)activated[username]=credentials[role]+'Activated';
 await expect(page.getByRole('heading',{name:'系统主页'})).toBeVisible();
}
async function visit(page:Page,label:string){await menu(page).getByRole('link',{name:label,exact:true}).click();}
async function apiStatus(page:Page,url:string,method='GET',body?:unknown){
 return page.evaluate(async({url,method,body})=>{
   const module=await import('/src/course-api.ts');try{await module.courseApi(url,method,body);return 200;}catch(error){return (error as {status:number}).status;}
 },{url,method,body});
}

test('UIUX password toggle works after blur and by keyboard',async({page})=>{
 test.skip(!credentials.employee,'Use isolated runner');await page.goto('/login');
 const input=page.getByLabel('密码',{exact:true});await input.fill(credentials.employee);await page.getByLabel('账号',{exact:true}).click();
 await page.getByRole('button',{name:'显示密码',exact:true}).click();expect(await input.getAttribute('type')).toBe('text');
 expect(await input.inputValue()===credentials.employee).toBe(true);
 await page.getByRole('button',{name:'隐藏密码',exact:true}).focus();await page.keyboard.press('Space');expect(await input.getAttribute('type')).toBe('password');
});
for(const role of ['employee','manager','hr','admin'])test(`UIUX ${role} menu, panels and backend denials`,async({page})=>{
 await login(page,role);
 if(role==='employee'){
   await expect(menu(page).getByRole('link',{name:'部门管理',exact:true})).toHaveCount(0);
   await expect(menu(page).getByRole('link',{name:'员工档案',exact:true})).toHaveCount(0);
   await visit(page,'考勤管理');await expect(page.getByRole('button',{name:'配置考勤规则',exact:true})).toHaveCount(0);
   await visit(page,'薪资管理');await expect(page.getByRole('button',{name:'保存薪资'})).toHaveCount(0);
   expect(await apiStatus(page,'/salaries?employee_id=00000000-0000-0000-0000-000000000000')).toBe(403);
 }else if(role==='manager'){
   await expect(menu(page).getByRole('link',{name:'直属部门审批',exact:true})).toBeVisible();
   await visit(page,'员工档案');await expect(page.getByRole('button',{name:'新增员工'})).toHaveCount(0);await expect(page.getByRole('button',{name:'导出 CSV（当前查询）'})).toBeVisible();await expect(page.getByRole('button',{name:'下载 XLSX 模板'})).toHaveCount(0);await expect(page.getByRole('heading',{name:'批量导入员工',exact:true})).toHaveCount(0);
   expect(await apiStatus(page,'/departments','POST',{code:'DENY',name:'不能新增'})).toBe(403);
 }else if(role==='hr'){
   await visit(page,'部门管理');await expect(page.getByRole('button',{name:'新增部门'})).toBeVisible();
   await visit(page,'考勤管理');await expect(page.getByRole('button',{name:'配置考勤规则',exact:true})).toBeVisible();
   await expect(menu(page).getByRole('link',{name:'用户管理与审计'})).toHaveCount(0);expect(await apiStatus(page,'/users')).toBe(403);
 }else{
   await visit(page,'用户管理与审计');await expect(page.getByRole('button',{name:'创建账号'})).toBeVisible();
   await expect(menu(page).getByRole('link',{name:'薪资管理',exact:true})).toHaveCount(0);expect(await apiStatus(page,'/salaries')).toBe(403);
   await visit(page,'部门管理');await expect(page.getByRole('button',{name:'新增部门'})).toHaveCount(0);
 }
 await expect(menu(page).locator('a.selected')).toHaveCount(1);await expect(page.locator('.page-tab.active')).toHaveCount(1);
});

test('UIUX unique highlight, retained filters, modal dirty close and clean reopen',async({page})=>{
 await login(page,'hr');await visit(page,'部门管理');await page.getByLabel('部门名称或编号').fill('保留查询');
 await visit(page,'职位管理');await page.getByLabel('每页条数').selectOption('50');await visit(page,'部门管理');
 await expect(page.getByLabel('部门名称或编号')).toHaveValue('保留查询');
 await expect(menu(page).locator('a.selected')).toHaveText('部门管理');await expect(menu(page).getByRole('link',{name:'工作台',exact:true})).not.toHaveClass(/selected/);
 await page.getByRole('button',{name:'新增部门',exact:true}).click();await page.getByLabel('部门编号',{exact:true}).fill('UNSAVED');
 await page.getByRole('button',{name:'关闭弹窗'}).click();await page.getByRole('dialog',{name:'放弃未保存修改'}).getByRole('button',{name:'继续编辑'}).click();await expect(page.getByLabel('部门编号',{exact:true})).toHaveValue('UNSAVED');
 await page.getByRole('button',{name:'关闭弹窗'}).click();await page.getByRole('dialog',{name:'放弃未保存修改'}).getByRole('button',{name:'放弃修改'}).click();
 await page.getByRole('button',{name:'关闭部门管理标签'}).click();await visit(page,'部门管理');await expect(page.getByLabel('部门编号',{exact:true})).toHaveCount(0);
 await visit(page,'职位管理');await expect(page.getByLabel('每页条数')).toHaveValue('50');
 await page.getByRole('button',{name:'折叠业务导航'}).click();await expect(page.locator('.app-frame')).toHaveClass(/nav-collapsed/);
});

test('UIUX transient save, department shortcut, page sizes and visual layout',async({page})=>{
 await login(page,'hr');await page.setViewportSize({width:1440,height:1000});await visit(page,'部门管理');
 await page.getByRole('button',{name:'新增部门',exact:true}).click();await page.getByLabel('部门编号',{exact:true}).fill('UIUX-SHORTCUT');await page.getByLabel('部门名称',{exact:true}).fill('虚构界面验收部');
 await page.getByRole('button',{name:'保存部门',exact:true}).click();const notice=page.getByRole('status').filter({hasText:'部门新增成功'});await expect(notice).toBeVisible();await expect(notice).toBeHidden({timeout:7000});
 const row=page.getByRole('row').filter({has:page.getByRole('cell',{name:'UIUX-SHORTCUT',exact:true})});
 await row.getByRole('button',{name:'停用',exact:true}).click();await page.getByRole('dialog',{name:'停用部门'}).getByRole('button',{name:'确认',exact:true}).click();await expect(row.getByRole('cell',{name:'停用',exact:true})).toBeVisible();
 await row.getByRole('button',{name:'恢复',exact:true}).click();await page.getByRole('dialog',{name:'恢复部门'}).getByRole('button',{name:'确认',exact:true}).click();await expect(row.getByRole('cell',{name:'启用',exact:true})).toBeVisible();
 await page.screenshot({path:path.resolve('..','var','uiux','departments-live.png'),fullPage:true});
 await visit(page,'员工档案');await page.getByLabel('每页条数').selectOption('50');await expect(page.getByLabel('每页条数')).toHaveValue('50');
 await expect(page.getByRole('button',{name:'导出 CSV（当前查询）'})).toBeVisible();await expect(page.getByRole('heading',{name:'批量导入员工',exact:true})).toBeVisible();
});

test('UIUX attendance persistent status and specific duplicate feedback',async({page})=>{
 const day=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',weekday:'short'}).format(new Date());test.skip(['Sat','Sun'].includes(day),'Workday live check; server-clock tests cover weekends');
 await login(page,'employee');await visit(page,'考勤管理');await expect(page.getByRole('button',{name:'上班打卡'})).toBeEnabled();
 const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/attendance/clock-in',{timeout:10000});
 await page.getByRole('button',{name:'上班打卡',exact:true}).click();const code=(await response).status();expect([200,409]).toContain(code);
 if(code===409)await page.getByRole('button',{name:'关闭反馈，查看今日状态'}).click();
 else {const message=page.getByRole('status').filter({hasText:'上班打卡成功'});await expect(message).toBeVisible();await expect(message).toBeHidden({timeout:7000});}
 await expect(page.locator('.persistent-punch')).toContainText('今日已完成');
 await page.getByRole('button',{name:'上班打卡',exact:true}).click();await expect(page.getByRole('alert')).toContainText('今日已完成上班打卡');
 await expect(page.locator('.persistent-punch')).toHaveCount(0);await page.getByRole('button',{name:'关闭反馈，查看今日状态'}).click();await expect(page.locator('.persistent-punch')).toBeVisible();
});

test('UIUX cached manager scope is revalidated after another user transfers an employee',async({page,browser})=>{
 const applicant=await browser.newPage();await login(applicant,'employee');expect(await apiStatus(applicant,'/leaves','POST',{start_date:'2040-01-02',end_date:'2040-01-02',leave_type:'OTHER',reason:'虚构缓存范围验收'})).toBe(200);await applicant.close();
 await login(page,'manager');await visit(page,'直属部门审批');await visit(page,'员工档案');
 const employeeRow=page.getByRole('row').filter({hasText:'FIXTURE-EMPLOYEE'});await employeeRow.getByRole('button',{name:'详情 / 历史'}).click();await expect(page.getByRole('heading',{name:'员工详情',exact:true})).toBeVisible();
 const hr=await page.context().newPage();await login(hr,'hr');
 const original=await hr.evaluate(async()=>{const {courseApi}=await import('/src/course-api.ts');const {items}=await courseApi('/employees?q=FIXTURE-EMPLOYEE');return items[0];});
 await hr.evaluate(async(original)=>{const {courseApi,tag}=await import('/src/course-api.ts');const {createDepartment}=await import('/src/api.ts');const dep=await createDepartment({code:'UIUX-SCOPE',name:'[虚构]范围外部门',status:'ACTIVE',parent_id:null});const pos=await courseApi('/positions','POST',{department_id:dep.id,code:'UIUX-SCOPE-P',name:'[虚构]范围外职位',grade_code:'G1',status:'ACTIVE'});await courseApi(`/employees/${original.id}/transfer`,'POST',{department_id:pos.department_id,position_id:pos.id},tag(original));return pos;},original);
 try{await page.bringToFront();// Headless Edge keeps tabs focused; explicitly deliver the recovery event without mocking APIs.
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(page.getByRole('dialog',{name:'员工详情'})).toHaveCount(0);await expect(page.getByRole('row').filter({hasText:'FIXTURE-EMPLOYEE'})).toHaveCount(0);await expect(page.getByRole('heading',{name:'员工详情',exact:true})).toHaveCount(0);
 await visit(page,'直属部门审批');await expect(page.getByRole('row').filter({hasText:'FIXTURE-EMPLOYEE'})).toHaveCount(0);
 expect(await apiStatus(page,`/employees/${original.id}`)).toBe(403);
 }finally{await hr.evaluate(async(original)=>{const {courseApi,tag}=await import('/src/course-api.ts');const row=await courseApi(`/employees/${original.id}`);await courseApi(`/employees/${original.id}/transfer`,'POST',{department_id:original.current_department_id,position_id:original.current_position_id},tag(row));},original);await hr.close();}
});

test('UIUX rule editor blocks unrelated attendance actions and protects draft',async({page})=>{
 await login(page,'hr');await visit(page,'考勤管理');await page.getByRole('button',{name:'配置考勤规则',exact:true}).click();await page.getByLabel('迟到宽限（分钟）').fill('11');
 await page.getByRole('button',{name:'关闭弹窗'}).click();await page.getByRole('dialog',{name:'放弃未保存修改'}).getByRole('button',{name:'继续编辑'}).click();await expect(page.getByLabel('迟到宽限（分钟）')).toHaveValue('11');
 await page.getByRole('button',{name:'关闭弹窗'}).click();await page.getByRole('dialog',{name:'放弃未保存修改'}).getByRole('button',{name:'放弃修改'}).click();
 await expect(page.getByRole('button',{name:'上班打卡',exact:true})).toBeEnabled();
});

test('UIUX multi-role union and revocation clear cached sensitive tabs',async({page,browser})=>{
 // Use a separately authorized fictional account, keeping the real per-account login limiter intact.
 await login(page,'hr');
 const eid=await page.evaluate(async()=>{const {courseApi}=await import('/src/course-api.ts');const {items}=await courseApi('/employees?q=FIXTURE-HR');const original=items[0];return (await courseApi('/employees','POST',{employee_no:'UIUX-MULTI',full_name:'[虚构]多角色测试',current_department_id:original.current_department_id,current_position_id:original.current_position_id,hire_date:original.hire_date,employment_status:'ACTIVE'})).id;});
 const admin=await browser.newPage();await login(admin,'admin');
 await admin.evaluate(async({eid,password})=>{const {courseApi}=await import('/src/course-api.ts');await courseApi('/users','POST',{username:'fixture-uiux-multi',password,employee_id:eid,roles:['HR'],department_ids:[]});},{eid,password:credentials.hr});
 await page.getByRole('button',{name:'账号菜单',exact:true}).click();await page.getByRole('menuitem',{name:'退出登录',exact:true}).click();await login(page,'hr','fixture-uiux-multi');await visit(page,'薪资管理');await visit(page,'员工档案');
 await visit(admin,'用户管理与审计');
 const row=admin.getByRole('row').filter({has:admin.getByRole('cell',{name:'fixture-uiux-multi',exact:true})});
 await row.getByRole('button',{name:'编辑 / 角色 / 停用',exact:true}).click();await admin.getByLabel('系统管理员',{exact:true}).check();await admin.getByRole('button',{name:'保存账号',exact:true}).click();
 await expect(admin.getByRole('status').filter({hasText:'账号已保存'})).toBeVisible();
 await page.bringToFront();await expect(page.getByRole('heading',{name:'登录账号'})).toBeVisible({timeout:10000});
 await expect(page.getByRole('navigation',{name:'已打开的页面'})).toHaveCount(0);
 await login(page,'hr','fixture-uiux-multi');await expect(menu(page).getByRole('link',{name:'用户管理与审计',exact:true})).toBeVisible();await expect(menu(page).getByRole('link',{name:'薪资管理',exact:true})).toBeVisible();
 await visit(page,'薪资管理');await admin.bringToFront();await row.getByRole('button',{name:'编辑 / 角色 / 停用',exact:true}).click();await admin.getByLabel('人事',{exact:true}).uncheck();await admin.getByRole('button',{name:'保存账号',exact:true}).click();
 await expect(admin.getByRole('status').filter({hasText:'账号已保存'})).toBeVisible();await page.bringToFront();await expect(page.getByRole('heading',{name:'登录账号'})).toBeVisible({timeout:10000});
 await login(page,'hr','fixture-uiux-multi');await expect(menu(page).getByRole('link',{name:'薪资管理',exact:true})).toHaveCount(0);expect(await apiStatus(page,'/salaries')).toBe(403);
 await admin.close();
});
