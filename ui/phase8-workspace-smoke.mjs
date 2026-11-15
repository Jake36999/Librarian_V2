import { build } from 'esbuild';
import { chromium } from 'playwright-core';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
const out=process.env.LIBRARIAN_PHASE8_QA;
if (!out || existsSync(out)) throw new Error('Use a fresh explicit LIBRARIAN_PHASE8_QA directory');
mkdirSync(out,{recursive:true});
await build({entryPoints:['src/pane.ts'],bundle:true,format:'iife',globalName:'Pane',outfile:path.join(out,'pane.js')});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage();
 await page.setContent('<main></main>');
 await page.addScriptTag({path:path.join(out,'pane.js')});
 await page.evaluate(async()=>{
   const api={get:async()=>({path:'workspace:owned/Guide.md',name:'Owned guide',text:'# Guide\n\nRead-only source.',read_only:true}),tool:async()=>({})};
   window.pane=new Pane.DocPane(api,document.createElement('section'),()=> 'Fixture',()=>{});
   document.querySelector('main').append(window.pane.el);
   await window.pane.open('workspace:owned/Guide.md');
 });
 const assert=(value,message)=>{if(!value)throw new Error(message);};
 assert(await page.getByText('Read-only attached document',{exact:true}).count()===1,'Person sees the read-only classification');
 await page.getByRole('button',{name:'Note actions'}).click();
 assert(await page.getByRole('menuitem',{name:/Rename or move/}).count()===0,'No rename/move affordance for attached source');
 assert(await page.getByRole('menuitem',{name:/Open this note in Obsidian/}).count()===0,'External source is not presented as a vault note');
 assert(await page.getByRole('menuitem',{name:/Copy path/}).count()===1,'The source remains navigable');
 await page.screenshot({path:path.join(out,'workspace.png'),fullPage:true});
 writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:4,model_calls:0},null,2));
 console.log('4 read-only workspace browser checks passed; zero model calls');
} finally {await browser.close();}
