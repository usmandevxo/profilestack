const {chromium}=require('/www/wwwroot/hermes-design-intelligence/node_modules/playwright');
const fs=require('fs'), path=require('path'), assert=require('assert');
(async()=>{
 const base='https://profilestack.rerouter.online';
 const {token}=JSON.parse(fs.readFileSync(path.join(process.env.TMPDIR,'profilestack-ui-session.json')));
 const browser=await chromium.launch({headless:true,executablePath:'/home/ubuntu/.cache/ms-playwright/chromium-1248/chrome-linux-arm64/chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addCookies([{name:'ps_session',value:token,url:base,httpOnly:true,secure:true,sameSite:'Lax'}]);
 const page=await context.newPage(), errors=[];page.on('pageerror',e=>errors.push(e.message));
 let id;
 try {
  await page.goto(base+'/api-keys');await page.waitForFunction(()=>!document.querySelector('#ak-create').disabled);
  await page.locator('#ak-create').click();const editor=page.locator('#ak-create-access');
  assert.equal(await editor.locator('input[type=checkbox]:checked').count(),3);
  assert(await editor.getByRole('radio',{name:'Selected profiles',exact:true}).isChecked());
  await editor.locator('input[value="profiles.create"]').check();
  const profiles=editor.locator('.ak-profile-list input');assert(await profiles.count()>0);await profiles.first().check();
  const name='Permission UI verification '+Date.now();await page.locator('#ak-create-name').fill(name);
  await page.locator('#ak-create-submit').click();await page.locator('#ak-secret-dialog').waitFor({state:'visible'});
  await page.locator('#ak-secret-dialog [data-dismiss]').click();
  let list=await (await context.request.get(base+'/api/api-keys')).json();let key=list.keys.find(k=>k.name===name);assert(key);id=key.id;
  assert(key.permissions.includes('profiles.create'));assert.equal(key.profile_access,'selected');assert.equal(key.profiles.length,1);
  const open=async()=>{await page.locator('#ak-rows tr').filter({hasText:name}).getByRole('button',{name:'Edit access '+name,exact:true}).click();};
  await open();let edit=page.locator('#ak-edit-access');
  await edit.getByRole('button',{name:'Full permission preset',exact:true}).click();
  assert(await edit.getByRole('radio',{name:'All profiles',exact:true}).isChecked());
  await page.locator('#ak-access-submit').click();await page.waitForFunction(()=>!document.querySelector('#ak-access-dialog').open);
  key=(await (await context.request.get(base+'/api/api-keys')).json()).keys.find(k=>k.id===id);assert.equal(key.permissions.length,14);assert.equal(key.profile_access,'all');
  await page.waitForFunction(()=>!document.querySelector('#ak-refresh').disabled);await open();edit=page.locator('#ak-edit-access');
  await edit.getByRole('button',{name:'Read-only permission preset',exact:true}).click();
  await edit.getByRole('radio',{name:'Specific group / folder',exact:true}).check();
  assert(await edit.locator('.ak-group-section').isVisible());
  const marketChoice = edit.locator('.ak-group-section input[value="marketplaces"]');
  if (await marketChoice.count() > 0) {
    await marketChoice.check();
  }
  await page.locator('#ak-access-submit').click();await page.waitForFunction(()=>!document.querySelector('#ak-access-dialog').open);
  key=(await (await context.request.get(base+'/api/api-keys')).json()).keys.find(k=>k.id===id);
  assert.equal(key.profile_access,'group');
  if (await marketChoice.count() > 0) {
    assert(key.folders.includes('marketplaces'));
  }
  await page.waitForFunction(()=>!document.querySelector('#ak-refresh').disabled);await open();edit=page.locator('#ak-edit-access');
  await edit.getByRole('radio',{name:'Selected profiles',exact:true}).check();
  assert(await edit.locator('input[value="profiles.create"]').isChecked()===false);
  assert(await edit.locator('input[value="system.read"]').isDisabled());
  await edit.getByRole('searchbox',{name:'Search profiles'}).fill('no-matching-profile-for-verification');
  assert(await edit.getByText('No profiles match your search.',{exact:true}).isVisible());
  await edit.getByRole('searchbox',{name:'Search profiles'}).fill('');
  for(const width of [320,375,768,1440]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth),0);
   assert.equal(await page.locator('#ak-access-dialog').evaluate(e=>e.scrollWidth-e.clientWidth),0);
   await page.screenshot({path:'.design/evidence/permissions-'+width+'.png',fullPage:true});
  }
  await page.locator('#ak-access-submit').click();await page.waitForFunction(()=>!document.querySelector('#ak-access-dialog').open);
  key=(await (await context.request.get(base+'/api/api-keys')).json()).keys.find(k=>k.id===id);assert(!key.permissions.includes('profiles.create'));assert.equal(key.profile_access,'selected');
  assert.deepEqual(errors,[]);
  console.log('Live create/select/edit/full/read-only permission persistence, search, global restrictions and 4 dialog widths passed.');
 } finally {
  if(id){await context.request.delete(base+'/api/api-keys/'+id,{headers:{'X-ProfileStack-Management':'1'}});const list=await (await context.request.get(base+'/api/api-keys')).json();assert.equal(list.keys.find(k=>k.id===id).status,'revoked');}
  await browser.close();
 }
})().catch(e=>{console.error(e.message);process.exit(1)});
