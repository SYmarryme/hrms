import {test,expect,type Page,type Locator} from '@playwright/test';
import {randomBytes} from 'node:crypto';
import {login,visit} from './data-refresh-helpers';

const timeError='下班时间必须晚于上班时间，请重新设置。';
const daysError='请至少选择一个工作日。';
function plusDays(iso:string,days:number){const date=new Date(iso+'T00:00:00Z');date.setUTCDate(date.getUTCDate()+days);return date.toISOString().slice(0,10);}
function chinese(iso:string){const [y,m,d]=iso.split('-');return `${y}年${Number(m)}月${Number(d)}日`;}
async function openRule(page:Page){
 await login(page);await visit(page,'考勤管理');
 const today=await page.evaluate(async()=>{const {courseApi}=await import('/src/course-api.ts');const month=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit'}).format(new Date());return (await courseApi<{today:string}>(`/attendance?month=${month}`)).today;});
 await page.getByRole('button',{name:'配置考勤规则',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'配置考勤规则',exact:true});await expect(dialog).toBeVisible();
 return {dialog,today};
}

test.describe('date-only rule control',()=>{
test.use({timezoneId:'America/Los_Angeles'});
test('rule date shows natural Chinese digits, calendar selection and ISO transport agree without timezone shifts',async({page})=>{
 const {dialog,today}=await openRule(page);const selected=`${Number(today.slice(0,4))+1}-01-02`,input=dialog.getByLabel('生效日期',{exact:true});
 await input.fill(selected);await dialog.getByRole('heading').click();await expect(input).toHaveValue(chinese(selected));
 await dialog.getByRole('button',{name:'选择生效日期',exact:true}).click();const calendar=dialog.getByRole('dialog',{name:'选择生效日期',exact:true});await expect(calendar).toBeVisible();
 await calendar.getByRole('button',{name:chinese(selected),exact:true}).click();await expect(calendar).not.toBeVisible();await expect(input).toHaveValue(chinese(selected));
 // Hide/revalidate the existing modal without losing its selected date or layout.
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect(dialog.getByRole('button',{name:'保存新规则',exact:true})).toBeVisible();await expect(input).toHaveValue(chinese(selected));
 const request=page.waitForRequest(r=>new URL(r.url()).pathname==='/api/v1/attendance/rules'&&r.method()==='POST');
 const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/attendance/rules'&&r.request().method()==='POST');
 await dialog.getByRole('button',{name:'保存新规则',exact:true}).click();expect((await request).postDataJSON().effective_from).toBe(selected);expect((await response).status()).toBe(201);await expect(dialog).not.toBeVisible();
 await page.getByRole('button',{name:'规则历史',exact:true}).click();await expect(page.getByRole('dialog',{name:'考勤规则历史'})).toContainText(selected+' 起');
});
});

test('rule validation shows precise errors, keeps all drafts and rejects invalid saves without a request',async({page})=>{
 const {dialog,today}=await openRule(page);const input=dialog.getByLabel('生效日期',{exact:true}),selected=plusDays(today,4);await input.fill(selected);await dialog.getByRole('heading').click();
 let writes=0;page.on('request',r=>{if(new URL(r.url()).pathname==='/api/v1/attendance/rules'&&r.method()==='POST')writes++;});
 await dialog.getByLabel('上班时间',{exact:true}).fill('14:00');await dialog.getByLabel('下班时间',{exact:true}).fill('06:00');
 for(const end of ['06:00','14:00']){
  await dialog.getByLabel('下班时间',{exact:true}).fill(end);await dialog.getByRole('button',{name:'保存新规则',exact:true}).click();await expect(dialog.getByRole('alert')).toHaveText(timeError);await expect(dialog.getByLabel('上班时间',{exact:true})).toHaveValue('14:00');await expect(input).toHaveValue(chinese(selected));
 }
 for(const checkbox of await dialog.getByRole('checkbox').all())await checkbox.uncheck();
 await dialog.getByRole('button',{name:'保存新规则',exact:true}).click();await expect(dialog.getByRole('alert')).toHaveText(daysError);
 await dialog.getByLabel('上班时间',{exact:true}).fill('09:00');await dialog.getByLabel('下班时间',{exact:true}).fill('18:00');await dialog.getByRole('button',{name:'保存新规则',exact:true}).click();await expect(dialog.getByRole('alert')).toHaveText(daysError);expect(writes).toBe(0);
 await dialog.getByRole('checkbox',{name:'周一',exact:true}).check();const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/attendance/rules'&&r.request().method()==='POST');await dialog.getByRole('button',{name:'保存新规则',exact:true}).click();expect((await response).status()).toBe(201);await expect(dialog).not.toBeVisible();expect(writes).toBe(1);
});

test('direct backend validation is shown inside the rule dialog and unrelated errors keep their wording',async({page})=>{
 const {dialog,today}=await openRule(page);const input=dialog.getByLabel('生效日期',{exact:true}),selected=plusDays(today,6);await input.fill(selected);
 // Send the actual request to FastAPI with invalid values, bypassing client validation.
 for(const [patch,message] of [
  [{start_time:'14:00',end_time:'06:00'},timeError],
  [{weekdays:[]},daysError],
  [{grace_minutes:121},'输入或查询参数不正确，请核对字段与长度'],
  [{effective_from:today},'考勤规则只能从明天或以后生效，不能改写历史打卡。'],
 ] as const){
  await page.route('**/api/v1/attendance/rules',async route=>{if(route.request().method()==='POST')await route.continue({postData:JSON.stringify({...route.request().postDataJSON(),...patch})});else await route.continue();},{times:1});
  await dialog.getByRole('button',{name:'保存新规则',exact:true}).click();await expect(dialog.getByRole('alert')).toHaveText(message);await expect(dialog).toBeVisible();await expect(input).toHaveValue(chinese(selected));
 }
});

async function nativeRevealDisplays(page:Page,input:Locator){
 const session=await page.context().newCDPSession(page);
 try{
  await session.send('DOM.enable');await session.send('CSS.enable');
  type NativeNode={nodeId:number;attributes?:string[];children?:NativeNode[];shadowRoots?:NativeNode[]};
  const id=await input.getAttribute('id');const {root}=await session.send('DOM.getDocument',{depth:-1,pierce:true});
  function find(current:NativeNode):NativeNode|undefined{const attrs=current.attributes||[];if(attrs.some((a,i)=>i%2===0&&a==='id'&&attrs[i+1]===id))return current;for(const child of [...(current.children||[]),...(current.shadowRoots||[])]){const found=find(child);if(found)return found;}}
  const node=find(root);expect(node).toBeDefined();
  const reveal:number[]=[];function visitNode(current:NativeNode){const attrs=current.attributes||[];if(attrs.some((a,i)=>i%2===0&&a==='pseudo'&&attrs[i+1]==='-ms-reveal'))reveal.push(current.nodeId);for(const child of [...(current.children||[]),...(current.shadowRoots||[])])visitNode(child);}
  visitNode(node!);expect(reveal.length).toBeGreaterThan(0);
  return await Promise.all(reveal.map(async nodeId=>(await session.send('CSS.getComputedStyleForNode',{nodeId})).computedStyle.find(style=>style.name==='display')?.value));
 }finally{await session.detach();}
}
async function singleReveal(page:Page,control:Locator){
 const input=control.locator('input'),button=control.getByRole('button'),sample=randomBytes(20).toString('base64url');
 try{
 await input.focus();await input.pressSequentially(sample);
 // Inspect actual Edge's UA shadow node: getComputedStyle(input,'::-ms-reveal')
 // returns an empty result even when the native button is visible.
 expect(await nativeRevealDisplays(page,input)).toEqual(['none']);
 await expect(button).toHaveCount(1);await expect(button).toBeVisible();await expect(input).toHaveAttribute('type','password');
 const geometry=await input.boundingBox();
 for(const phase of ['typing','blurred','refocused']){
  if(phase==='blurred')await button.focus();if(phase==='refocused')await input.focus();
  await button.click();await expect(input).toHaveAttribute('type','text');expect(await input.evaluate((el,value)=>(el as HTMLInputElement).value===value,sample)).toBe(true);
  await button.press('Space');await expect(input).toHaveAttribute('type','password');expect(await input.evaluate((el,value)=>(el as HTMLInputElement).value===value,sample)).toBe(true);
  expect(await nativeRevealDisplays(page,input)).toEqual(['none']);
  expect(await input.boundingBox()).toEqual(geometry);
 }
 }finally{
  // An assertion failure must not leave a visible test password in diagnostic artifacts.
  await input.fill('');if(await input.getAttribute('type')==='text')await button.click();
 }
}

test('installed Edge login and daily password controls suppress native reveal through focus and typing states',async({page})=>{
 expect(await page.evaluate(()=>navigator.userAgent.includes('Edg/'))).toBe(true);
 await page.goto('/login');await singleReveal(page,page.locator('.password-control'));
 await login(page,'employee');await page.getByRole('button',{name:'账号菜单',exact:true}).click();await page.getByRole('menuitem',{name:'设置',exact:true}).click();await page.getByRole('button',{name:'账号安全',exact:true}).click();
 for(const control of await page.locator('.password-field-control').all())await singleReveal(page,control);
});

test('installed Edge first-login and reset force-change controls each retain exactly one custom reveal',async({page,browser})=>{
 await login(page,'admin');const temporary=randomBytes(24).toString('base64url');
 const id=await page.evaluate(async password=>{const {courseApi}=await import('/src/course-api.ts');return (await courseApi<{id:string}>('/users','POST',{username:'fixture-eye-check',password,employee_id:null,roles:['ADMIN'],department_ids:[]})).id;},temporary);
 const user=await browser.newPage();await user.goto('/login');
 async function enter(){await user.getByLabel('账号',{exact:true}).fill('fixture-eye-check');await user.getByLabel('密码',{exact:true}).fill(temporary);await user.getByRole('button',{name:'登录',exact:true}).click();await expect(user.getByRole('dialog',{name:'首次登录 · 请修改密码'})).toBeVisible();}
 await enter();for(const control of await user.locator('.password-field-control').all())await singleReveal(user,control);
 await user.getByRole('button',{name:'退出登录',exact:true}).click();
 await page.evaluate(async({id,password})=>{const {courseApi}=await import('/src/course-api.ts');await courseApi(`/users/${id}/password`,'POST',{password},'"v1"');},{id,password:temporary});
 await enter();for(const control of await user.locator('.password-field-control').all())await singleReveal(user,control);await user.close();
});
