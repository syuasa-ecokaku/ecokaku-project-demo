"""Shared purchasing masters, historical snapshots, safe upgrade and atomic persistence.
Run: python tests/procurement_masters_smoke.py
"""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import fixture
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-procurement-masters')
INJECT='window.__mt={data:()=>pcData,masters:()=>pcmData,buffer:pcuBuffer,view:pcuView,filter:pcF,snapshot:lifecycleSnapshot,stock:pcStock,transact:lifecycleTransaction};'
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[]
 old=subprocess.check_output(['git','show','b2cc41a:index.html'],cwd=ROOT,text=True);raw=(ROOT/'index.html').read_text();body=[fixture(old,INJECT.replace('masters:()=>pcmData,',''))]
 def done(name):passed.append(name);print('PASS',name,flush=True)
 with server() as url,sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);p=browser.new_page(viewport={'width':1540,'height':1200});p.set_default_timeout(10000);p.on('pageerror',lambda e:errors.append(str(e)));p.route(url,lambda route:route.fulfill(body=body[0],content_type='text/html'));p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');m=f.locator('#procurement-workspace');s=f.locator('#settings-demo-detail')
  def api(code):return p.frames[1].evaluate(code)
  def masters():return api('()=>__mt.masters()')
  def data():return api('()=>__mt.data()')
  def wait():expect(f.locator('.lc-busy')).to_be_hidden()
  def click(action):s.locator('[data-pcm-action='+action+']').click();wait()
  def screen(kind):s.locator('[data-pcm-screen='+kind+']').click()
  def field(name):return s.locator('#pcm-form [name='+name+']')
  def fill(name,value):field(name).fill(str(value))
  def row(id):return s.locator('tbody tr').filter(has=s.locator('[data-pcm-id="'+id+'"]'))
  def rowclick(id,action):s.locator('[data-pcm-action='+action+'][data-pcm-id="'+id+'"]').click();wait()
  def cell(id,key):return m.locator('[data-pcu-col=orders][data-pcu-row="'+id+'"][data-pcu-key='+key+']')
  def purchase(biz='battery',section='prep'):
   f.locator('[data-page=procurement]').click();m.locator('[data-dept-business='+biz+']').click();m.locator('[data-pcu-tab=bulk]').click();m.locator('#pcu-section').select_option(section)
  def savepo():m.locator('[data-pcu-action=save]').click();wait()
  def settings():f.locator('[data-page=settings]').click();f.locator('[data-setting=masters]').click()
  # Persist legacy free-text data before loading the new implementation.
  purchase();cell('po-battery-1','owner').fill('旧担当者（未特定）');savepo();legacy=data();stock=api('()=>__mt.stock("battery","pile","架空第一倉庫")');others=api('()=>{const d=__mt.snapshot();delete d.procurement;return d}')
  body[0]=fixture(raw,INJECT);p.reload(wait_until='networkidle');upgraded=data()
  for col in ['lines','receipts','allocations','issues','transfers','invoices','payments','usagePlans']:assert upgraded[col]==legacy[col],col
  for before in legacy['orders']:
   after=next(o for o in upgraded['orders'] if o['id']==before['id']);assert all(after.get(k)==v for k,v in before.items())
  purchase();assert cell('po-battery-1','ownerEmployeeId').input_value()=='__legacy';assert '旧担当者' in cell('po-battery-1','ownerEmployeeId').inner_text();assert next(o for o in data()['orders'] if o['id']=='po-battery-1')['ownerEmployeeId']==''
  assert api('()=>__mt.stock("battery","pile","架空第一倉庫")')==stock
  done('previous saved orders and all ledgers survive upgrade; unknown free-text owner remains visible and unlinked')
  # Earlier purchasing versions persisted text-based section drafts. Keep the draft and align its conflict baseline.
  api('()=>__mt.transact(()=>{__mt.data().inputDrafts["po-battery-2"]={order:{owner:"旧下書きの未特定担当者",supplier:"supplier-a"},lines:{},added:[],reason:"旧区分の下書き引継ぎ"};})');wait();p.reload(wait_until='networkidle');purchase();assert cell('po-battery-2','ownerEmployeeId').input_value()=='__legacy';assert '旧下書きの未特定担当者' in cell('po-battery-2','ownerEmployeeId').inner_text();savepo();assert '保存できません' not in m.inner_text();migrated=next(o for o in data()['orders'] if o['id']=='po-battery-2');assert migrated['ownerEmployeeId']=='' and migrated['supplier']=='supplier-a' and migrated['owner']=='旧下書きの未特定担当者';assert 'po-battery-2' not in data()['inputDrafts']
  done('old persisted section drafts keep their text names and supplier choice, migrate without false conflicts, and save without guessed employee IDs')
  # Settings route and supplier validation/search/edit.
  settings();expect(f.locator('[data-setting=masters]')).to_have_text('マスター管理')
  for kind,label in [('suppliers','仕入先'),('employees','社員・担当者'),('assignees','担当者設定')]:screen(kind);assert label in s.locator('h3').first.inner_text()
  screen('suppliers');click('new');click('save');assert '仕入先コードと会社名' in s.locator('#pcm-error').inner_text();fill('code','sup-001');fill('name','重複の架空会社');click('save');assert '重複' in s.locator('#pcm-error').inner_text();fill('code','SUP-QA');fill('name','架空仕入先QA');fill('contact','窓口デモ担当');fill('email','qa@example.invalid');fill('phone','000-0000-0000');fill('memo','検証用架空データ');click('new');assert field('code').input_value()=='SUP-QA';click('save');assert '保存しました' in s.locator('#pcm-message').inner_text();supplier=next(x for x in masters()['suppliers'] if x['code']=='SUP-QA');sid=supplier['id'];s.locator('[data-pcm-filter=search]').fill('SUP-QA');expect(s.locator('tbody tr')).to_have_count(1);s.locator('[data-pcm-filter=search]').fill('');s.screenshot(path=str(OUT/'suppliers.png'))
  done('all three master screens open under settings; supplier required/duplicate checks, complete registration and code search work')
  # Employee registry is common; same names are permitted but codes are unique.
  screen('employees');click('new');click('save');assert '社員コードと氏名' in s.locator('#pcm-error').inner_text();fill('code','EMP-QA-001');fill('name','購買検証担当');fill('department','営業');click('save');e1=next(e for e in masters()['employees'] if e['code']=='EMP-QA-001');click('new');fill('code','emp-qa-001');fill('name','別の架空担当');click('save');assert '重複' in s.locator('#pcm-error').inner_text();fill('code','EMP-QA-002');fill('name','購買検証担当');fill('department','購買');click('save');e2=next(e for e in masters()['employees'] if e['code']=='EMP-QA-002');assert e1['id']!=e2['id'];s.locator('[data-pcm-filter=department]').select_option('営業');assert '購買検証担当' in s.locator('tbody').inner_text();s.locator('[data-pcm-filter=department]').select_option('');s.screenshot(path=str(OUT/'employees.png'))
  screen('assignees');click('new');field('employeeId').select_option(e1['id']);assert '営業' in s.locator('[data-pcm-employee-reference]').inner_text();assert not s.locator('#pcm-form [name=name],#pcm-form [name=department]').count();fill('sort',5);field('sort').press('Enter');wait();assignment=next(a for a in masters()['purchasingAssignees'] if a['employeeId']==e1['id']);aid=assignment['id'];click('new');field('employeeId').select_option(e1['id']);click('save');assert '登録済み' in s.locator('#pcm-error').inner_text();click('cancel');s.screenshot(path=str(OUT/'assignees.png'))
  done('employee codes/departments/duplicate names stay distinct; assignees reference employee IDs and reject duplicate assignment')
  # Round trip keeps the exact view/filter and unsaved purchase fields.
  purchase('solar');m.locator('#pcu-filters [name=search]').fill('DEMO-SOLAR-001');cell('po-solar-1','memo').fill('マスター往復でも保持');cell('po-solar-1','changeReason').fill('検証用の仕入先・担当者を選択');cell('po-solar-1','supplier').select_option(sid);cell('po-solar-1','ownerEmployeeId').select_option(e1['id']);assert cell('po-solar-1','ownerEmployeeId').locator('option').nth(1).get_attribute('value')==e1['id'];before_buffer=api('()=>__mt.buffer()');before_view=api('()=>__mt.view()');before_filter=api('()=>__mt.filter()');m.locator('[data-pcm-open=assignees]').first.click();rowclick(aid,'edit');fill('sort',3);click('save');click('return');assert api('()=>__mt.buffer()')==before_buffer;assert api('()=>__mt.view()')==before_view;assert api('()=>__mt.filter()')==before_filter;assert cell('po-solar-1','memo').input_value()=='マスター往復でも保持';savepo();assert '保存できません' not in m.inner_text();ordered=next(o for o in data()['orders'] if o['id']=='po-solar-1');assert ordered['ownerEmployeeId']==e1['id'] and ordered['owner']=='購買検証担当' and ordered['supplierNameAtOrder']=='架空仕入先QA'
  done('ordered dropdowns and inline master links preserve business/section/filters and all unsaved fields; order names are snapshotted')
  # Rename masters; historical values must not be overwritten.
  m.locator('[data-pcm-open=suppliers]').first.click();rowclick(sid,'edit');fill('name','改名後の架空仕入先QA');click('save');screen('employees');rowclick(e1['id'],'edit');fill('name','改名後の購買検証担当');fill('department','購買');click('save');screen('assignees');assert '改名後の購買検証担当' in s.locator('tbody').inner_text();click('return');after=next(o for o in data()['orders'] if o['id']=='po-solar-1');assert after==ordered;assert '架空仕入先QA' in cell('po-solar-1','supplier').inner_text() and '現在：' in cell('po-solar-1','supplier').inner_text();assert '購買検証担当' in cell('po-solar-1','ownerEmployeeId').inner_text();assert '現在：' in cell('po-solar-1','ownerEmployeeId').inner_text()
  # Employee and assignment activation are independent gates.
  m.locator('[data-pcm-open=assignees]').first.click();rowclick(aid,'toggle');click('return');assert cell('po-solar-1','ownerEmployeeId').locator('option:checked').is_disabled();assert '無効' in cell('po-solar-1','ownerEmployeeId').inner_text();m.locator('[data-pcm-open=assignees]').first.click();rowclick(aid,'toggle');screen('employees');rowclick(e1['id'],'toggle');screen('suppliers');rowclick(sid,'toggle');click('return');assert cell('po-solar-1','supplier').locator('option:checked').is_disabled();assert cell('po-solar-1','ownerEmployeeId').locator('option:checked').is_disabled();cell('po-solar-1','memo').fill('無効な過去設定でも他項目は保存可能');savepo();assert '保存できません' not in m.inner_text();assert next(o for o in data()['orders'] if o['id']=='po-solar-1')['supplier']==sid
  assert '無効' in m.locator('#pcu-filters [name=supplier] option[value="'+sid+'"]').inner_text();assert '無効' in m.locator('#pcu-filters [name=owner] option[value="'+e1['id']+'"]').inner_text();m.locator('#pcu-filters [name=owner]').select_option(e1['id']);expect(cell('po-solar-1','memo')).to_have_count(1)
  done('master renames preserve historical order names; either employee/assignment gate removes new choices; inactive history stays visible, searchable and editable')
  # New orders in all businesses use exactly the same master IDs, excluding inactive values.
  for biz in ['battery','solar','datacenter']:
   purchase(biz);m.locator('[data-pcu-action=new-order]').click();newid=api('()=>Object.keys(__mt.buffer().orders).at(-1)');assert not cell(newid,'supplier').locator('option[value="'+sid+'"]').count();assert not cell(newid,'ownerEmployeeId').locator('option[value="'+e1['id']+'"]').count();assert cell(newid,'supplier').locator('option[value=supplier-a]').count();cell(newid,'memo').fill('事業別の下書き '+biz)
  pending=api('()=>__mt.buffer()');m.locator('[data-pcm-open=suppliers]').first.click();master_before=masters();actual_before=data();click('new');fill('code','SUP-FAIL');fill('name','保存失敗確認用の架空会社');p.evaluate("()=>{window.__realSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.includes('case-lifecycle'))throw new DOMException('quota','QuotaExceededError');return window.__realSet.call(this,k,v)}}");click('save');assert '保存できません' in s.locator('#pcm-error').inner_text();assert masters()==master_before;assert data()==actual_before;assert field('code').input_value()=='SUP-FAIL';p.evaluate('()=>{Storage.prototype.setItem=window.__realSet}');click('save');assert any(x['code']=='SUP-FAIL' for x in masters()['suppliers']);click('return');assert api('()=>__mt.buffer()')==pending
  done('all three businesses share candidates; storage failure rolls back masters/orders, preserves form and purchase drafts, and retry succeeds')
  # Reload persists invalidation and does not reimport or duplicate records.
  persisted=masters();p.reload(wait_until='networkidle');assert masters()==persisted;assert not next(sup for sup in masters()['suppliers'] if sup['id']==sid)['active'];assert not next(e for e in masters()['employees'] if e['id']==e1['id'])['active'];assert api('()=>__mt.stock("battery","pile","架空第一倉庫")')==stock
  # Simulate an old text-only name matching two distinct employees: never guess an ID.
  api('()=>__mt.transact(()=>{const o=__mt.data().orders.find(o=>o.id==="po-battery-2");o.owner="購買検証担当";delete o.ownerEmployeeId;__mt.masters().employees.find(e=>e.code==="EMP-QA-001").name="購買検証担当";})');wait();p.reload(wait_until='networkidle');ambiguous=next(o for o in data()['orders'] if o['id']=='po-battery-2');assert ambiguous['owner']=='購買検証担当' and ambiguous['ownerEmployeeId']==''
  purchase();assert cell('po-battery-2','ownerEmployeeId').input_value()=='__legacy';cell('po-battery-2','memo').fill('同名未対応付けでも履歴は保持');savepo();assert '保存できません' not in m.inner_text()
  settings();screen('legacy');assert f.locator('#settings-master-kind').is_visible();f.locator('[data-setting=users]').click();assert f.locator('#settings-user-name').is_visible()
  for dept in ['sales','power','legal','realestate','construction','maintenance','home']:f.locator('[data-page='+dept+']').click()
  assert not errors,errors;browser.close();done('reload preserves masters and inactive states; ambiguous names remain unlinked; existing settings masters/users and other departments still open')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'errors':errors},ensure_ascii=False,indent=2));print('Results:',OUT)
if __name__=='__main__':run()
