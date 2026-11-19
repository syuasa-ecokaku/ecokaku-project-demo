"""Battery-only stage columns, per-round dedicated fields and scoped UI regressions.
Run: python tests/power_battery_stage_fields_smoke.py
"""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture
from verified_cdn import verified_cdn
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-power-battery-stage-fields')
LABELS=['基本情報・設備','事前相談','接続検討申込','本申込・工事費','名義・設備変更','連系準備・受電','商用運転・市場参入','取下']
NEW=['preconsultationAppliedAt','preconsultationAnsweredAt','withdrawalDate','withdrawalReason']
HEADERS={
 'basic':['起案区分','事業種別','案件名称','担当者','案件住所','地目','地積','申請名義','AC容量','DC蓄電容量','蓄電型式','台数','PCS型式','台数','仲介・紹介者'],
 'consultation':['担当','事前相談申請日','回答日'],
 'connection':['担当','対応状態','接続検討申請日','接続検討料 請求書受領日','接続検討料 支払日','接続検討料 支払証送付日','接続検討 受付日','接続検討 受付番号','接続検討 回答予定日','接続検討 回答日','概算負担金総額（税込）','所要工期（月）'],
 'main':['担当者','対応状態','対応期限','本申込日（送配電事業者）','保証金 請求書受領日','保証金 請求書記載の請求額','保証金 支払期限日','保証金 支払日','保証金 支払証送付日','発調本受付日','発調 受付番号','本回答予定日','接続供給申込会社（小売電気事業者）','接続供給申込日（小売電気事業者）','接続供給申込受付番号','本回答 承諾日','本回答 供給開始予定日','負担金総額（税込・保証金控除前）','負担金 請求書受領日','負担金 請求書記載の請求金額','負担金 支払期限日','負担金 入金予定日','負担金 支払日','負担金 支払証送付日'],
 'aggregator':['担当者','対応状態','対応期限','発電契約者','設備変更（承諾後）申請内容','設備変更（承諾後）申請日','設備変更（承諾後）受付日','要否結果','託送供給の承諾のお知らせ日','最終発電契約者','最終発電者','地位移転申請日（書類お渡し日）','地位移転変更完了日','受電地点特定番号'],
 'grid':['担当者','対応状態','対応期限','電力会社','支社','設計番号','発電側受付番号','最終 接続供給会社（小売電気事業者）','供給側受付番号','連系協議開始日','連系見込日','B種接地抵抗値書面 発行日','整定値一覧 発行日','エコ革名義 受電地点番号','エコ革名義 発電所ID','アグリ名義 発電所ID','発電所系統コード','連系希望日（受電日）','連系日（受電日）','運転希望日','運転開始日','蓄電池・PCS型式／台数'],
 'operation':['担当者','対応状態','対応期限','回覧板配信日','EMS試験結果共有日','商用運転開始予定日','JEPX参入日','参入資料提出日（需給調整市場）','EPRX参入日'],
 'withdrawal':['担当者','取下日','取下げ理由'],
}
INJECT='window.__sf={snapshot:lifecycleSnapshot,cases:lifecycleSources,data:id=>powerRecord(powerProjects.find(p=>p.id===id)),set:(id,k,v)=>powerSetDraft(powerProjects.find(p=>p.id===id),"v:"+k,v),render:renderPower,ui:()=>powerUI,drafts:()=>powerDrafts,forecast:powerForecast,stage:powerStage,tx:lifecycleTransaction};'
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[]
 raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','b016135:index.html'],cwd=ROOT,text=True);body=[fixture(baseline,INJECT)];previous=subprocess.check_output(['git','show','72a1387:index.html'],cwd=ROOT,text=True)
 def done(s):passed.append(s);print('PASS',s,flush=True)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);p=b.new_page(viewport={'width':1500,'height':1200});p.set_default_timeout(12000);verified_cdn(p);p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.route(url,lambda r:r.fulfill(body=body[0],content_type='text/html'));p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');m=f.locator('#power-workspace')
  def api(js):return p.frames[1].evaluate(js)
  def data(id):return api('()=>__sf.data('+json.dumps(id)+')')
  def snapshot():return api('()=>__sf.snapshot()')
  def wait():expect(f.locator('.lc-busy')).to_be_hidden()
  def nav():f.locator('[data-page=power]').click()
  def stage(k):m.locator('[data-power-tab=bulk]').click();m.locator('#power-bulk-stage').select_option(k)
  def cell(id,k):return m.locator('[data-power-bulk-row="'+id+'"] [data-power-field="'+k+'"]')
  def save():m.locator('[data-power-action=saveAll]').click();wait()
  def cancel():m.locator('[data-power-action=cancelAll]').click()
  def detail(id,section='basic'):
   i=api('()=>__sf.cases().filter(s=>s.businessId==="battery").findIndex(s=>s.id==='+json.dumps(id)+')');m.locator('[data-power-open="'+str(i)+'"]').first.click()
   node=m.locator('#power-section-'+section)
   if node.get_attribute('open') is None:node.locator(':scope > summary').click()
   return node
  # Save an actual prior release before loading new code: no new defaults, mapping or reset.
  api('()=>__sf.tx(()=>{__sf.data("G-00009").values.commonDue="2026-12-24";__sf.data("G-00009").values.commonStatus="保留";})');wait();before=snapshot();body[0]=fixture(raw,INJECT);p.reload(wait_until='networkidle');assert snapshot()==before;assert all(k not in data('G-00009')['values'] for k in NEW);nav();stage('consultation');assert m.locator('#power-bulk-stage option').all_text_contents()==LABELS;assert all(cell('G-00009',k).input_value()=='' for k in NEW[:2]);assert not m.locator('[data-power-field=commonDue],[data-power-field=commonStatus],[data-power-field="42"]').count();assert m.locator('thead th').all_text_contents()==['案件番号','申請案件名','担当','事前相談申請日','回答日','詳細'];assert cell('G-00009','owner').locator('option').all_text_contents();done('old saved catalogue/masters/approvals/history is unchanged; eight stages are in the required order and consultation has exactly three business fields with blank dedicated dates')
  # Existing intake data stays in the same object and equipment editor, with no new fields.
  stage('basic');basic=m.locator('[data-pin-source][data-pin-field=applicantName]').first;sid=basic.get_attribute('data-pin-source');basic.fill('共通基本情報の架空確認名義');save();source=next(s for s in snapshot()['cases'] if s['internalId']==sid);assert source['power']['intake']['applicantName']=='共通基本情報の架空確認名義';assert not any(k.startswith('pin_') for k in source['power']['values']);assert m.locator('[data-pin-equipment="'+sid+'"]').count()==4;done('basic information/equipment continues using source.power.intake and the shared equipment editor without duplicate storage')
  # Connection columns alone change; hidden stored values and all forecast alternatives stay intact.
  stage('connection');headers=m.locator('thead th').all_text_contents();assert '所要工期（月）' in headers;assert not {'対応期限（共通）','接続検討料 支払期限日','接続検討回答 文書受領日','本申込後の工期（月）'} & set(headers);assert len(headers)==15;hidden={k:data('P-00001')['values'].get(k) for k in ['commonDue','connectionDue','connectionReceived','35']};forecasts=api('()=>Object.fromEntries(["connection","main","coordination"].map(phase=>{const d=JSON.parse(JSON.stringify(__sf.data("P-00001")));d.values.forecastPhase=phase;return [phase,__sf.forecast(d)]}))');expected_forecasts=json.loads(json.dumps(forecasts));months=cell('P-00001','34').input_value();assert cell('P-00001','34').get_attribute('aria-label').endswith('所要工期（月）');assert cell('P-00001','34').get_attribute('step')=='1';cell('P-00001','34').fill('1.5');save();assert '所要工期（月）' in m.locator('.pw-errors').inner_text() and '整数' in m.locator('.pw-errors').inner_text();cancel();assert cell('P-00001','34').input_value()==months;assert {k:data('P-00001')['values'].get(k) for k in hidden}==hidden;assert api('()=>Object.fromEntries(["connection","main","coordination"].map(phase=>{const d=JSON.parse(JSON.stringify(__sf.data("P-00001")));d.values.forecastPhase=phase;return [phase,__sf.forecast(d)]}))')==expected_forecasts;p.screenshot(path=str(OUT/'connection.png'));done('connection removes only four displayed columns; No.34 has its new label, old key/integer/month value and all forecast computations remain unchanged')
  # Dedicated dates follow native drafts, validation and atomic save across hidden rows/stages.
  stage('consultation');saved_owner=cell('G-00009','owner').input_value();cell('G-00009','preconsultationAppliedAt').fill('2026-11-01');cell('G-00009','preconsultationAnsweredAt').fill('2026-11-12');assert 'is-dirty' in cell('G-00009','preconsultationAppliedAt').get_attribute('class');cell('G-00009','preconsultationAppliedAt').press('Tab');expect(cell('G-00009','preconsultationAnsweredAt')).to_be_focused();cell('G-00009','preconsultationAnsweredAt').press('Shift+Tab');expect(cell('G-00009','preconsultationAppliedAt')).to_be_focused();assert data('G-00009')['values'].get('preconsultationAppliedAt','')=='';cancel();assert cell('G-00009','preconsultationAppliedAt').input_value()=='';cell('G-00009','preconsultationAppliedAt').fill('2026-11-01');cell('G-00009','preconsultationAnsweredAt').fill('2026-11-12');cell('G-00010','preconsultationAppliedAt').fill('2026-11-03');api('()=>{__sf.set("G-00009","preconsultationAnsweredAt","2026-02-30");__sf.render()}');save();assert '有効な日付' in m.locator('.pw-errors').inner_text();assert data('G-00010')['values'].get('preconsultationAppliedAt','')=='';cell('G-00009','preconsultationAnsweredAt').fill('2026-11-12');m.locator('#power-search').fill('G-00010');m.locator('#power-search').press('Tab');expect(m.locator('[data-power-bulk-row]')).to_have_count(1);save();assert not m.locator('.pw-errors').count(),api('()=>({errors:__sf.ui().errors,drafts:__sf.drafts()})');assert data('G-00009')['values'].get('preconsultationAppliedAt')=='2026-11-01',api('()=>({message:__sf.ui().message,drafts:__sf.drafts(),g9:__sf.data("G-00009").values,g10:__sf.data("G-00010").values})');assert data('G-00010')['values']['preconsultationAppliedAt']=='2026-11-03';assert data('G-00010')['values'].get('preconsultationAnsweredAt','')=='';assert data('G-00009')['values']['commonDue']=='2026-12-24';assert data('G-00009')['values']['commonStatus']=='保留';assert data('G-00009')['values']['owner']==saved_owner;m.locator('[data-power-action=clearFilters]').click();p.screenshot(path=str(OUT/'consultation.png'));done('consultation dates support dirty styling, Tab/Shift-Tab, cancel, real date validation and atomic all-row saves; shared status/deadline and other-case values are never repurposed')
  # Withdrawal is record-only and multiline; common owner remains the same source/options.
  stage('withdrawal');assert m.locator('thead th').all_text_contents()==['案件番号','申請案件名','担当者','取下日','取下げ理由','詳細'];assert not m.locator('[data-power-field=commonStatus],[data-power-field=commonDue],[data-power-field="42"]').count();assert cell('G-00009','withdrawalDate').input_value()=='';assert cell('G-00009','withdrawalReason').evaluate('(e)=>e.tagName')=='TEXTAREA';case_before=next(s for s in snapshot()['cases'] if s['id']=='G-00009' and s.get('businessId')=='battery');progress=api('()=>__sf.stage(__sf.data("G-00009"))');reason='取下の記録例（架空）\n<確認>理由の2行目\n関係者への連絡を確認';cell('G-00009','withdrawalReason').fill('取下の記録例（架空）');cell('G-00009','withdrawalReason').press('End');cell('G-00009','withdrawalReason').press('Enter');cell('G-00009','withdrawalReason').type('<確認>理由の2行目');assert '\n' in cell('G-00009','withdrawalReason').input_value();cell('G-00009','withdrawalReason').fill(reason);cell('G-00009','withdrawalDate').fill('2026-11-13');cell('G-00009','withdrawalDate').press('Tab');expect(cell('G-00009','withdrawalReason')).to_be_focused();cell('G-00009','withdrawalReason').press('Shift+Tab');expect(cell('G-00009','withdrawalDate')).to_be_focused();stage('consultation');assert cell('G-00009','preconsultationAppliedAt').input_value()=='2026-11-01';stage('withdrawal');assert cell('G-00009','withdrawalReason').input_value()==reason;cancel();assert cell('G-00009','withdrawalReason').input_value()=='';cell('G-00009','withdrawalReason').fill(reason);cell('G-00009','withdrawalDate').fill('2026-11-13');save();case_after=next(s for s in snapshot()['cases'] if s['internalId']==case_before['internalId']);assert {k:v for k,v in case_before.items() if k!='power'}=={k:v for k,v in case_after.items() if k!='power'};assert api('()=>__sf.stage(__sf.data("G-00009"))')==progress;assert data('G-00010')['values'].get('withdrawalReason','')=='';assert data('G-00009')['values']['owner']==saved_owner;p.screenshot(path=str(OUT/'withdrawal.png'));done('withdrawal has only owner/date/multiline reason plus case identity; Enter/cancel/save work, cases stay separate and saving does not close/withdraw a case or change progress')
  # Saved-only detail references use the same field keys; unsaved edits do not masquerade as saved data.
  stage('consultation');cell('G-00009','preconsultationAppliedAt').fill('2026-12-01');node=detail('G-00009');saved=node.locator('[data-power-round-saved=consultation]');assert '2026-11-01' in saved.inner_text() and '2026-12-01' not in saved.inner_text();records=m.locator('#power-section-records');records.locator(':scope > summary').click();wr=records.locator('[data-power-round-saved=withdrawal]');assert reason in wr.inner_text();assert wr.locator('.pw-round-reason').evaluate('(e)=>getComputedStyle(e).whiteSpace')=='pre-wrap';assert not wr.locator('input,textarea').count();stage('consultation');assert cell('G-00009','preconsultationAppliedAt').input_value()=='2026-12-01';cancel();done('detail shows saved consultation and withdrawal values including line breaks, from the same current-round store; unsaved list values remain separate')
  # Failed local storage retains drafts and current canonical values; retry/reload restores all fields.
  stage('withdrawal');cell('G-00010','withdrawalReason').fill('保存失敗でも残す下書き\n二行目');before=snapshot();p.evaluate("()=>{window.__set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__set.call(this,k,v)}}");save();assert '保存できません' in m.locator('#power-message').inner_text();assert snapshot()==before;assert cell('G-00010','withdrawalReason').input_value().endswith('二行目');p.evaluate('()=>Storage.prototype.setItem=window.__set');save();p.reload(wait_until='networkidle');nav();stage('withdrawal');assert cell('G-00009','withdrawalReason').input_value()==reason;assert cell('G-00010','withdrawalReason').input_value()=='保存失敗でも残す下書き\n二行目';stage('consultation');assert cell('G-00009','preconsultationAppliedAt').input_value()=='2026-11-01';assert cell('G-00010','preconsultationAppliedAt').input_value()=='2026-11-03';done('storage failure rolls back all committed data and retains textarea drafts; retry and reload restore dedicated dates/reasons with original case IDs')
  # Reconnect must archive all new fields and start an empty new round without touching other cases/common data.
  old=data('G-00009');detail('G-00009','connection');m.locator('[data-power-action=reconnect]').click();m.locator('[data-power-action=reconnectConfirm]').click();wait();new=data('G-00009');assert new['round']==old['round']+1;assert all(new['values'][k]=='' for k in NEW);assert new['archives'][0]['round']==old['round'];assert {k:new['archives'][0]['values'][k] for k in NEW}=={k:old['values'][k] for k in NEW};assert new['values']['owner']==old['values']['owner'] and new['values']['commonDue']==old['values']['commonDue'];assert data('G-00010')['values']['withdrawalReason']=='保存失敗でも残す下書き\n二行目';stage('withdrawal');assert cell('G-00009','withdrawalReason').input_value()=='';cell('G-00009','withdrawalReason').fill('新しい申請回の理由');save();p.reload(wait_until='networkidle');assert data('G-00009')['values']['withdrawalReason']=='新しい申請回の理由';assert data('G-00009')['archives'][0]['values']['withdrawalReason']==reason;done('reconnection archives all four new fields under the old round and clears the active round; new/old round values and other cases never mix')
  # Excel headers and data types through the normal entry points.
  nav()
  for group,headers in HEADERS.items():
   stage(group)
   assert m.locator('thead th').all_text_contents()==['案件番号','申請案件名',*headers,'詳細'],(group,m.locator('thead th').all_text_contents())
  done('all eight data tables match the Excel field order, with the confirmed legacy gross burden definition')
  target='G-00009';other='G-00010'
  stage('basic')
  row=m.locator('[data-power-bulk-row="'+target+'"]')
  row.locator('[data-power-case-field=name]').fill('架空の案件名称')
  row.locator('[data-power-case-field=address]').fill('架空の案件住所')
  row.locator('[data-pin-field=landDesignationOther]').fill('雑種地・田')
  cell(target,'landAreaSqm').fill('175.5')
  cell(target,'batteryEquipmentType').select_option('高圧蓄電池')
  cell(target,'brokers').fill('架空の仲介者A\n架空の紹介者B')
  save()
  source=next(s for s in snapshot()['cases'] if s['id']==target and s.get('businessId')=='battery')
  assert source['name']=='架空の案件名称'
  assert source['common']['address']=='架空の案件住所'
  assert source['power']['intake']['landDesignationOther']=='雑種地・田'
  assert data(target)['values']['landAreaSqm']=='175.5'
  assert data(target)['values']['kind']=='蓄電池'
  assert data(target)['values']['brokers']==['架空の仲介者A','架空の紹介者B']
  assert data(target)['values']['7']!='架空の案件名称'
  stage('connection')
  original=data(target)
  cell(target,'connectionAnsweredAt').fill('2026-10-02')
  cell(target,'connectionPaidAt').fill('2026-10-01')
  cell(target,'33').fill('123456789')
  cell(target,'durationDescription').fill('入金後6ヵ月（受給申込後14ヵ月）')
  flag=row.locator('[data-power-na="25"]')
  flag.check()
  stage('main')
  cell(target,'54').fill('2027-10-01')
  cell(target,'mainSupplyCondition').fill('入金後12ヵ月')
  cell(target,'supplyApplicationNumber').fill('00001234')
  stage('aggregator')
  cell(target,'generationContractor').fill('架空の契約者')
  cell(target,'finalGenerator').fill('架空の発電者')
  cell(target,'equipmentChangeRequest').fill('架空型式X、2台\n架空型式Y、1台')
  stage('grid')
  cell(target,'generationReceiptNumber').fill('00005678')
  cell(target,'gridEquipment').fill('連系時の架空蓄電池2台、PCS1台')
  cell(target,'operationStartedAt').fill('2027-10-02')
  save()
  result=data(target)
  assert result['na']['25'] and result['values'].get('25')==original['values'].get('25')
  assert all(result['values'].get(k)==original['values'].get(k) for k in ['29','connectionReceived','34','supplyStart','17','18','19','20'])
  assert result['accounting']==original['accounting']
  assert result['values']['33']==123456789 and result['values']['durationDescription'].startswith('入金後6')
  assert not data(other)['values'].get('generationReceiptNumber')
  p.reload(wait_until='networkidle');nav();stage('main')
  assert cell(target,'54').input_value()=='2027-10-01'
  assert cell(target,'mainSupplyCondition').input_value()=='入金後12ヵ月'
  assert cell(target,'supplyApplicationNumber').input_value()=='00001234'
  stage('grid')
  assert cell(target,'generationReceiptNumber').input_value()=='00005678'
  assert cell(target,'gridEquipment').input_value()=='連系時の架空蓄電池2台、PCS1台'
  assert cell(other,'operationStartedAt').input_value()==''
  stage('connection')
  assert cell(target,'25').input_value()=='対象外'
  assert cell(other,'durationDescription').input_value()==''
  assert cell(target,'connectionPaidAt').input_value()=='2026-10-01'
  detail(target,'connection')
  m.locator('[data-power-action=reconnect]').click()
  m.locator('[data-power-action=reconnectConfirm]').click()
  wait()
  after=data(target)
  for key in ['connectionAnsweredAt','connectionPaidAt','durationDescription','mainSupplyCondition','supplyApplicationNumber','equipmentChangeRequest','gridEquipment','generationReceiptNumber','operationStartedAt']:
   assert after['values'][key]=='' and after['archives'][0]['values'][key]==result['values'][key],key
  assert after['values']['landAreaSqm']=='175.5'
  done('ordinary save, reload and reconnection preserve common/intake fields, separate legacy dates and equipment, and archive new per-round values with their original types')
  # Exact old DOM for out-of-scope views.
  fresh=b.new_page(viewport={'width':1500,'height':1200});oldpage=b.new_page(viewport={'width':1500,'height':1200});verified_cdn(fresh);verified_cdn(oldpage);fresh.route(url,lambda r:r.fulfill(body=raw,content_type='text/html'));oldpage.route(url,lambda r:r.fulfill(body=previous,content_type='text/html'));fresh.goto(url,wait_until='networkidle');oldpage.goto(url,wait_until='networkidle');ff=fresh.frame_locator('#codex-visualization');of=oldpage.frame_locator('#codex-visualization')
  for fr in [ff,of]:fr.locator('[data-page=power]').click();fr.locator('[data-power-tab=bulk]').click()
  views=0
  for dep in ['realestate','power','sales','legal','procurement','construction','maintenance']:
   for business in ['battery','solar','datacenter']:
    for tab in ['summary','bulk','detail']:
     if dep=='power' and business=='battery' and tab=='bulk':continue
     states=[]
     for fr in [ff,of]:
      fr.locator('[data-page='+dep+']').click();mount=fr.locator('#'+dep+'-workspace');mount.locator('.du-business-tabs').get_by_role('tab',name={'battery':'蓄電池','solar':'太陽光','datacenter':'データセンター'}[business],exact=True).click();mount.locator('.du-work-tabs').get_by_role('tab',name={'summary':'サマリー','bulk':'データ入力','detail':'案件詳細'}[tab],exact=True).click();states.append(mount.evaluate('(e)=>e.innerHTML'))
     assert states[0]==states[1],(dep,business,tab);views+=1
  assert views==62;fresh.close();oldpage.close();done('62 out-of-scope summary, detail, business and department views match the prior release exactly')
  # Narrow textarea remains editable and no artificial filler columns appear.
  nav();stage('withdrawal');p.set_viewport_size({'width':800,'height':1000});reason_cell=cell('G-00009','withdrawalReason');reason_cell.focus();box=reason_cell.bounding_box();assert box['height']>=68 and box['width']>=300;assert m.locator('thead th').count()==6;assert errors==[],errors;assert writes==[],writes;b.close();done('withdrawal textarea remains usable in narrow layout; no empty columns, JavaScript errors or external writes')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors,'external_writes':writes},ensure_ascii=False,indent=2));print('Results:',OUT)
if __name__=='__main__':run()
