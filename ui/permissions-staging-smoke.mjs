import {build} from 'esbuild';
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdirSync} from 'node:fs';
const out=process.env.QA_OUT;mkdirSync(out,{recursive:true});
await build({entryPoints:['src/settings.ts','src/views.ts'],bundle:true,format:'esm',outdir:out});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
 const page=await browser.newPage();await page.goto('file:///'+out.replaceAll('\\','/')+'/blank.html').catch(()=>{});
 // Inject bundled modules without a file-origin module fetch.
 await build({entryPoints:['src/settings.ts'],bundle:true,format:'iife',globalName:'Config',outfile:out+'/config.js'});
 await page.setContent('<main></main>');await page.addScriptTag({path:out+'/config.js'});
 await page.evaluate(()=>{window.writes=[];const api={get:async()=>({tool_settings:{intake_run:'ask'}}),post:async(u,b)=>{window.writes.push({u,b});return{tool_settings:{intake_run:b.setting}};}};
 const s=new Config.Settings(api,()=>({vault:'Fixture'}),async()=>{});document.body.append(s.dialog);s.open();});
 await page.getByRole('button',{name:'Permissions',exact:true}).click({timeout:2000});
 await page.getByLabel('Permission for intake_run').selectOption('allow');
 assert.equal(await page.getByRole('status').last().innerText(),'Saved for this library.');
 assert.deepEqual(await page.evaluate(()=>window.writes),[{u:'/api/tool-setting',b:{tool:'intake_run',setting:'allow'}}]);
 console.log('PASS: Permissions page saves only the selected tool');
}finally{await browser.close();}
