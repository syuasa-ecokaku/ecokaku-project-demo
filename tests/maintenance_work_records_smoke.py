"""P/M canonical work records: update, start, finish, cancel, correction and aggregate consistency."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture,inner
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-maintenance-work-review')
INJECT="""
maintenanceToday=()=> '2026-11-06';
if(!lifecycleSources().some(s=>s.baseNumber==='M-00001')){
 const s=lifecycleNewSource({name:'架空M点検案件',prefecture:'架空県',city:'架空市',street:'',business:'battery',owner:'保守デモ担当A',memo:'',broker:'',files:[]},'M-00001');s.maintenanceOnly=true;s.maintenance={route:'standalone',intakeType:'メンテナンス単独受託',intakeState:'accepted',caseState:'管理中',customerParty:'架空契約先',events:[]};s.assets=[{id:'asset-m-work',caseId:s.internalId,name:'架空M設備',model:'架空型式'}];s.contracts=[{id:'contract-m-work',caseId:s.internalId,purpose:'maintenance',kind:'保守契約',name:'架空M保守契約',party:'架空契約先',state:'締結済み',signedDate:'2026-11-01',startDate:'2026-11-01',endDate:'2026-12-31',files:['既存保守契約.pdf']}];s.records={inspections:[{id:'legacy-m-inspection',caseId:s.internalId,date:'2026-11-01',memo:'日付と結果があっても状態は不明',result:'既存結果あり'}],incidents:[{id:'legacy-m-incident',caseId:s.internalId,memo:'結果空欄でも未対応とは限らない',result:''}]};Object.assign(s.departments.maintenance,{owner:'保守デモ担当A',status:'対応中',incident:'過去の障害内容（自由記述）',priority:'緊急',nextInspection:'2026-11-30'});lifecycleInsert(s);noticeCenter.registerCase('battery',s);maintenanceEnsure(s);maintenanceWorkNormalize(s);
}
window.__wr={sources:lifecycleSources,items:maintenanceWorkList,state:maintenanceWorkState,next:maintenanceNextInspection,unknown:maintenanceWorkUnknown,openinc:maintenanceWorkPendingIncidents,urgent:maintenanceWorkUrgent,overdue:maintenanceWorkOverdue,open:maintenanceOpen,snapshot:lifecycleSnapshot,kpis:()=>departmentKpis('maintenance'),home:homeProjection,homeClass:()=>homeBusinessCases('battery').map(r=>({id:r.source.internalId,primary:(()=>{const {needs,...p}=homePrimary(r);return p})(),active:homeProjection().active.some(x=>x.source===r.source)})),reference:maintenanceWorkReference};
"""
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[]
 raw=(ROOT/'index.html').read_text();base=inner(subprocess.check_output(['git','show','e4765ca:index.html'],cwd=ROOT,text=True));current=inner(raw)
 # Contract operations and global classification must remain exactly as implemented in ①.
 for start,end in [('function maintenanceContractEndDate(', 'const contractOperationValue='),('maintenanceContractsHTML=function(s){','const maintenanceContractOperation='),('function homeProjection(){','function homeRecord')]:
  if start=='function homeProjection(){':assert current.split(start,1)[1].split('\n',1)[0]==base.split(start,1)[1].split('\n',1)[0]
  else:assert current.split(start,1)[1].split(end,1)[0]==base.split(start,1)[1].split(end,1)[0]
 for name in ['homePrimary','homeDepartmentInfo','maintenanceHomeProjection']:
  token='function '+name+'('
  if token in base:assert current.split(token,1)[1].split('\n',1)[0]==base.split(token,1)[1].split('\n',1)[0]
 body=fixture(raw,INJECT)
 def done(v):passed.append(v);print('PASS',v,flush=True)
 with server() as url,sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=browser.new_page(viewport={'width':1540,'height':1200},timezone_id='Asia/Tokyo');p.route(url,lambda r:r.fulfill(body=body,content_type='text/html'));p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');m=f.locator('#maintenance-workspace');dlg=f.locator('#case-lifecycle-dialog')
  def api(s):return p.frames[1].evaluate(s)
  def ref(no):return '__wr.sources().find(s=>(s.baseNumber||s.id)==='+json.dumps(no)+')'
  def case(no):return api('()=>'+ref(no))
  def items(no):return api('()=>__wr.items('+ref(no)+')')
  def record(no,rid):return next(x['record'] for x in items(no) if x['record']['id']==rid)
  def open(no):api('()=>__wr.open('+ref(no)+')')
  def wait():expect(f.locator('.lc-busy')).to_be_hidden()
  def submit():dlg.locator('#lc-submit').click();wait()
  def close():dlg.locator('[data-lc-close]').first.click()
  def row(rid):return m.locator('[data-maint-record="'+rid+'"]')
  def op(no,rid,kind):open(no);row(rid).locator('[data-wr-operation='+kind+']').click()
  def kpi(key):return next(k['value'] for k in api('()=>__wr.kpis()') if k['id']==key)
  def summary():m.locator('.du-work-tabs [data-dept-tab=summary]').click()
  def fixed(no):
   c=case(no);return {k:c.get(k) for k in ['id','internalId','baseNumber','formalNumber','revision','phase','contracts','assets']}|{'caseState':c['maintenance']['caseState']}
  initial={no:fixed(no) for no in ['P-00001','M-00001']};case_count=api('()=>__wr.snapshot().cases.length');home_before=api('()=>__wr.homeClass()')
  open('M-00001');assert len(api('()=>__wr.unknown('+ref('M-00001')+')'))==2;summary();assert kpi('incident')==0 and kpi('urgent')==0 and kpi('inspection')==0;assert kpi('unknownRecords')==4;assert api('()=>__wr.next('+ref('M-00001')+')')=='';open('M-00001');assert '状態未確認' in row('legacy-m-inspection').inner_text();assert '既存結果あり' in row('legacy-m-inspection').inner_text();assert '状態未確認' in row('legacy-m-incident').inner_text();assert row('legacy-m-inspection').locator('[data-wr-operation]').count()==1
  open('M-00001');m.locator('[data-maint-record-add]').click();f.locator('#mt-kind').select_option('');submit();assert '記録区分' in f.locator('#lc-error').inner_text();close();assert len(items('M-00001'))==2
  done('legacy dates/memos/results are preserved as state-unknown, not inferred complete or unhandled; unknown records have a separate count and no active/urgent/planned contribution')
  legacy_ids={no:{x['type']:x['record']['id'] for x in items(no)} for no in initial}
  for no in initial:
   rid=legacy_ids[no]['inspection'];before=record(no,rid);op(no,rid,'confirm');f.locator('#mt-workState').select_option('planned');f.locator('#lc-mt-plannedDate').fill('2026-11-20' if no.startswith('M') else '2026-11-15');f.locator('#mt-priority').select_option('通常');f.locator('#lc-mt-reason').fill('管理資料で予定を確認（デモ）');submit();after=record(no,rid);assert after['id']==before['id'] and after['date']==before['date'];assert after['workState']=='planned' and after['legacyOriginal']['memo']==before['memo'];assert len(items(no))==2
  op('P-00001',legacy_ids['P-00001']['incident'],'confirm');f.locator('#mt-workState').select_option('unhandled');f.locator('#mt-priority').select_option('緊急');f.locator('#lc-mt-reason').fill('対応未了を確認（デモ）');submit()
  op('M-00001','legacy-m-incident','confirm');f.locator('#mt-workState').select_option('completed');f.locator('#lc-mt-actualDate').fill('2026-11-05');f.locator('#mt-operator').select_option(label='保守デモ担当A');f.locator('#mt-priority').select_option('通常');f.locator('#lc-mt-result').fill('記録上の完了を確認');f.locator('#lc-mt-reason').fill('担当者から完了確認');submit();assert record('M-00001','legacy-m-incident')['workState']=='completed';assert not record('M-00001','legacy-m-incident').get('startedAt')
  done('explicit state confirmation updates the same legacy IDs, keeps original values and can establish planned, unhandled or directly completed states with evidence')
  def add(no,kind,name,date='',priority='通常',completed=False,actual='',result=''):
   open(no);before={x['record']['id'] for x in items(no)};m.locator('[data-maint-record-add]').click();f.locator('#mt-kind').select_option(kind);f.locator('#mt-recordEntry').select_option('completed' if completed else 'planned');f.locator('#lc-mt-description').fill(name);f.locator('#lc-mt-plannedDate').fill(date);f.locator('#mt-priority').select_option(priority)
   if completed:f.locator('#lc-mt-actualDate').fill(actual);f.locator('#lc-mt-result').fill(result)
   submit();expect(dlg).not_to_be_visible();return next(x['record']['id'] for x in items(no) if x['record']['id'] not in before)
  plans={}
  for no in initial:
   plans[no]={}
   for date in ['2026-11-12','2026-11-03','2026-11-09']:plans[no][date]=add(no,'inspection','架空点検 '+date,date)
   assert api('()=>__wr.next('+ref(no)+')')=='2026-11-03';assert len(api('()=>__wr.overdue('+ref(no)+')'))==1
   open(no);assert '対象設備未指定' in row(plans[no]['2026-11-03']).inner_text();summary();assert '2026-11-03' in m.locator('[data-summary-card=upcoming]').inner_text();assert '期限超過' in m.locator('[data-summary-card=upcoming]').inner_text()
  assert kpi('recordOverdue')==2;p.screenshot(path=str(OUT/'overdue-summary.png'))
  done('next inspection uses the earliest open planned date regardless of registration order, retains overdue dates, and surfaces overdue work consistently in list, KPI and upcoming schedules')
  for no in initial:
   rid=plans[no]['2026-11-03'];op(no,rid,'start');f.locator('#mt-operator').select_option('');submit();assert '担当者' in f.locator('#lc-error').inner_text();f.locator('#mt-operator').select_option(label='保守デモ担当A');submit();assert record(no,rid)['workState']=='in_progress';assert record(no,rid)['startedBy'] and record(no,rid)['startedAt'];op(no,rid,'complete');f.locator('#lc-mt-actualDate').fill('');f.locator('#mt-operator').select_option('');f.locator('#lc-mt-result').fill('');submit();assert all(t in f.locator('#lc-error').inner_text() for t in ['実績日','担当者','対応結果']);f.locator('#lc-mt-actualDate').fill('2026-11-07');f.locator('#mt-operator').select_option(label='保守デモ担当A');f.locator('#lc-mt-result').fill('架空の点検完了');submit();assert '未来' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-actualDate').fill('2026-11-06');f.locator('#lc-files').set_input_files({'name':'完了報告.pdf','mimeType':'application/pdf','buffer':b'demo'});p.screenshot(path=str(OUT/'complete-inspection.png'));before_len=len(items(no));f.locator('#lc-submit').evaluate('(b)=>{b.click();b.click()}');wait();assert record(no,rid)['workState']=='completed';assert len(items(no))==before_len;assert api('()=>__wr.next('+ref(no)+')')=='2026-11-09';assert len(record(no,rid)['operationHistory'])==3
  done('P/M start records actor/time; completion validates required facts and future dates, updates the same ID once under double-click and advances the next schedule')
  for no in initial:
   rid=legacy_ids[no]['inspection'];op(no,rid,'complete');f.locator('#lc-mt-actualDate').fill('2026-11-06');f.locator('#mt-operator').select_option(label='保守デモ担当A');f.locator('#lc-mt-result').fill('予定日前に実施完了');submit();assert record(no,rid)['workState']=='completed';assert not record(no,rid).get('startedAt');assert record(no,rid)['actualDate']<record(no,rid)['plannedDate']
  rid=legacy_ids['P-00001']['incident'];op('P-00001',rid,'complete');f.locator('#lc-mt-actualDate').fill('2026-11-06');f.locator('#mt-operator').select_option(label='保守デモ担当A');f.locator('#lc-mt-result').fill('直接完了を確認');submit();assert not record('P-00001',rid).get('startedAt')
  done('planned/unhandled records can complete directly without fabricated start events, including work performed earlier than its plan')
  for no in initial:
   rid=plans[no]['2026-11-09'];before=record(no,rid);op(no,rid,'cancel');submit();assert '中止理由' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-reason').fill('設備点検日程の取り消し（デモ）');f.locator('#wr-notes').fill('中止に関する補足');submit();r=record(no,rid);assert r['workState']=='cancelled' and r['plannedDate']==before['plannedDate'] and r['description']==before['description'];assert r['cancelReason'] and r['cancelledAt'] and r['cancelledBy'];assert r['notes']=='中止に関する補足';assert api('()=>__wr.next('+ref(no)+')')=='2026-11-12';assert not row(rid).locator('[data-wr-operation]').count()
  summary();assert kpi('recordOverdue')==0
  done('cancellation requires a reason and preserves the plan/content/notes/history while excluding the work from open, upcoming and overdue aggregates')
  no='M-00001';rid=plans[no]['2026-11-03'];before=record(no,rid);op(no,rid,'correct');f.locator('#lc-mt-result').fill('訂正後の点検結果');submit();assert '訂正理由' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-reason').fill('報告書の誤記訂正');f.locator('#lc-mt-result').fill('');submit();assert '対応結果' in f.locator('#lc-error').inner_text();f.locator('#lc-mt-result').fill('訂正後の点検結果');f.locator('#lc-files').set_input_files({'name':'訂正版報告.pdf','mimeType':'application/pdf','buffer':b'demo'});submit();r=record(no,rid);assert r['workState']=='completed';assert set(r['files'])=={'完了報告.pdf','訂正版報告.pdf'};assert r['operationHistory'][0]['before']['result']==before['result'];assert r['operationHistory'][0]['after']['result']=='訂正後の点検結果';row(rid).locator('.wr-history > summary').click();row(rid).locator('[data-wr-history]').first.click();assert before['result'] in dlg.inner_text() and '訂正後の点検結果' in dlg.inner_text();assert not dlg.locator('input:not([readonly])').count();p.screenshot(path=str(OUT/'correction-history.png'));close()
  done('completed records have a separate reason-required correction path, remain completed, retain attachments and expose immutable before/after history')
  urgent=add(no,'incident','架空緊急障害A',priority='緊急');normal=add(no,'incident','架空不具合B');open(no);summary();assert kpi('incident')==1 and kpi('urgent')==1;op(no,urgent,'start');submit();assert record(no,urgent)['workState']=='in_progress';op(no,urgent,'complete');f.locator('#lc-mt-actualDate').fill('2026-11-06');f.locator('#lc-mt-result').fill('架空復旧完了');submit();summary();assert kpi('incident')==1 and kpi('urgent')==0;op(no,normal,'cancel');f.locator('#lc-mt-reason').fill('対応不要と確認');submit();summary();assert kpi('incident')==0 and kpi('urgent')==0;assert '過去の障害内容' in case(no)['departments']['maintenance']['incident'];newjob=add(no,'incident','再発は別の作業として追加',completed=True,actual='2026-11-06',result='再対応完了');assert newjob not in [urgent,normal];assert not record(no,newjob).get('startedAt')
  done('two open incidents count one case; completing one retains the other, urgent drops independently, all complete/cancel removes the case, and old free text never creates active work')
  # Representative columns are references to explicitly selected records, not another writer.
  open(no);m.locator('.du-work-tabs [data-dept-tab=bulk]').click();m.locator('[data-dept-group]').select_option('business');mid=case(no)['id'];bulk=m.locator('[data-dept-row="'+mid+'"]');assert not bulk.locator('[data-dept-field=incident],[data-dept-field=inspectionDate],[data-dept-field=inspectionMemo],[data-dept-field=nextInspection]').count();bulk.locator('[data-wr-link=incident]').first.click();f.locator('#mt-linkedRecord').select_option(urgent);before_ids=[x['record']['id'] for x in items(no)];submit();assert [x['record']['id'] for x in items(no)]==before_ids;assert api('()=>__wr.reference('+ref(no)+',"incident").id')==urgent
  open(no);m.locator('.du-work-tabs [data-dept-tab=summary]').click();m.locator('[data-dept-filter=recordWorkState]').select_option('inspection:planned');assert m.locator('[data-dept-summary-row]').count()==2;m.locator('#dept-clear-maintenance').click();assert m.locator('[data-dept-filter=recordWorkState]').input_value()=='';m.locator('[data-dept-filter=recordWorkState]').select_option('unknown');assert m.locator('[data-dept-summary-row]').count()==0;m.locator('#dept-clear-maintenance').click()
  done('representative columns cannot create duplicate tasks or overwrite arbitrary records; explicit reference selection preserves IDs; record-state filters and the shared reset agree with case-level counts')
  # Foreign equipment is rejected; an unassigned case-level record is accepted.
  open(no);m.locator('[data-maint-record-add]').click();f.locator('#lc-mt-description').fill('設備所属の検証');f.locator('#lc-mt-plannedDate').fill('2026-11-10');other=case('P-00001')['assets'][0]['id'];f.locator('#mt-asset').evaluate('(e,v)=>e.add(new Option("別案件の設備",v))',other);f.locator('#mt-asset').select_option(other);length=len(items(no));submit();assert '所属する設備' in f.locator('#lc-error').inner_text() and len(items(no))==length;f.locator('#mt-asset').select_option('');close();assert len(items(no))==length
  done('equipment options are case-scoped and foreign equipment IDs are rejected; cancellation allocates no record and equipment-unassigned work remains supported')
  # Save failure must not leave a completed state or an extra operation log.
  rid=plans[no]['2026-11-12'];op(no,rid,'complete');f.locator('#lc-mt-actualDate').fill('2026-11-06');f.locator('#lc-mt-result').fill('保存失敗後の再試行');before=record(no,rid);p.evaluate("()=>{window.__realSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k).includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__realSet.call(this,k,v);};}");submit();assert '保存容量' in f.locator('#lc-error').inner_text();assert record(no,rid)==before;assert f.locator('#lc-mt-result').input_value()=='保存失敗後の再試行';p.evaluate('()=>{Storage.prototype.setItem=window.__realSet;}');submit();assert record(no,rid)['workState']=='completed';assert len(record(no,rid)['operationHistory'])==len(before['operationHistory'])+1
  for no in initial:assert fixed(no)==initial[no]
  assert api('()=>__wr.snapshot().cases.length')==case_count;assert api('()=>__wr.homeClass()')==home_before
  saved=api('()=>__wr.snapshot()');p.reload(wait_until='networkidle');assert api('()=>__wr.snapshot()')==saved;open('M-00001');assert record('M-00001',rid)['workState']=='completed';assert api('()=>__wr.next('+ref('M-00001')+')')=='';assert api('()=>__wr.next('+ref('P-00001')+')')=='2026-11-12'
  # Completed/cancelled record dates must not remain in the global maintenance schedule.
  events=api('()=>__wr.home().events.filter(e=>e.dept==="maintenance"&&e.key.endsWith(":nextInspection")).map(e=>({id:e.record.id,date:e.date}))');assert all(e['date'] not in ['2026-11-03','2026-11-09'] for e in events)
  p.set_viewport_size({'width':390,'height':844});op('P-00001',plans['P-00001']['2026-11-12'],'complete');expect(f.locator('#lc-submit')).to_be_visible();p.screenshot(path=str(OUT/'record-completion-mobile.png'));close();assert not errors,errors;assert not writes,writes
  done('storage failure restores record/state/history atomically and keeps inputs for retry; reload restores all data; case IDs/numbers/branches/counts/contracts and global classification remain unchanged while schedule references update; mobile works without JS/upload errors')
  browser.close()
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors,'writes':writes},ensure_ascii=False,indent=2));print('Results:',OUT,flush=True)
if __name__=='__main__':run()
