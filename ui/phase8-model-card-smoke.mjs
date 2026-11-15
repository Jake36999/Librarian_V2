import { build } from 'esbuild';
import { chromium } from 'playwright-core';
import { existsSync,mkdirSync,writeFileSync } from 'node:fs';
import path from 'node:path';
const out=process.env.LIBRARIAN_PHASE8_QA;
if(!out||existsSync(out))throw new Error('Use a fresh LIBRARIAN_PHASE8_QA directory');
mkdirSync(out,{recursive:true});
await build({entryPoints:['src/panels.ts'],bundle:true,format:'iife',globalName:'Panels',outfile:path.join(out,'panels.js')});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage();await page.setContent('<main></main>');
 await page.addScriptTag({path:path.join(out,'panels.js')});
 await page.evaluate(async()=>{
   const trigger=document.createElement('button');document.querySelector('main').append(trigger);
   const pop=new Panels.Popover('models','Models',trigger);document.querySelector('main').append(pop.el);pop.show(true);
   window.bindingWrites=0;
   const api={get:async url=>url.includes('provider=deepinfra')?{status:'ready',models:[{id:'example/model',profile:{
     suggested_tier:'Tier_1',task_class:'Sub_Agent',context_length:131072,tool_calling:true,
     field_authorship:{task_class:'owner_created',context_length:'owner_created'}}}]}:{status:'offline',models:[]},
     post:async()=>{window.bindingWrites++;return{};}};
   const tile=new Panels.ModelTile(pop,api,()=>[],()=>({deepinfra:true}));await tile.refresh();
 });
 const card=page.locator('.lib-model-card').first(); const text=await card.innerText();
 const assert=(ok,message)=>{if(!ok)throw new Error(message);};
 assert(text.includes('Owner class: Sub Agent'),'Owner class is visible in the real picker tile');
 assert(text.includes('Tier 1'),'Unapproved class-to-tier mapping is not applied');
 assert(text.includes('131k ctx'),'Owner context metadata is shown');
 assert(await page.evaluate(()=>window.bindingWrites)===0,'Reading metadata does not change a binding');
 await page.screenshot({path:path.join(out,'models.png'),fullPage:true});
 writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:4,model_calls:0,binding_changes:0},null,2));
 console.log('4 model-card picker checks passed; zero model calls/binding changes');
} finally {await browser.close();}
