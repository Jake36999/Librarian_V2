// Free component acceptance; production/Core end-to-end follows at S6.
import { build } from 'esbuild';
import { chromium } from 'playwright-core';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
const out = process.env.LIBRARIAN_PHASE8_QA;
if (!out || existsSync(out)) throw new Error('Use a fresh explicit LIBRARIAN_PHASE8_QA output directory');
mkdirSync(out, {recursive:true});
await build({entryPoints:['src/catalogue.ts'],bundle:true,format:'iife',globalName:'Catalogue',outfile:path.join(out,'component.js')});
const executablePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const browser = await chromium.launch({executablePath,headless:true});
try {
  const page = await browser.newPage();
  await page.setContent('<main></main>');
  await page.addScriptTag({path:path.join(out,'component.js')});
  await page.evaluate(() => {
    window.originalRequests=[];
    document.querySelector('main').append(Catalogue.renderCatalogue({when_relevant:'Compare mechanisms.',
      use_rollup:{log_use_count:2,application_count:1,recent_uses:[{used_for:'A recorded use.'}],applications:[]},
      original:{available:true,download_source:'Target',name:'original.pdf'},
      chapters:[{title:'Method',locator:'pp. 2-3',status:'observed',coverage:'full',summary:['<img src=x onerror=alert(1)>']},
        {title:'Appendix',locator:'pp. 4-5',status:'not examined',coverage:'not opened',summary:[]}]
    }, async source => window.originalRequests.push(source)));
  });
  const assert = (value, message) => {if (!value) throw new Error(message);};
  assert(await page.locator('details').count()===2,'Each chapter is expandable');
  assert(await page.locator('details[open]').count()===0,'Chapters start collapsed');
  await page.locator('details summary').first().click();
  assert(await page.locator('details[open]').count()===1,'A person can expand a chapter');
  assert(await page.locator('img').count()===0,'Source summary text is not executable HTML');
  await page.getByRole('button',{name:'Open original'}).click();
  assert((await page.evaluate(()=>window.originalRequests)).join()==='Target','Original request uses the catalogue source');
  await page.locator('details summary').nth(1).click();
  assert((await page.locator('details').nth(1).innerText()).includes('Not examined'),'Unread chapters remain explicit');
  await page.screenshot({path:path.join(out,'catalogue.png'),fullPage:true});
  writeFileSync(path.join(out,'result.json'),JSON.stringify({passed:7,model_calls:0},null,2));
  console.log('7 catalogue browser checks passed; zero model calls');
} finally {await browser.close();}
