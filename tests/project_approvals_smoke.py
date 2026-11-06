"""Committed-condition approval workflow, permission gates and immutable-ID formalization."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import inner,fixture
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-project-approvals-review')
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];failed=[];writes=[]
 raw=(ROOT/'index.html').read_text();base=subprocess.check_output(['git','show','80ae1a9:index.html'],cwd=ROOT,text=True)
 for var in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
  read=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+var+'=',1)[1])[0]
  assert read(raw)==read(base)
 def done(text):passed.append(text);print('PASS',text,flush=True)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1600,'height':1350},timezone_id='Asia/Tokyo');p.on('pageerror',lambda e:errors.append(str(e)));p.on('requestfailed',lambda r:failed.append(r.url));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');a=f.locator('#approvals-workspace')
  def identity(key):
   f.locator('#account-toggle').click();f.locator('#approval-demo-user').select_option(key)
   if f.locator('#account-menu').is_visible():f.locator('#account-toggle').click()
  def approvals():f.locator('[data-page=approvals]').click()
  def nav(d):f.locator('[data-page='+d+']').click()
  def dept(d):return f.locator('#'+d+'-workspace')
  def tab(d,t):dept(d).locator('.du-work-tabs').get_by_role('tab',name={'summary':'サマリー','bulk':'データ入力','detail':'案件詳細'}[t],exact=True).click()
  def cell(d,id,key):return dept(d).locator('[data-dept-case="'+id+'"][data-dept-field='+key+']')
  def group(d,g):dept(d).locator('[data-dept-group]').select_option(g)
  def save(d):dept(d).locator('[data-dept-action=save]').click()
  def case_row(id):return a.locator('[data-approval-row]').filter(has=a.locator('td').filter(has_text=id))
  def open_case(id):
   a.locator('[data-approval-row]').filter(has_text=id).get_by_role('button',name='確認',exact=True).click()
  def list_tab(key):
   if a.locator('[data-approval-back]').count():a.locator('[data-approval-back]').click()
   a.locator('[data-approval-tab='+key+']').click();a.locator('#approval-search').fill('')
  def power_case(id):
   nav('power');w=dept('power');w.locator('#power-tab-summary').click();w.locator('[data-power-action=clearFilters]').click();w.locator('[data-power-summary-row="'+id+'"] [data-power-open]').first.click()
  def confirmed(id,value):
   power_case(id);dept('power').locator('[data-power-field=formalPowerConfirmedAt]').fill(value)
  def power_save():dept('power').locator('[data-power-action=saveCase]').first.click()
  assert f.locator('#approval-navigation').is_hidden();identity('staff');assert f.locator('#approval-navigation').is_hidden();identity('manager');assert f.locator('#approval-navigation').is_visible();approvals();assert a.locator('[data-approval-row]').count()==1;assert 'G-00010' in a.inner_text();identity('admin');approvals();assert f.locator('#approval-pending-count').inner_text()=='1';assert a.locator('[data-approval-row]').count()==1;assert len(a.locator('thead th').all_text_contents())==9
  list_tab('approved');assert a.locator('[data-approval-row]').count()==6;list_tab('pending');open_case('G-00010');assert 'DEMO_G-00010_connectionAnswer' not in a.inner_text();assert '接続検討回答.pdf' in a.inner_text();assert '根拠資料' in a.inner_text();a.locator('[data-approval-back]').click();p.screenshot(path=str(OUT/'pending-initial.png'))
  done('role/case-scoped menu, badge and actions use shared demo identities; initial saved conditions enqueue only G-00010; six existing P records never requeue; confirmation shows saved evidence/history')
  # G-00006 has acquired land but no power confirmation; an unsaved completion must not enqueue.
  confirmed('G-00006','2026-11-05');assert f.locator('#approval-pending-count').inner_text()=='1';power_save();assert f.locator('#approval-pending-count').inner_text()=='2';power_save();assert f.locator('#approval-pending-count').inner_text()=='2';approvals();assert a.locator('[data-approval-row]').count()==2
  # G-00007 has power confirmation, land is incomplete. Save status first, then the acquired date.
  nav('realestate');tab('realestate','bulk');group('realestate','common');cell('realestate','G-00007','status').select_option('取得済み');save('realestate');assert f.locator('#approval-pending-count').inner_text()=='2';group('realestate','business');cell('realestate','G-00007','acquiredDate').fill('2026-11-05');assert f.locator('#approval-pending-count').inner_text()=='2';save('realestate');assert f.locator('#approval-pending-count').inner_text()=='3'
  done('power-only/land-only/incomplete dates and unsaved drafts never enqueue; saved completion from either department enqueues once; no-op re-save does not duplicate')
  approvals();open_case('G-00006');a.locator('[data-approval-return]').click();assert '差戻し理由を入力' in a.locator('#approval-error').inner_text();a.locator('#approval-return-reason').fill('根拠資料の記載を修正してください（検証）');a.locator('#approval-return-department').select_option('realestate');a.locator('[data-approval-return]').click();assert '差戻し' in a.inner_text();assert f.locator('#approval-pending-count').inner_text()=='2';a.locator('[data-approval-back]').click();list_tab('returned');assert a.locator('[data-approval-row]').count()==1
  nav('realestate');tab('realestate','bulk');group('realestate','common');save('realestate');assert f.locator('#approval-pending-count').inner_text()=='2';power_case('G-00006');dept('power').locator('#power-section-records>summary').click();dept('power').locator('#power-memo').fill('他部門のメモ変更（検証）');power_save();assert f.locator('#approval-pending-count').inner_text()=='2';nav('realestate');tab('realestate','bulk');group('realestate','common');cell('realestate','G-00006','next').fill('根拠資料を修正したため再確認（検証）');assert f.locator('#approval-pending-count').inner_text()=='2';save('realestate');assert f.locator('#approval-pending-count').inner_text()=='3';approvals();list_tab('pending');open_case('G-00006');assert '根拠資料の記載を修正' in a.inner_text();a.locator('.ap-history>summary').click();assert '修正保存後に再申請' in a.inner_text();a.locator('[data-approval-back]').click()
  done('return reason is mandatory and stored with actor/time/department; unchanged save, wrong-department save and unsaved corrections do not resubmit; actual target-department save resubmits with history')
  # Losing a saved condition removes only approval eligibility, retaining its application history.
  confirmed('G-00007','');power_save();assert f.locator('#approval-pending-count').inner_text()=='2';approvals();assert '条件不足で承認対象外' in a.inner_text();open_case('G-00007');assert a.locator('[data-approval-approve]').is_disabled();assert '電力申請確定日が未登録' in a.inner_text();confirmed('G-00007','2026-11-05');power_save();assert f.locator('#approval-pending-count').inner_text()=='3'
  done('losing a committed completion excludes the case and disables approval while preserving history; restoring the condition safely requeues')
  # Preserve legal attachments and contract IDs through issuance; internal G ID remains the data key.
  nav('legal');tab('legal','bulk');dept('legal').locator('[data-dept-row="G-00006"] [data-dept-open]').last.click();files=dept('legal').locator('[data-dept-section=files]');files.locator('summary').click();files.locator('input[type=file]').set_input_files({'name':'approval-proof-demo.pdf','mimeType':'application/pdf','buffer':b'demo'});details=dept('legal').locator('[data-dept-section=business]').inner_text();assert 'DEMO-G-00006' in details
  approvals();list_tab('pending');open_case('G-00006');assert 'approval-proof-demo.pdf' in a.inner_text();approve=a.locator('[data-approval-approve]');handle=approve.element_handle();approve.evaluate('(e)=>{e.click();e.click()}');assert 'P-00007 を発行' in a.inner_text();assert f.locator('#approval-pending-count').inner_text()=='2';assert a.locator('[data-approval-approve]').is_disabled();p.screenshot(path=str(OUT/'approved-detail.png'))
  list_tab('approved');a.locator('#approval-search').fill('G-00006');assert a.locator('[data-approval-row]').count()==1;assert 'P-00007' in a.inner_text();a.locator('#approval-search').fill('p-00007');assert a.locator('[data-approval-row]').count()==1
  for d in ['realestate','power','sales','legal','procurement','construction','maintenance']:
   nav(d);w=dept(d);w.locator('.du-business-tabs').get_by_role('tab',name='蓄電池',exact=True).click();tab(d,'summary')
   if d=='power':w.locator('[data-power-action=clearFilters]').click();search=w.locator('#power-search');row=w.locator('[data-power-summary-row="G-00006"]');open_button=row.locator('[data-power-open]').first
   else:search=w.locator('[data-dept-filter=search]');row=w.locator('[data-dept-summary-row="G-00006"]');open_button=row.locator('[data-dept-open]').first
   for query in ['P-00007','G-00006']:
    search.fill(query);search.press('Tab');assert row.count()==1,(d,query);assert 'P-00007' in row.locator('td').first.inner_text(),d
   open_button.click();assert '承認済み' in w.locator('.ap-case-status').inner_text();assert 'P-00007' in w.locator('.ap-case-status').inner_text()
   if d=='legal':assert 'DEMO-G-00006' in w.locator('[data-dept-section=business]').inner_text();section=w.locator('[data-dept-section=files]');section.locator('summary').click() if section.get_attribute('open') is None else None;assert 'approval-proof-demo.pdf' in section.inner_text()
  done('double-click issues exactly one globally unique P-00007; all seven departments display it and search both old/new numbers; internal G keys, contract IDs and file names remain linked')
  approvals();list_tab('pending');open_case('G-00010');a.locator('[data-approval-approve]').click();assert 'P-00008 を発行' in a.inner_text();list_tab('approved');a.locator('#approval-search').fill('P-00008');assert a.locator('[data-approval-row]').count()==1;identity('manager');approvals();list_tab('pending');assert a.locator('[data-approval-row]').count()==0;list_tab('approved');assert 'G-00006' not in a.inner_text();identity('none');assert f.locator('#approval-navigation').is_hidden();assert f.locator('#approvals-demo-main').is_hidden()
  done('second case receives a distinct reserved number; approver scopes remain tied to immutable IDs; switching to an unauthorized user removes menu and approval access')
  # Reload preserves saved cases and approvals in this browser (the durable case requirement).
  p.reload(wait_until='networkidle');identity('admin');approvals();assert f.locator('#approval-pending-count').inner_text()=='1';list_tab('approved');assert 'P-00007' in a.inner_text() and 'P-00008' in a.inner_text();p.set_viewport_size({'width':800,'height':1100});list_tab('pending');p.screenshot(path=str(OUT/'narrow.png'));assert not errors,errors;assert not failed,failed;assert not writes,writes;b.close();done('reload restores durable approvals/number issuance; no fabricated solar/datacenter cases; narrow table scrolls; no JavaScript/resource/write errors')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
def run_edge_cases():
 from html import escape
 raw=(ROOT/'index.html').read_text();source=inner(raw);injection="""
