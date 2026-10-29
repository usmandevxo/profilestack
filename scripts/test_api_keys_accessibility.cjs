const {chromium}=require('/www/wwwroot/hermes-design-intelligence/node_modules/playwright');
const AxeBuilder=require('/www/wwwroot/hermes-design-intelligence/node_modules/@axe-core/playwright').default;
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const {token}=JSON.parse(fs.readFileSync(path.join(process.env.TMPDIR,'profilestack-ui-session.json')));
 const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||'/home/ubuntu/.cache/ms-playwright/chromium-1248/chrome-linux-arm64/chrome'});
 const context=await browser.newContext({viewport:{width:375,height:800},reducedMotion:'reduce'});
 await context.addCookies([{name:'ps_session',value:token,url:'https://profilestack.apanel.eu.cc',httpOnly:true,secure:true}]);
 const page=await context.newPage();await page.goto('https://profilestack.apanel.eu.cc/api-keys');await page.waitForFunction(()=>document.querySelector('#ak-active-count').textContent!=='—');
 let violations=(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations;
 await page.locator('#ak-create').click();
 for(let i=0;i<8;i++){await page.keyboard.press('Tab');assert(await page.evaluate(()=>document.querySelector('#ak-create-dialog').contains(document.activeElement)));}
 violations.push(...(await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations);
 await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>document.activeElement.id),'ak-create');
 await page.evaluate(()=>document.documentElement.style.fontSize='200%');
 assert.equal(await page.evaluate(()=>Math.max(0,document.documentElement.scrollWidth-document.documentElement.clientWidth)),0);
 await page.setViewportSize({width:768,height:375});await page.locator('#ak-create').click();await page.locator('#ak-create-submit').scrollIntoViewIfNeeded();assert(await page.locator('#ak-create-submit').isVisible());await page.keyboard.press('Escape');
 // Exercise loading failure and retry without persisting fabricated data.
 await page.route('**/api/api-keys',route=>route.abort());await page.locator('#ak-refresh').click();await page.locator('#ak-load-error').waitFor({state:'visible'});
 await page.unroute('**/api/api-keys');await page.locator('#ak-retry').click();await page.waitForFunction(()=>document.querySelector('#ak-load-error').hidden);
 const report={violations:violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>n.target)})),assertions:[{name:'Dialog keyboard focus contained and restored',passed:true},{name:'200% text no document overflow',passed:true},{name:'Short landscape dialog actions reachable',passed:true},{name:'Load failure and retry verified',passed:true},{name:'Reduced motion enabled',passed:true}]};
 fs.writeFileSync('.design/evidence/accessibility.json',JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify(report));assert.equal(violations.length,0,'Accessibility violations detected');
})().catch(e=>{console.error(e.message);process.exit(1)});
