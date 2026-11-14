// Free browser contract for folder authorship choices; no Core/models/live library.
import {build} from 'esbuild';
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdirSync, existsSync} from 'node:fs';
import {resolve, sep} from 'node:path';

const output=resolve(process.argv[2]);
assert.ok(output.toLowerCase().startsWith(resolve('G:/Libraries/_qa').toLowerCase()+sep));
assert.ok(!existsSync(output)); mkdirSync(output,{recursive:true});
const bundle=await build({entryPoints:['src/folders.ts'],bundle:true,write:false,format:'iife',globalName:'FolderPanel'});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try {
  const page=await browser.newPage();
  await page.setContent('<main id="fixture"></main>');
  await page.addScriptTag({content:bundle.outputFiles[0].text});
  await page.evaluate(async()=>{
    window.fixtureApi={get:async()=>({enabled:true,cards:[{id:'fixture',path:'data',status:'staged',
      source_root:'G:/Libraries/_qa/synthetic',bytes:10,file_counts:{'.txt':1},reasons:['Synthetic fixture'],
      suggested_purpose:'data',suggested_graph:'fixture',description:{text:'Synthetic data',state:'awaiting_model_draft'},
      folder_fingerprint:'fixture'}]}),post:async(path,body)=>{window.submitted=body;return {};}};
    await FolderPanel.folderReview(window.fixtureApi,document.querySelector('main'));
  });
  const author=page.getByLabel('Authorship',{exact:true});
  await author.waitFor({timeout:3000});
  assert.equal(await author.inputValue(),''); // ambiguous purposes have no default
  await page.getByLabel('Purpose',{exact:true}).selectOption('third-party');
  assert.equal(await author.inputValue(),'third_party');
  assert.equal(await author.isDisabled(),true);
  await page.getByLabel('Purpose',{exact:true}).selectOption('data');
  assert.equal(await author.inputValue(),'');
  assert.equal(await author.isDisabled(),false);
  await author.selectOption('generated');
  await page.getByRole('button',{name:'Accept folder decision',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.submitted.authorship),'generated');
  await page.screenshot({path:resolve(output,'authorship-choice.png'),fullPage:true});
  console.log('PASS: purpose derivation, no data default, explicit authorship submission.');
} finally { await browser.close(); }
