"""Real Chromium checks for shared initiation, revision transactions and durable approvals."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server
from department_notices_smoke import fixture
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/tmp/ecokaku-case-lifecycle-review')
INJECT="""window.__lifecycle={snapshot:lifecycleSnapshot,sources:lifecycleSources,open:lifecycleOpenCase,number:approvalNumber,ref:approvalRef,conditions:approvalConditions,identity:id=>noticeCenter.selectUser(id),powerSave:ids=>powerSave(ids),departmentSave:d=>departmentSave(d),selectBusiness:(d,b)=>{departmentState(d).business=b;},draft:(d,s,k,v)=>{const r=departmentStore(d).records.find(r=>r.id===s.id);departmentEdit(d,{dataset:{deptCase:s.id,deptField:k},value:v,validity:{badInput:false}});},approve:s=>approvalApprove(approvalRef(s)),returned:s=>approvalReturn(approvalRef(s)),state:()=>lifecycleState};"""
def run():
 OUT.mkdir(exist_ok=True);results=[];errors=[]
 raw=fixture((ROOT/'index.html').read_text(),INJECT)
 with server() as url,sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  context=browser.new_context(viewport={'width':1500,'height':1250},timezone_id='Asia/Tokyo')
  def page():
   p=context.new_page();p.route(url,lambda route:route.fulfill(body=raw,content_type='text/html'));p.on('pageerror',lambda e:errors.append(str(e)));p.goto(url,wait_until='networkidle');return p
  p=page();f=p.frame_locator('#codex-visualization')
  def api(script):return p.frames[1].evaluate(script)
  def done(s):results.append(s);print('PASS',s,flush=True)
  def sources():return api('()=>__lifecycle.snapshot().cases')
  def find(name):return next(c for c in sources() if c['name']==name)
  def nav(d):f.locator('[data-page='+d+']').click()
  def open_case(s,d):api('()=>__lifecycle.open(__lifecycle.sources().find(s=>s.internalId==='+json.dumps(s['internalId'])+'),'+json.dumps(d)+')')
  def wait():expect(f.locator('.lc-busy')).to_be_hidden()
  def initiate(d,name,business='battery'):
   nav(d);f.locator('[data-lc-new='+d+']').click();f.locator('#lc-business').select_option(business)
   for k,v in {'name':name,'prefecture':'架空県','city':'検証市'+name[-2:]}.items():f.locator('#lc-'+k).fill(v)
   f.locator('#lc-owner').select_option(label='不動産デモ担当A')
  def submit():f.locator('#lc-submit').click();wait()
  def change(s,d,target,value,reason='デモ検証のため'):
   open_case(s,d);f.locator('[data-lc-change="'+s['internalId']+'"]:visible').click();f.locator('#lc-target').select_option(target);f.locator('#lc-after').fill(value);f.locator('#lc-reason').fill(reason);submit();expect(f.locator('#case-lifecycle-dialog')).not_to_be_visible()
  initial=len(sources());nav('realestate');f.locator('[data-lc-new=realestate]').click();submit();assert '仮案件名' in f.locator('#lc-error').inner_text();assert len(sources())==initial;f.locator('[data-lc-close]').first.click();assert not p.evaluate('Object.keys(localStorage).some(k=>k.includes("case-lifecycle"))')
  initiate('realestate','架空起案検証01');p.screenshot(path=str(OUT/'initiation-desktop.png'));f.locator('#lc-files').set_input_files({'name':'起案根拠（デモ）.txt','mimeType':'text/plain','buffer':b'demo'});f.locator('#lc-submit').evaluate('(b)=>{b.click();b.click();}');wait();s=find('架空起案検証01');assert s['baseNumber']=='R-00005' and s['id'].startswith('case-');assert len(sources())==initial+1 and len(s['relatedFiles'])==1
  for d in ['realestate','power','sales','legal','procurement','construction','maintenance']:
   open_case(s,d);expect(f.locator('#'+d+'-demo-main [data-lifecycle-case="'+s['internalId']+'"]').first).to_be_visible()
  initiate('power','架空起案検証02');f.locator('#lc-city').fill('検証市01');submit();assert '既存案件候補' in f.locator('#lc-error').inner_text();f.locator('#lc-separate').check();submit();g=find('架空起案検証02');assert g['baseNumber']=='G-00011';assert len(sources())==initial+2
  done('R/G registration only after valid commit; errors/cancel/double-click consume no numbers; one immutable case is visible in all seven departments; filename metadata is saved')
  initiate('power','架空起案検証01');candidate=f.locator('[data-lc-existing="'+s['internalId']+'"]');expect(candidate).to_be_visible();candidate.click();wait();assert len(sources())==initial+2;expect(f.locator('#power-view [data-lifecycle-case="'+s['internalId']+'"]')).to_be_visible();assert 'R-00005' in f.locator('#power-view').inner_text()
  done('duplicate candidates open the same R case from power without a second G record')
  open_case(s,'realestate');f.locator('[data-lc-change="'+s['internalId']+'"]:visible').click();f.locator('#lc-reason').fill('変更なし');submit();assert '同じ値' in f.locator('#lc-error').inner_text();assert not find(s['name']).get('revision');f.locator('[data-lc-close]').first.click()
  change(s,'realestate','name','架空起案変更01');s=find('架空起案変更01');assert s['revision']==1 and s['changeHistory'][0]['number']=='R-00005-01';assert s['power']['values']['7']=='架空起案検証01'
  change(s,'legal','address','架空県検証市変更地区99番');s=find(s['name']);assert s['revision']==2 and s['changeHistory'][0]['number']=='R-00005-02';assert s['power']['values']['追加1']!='架空県検証市変更地区99番';assert len(sources())==initial+2
  f.locator('[data-lc-change="'+s['internalId']+'"]:visible').click();f.locator('#lc-target').select_option('power14');f.locator('#lc-after').fill('2500');f.locator('#lc-reason').fill('設備容量変更（デモ）');p.screenshot(path=str(OUT/'change-desktop.png'));f.locator('[data-lc-close]').first.click()
  hist=f.locator('[data-lifecycle-case="'+s['internalId']+'"]:visible details');hist.locator('summary').click();hist.locator('[data-lc-history]').last.click();assert '架空起案検証01' in f.locator('#case-lifecycle-dialog').inner_text();assert f.locator('#case-lifecycle-dialog input:not([readonly])').count()==0;p.screenshot(path=str(OUT/'history-readonly.png'));f.locator('[data-lc-close]').first.click()
  done('unchanged registration rejected; revisions 01/02 shared across departments without extra cases; independent application names/addresses preserved; historical snapshots are read-only')
  # Ordinary, actual department save and power confirmation feed the existing approval evaluator.
  open_case(s,'realestate');api('''async()=>{const s=__lifecycle.sources().find(s=>s.baseNumber==='R-00005');__lifecycle.draft('realestate',s,'status','取得済み');__lifecycle.draft('realestate',s,'acquiredDate','2026-11-06');await __lifecycle.departmentSave('realestate');}''');wait();s=find(s['name']);assert s['revision']==2;assert api("()=>__lifecycle.ref(__lifecycle.sources().find(s=>s.baseNumber==='R-00005')).state")=='unsubmitted'
  open_case(s,'power');f.locator('#power-value-formalPowerConfirmedAt').fill('2026-11-06');f.locator('[data-power-action=saveCase]').first.click();wait();assert api("()=>__lifecycle.ref(__lifecycle.sources().find(s=>s.baseNumber==='R-00005')).state")=='pending'
  api("()=>__lifecycle.identity('admin')");api("async()=>{const s=__lifecycle.sources().find(s=>s.baseNumber==='R-00005');await __lifecycle.approve(s);await __lifecycle.approve(s);}");wait();s=find(s['name']);assert s['formalNumber']=='P-00007' and s['revision']==0 and len(s['changeHistory'])==2;assert 'R-00005-02' in s['previousNumbers']
  change(s,'construction','name','架空正式化変更01');s=find('架空正式化変更01');assert s['revision']==1 and s['changeHistory'][0]['number']=='P-00007-01';assert len(sources())==initial+2
  for d in ['realestate','power','sales','legal','procurement','construction','maintenance']:
   if d=='maintenance':
    open_case(s,d);assert 'P-00007-01' in f.locator('#maintenance-workspace [data-lifecycle-case]').inner_text();continue
   open_case(s,d);m=f.locator('#'+d+'-workspace');m.locator('#power-tab-summary' if d=='power' else '.du-work-tabs [data-dept-tab=summary]').click();search=m.locator('#power-search' if d=='power' else '[data-dept-filter=search]')
   for number in ['R-00005','R-00005-02','P-00007','P-00007-01']:
    search.fill(number);search.press('Tab');assert m.locator('[data-power-summary-row]' if d=='power' else '[data-dept-summary-row]').count()==1,(d,number)
   m.locator('[data-power-action=clearFilters]' if d=='power' else '#dept-clear-'+d).click()
  done('ordinary save keeps revision; committed completion conditions enqueue existing approval; approval issues one P and resets revision; first formal revision is 01 and old temp history survives')
  # Save failure is an atomic rollback, including identifiers and pending drafts.
  p.evaluate("()=>{window.__realSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k).includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__realSet.call(this,k,v);};}")
  open_case(s,'sales');f.locator('[data-lc-change="'+s['internalId']+'"]:visible').click();f.locator('#lc-after').fill('保存失敗する変更');f.locator('#lc-reason').fill('容量不足テスト');submit();assert '保存容量' in f.locator('#lc-error').inner_text();assert find(s['name'])['revision']==1 and len(find(s['name'])['changeHistory'])==3;f.locator('[data-lc-close]').first.click()
  open_case(s,'realestate');api("async()=>{const s=__lifecycle.sources().find(s=>s.baseNumber==='R-00005');__lifecycle.draft('realestate',s,'next','保存失敗の下書き');await __lifecycle.departmentSave('realestate');}");wait();assert find(s['name'])['departments']['realestate']['next']!='保存失敗の下書き';assert '保存失敗の下書き' in f.locator('#realestate-workspace [data-dept-field=next]').input_value();f.locator('#realestate-workspace [data-dept-action=cancel]').first.click()
  initiate('power','架空失敗起案03');submit();assert '保存容量' in f.locator('#lc-error').inner_text();assert len(sources())==initial+2;f.locator('[data-lc-close]').first.click();p.evaluate('()=>{Storage.prototype.setItem=window.__realSet;}')
  initiate('power','架空成功起案03');submit();third=find('架空成功起案03');assert third['baseNumber']=='G-00012'
  done('storage quota failures roll back data, branch/history and new-case registration; next successful registration reuses the unconsumed number')
  p.reload(wait_until='networkidle');s=find('架空正式化変更01');assert s['revision']==1 and s['formalNumber']=='P-00007' and len(s['changeHistory'])==3;assert len(sources())==initial+3;open_case(s,'procurement');expect(f.locator('[data-lifecycle-case="'+s['internalId']+'"]:visible')).to_contain_text('P-00007-01')
  done('reload restores common cases, exact immutable IDs, formal number, revisions, history and approval state')
  for business,name in [('solar','架空太陽光検証04'),('datacenter','架空DC検証05')]:
   initiate('realestate',name,business);submit();c=find(name)
   for d in ['realestate','power','sales','legal','procurement','construction','maintenance']:open_case(c,d);expect(f.locator('#'+d+'-demo-main [data-lifecycle-case="'+c['internalId']+'"]').first).to_be_visible()
   change(c,'power','name',name+'改');assert find(name+'改')['revision']==1
  done('solar/datacenter initiation and shared details work across all departments without copying battery workflow fields')
  # Stale browser tabs cannot silently overwrite a newer catalogue or issue the same number.
  stale=page();sf=stale.frame_locator('#codex-visualization');initiate('realestate','架空最新起案06');submit();current_count=len(sources());sf.locator('[data-page=power]').click();sf.locator('[data-lc-new=power]').click()
  for k,v in {'name':'架空競合起案07','prefecture':'架空県','city':'競合市'}.items():sf.locator('#lc-'+k).fill(v)
  sf.locator('#lc-owner').select_option(label='不動産デモ担当A');sf.locator('#lc-submit').click();expect(sf.locator('.lc-busy')).to_be_hidden();assert '別の画面' in sf.locator('#lc-error').inner_text();stale.reload(wait_until='networkidle');assert stale.frames[1].evaluate('()=>__lifecycle.sources().length')==current_count;stale.close()
  done('same-origin multi-tab sequence conflict rejects stale writes, prevents duplicate issuance and preserves the latest catalogue')
  p.set_viewport_size({'width':390,'height':844});nav('power');f.locator('[data-lc-new=power]').click();p.screenshot(path=str(OUT/'initiation-mobile.png'));box=f.locator('#case-lifecycle-dialog').bounding_box();assert box['width']<=390 and box['height']<=844;f.locator('#lc-name').fill('架空');f.locator('#lc-submit').scroll_into_view_if_needed();expect(f.locator('#lc-submit')).to_be_visible();f.locator('[data-lc-close]').first.click()
  assert not errors,errors
  done('scrollable desktop/mobile modal keeps fields/actions reachable; no JavaScript errors')
  browser.close()
 (OUT/'results.json').write_text(json.dumps({'passed':results,'errors':errors},ensure_ascii=False,indent=2))
 print('Results:',OUT,flush=True)
if __name__=='__main__':run()
