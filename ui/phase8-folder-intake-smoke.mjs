import {build} from 'esbuild';
import {chromium} from 'playwright-core';
import {existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import path from 'node:path';
const out=process.env.LIBRARIAN_PHASE8_QA;
if(!out||existsSync(out))throw Error('Use a fresh LIBRARIAN_PHASE8_QA directory');
mkdirSync(out,{recursive:true});
const entry=process.env.FOLDER_INTAKE_BASELINE
 ? {stdin:{contents:readFileSync(process.env.FOLDER_INTAKE_BASELINE,'utf8'),resolveDir:path.resolve('src'),sourcefile:'folders.ts',loader:'ts'}}
 : {entryPoints:['src/folders.ts']};
await build({...entry,bundle:true,format:'iife',globalName:'Folders',outfile:path.join(out,'folders.js')});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage();await page.setContent('<main></main>');await page.addScriptTag({path:path.join(out,'folders.js')});
 await page.evaluate(async()=>{
   window.calls=[];const card={id:'folder-test',path:'src',source_root:'fixture',status:'staged',bytes:12,file_counts:{'.py':1},
    suggested_purpose:'own-current',suggested_graph:'code',reasons:['fixture'],description:{state:'awaiting_model_draft',text:''}};
   const api={get:async()=>({enabled:true,drafting_available:false,cards:[card],credential_refusals:{count:0,paths:[]}}),
    post:async(url,body)=>{window.calls.push({url,body});return{};}};
   await Folders.folderReview(api,document.querySelector('main'));
 });
 const assert=(ok,msg)=>{if(!ok)throw Error(msg);};
 await page.getByText('Optional model draft',{exact:true}).click();
 assert(await page.getByRole('button',{name:'Draft from inventory metadata',exact:true}).isDisabled(),'Production drafting disabled');
 assert((await page.locator('main').innerText()).includes('content not examined'),'No inferred reading coverage');
 await page.getByLabel('Include src in processing batch').check();
 await page.getByRole('button',{name:'Approve selected for processing',exact:true}).click();
 const calls=await page.evaluate(()=>window.calls);
 assert(calls.length===1&&calls[0].url==='/api/folders/approve-batch','One native batch approval');
 assert(calls[0].body.items.join(',')==='folder-test','Exact selected set');
 await page.screenshot({path:path.join(out,'folder-intake.png'),fullPage:true});
 writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:4,model_calls:0},null,2));
 console.log('4 folder intake browser checks passed; zero models');
} finally {await browser.close();}