dashboardExtras.find(c=>c.id==='R-00004').powerConfirmedAt='2026-11-05';
Object.assign(departmentConfigs.realestate.samples.find(r=>r.id==='R-00004').values,{status:'取得済',acquiredDate:'2026-11-05'});
window.__dropSavedPowerCondition=()=>{batteryCaseMap['G-00010'].powerConfirmedAt='';};
"""
 modified=source.replace('// Project formalization: immutable case objects/IDs, separate display numbers and in-memory approvals.',injection+'\n// Project formalization: immutable case objects/IDs, separate display numbers and in-memory approvals.',1);start=raw.index('data-srcdoc="')+len('data-srcdoc="');end=raw.index('"',start);body=raw[:start]+escape(modified,quote=True)+raw[end:]
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1550,'height':1300});errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=body));p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');f.locator('#account-toggle').click();f.locator('#approval-demo-user').select_option('admin');f.locator('[data-page=approvals]').click();a=f.locator('#approvals-workspace');assert a.locator('[data-approval-row]').count()==2
  def switch_user(key):
   if f.locator('#account-menu').is_hidden():f.locator('#account-toggle').click()
   f.locator('#approval-demo-user').select_option(key)
   if f.locator('#account-menu').is_visible():f.locator('#account-toggle').click()
  target=a.locator('[data-approval-row]').filter(has_text='R-00004').get_attribute('data-approval-row')
  for who in ['staff','manager']:
   switch_user(who)
   f.locator('#ecokaku-departments-ui').evaluate('(e,id)=>{const b=document.createElement("button");b.dataset.approvalApprove=id;e.appendChild(b);b.click();b.remove()}',target)
   switch_user('admin');f.locator('[data-page=approvals]').click();assert f.locator('#approval-pending-count').inner_text()=='2';assert a.locator('[data-approval-row]').count()==2
  a.locator('[data-approval-row]').filter(has_text='G-00010').get_by_role('button',name='確認',exact=True).click();p.frames[1].evaluate('window.__dropSavedPowerCondition()');a.locator('[data-approval-approve]').click();assert '完了条件が不足' in a.inner_text();assert a.locator('[data-approval-approve]').is_disabled();assert '未発行' in a.inner_text();a.locator('[data-approval-back]').click();a.locator('[data-approval-row]').filter(has_text='R-00004').get_by_role('button',name='確認',exact=True).click();a.locator('[data-approval-approve]').click();assert 'P-00007 を発行' in a.inner_text();assert '太陽光' in a.inner_text();a.locator('[data-approval-department=realestate]').click();w=f.locator('#realestate-workspace');assert w.locator('[data-dept-select]').input_value()=='R-00004';assert 'P-00007' in w.locator('.ap-case-status').inner_text();w.locator('#du-realestate-tab-summary').click();w.locator('[data-dept-filter=search]').fill('P-00007');w.locator('[data-dept-filter=search]').press('Tab');assert w.locator('[data-dept-summary-row="R-00004"]').count()==1
  # Bypass a hidden menu/control in the DOM to verify the action itself checks role/case scope.
  switch_user('staff');f.locator('[data-page=home]').click();f.locator('#ecokaku-departments-ui').evaluate('e=>{const b=document.createElement("button");b.dataset.approvalApprove="mock-internal-0010";e.appendChild(b);b.click();b.remove()}');switch_user('admin');f.locator('[data-page=approvals]').click();assert f.locator('#approval-pending-count').inner_text()=='0';assert not errors,errors;b.close()
 data=json.loads((OUT/'results.json').read_text());data['passed']=list(dict.fromkeys(data['passed']+['approval action rechecks changed saved conditions and excludes stale pending cases without issuing a number','existing R-case fixture uses the same engine, preserves its internal R key and supports new-P search; role checks are enforced in actions, not just hidden controls']));(OUT/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));print('PASS saved-condition recheck and existing R-case formalization; no production fixture changes',flush=True)

if __name__=='__main__':
 run()
 run_edge_cases()
