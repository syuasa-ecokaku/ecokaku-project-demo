"""Contract-only operations preserve cases, equipment, operational records and dashboard classification."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture,inner
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-maintenance-contract-review')
INJECT="""
let mcClock='2026-11-06';maintenanceToday=()=>mcClock;
const fixtureP=batteryCaseMap['P-00001'];
if(!fixtureP.mcFixtureReady){const c=fixtureP.contracts.find(c=>c.kind==='保守契約');Object.assign(c,{name:'架空P保守契約',party:'架空P契約先',state:'未締結',signedDate:'',startDate:'2026-11-20',endDate:'2026-12-31',files:['既存P資料.pdf'],autoRenew:false});fixtureP.mcFixtureReady=true;}
if(!lifecycleSources().some(s=>s.baseNumber==='M-00001')){
 const s=lifecycleNewSource({name:'架空M保守案件',prefecture:'架空県',city:'架空市',street:'',business:'battery',owner:'保守デモ担当A',memo:'',broker:'',files:[]},'M-00001');s.maintenanceOnly=true;s.maintenance={route:'standalone',intakeType:'メンテナンス単独受託',intakeState:'accepted',caseState:'管理中',customerParty:'架空M契約先',equipmentOwner:'架空設備所有者',startDate:'2026-11-01',events:[]};s.assets=[{id:'asset-m-test',caseId:s.internalId,name:'架空設備',model:'デモ型式'}];s.records={inspections:[{id:'inspection-before-contract',caseId:s.internalId,memo:'既存点検記録'}],incidents:[{id:'incident-before-contract',caseId:s.internalId,memo:'既存対応記録'}]};s.contracts=[{id:'contract-m-test',caseId:s.internalId,purpose:'maintenance',kind:'保守契約',name:'架空M保守契約',party:'架空M契約先',state:'未締結',signedDate:'',startDate:'2026-11-20',endDate:'2026-12-31',amount:100000,autoRenew:false,number:'DEMO-M-CONTRACT',files:['既存M資料.pdf']}];lifecycleInsert(s);noticeCenter.registerCase('battery',s);maintenanceEnsure(s);
}
window.__mc={sources:lifecycleSources,open:maintenanceOpen,contracts:maintenanceContracts,status:maintenanceContractStatus,current:maintenanceCurrentContract,listStatus:maintenanceCaseContractStatus,endNote:maintenanceContractEndNote,home:homeProjection,clock:d=>{mcClock=d;},snapshot:lifecycleSnapshot,render:()=>departmentRender('maintenance'),operate:maintenanceOpenContractOperation};
"""
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[]
 raw=(ROOT/'index.html').read_text();s=inner(raw)
 # Contract-operation regression: preserve global classification; work-record operations are verified separately.
 import subprocess
 baseline=inner(subprocess.check_output(['git','show','5192e9a:index.html'],cwd=ROOT,text=True))
 for name in ['homeProjection','homePrimary','homeDepartmentInfo']:
  token='function '+name+'(';assert s.split(token,1)[1].split('\n',1)[0]==baseline.split(token,1)[1].split('\n',1)[0],name
 body=fixture(raw,INJECT)
 def done(v):passed.append(v);print('PASS',v,flush=True)
 with server() as url,sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=browser.new_page(viewport={'width':1540,'height':1200},timezone_id='Asia/Tokyo');p.route(url,lambda r:r.fulfill(body=body,content_type='text/html'));p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');m=f.locator('#maintenance-workspace');dialog=f.locator('#case-lifecycle-dialog')
  def api(v):return p.frames[1].evaluate(v)
  def source(no):return '__mc.sources().find(s=>(s.baseNumber||s.id)==='+json.dumps(no)+')'
  def case(no):return api('()=>'+source(no))
  def contracts(no):return api('()=>__mc.contracts('+source(no)+')')
  def active(no):return api('()=>__mc.current('+source(no)+')')
  def open(no):api('()=>__mc.open('+source(no)+')')
  def clock(day):api('()=>__mc.clock('+json.dumps(day)+')')
  def wait():expect(f.locator('.lc-busy')).to_be_hidden()
  def submit():dialog.locator('#lc-submit').click();wait()
  def close():dialog.locator('[data-lc-close]').first.click()
  def item(cid):
   loc=m.locator('[data-contract-id="'+cid+'"]');loc.locator(':scope > summary').click() if loc.get_attribute('open') is None else None;return loc
  def operation(no,cid,kind):open(no);item(cid).locator('[data-mc-operation='+kind+']').click()
  def fixed(no):
   c=case(no);return {k:c.get(k) for k in ['id','internalId','baseNumber','formalNumber','revision','phase','assets','records']}|{'caseState':c['maintenance']['caseState']}
  originals={n:fixed(n) for n in ['P-00001','M-00001']};initial_count=api('()=>__mc.snapshot().cases.length');home_ids=api('()=>__mc.home().active.map(r=>r.source.internalId)');ids={n:contracts(n)[0]['id'] for n in originals}
  for no in originals:
   cid=ids[no];before=contracts(no)[0];operation(no,cid,'edit');assert f.locator('#lc-mt-party').input_value()==before['party'];assert f.locator('#lc-mt-name').input_value()==before['name'];f.locator('#lc-mt-name').fill(before['name']+'修正');close();assert contracts(no)[0]==before
   operation(no,cid,'edit');f.locator('#lc-mt-name').fill(before['name']+'修正');f.locator('#lc-files').set_input_files({'name':'追加資料.pdf','mimeType':'application/pdf','buffer':b'demo'});submit();c=contracts(no)[0];assert c['id']==cid and c['caseId']==case(no)['internalId'];assert len(contracts(no))==1 and set(c['files'])==set(before['files']+['追加資料.pdf']);assert c['state']=='未締結';assert c['operationHistory'][0]['before']['name']==before['name'];assert c['operationHistory'][0]['after']['name']==c['name']
  done('P/M editing updates the same contract and case IDs, preloads values, appends filenames, records before/after and leaves cancellation untouched')
  for no in originals:
   cid=ids[no];operation(no,cid,'sign');f.locator('#lc-mt-signedDate').fill('');submit();assert '契約締結日' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-signedDate').fill('2026-11-07');submit();assert '未来' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-signedDate').fill('2026-11-06');p.screenshot(path=str(OUT/'sign-confirmation.png'));f.locator('#lc-submit').evaluate('(b)=>{b.click();b.click()}');wait();assert contracts(no)[0]['id']==cid and len(contracts(no))==1;assert contracts(no)[0]['state']=='締結済み';assert len(contracts(no)[0]['operationHistory'])==2;assert api('()=>__mc.status(__mc.contracts('+source(no)+')[0])')=='開始前';assert active(no) is None;open(no);assert '現在有効な契約はありません（開始前）' in m.locator('[data-contract-current]').inner_text();assert not item(cid).locator('[data-mc-operation=sign]').count()
  clock('2026-11-20')
  for no in originals:assert active(no)['id']==ids[no]
  done('signature requires a real non-future date; double-click cannot sign twice; future starts remain inactive and become current only on their start day')
  for no in originals:
   cid=ids[no];operation(no,cid,'edit');assert not f.locator('#mt-contractState').count();assert f.locator('#lc-mc-state').get_attribute('readonly') is not None;f.locator('#lc-mt-amount').fill('123456');submit();assert '修正理由' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-reason').fill('契約金額の誤記修正（デモ）');f.locator('#lc-mt-amount').fill('-1');submit();assert '整数' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-amount').fill('123456');p.screenshot(path=str(OUT/'edit-signed-contract.png'));submit();assert contracts(no)[0]['amount']==123456;assert contracts(no)[0]['state']=='締結済み';assert contracts(no)[0]['operationHistory'][0]['reason']=='契約金額の誤記修正（デモ）'
  done('signed edits require a reason and valid amount; normal editing cannot alter signature/end state and preserves the operation audit')
  for no in originals:
   cid=ids[no];operation(no,cid,'end');f.locator('#lc-mt-terminationDate').fill('2026-11-19');f.locator('#lc-mt-endReason').fill('設備保守契約の見直し（デモ）');submit();assert '開始日以降' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-terminationDate').fill('2027-01-01');submit();assert '終了日以前' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-terminationDate').fill('2026-11-30');p.screenshot(path=str(OUT/'end-schedule.png'));f.locator('#lc-submit').evaluate('(b)=>{b.click();b.click()}');wait();assert contracts(no)[0]['endDate']=='2026-12-31';assert contracts(no)[0]['startDate']=='2026-11-20';assert contracts(no)[0]['termination']['endDate']=='2026-11-30';assert active(no)['id']==cid
   operation(no,cid,'end-edit');f.locator('#lc-mt-terminationDate').fill('2026-12-15');submit();assert '修正理由' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-reason').fill('引継ぎ日程を調整（デモ）');submit();assert contracts(no)[0]['termination']['endDate']=='2026-12-15';assert contracts(no)[0]['operationHistory'][0]['before']['termination']['endDate']=='2026-11-30';assert contracts(no)[0]['operationHistory'][0]['after']['termination']['endDate']=='2026-12-15'
  operation('P-00001',ids['P-00001'],'end-edit');f.locator('#mt-endType').select_option('expiry');f.locator('#lc-mt-endReason').fill('期間満了（デモ）');f.locator('#lc-mt-reason').fill('満了で終了する方針に変更');f.locator('#lc-mt-terminationDate').fill('2026-12-15');submit();assert '一致' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-terminationDate').fill('2026-12-31');submit();assert contracts('P-00001')[0]['termination']['type']=='expiry'
  done('early termination and expiry preserve original periods; schedule revision requires reasons and records old/new dates; invalid boundaries and mismatched expiry are blocked')
  for no,new_start,new_end in [('M-00001','2026-12-16','2027-01-31'),('P-00001','2027-01-01','2027-02-28')]:
   cid=ids[no];old=contracts(no)[0];open(no);item(cid).locator('[data-maint-renew]').click();f.locator('#lc-mt-name').fill(no+'更新契約');f.locator('#lc-mt-startDate').fill(new_start);f.locator('#lc-mt-endDate').fill(new_end);submit();cs=contracts(no);assert len(cs)==2 and cs[0]==old and cs[1]['previousContractId']==cid;assert active(no)['id']==cid;newid=cs[1]['id'];operation(no,newid,'sign');f.locator('#lc-mt-signedDate').fill('2026-11-20');submit();assert active(no)['id']==cid;assert api('()=>__mc.status(__mc.contracts('+source(no)+')[1])')=='開始前'
  clock('2026-12-15');assert active('M-00001')['id']==ids['M-00001'];clock('2026-12-16');assert active('M-00001')['id']==contracts('M-00001')[1]['id'];open('M-00001');closed=item(ids['M-00001']);assert '終了' in closed.inner_text();assert not closed.locator('[data-mc-operation]').count();assert closed.locator('[data-maint-renew]').count()==1
  clock('2026-12-31');assert active('P-00001')['id']==ids['P-00001'];clock('2027-01-01');assert active('P-00001')['id']==contracts('P-00001')[1]['id']
  done('end day is inclusive, the next day closes the old contract; renewals keep distinct IDs/previous links, unsigned and future renewals leave the old current contract intact, then switch automatically when valid')
  clock('2026-11-20');open('M-00001');m.locator('.du-work-tabs [data-dept-tab=summary]').click();m.locator('[data-dept-filter=contractState]').select_option('契約中');row=m.locator('[data-dept-summary-row="'+case('M-00001')['id']+'"]');assert row.count()==1 and '終了予定日：2026-12-15' in row.inner_text();m.locator('#dept-clear-maintenance').click();clock('2026-12-16');open('M-00001');assert 'M-00001更新契約' in m.locator('[data-contract-current]').inner_text()
  done('list, details, contract history status, filters and scheduled-end supplementary text agree with the shared state evaluator')
  open('M-00001');current=contracts('M-00001')[1];item(current['id']).locator('[data-maint-renew]').click();f.locator('#lc-mt-name').fill('重複期間の更新契約');f.locator('#lc-mt-startDate').fill('2026-12-20');f.locator('#lc-mt-endDate').fill('2027-02-15');submit();assert '重複' in f.locator('#lc-error').inner_text();assert len(contracts('M-00001'))==2;f.locator('#mc-overlap-confirm').check();submit();overlap_id=contracts('M-00001')[2]['id'];assert active('M-00001')['id']==current['id'];clock('2026-12-20');operation('M-00001',overlap_id,'sign');f.locator('#lc-mt-signedDate').fill('2026-12-20');f.locator('#mc-overlap-confirm').check();assert not f.locator('#mc-switch-current').is_checked();submit();assert active('M-00001')['id']==current['id'];operation('M-00001',overlap_id,'edit');f.locator('#lc-mt-reason').fill('重複確認のうえ一覧の契約を選択');f.locator('#mc-overlap-confirm').check();f.locator('#mc-switch-current').check();submit();assert active('M-00001')['id']==overlap_id
  done('overlap registration requires explicit confirmation; signing an overlap never silently switches the selected current contract, and an explicit choice is audited')
  # Parent storage failure rolls back contract fields, current selection and operation log together.
  before=contracts('M-00001');p.evaluate("()=>{window.__realSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k).includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__realSet.call(this,k,v);};}")
  operation('M-00001',overlap_id,'edit');f.locator('#lc-mt-amount').fill('456789');f.locator('#lc-mt-reason').fill('保存失敗を検証');f.locator('#mc-overlap-confirm').check();submit();assert '保存容量' in f.locator('#lc-error').inner_text();assert contracts('M-00001')==before;assert f.locator('#lc-mt-amount').input_value()=='456789';assert f.locator('#lc-mt-reason').input_value()=='保存失敗を検証';p.evaluate('()=>{Storage.prototype.setItem=window.__realSet;}');submit();assert contracts('M-00001')[2]['amount']==456789;assert len(contracts('M-00001')[2]['operationHistory'])==len(before[2]['operationHistory'])+1
  done('storage failure atomically restores contract/current selection/history and keeps the entered form available for a single successful retry')
  for no in originals:assert fixed(no)==originals[no]
  assert api('()=>__mc.snapshot().cases.length')==initial_count;assert api('()=>__mc.home().active.map(r=>r.source.internalId)')==home_ids
  saved=api('()=>__mc.snapshot()');p.reload(wait_until='networkidle');clock('2026-12-20');assert api('()=>__mc.snapshot()')==saved;open('M-00001');item(overlap_id).locator('.mc-history > summary').click();item(overlap_id).locator('[data-mc-history]').first.click();assert '読み取り専用' in dialog.inner_text();assert case('M-00001')['internalId'] in dialog.inner_text();assert '456789' in dialog.inner_text();assert not dialog.locator('input:not([readonly])').count();p.screenshot(path=str(OUT/'contract-operation-history.png'));close()
  p.set_viewport_size({'width':390,'height':844});operation('M-00001',overlap_id,'edit');expect(f.locator('#lc-submit')).to_be_visible();p.screenshot(path=str(OUT/'contract-edit-mobile.png'));close();assert not errors,errors;assert not writes,writes
  done('reload preserves contracts and audit; case numbers/revisions/counts, equipment, inspections/incidents and dashboard classification are unchanged; history and narrow-screen forms remain usable; no JS or write/upload errors')
  browser.close()
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors,'writes':writes},ensure_ascii=False,indent=2));print('Results:',OUT,flush=True)
if __name__=='__main__':run()
