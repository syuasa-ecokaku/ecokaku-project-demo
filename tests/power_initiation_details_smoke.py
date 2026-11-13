"""Power initiation classifications, shared equipment details and transactional persistence.
Run: python tests/power_initiation_details_smoke.py
"""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-power-initiation')
INJECT='window.__pi={cases:lifecycleSources,snapshot:lifecycleSnapshot,open:lifecycleOpenCase,ui:()=>powerUI,pins:()=>pinUI,stores:()=>powerBusinessStores,approval:approvalRef,tx:lifecycleTransaction};'
def diff(a,b,path=''):
 if type(a)!=type(b):return [(path,a,b)]
 if isinstance(a,dict):return sum([diff(a.get(k),b.get(k),path+'.'+k) for k in a.keys()|b.keys()],[])[:30]
 if isinstance(a,list):return sum([diff(x,y,path+'['+str(i)+']') for i,(x,y) in enumerate(zip(a,b))],[])[:30] if len(a)==len(b) else [(path,len(a),len(b))]
 return [] if a==b else [(path,a,b)]
def restored_equal(before,after):
 # The existing maintenance hydration adds caseId/purpose to legacy contracts;
 # approval/case arrays enumerate by business after restoring new battery cases.
 before=json.loads(json.dumps(before));after=json.loads(json.dumps(after))
 prior={c['internalId']:c for c in before['cases']}
 for c in after['cases']:
  for contract in c.get('contracts',[]):
   old=next((x for x in prior[c['internalId']].get('contracts',[]) if x['id']==contract['id']),{})
   for key in ['caseId','purpose']:
    if key not in old:contract.pop(key,None)
 for data in [before,after]:
  for key in ['cases','approvals']:data[key].sort(key=lambda x:x['internalId'])
 return before==after
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[]
 raw=(ROOT/'index.html').read_text();old=subprocess.check_output(['git','show','7b18555:index.html'],cwd=ROOT,text=True);body=[fixture(old,INJECT)]
 def done(s):passed.append(s);print('PASS',s,flush=True)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx=b.new_context(viewport={'width':1540,'height':1250},timezone_id='Asia/Tokyo');p=ctx.new_page();p.set_default_timeout(10000);p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.route(url,lambda r:r.fulfill(body=body[0],content_type='text/html'));p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');m=f.locator('#power-workspace');d=f.locator('#case-lifecycle-dialog');ed=f.locator('#pin-equipment-dialog')
  def api(js):return p.frames[1].evaluate(js)
  def snapshot():return api('()=>__pi.snapshot()')
  def cases():return api('()=>__pi.cases()')
  def case(name):return next(s for s in cases() if s['name']==name)
  def wait():expect(f.locator('.lc-busy')).to_be_hidden()
  def nav(dep='power'):f.locator('[data-page='+dep+']').click()
  def lc(k):return d.locator('#lc-'+k)
  def submit():lc('submit').click();wait()
  def close():d.locator('[data-lc-close]').first.click()
  def start(name,biz='battery',kind='new',dep='power'):
   nav(dep);f.locator('[data-lc-new='+dep+']').click();lc('business').select_option(biz)
   if dep=='power':lc('caseType').select_option(kind)
   for k,v in {'name':name,'prefecture':'架空県','city':'起案確認市'+name[-3:]}.items():lc(k).fill(v)
   lc('owner').select_option(label='不動産デモ担当A')
  def open_case(s):api('()=>__pi.open(__pi.cases().find(s=>s.internalId==='+json.dumps(s['internalId'])+'),"power")')
  def bulk(biz='battery'):
   m.locator('[data-power-business='+biz+']').click();m.locator('[data-power-tab=bulk]').click()
   if biz=='battery':m.locator('#power-bulk-stage').select_option('basic')
  def cell(s,key):return m.locator('[data-pin-source="'+s['internalId']+'"][data-pin-field='+key+']')
  def save(biz='battery'):m.locator('[data-power-action=saveAll]' if biz=='battery' else '[data-pin-save=all]').click();wait()
  def cancel(biz='battery'):m.locator('[data-power-action=cancelAll]' if biz=='battery' else '[data-pin-cancel=all]').click()
  def row(host,kind,n=0):return host.locator('[data-pin-models='+kind+'] [data-pin-row]').nth(n)
  def model(host,kind,n,name,qty):row(host,kind,n).locator('[data-pin-model=model]').fill(name);row(host,kind,n).locator('[data-pin-model=qty]').fill(qty)
  # Persist a real prior release and compare all saved records before adding any new fields.
  api('()=>__pi.tx(()=>{const s=__pi.cases().find(s=>s.businessId==="battery");s.memo="既存データを保持（デモ）";})');wait();before=snapshot();body[0]=fixture(raw,INJECT);p.reload(wait_until='networkidle');after=snapshot();assert after==before;assert all('intake' not in s.get('power',{}) for s in cases());oldcase=next(s for s in cases() if s.get('businessId')=='battery');oldlatest={k:oldcase['power']['values'].get(k) for k in ['14','15','17','18','19','20']};nav();bulk();assert cell(oldcase,'caseType').input_value()=='';assert cell(oldcase,'acCapacityKw').input_value()==''
  done('previous saved cases, purchasing/customer masters, approvals and history hydrate exactly unchanged; new legacy fields remain unregistered without inferred capacities/models')
  # Required type, unchanged required fields and origin numbering.
  nav();f.locator('[data-lc-new=power]').click();assert lc('caseType').input_value()=='';assert lc('caseType').locator('option').all_text_contents()==['選択してください','新規案件','EPC案件','権利譲渡案件','申請依頼案件'];count=len(cases());submit();assert '起案区分を選択' in lc('error').inner_text();assert len(cases())==count;lc('caseType').select_option('new');submit();assert '仮案件名' in lc('error').inner_text();close()
  issued=[]
  for i,kind in enumerate(['new','epc','rights-transfer','application-request']):
   name='架空区分確認'+str(i+1)+'号';start(name,kind=kind);submit();s=case(name);issued.append(s);assert s['origin']=='power' and s['baseNumber'].startswith('G-');assert s['power']['intake']['caseType']==kind;assert s['power']['intake']['acCapacityKw']=='' and s['power']['intake']['batteryCapacityKwh']=='';assert s['power']['intake']['batteryModels']==[] and s['power']['intake']['pcsModels']==[];assert s['powerConfirmedAt']=='' and not s['formalApprovedAt'];assert api('()=>__pi.approval(__pi.cases().find(s=>s.internalId==='+json.dumps(s['internalId'])+')).state')=='unsubmitted'
  assert [s['baseNumber'] for s in issued]==['G-00011','G-00012','G-00013','G-00014'];done('all four case types register under independent power origin; empty type is rejected, optional blanks stay empty and G numbering/formalization rules remain unchanged')
  # Invalid decimal capacities and paired rows are blocked without consuming a number.
  start('架空複数設備確認001','battery','epc');lc('applicantName').fill('架空申請名義株式会社');lc('acCapacityKw').fill('0');submit();assert '0より大きい' in lc('error').inner_text();lc('acCapacityKw').fill('-2');submit();assert '0より大きい' in lc('error').inner_text();lc('acCapacityKw').fill('19.75');lc('batteryCapacityKwh').fill('100.125');model(d,'batteryModels',0,'架空BAT-A','');submit();assert '両方' in lc('error').inner_text();row(d,'batteryModels').locator('[data-pin-model=qty]').fill('1.5');submit();assert '正の整数' in lc('error').inner_text();row(d,'batteryModels').locator('[data-pin-model=qty]').fill('2');d.locator('[data-pin-row-add=batteryModels]').click();model(d,'batteryModels',1,'架空BAT-B','3');d.locator('[data-pin-row-add=batteryModels]').click();assert d.locator('[data-pin-models=batteryModels] [data-pin-row]').count()==3;d.locator('[data-pin-row-add=pcsModels]').click();model(d,'pcsModels',0,'架空PCS-A','1');model(d,'pcsModels',1,'架空PCS-B','4');d.locator('[data-pin-row-add=pcsModels]').click();row(d,'pcsModels',2).locator('[data-pin-row-remove]').click();lc('landDesignation').select_option('other');lc('landDesignationOther').fill('地目デモ分類');lc('landClassification').select_option('other');lc('landClassificationOther').fill('地類デモ分類');lc('files').set_input_files({'name':'架空設備資料.txt','mimeType':'text/plain','buffer':b'demo'});p.screenshot(path=str(OUT/'initiation-desktop.png'))
  # Keep both independent DC form values across switches and do not register hidden capacity.
  lc('business').select_option('solar');expect(lc('solarCapacityKw')).to_be_visible();expect(lc('batteryCapacityKwh')).to_be_hidden();lc('solarCapacityKw').fill('31.625');lc('business').select_option('datacenter');expect(lc('solarCapacityKw')).to_be_hidden();expect(lc('batteryCapacityKwh')).to_be_hidden();lc('business').select_option('battery');assert lc('batteryCapacityKwh').input_value()=='100.125';assert lc('applicantName').input_value()=='架空申請名義株式会社';lc('business').select_option('solar');assert lc('solarCapacityKw').input_value()=='31.625';assert row(d,'batteryModels',1).locator('[data-pin-model=model]').input_value()=='架空BAT-B';submit();s=case('架空複数設備確認001');v=s['power']['intake'];assert 'batteryCapacityKwh' not in v and v['solarCapacityKw']==31.625;assert v['acCapacityKw']==19.75 and v['applicantName']!=s['mainOwner'] and v['applicantName']!=s['customer'];assert v['landDesignationOther']=='地目デモ分類' and v['landClassificationOther']=='地類デモ分類';assert s['relatedFiles']==['架空設備資料.txt'];assert [(r['model'],r['qty']) for r in v['batteryModels']]==[('架空BAT-A',2),('架空BAT-B',3)];assert len(v['pcsModels'])==2 and all(r['id'] for r in v['pcsModels']);assert s['baseNumber']=='G-00015'
  done('positive decimal AC/DC, model/count pairing and positive integer validation work; multiple independent arrays, blank-row exclusion, land Other values and filename-only attachments persist')
  done('business switching restores hidden values without conversion or erasure; solar kW alone is registered while battery kWh is excluded')
  # Shared solar list/detail edits with the existing confirmation draft, ordinary save and cancellation.
  bulk('solar');assert cell(s,'solarCapacityKw').input_value()=='31.625';assert not cell(s,'batteryCapacityKwh').count();cell(s,'applicantName').fill('修正した架空申請名義');cell(s,'acCapacityKw').fill('21.25');expect(cell(s,'acCapacityKw')).to_have_class('pw-edit is-dirty');m.locator('[data-lc-open="'+s['internalId']+'"]').click();expect(cell(s,'applicantName')).to_have_value('修正した架空申請名義');m.locator('#lc-power-confirmed').fill('2026-11-12');assert api('()=>Object.keys(__pi.stores().solar.drafts['+json.dumps(s['id'])+']).length')==3;m.locator('[data-pin-save="'+s['internalId']+'"]').click();wait();s=case(s['name']);assert s['power']['intake']['acCapacityKw']==21.25 and s['powerConfirmedAt']=='2026-11-12';assert s['revision']==0;assert '保存しました' in m.inner_text();bulk('solar');cell(s,'solarCapacityKw').fill('0');save('solar');assert '0より大きい' in m.inner_text();assert case(s['name'])['power']['intake']['solarCapacityKw']==31.625;cancel('solar');assert cell(s,'solarCapacityKw').input_value()=='31.625';cell(s,'solarCapacityKw').fill('33.5');bulk('datacenter');bulk('solar');assert cell(s,'solarCapacityKw').input_value()=='33.5';cancel('solar')
  done('solar list and detail share drafts with existing power-confirmation dates; scoped save/cancel, validation, decimal types and tab/business switching remain consistent without revision changes')
  # Common equipment auxiliary editing follows parent drafts and never persists by itself.
  m.locator('[data-pin-equipment="'+s['internalId']+'"]').click();model(ed,'batteryModels',0,'補助画面で修正した型式','5');ed.locator('[data-pin-row-add=pcsModels]').click();model(ed,'pcsModels',2,'架空PCS-C','2');ed.locator('[data-pin-equipment-apply]').click();assert not ed.is_visible(),(ed.locator('#pin-equipment-error').inner_text(),errors,api('()=>({ui:__pi.pins(),html:document.getElementById("pin-equipment-dialog").innerHTML})'));assert case(s['name'])['power']['intake']['batteryModels'][0]['model']=='架空BAT-A';assert '未保存' in m.inner_text();open_case(s);assert '補助画面で修正した型式' in m.inner_text(),api('()=>__pi.stores().solar.drafts');bulk('solar');cancel('solar');m.locator('[data-pin-equipment="'+s['internalId']+'"]').click();assert row(ed,'batteryModels').locator('[data-pin-model=model]').input_value()=='架空BAT-A';model(ed,'batteryModels',0,'保存する新型式','5');ed.locator('[data-pin-equipment-apply]').click();save('solar');assert case(s['name'])['power']['intake']['batteryModels'][0]['qty']==5;assert case(s['name'])['power']['intake']['batteryModels'][0]['model']=='保存する新型式';m.locator('[data-pin-equipment="'+s['internalId']+'"]').click();row(ed,'batteryModels').locator('[data-pin-model=qty]').fill('0');ed.locator('[data-pin-equipment-apply]').click();assert '正の整数' in ed.locator('#pin-equipment-error').inner_text();ed.locator('[data-pin-equipment-close]').first.click()
  done('one shared equipment editor stages multi-model edits into parent drafts, rejects invalid rows, supports cancel and only persists on ordinary parent save')
  # Battery list and existing basic detail use the same data; legacy records are not overwritten.
  battery=issued[0];bulk();cell(battery,'acCapacityKw').fill('7.75');cell(battery,'batteryCapacityKwh').fill('25.125');cell(battery,'landDesignation').select_option('other');cell(battery,'landDesignationOther').fill('蓄電池地目デモ');cell(battery,'landClassification').focus();cell(battery,'landClassification').press('Tab');expect(m.locator('[data-pin-equipment="'+battery['internalId']+'"]')).to_be_focused();m.locator('[data-pin-equipment="'+battery['internalId']+'"]').press('Shift+Tab');expect(cell(battery,'landClassification')).to_be_focused();save();battery=case(battery['name']);assert battery['power']['intake']['acCapacityKw']==7.75 and battery['power']['intake']['batteryCapacityKwh']==25.125;assert 'solarCapacityKw' not in battery['power']['intake'];open_case(battery);assert cell(battery,'acCapacityKw').input_value()=='7.75';cell(battery,'applicantName').fill('蓄電池名義デモ');m.locator('[data-power-action=saveCase]').first.click();wait();bulk();assert cell(battery,'applicantName').input_value()=='蓄電池名義デモ';latest=next(x for x in cases() if x['internalId']==oldcase['internalId']);assert {k:latest['power']['values'].get(k) for k in oldlatest}==oldlatest
  done('battery basic input and existing basic detail share editable metadata; battery kWh and solar kW have distinct saved keys while existing latest application values and old single-model data stay intact')
  # Capacity definitions are intentionally absent for data centers.
  start('架空データセンター確認777','datacenter','application-request');lc('acCapacityKw').fill('44.25');assert lc('batteryCapacityKwh').is_hidden() and lc('solarCapacityKw').is_hidden();submit();dc=case('架空データセンター確認777');assert dc['power']['intake']['acCapacityKw']==44.25;assert not ({'batteryCapacityKwh','solarCapacityKw'} & set(dc['power']['intake']));bulk('datacenter');assert not m.locator('[data-pin-field=batteryCapacityKwh],[data-pin-field=solarCapacityKw]').count();cell(dc,'applicantName').fill('DC名義デモ');save('datacenter');assert case(dc['name'])['power']['intake']['applicantName']=='DC名義デモ'
  done('data-center initiation/input/detail use AC and common fields with no invented DC definition or persisted hidden-unit values')
  # Candidate handling still requires acknowledgement and can open an existing case without issuance.
  existing_count=len(cases());start(s['name']);expect(d.locator('[data-lc-existing="'+s['internalId']+'"]').first).to_be_visible();submit();assert '既存案件候補' in lc('error').inner_text();d.locator('[data-lc-existing="'+s['internalId']+'"]').first.click();wait();assert len(cases())==existing_count;assert s['baseNumber'] in m.inner_text();start('不動産の既存起案確認888',dep='realestate');assert not d.locator('#lc-caseType').count();assert lc('origin').input_value()=='不動産先行';submit();r=case('不動産の既存起案確認888');assert r['baseNumber']=='R-00005' and r['origin']=='realestate' and 'intake' not in r['power']
  done('existing case name/location candidates still prevent accidental duplicates and open the same case; unmodified real-estate initiation keeps independent R numbering')
  # Store failure leaves the new form, catalogue, model rows and number sequence untouched.
  start('架空保存失敗確認999',kind='rights-transfer');lc('acCapacityKw').fill('2.5');model(d,'pcsModels',0,'失敗後に保持する型式','2');saved=snapshot();p.evaluate("()=>{window.__set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__set.call(this,k,v)}}");submit();assert '保存容量' in lc('error').inner_text();assert snapshot()==saved;assert lc('acCapacityKw').input_value()=='2.5';assert row(d,'pcsModels').locator('[data-pin-model=model]').input_value()=='失敗後に保持する型式';p.evaluate('()=>Storage.prototype.setItem=window.__set');submit();last=case('架空保存失敗確認999');assert last['baseNumber']=='G-00017';saved=snapshot();p.reload(wait_until='networkidle');assert restored_equal(saved,snapshot()), diff(saved,snapshot());open_case(s);assert cell(s,'landClassificationOther').input_value()=='地類デモ分類';assert cell(s,'applicantName').input_value()=='修正した架空申請名義';assert '保存する新型式' in m.inner_text()
  done('storage failure atomically rolls back catalogue/number/metadata, retains the form for retry, and all saved values/IDs/other departments restore exactly on reload')
  # Responsive form, infinite numeric input and deleting the final row.
  p.set_viewport_size({'width':390,'height':844});start('架空狭幅確認000');lc('acCapacityKw').fill('1e309');submit();assert '数値' in lc('error').inner_text();lc('acCapacityKw').fill('0.125');row(d,'batteryModels').locator('[data-pin-row-remove]').click();assert d.locator('[data-pin-models=batteryModels] [data-pin-row]').count()==1;assert row(d,'batteryModels').locator('[data-pin-model=model]').input_value()=='';lc('landDesignation').select_option('other');lc('landDesignationOther').fill('狭幅デモ');lc('submit').scroll_into_view_if_needed();expect(lc('submit')).to_be_visible();p.screenshot(path=str(OUT/'initiation-mobile.png'));box=d.bounding_box();assert box['width']<=390 and box['height']<=844;assert d.locator('.lc-grid').first.evaluate('(el)=>getComputedStyle(el).gridTemplateColumns').count(' ')==0;close();assert errors==[],errors;assert writes==[],writes;b.close()
  done('responsive single-column scrollable form keeps actions reachable; nonfinite numbers are rejected and deleting the final equipment row restores one empty row; no JS errors/external writes')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors,'external_writes':writes},ensure_ascii=False,indent=2));print('Results:',OUT)
if __name__=='__main__':run()
