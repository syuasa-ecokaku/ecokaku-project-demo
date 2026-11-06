"""P handover and M standalone use the same catalogue, contracts, records and transactions."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-maintenance-intake-review')
INJECT="""window.__maint={sources:lifecycleSources,all:maintenanceAll,open:maintenanceOpen,openDept:lifecycleOpenCase,snapshot:lifecycleSnapshot,ref:approvalRef,contracts:maintenanceContracts,contractStatus:maintenanceContractStatus,current:maintenanceCurrentContract,eligible:maintenanceEligible,number:approvalNumber,state:()=>departmentState('maintenance'),filters:()=>departmentFilters('maintenance'),transaction:lifecycleTransaction,home:()=>homeProjection(),today:maintenanceToday};"""
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[];raw=fixture((ROOT/'index.html').read_text(),INJECT)
 def done(s):passed.append(s);print('PASS',s,flush=True)
 with server() as url,sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=browser.new_page(viewport={'width':1540,'height':1200},timezone_id='Asia/Tokyo');p.route(url,lambda r:r.fulfill(body=raw,content_type='text/html'));p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');m=f.locator('#maintenance-workspace');dlg=f.locator('#case-lifecycle-dialog')
  def api(js):return p.frames[1].evaluate(js)
  def case(number):return api('()=>__maint.sources().find(s=>(s.baseNumber||s.id)==='+json.dumps(number)+')')
  def snap():return api('()=>__maint.snapshot()')
  def active():return api('()=>__maint.all().map(s=>s.id)')
  def nav():f.locator('[data-page=maintenance]').click()
  def tab(key):m.locator('.du-work-tabs [data-dept-tab='+key+']').click()
  def wait():expect(f.locator('.lc-busy')).to_be_hidden()
  def submit():dlg.locator('#lc-submit').click();wait()
  def close():dlg.locator('[data-lc-close]').first.click()
  def open(number,dept='maintenance'):
   api('()=>{const s=__maint.sources().find(s=>(s.baseNumber||s.id)==='+json.dumps(number)+');'+('__maint.open(s)' if dept=='maintenance' else '__maint.openDept(s,'+json.dumps(dept)+')')+';}')
  def source(number):return '__maint.sources().find(s=>(s.baseNumber||s.id)==='+json.dumps(number)+')'
  def register(name='架空単独保守01',business='battery',city='保守市01'):
   nav();f.locator('[data-maintenance-new]').click();f.locator('#mt-business').select_option(business)
   for id,v in {'lc-name':name,'lc-prefecture':'架空県','lc-city':city,'lc-mt-party':'架空保守契約会社（デモ）','lc-mt-equipmentOwner':'架空設備所有法人（デモ）','lc-mt-assetName':'架空設備ユニット','lc-mt-assetModel':'型式サンプル'}.items():f.locator('#'+id).fill(v)
   f.locator('#mt-operator').select_option(label='保守デモ担当A')
  def contract(number,name,renew=False,state='締結済み',start='2026-11-06',end='2026-11-30'):
   open(number)
   if renew:m.locator('.mt-contract').first.locator('summary').click();m.locator('.mt-contract').first.locator('[data-maint-renew]').click()
   else:m.locator('#maintenance-contracts [data-maint-contract]').first.click()
   for k,v in {'name':name,'party':'架空契約先（デモ）','signedDate':'2026-11-06','startDate':start,'endDate':end,'deadline':'2026-11-15','amount':'120000','scope':'設備の基本点検（デモ）','billingCycle':'月次'}.items():f.locator('#lc-mt-'+k).fill(v)
   f.locator('#mt-contractState').select_option(state);f.locator('#mt-autoRenew').select_option('あり');f.locator('#lc-files').set_input_files({'name':name+'.pdf','mimeType':'application/pdf','buffer':b'demo'});submit();expect(dlg).not_to_be_visible()
  def record(number,kind):
   open(number);m.locator('[data-maint-record-add]').click();f.locator('#mt-kind').select_option(kind);f.locator('#mt-operator').select_option(label='保守デモ担当A');f.locator('#lc-mt-description').fill('架空の点検・不具合記録')
   if kind=='inspection':f.locator('#lc-mt-plannedDate').fill('2026-11-18')
   else:f.locator('#lc-mt-actualDate').fill(api('()=>__maint.today()'));f.locator('#lc-mt-result').fill('架空の復旧確認済み')
   f.locator('#lc-files').set_input_files({'name':'点検報告（デモ）.pdf','mimeType':'application/pdf','buffer':b'demo'});submit();expect(dlg).not_to_be_visible()
  nav();initial=len(snap()['cases']);initial_home=api('()=>__maint.home().all.length');assert len(active())==1 and 'P-00001' in active();assert m.locator('[data-dept-summary-row]').count()==1;assert case('P-00001')['maintenance']['route']=='internal';assert '未記録' in case('P-00001')['maintenance']['notes'];open('P-00002','construction');expect(f.locator('#construction-workspace [data-maint-handover]')).to_be_disabled();open('G-00010','realestate');expect(f.locator('#realestate-workspace [data-maint-handover]')).to_be_disabled()
  done('legacy active P data is retained; pre-handover development records are preserved outside active counts; unapproved and pre-cutover cases cannot be handed over')
  api("async()=>{const s="+source('P-00002')+";await __maint.transaction(()=>{Object.assign(s.departments.construction,{completionActual:'2026-10-20',inspectionActual:'2026-10-21',handoverActual:'2026-10-22'});s.power.values['89']='2026-10-23';});}")
  open('P-00002','construction');f.locator('#construction-workspace [data-maint-handover]').click();assert '未登録' in dlg.inner_text();assert case('P-00002').get('maintenance') is None;f.locator('#mt-operator').select_option(label='保守デモ担当B');f.locator('#lc-mt-notes').fill('架空の引継ぎ事項');p.screenshot(path=str(OUT/'handover-confirmation.png'));f.locator('#lc-submit').evaluate('(b)=>{b.click();b.click()}');wait();expect(dlg).not_to_be_visible();c=case('P-00002');assert c['id']=='P-00002' and c['maintenance']['route']=='internal';assert c['maintenance']['intakeState']=='accepted' and len(c['maintenance']['events'])==1;assert len(snap()['cases'])==initial;assert not any(x.get('baseNumber','').startswith('M-') for x in snap()['cases']);assert all(x['state']!='締結済み' for x in c['contracts'] if x['kind']=='保守契約');open('P-00002','construction');expect(f.locator('#construction-workspace [data-maint-handover]')).to_be_disabled();open('P-00002');assert len(active())==2
  done('handover preserves the exact P number/internal ID and development references; repeated/double intake cannot duplicate records or issue M; unregistered contracts stay unregistered')
  nav();f.locator('[data-maintenance-new]').click();submit();assert '案件名' in dlg.locator('#lc-error').inner_text();close();assert len(snap()['cases'])==initial
  register();p.screenshot(path=str(OUT/'standalone-register.png'));f.locator('#lc-submit').evaluate('(b)=>{b.click();b.click()}');wait();expect(dlg).not_to_be_visible();c=case('M-00001');mid=c['internalId'];assert c['id']==mid and c['maintenanceOnly'] and c['maintenance']['caseState']=='商談中';assert c['maintenance']['equipmentOwner']!=c['maintenance']['customerParty'];assert api('()=>__maint.ref('+source('M-00001')+')') is None;assert len(snap()['cases'])==initial+1;assert len(active())==3
  for d in ['realestate','power','sales','legal','procurement','construction']:
   f.locator('[data-page='+d+']').click();w=f.locator('#'+d+'-workspace');assert 'M-00001' not in w.inner_text()
  nav();assert 'M-00001' in m.inner_text();assert api('()=>__maint.home().all.length')==initial_home+1
  done('M registration is atomic, cancel/error/double-click safe, separate from ownership and formalization; the one new case never enters development/power/construction stores')
  for selector,value,count in [('[data-dept-filter=intakeRoute]','standalone',1),('[data-dept-filter=caseState]','商談中',1),('[data-dept-filter=contractState]','未登録',2)]:
   m.locator(selector).select_option(value);assert m.locator('[data-dept-summary-row]').count()==count;assert int(m.locator('[data-dept-metric=all] strong').inner_text())==count;m.locator('#dept-clear-maintenance').click();assert m.locator('[data-dept-summary-row]').count()==3
  for term in ['M-00001','架空単独保守01','架空県保守市01','架空保守契約会社']:
   m.locator('[data-dept-filter=search]').fill(term);m.locator('[data-dept-filter=search]').press('Tab');assert m.locator('[data-dept-summary-row]').count()==1;m.locator('#dept-clear-maintenance').click()
  m.locator('[data-maint-state=商談中]').click();assert m.locator('[data-dept-summary-row]').count()==1;m.locator('#dept-clear-maintenance').click();assert m.locator('[data-dept-summary-row]').count()==3;p.screenshot(path=str(OUT/'mixed-summary.png'))
  done('P/M mixed list supports number/name/address/customer, intake/state/contract/owner filters, status card filtering and one-button reset; all counts use the same accepted catalogue')
  for number in ['P-00002','M-00001']:
   contract(number,'架空保守契約'+number);before=case(number);count=len(api('()=>__maint.contracts('+source(number)+')'));contract(number,'架空更新契約'+number,True,start='2026-12-01',end='2027-11-30');after=case(number);assert len(api('()=>__maint.contracts('+source(number)+')'))==count+1;assert after.get('revision',0)==before.get('revision',0);assert api('()=>__maint.current('+source(number)+').name')=='架空保守契約'+number;assert any(c.get('previousContractId') for c in after['contracts']);assert after['baseNumber']==before['baseNumber'];record(number,'inspection');record(number,'incident');c=case(number);assert c['records']['inspections'][-1]['caseId']==c['internalId'];assert c['records']['incidents'][-1]['result']=='架空の復旧確認済み'
  assert len(snap()['cases'])==initial+1;assert not case('M-00001').get('revision');open('M-00001');p.screenshot(path=str(OUT/'contracts-and-records.png'))
  done('P/M share contract IDs, filename attachments, signed-state validation, renewal records and current-contract selection; inspection/emergency records survive renewal without extra cases or branches')
  tab('bulk');m.locator('[data-dept-group]').select_option('intake');cell=m.locator('[data-dept-row="'+mid+'"] [data-dept-field=caseState]');cell.select_option('管理中');assert case('M-00001')['maintenance']['caseState']=='商談中';m.locator('[data-dept-action=cancel]').first.click();assert case('M-00001')['maintenance']['caseState']=='商談中';cell.select_option('管理中');m.locator('[data-dept-action=save]').first.click();wait();assert case('M-00001')['maintenance']['caseState']=='管理中';assert not case('M-00001').get('revision');open('M-00001');m.locator('[data-lc-change]').click();f.locator('#lc-after').fill('架空単独保守01変更');f.locator('#lc-reason').fill('設備名称の明示的な変更（デモ）');submit();assert case('M-00001')['revision']==1;assert case('M-00001')['changeHistory'][0]['number']=='M-00001-01';assert len(snap()['cases'])==initial+1
  done('the existing Excel editor saves/cancels maintenance metadata and preserves draft semantics; only explicit shared change registration issues M-00001-01')
  p.reload(wait_until='networkidle');nav();assert case('M-00001')['revision']==1 and len(case('M-00001')['records']['inspections'])==1;assert len(api('()=>__maint.contracts('+source('M-00001')+')'))==2;assert case('P-00002')['maintenance']['intakeState']=='accepted';assert len(snap()['cases'])==initial+1
  done('reload restores P intake, M case/route, exact IDs, contracts/renewal chain, equipment, operational records and revision history')
  # A browser storage failure must not consume M numbers, retain a partial contract or erase its draft.
  p.evaluate("()=>{window.__realSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k).includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__realSet.call(this,k,v);};}")
  before_contract=case('M-00001');open('M-00001');m.locator('#maintenance-contracts [data-maint-contract]').first.click();f.locator('#lc-mt-name').fill('保存失敗契約');submit();assert '保存容量' in dlg.locator('#lc-error').inner_text();assert case('M-00001')['contracts']==before_contract['contracts'];assert case('M-00001')['maintenance']==before_contract['maintenance'];close()
  register('架空失敗M02',city='失敗市02');submit();assert '保存容量' in dlg.locator('#lc-error').inner_text();assert case('M-00002') is None;close();assert len(snap()['cases'])==initial+1;p.evaluate('()=>{Storage.prototype.setItem=window.__realSet;}');register('架空成功M02',city='成功市02');submit();assert case('M-00002')
  done('quota failure rolls back the M catalogue and reserved number; the next successful creation receives the same unconsumed M-00002')
  for business,name,number in [('solar','架空太陽光保守03','M-00003'),('datacenter','架空DC保守04','M-00004')]:
   register(name,business,city=name);submit();assert case(number)['businessId']==business;tab('summary');assert m.locator('[data-dept-summary-row]').count()==1
  contract('M-00004','架空終了契約',state='終了');assert api('()=>__maint.current('+source('M-00004')+')') is None;tab('summary');m.locator('[data-dept-filter=contractState]').select_option('終了');assert m.locator('[data-dept-summary-row]').count()==1;m.locator('#dept-clear-maintenance').click()
  p.set_viewport_size({'width':390,'height':844});nav();f.locator('[data-maintenance-new]').click();expect(f.locator('#lc-submit')).to_be_visible();box=dlg.bounding_box();assert box['width']<=390 and box['height']<=844;p.screenshot(path=str(OUT/'standalone-mobile.png'));close();assert not errors,errors;assert not writes,writes
  done('business tabs isolate battery/solar/datacenter M cases; desktop/mobile modal scrolls without hiding actions; no JavaScript errors or external write/upload requests')
  browser.close()
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors,'writes':writes},ensure_ascii=False,indent=2));print('Results:',OUT)
def run_legacy_restore():
 errors=[]
 raw=fixture((ROOT/'index.html').read_text(),INJECT)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page();p.route(url,lambda r:r.fulfill(body=raw,content_type='text/html'));p.on('pageerror',lambda e:errors.append(str(e)));p.goto(url,wait_until='networkidle')
  snapshot=p.frames[1].evaluate('()=>__maint.snapshot()')
  for c in snapshot['cases']:
   c.pop('maintenance',None);c.pop('maintenanceSchemaVersion',None)
   for contract in c.get('contracts',[]):
    for key in ['caseId','purpose']:contract.pop(key,None)
  snapshot.update(sequence=1,transaction='legacy-before-maintenance')
  p.evaluate("data=>localStorage.setItem('ecokaku-project-demo:case-lifecycle:v1:',JSON.stringify(data))",snapshot)
  p.reload(wait_until='networkidle');f=p.frame_locator('#codex-visualization');f.locator('[data-page=maintenance]').click();assert f.locator('#maintenance-workspace [data-dept-summary-row]').count()==1
  assert p.frames[1].evaluate("()=>__maint.sources().find(s=>s.id==='P-00001').maintenance.acceptedAt")==''
  assert p.frames[1].evaluate("()=>__maint.sources().find(s=>s.id==='P-00002').maintenance||null") is None
  assert p.frames[1].evaluate("()=>__maint.contractStatus({state:'未締結',endDate:'2020-01-01'})")=='未締結'
  assert p.frames[1].evaluate("()=>__maint.contractStatus({state:'締結済み',endDate:'2020-01-01'})")=='終了'
  p.frames[1].evaluate("async()=>{const s=__maint.sources().find(s=>s.id==='P-00002');await __maint.transaction(()=>{s.departments.maintenance.status='対応中';s.departments.construction.handoverActual='2026-10-22';s.power.values['89']='2026-10-23';});}")
  p.reload(wait_until='networkidle');assert p.frames[1].evaluate("()=>__maint.sources().find(s=>s.id==='P-00002').maintenance||null") is None
  p.frames[1].evaluate("()=>__maint.open(__maint.sources().find(s=>s.id==='P-00002'))");owner=f.locator('#maintenance-workspace [data-dept-case=P-00002][data-dept-field=owner]');owner.fill('保守準備担当（デモ）');f.locator('#maintenance-workspace [data-dept-action=save]').first.click();expect(f.locator('.lc-busy')).to_be_hidden();assert p.frames[1].evaluate("()=>__maint.sources().find(s=>s.id==='P-00002').departments.maintenance.owner")=='保守準備担当（デモ）';assert p.frames[1].evaluate("()=>__maint.sources().find(s=>s.id==='P-00002').maintenance||null") is None
  assert not errors,errors;b.close()
 data=json.loads((OUT/'results.json').read_text());data['passed']=list(dict.fromkeys(data['passed']+['legacy saved cases without maintenance fields restore safely; unknown historical acceptance dates remain unknown; unsigned contracts do not become ended solely from a past date']));(OUT/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print('PASS legacy save restoration and contract-state date rules',flush=True)
if __name__=='__main__':
 run()
 run_legacy_restore()
