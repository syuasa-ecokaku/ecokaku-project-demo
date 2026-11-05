"""One reset control across departments, full filter clearing and draft preservation."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import inner
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-unified-reset-review');DEPTS=['realestate','sales','legal','procurement','construction','maintenance']
def run():
 OUT.mkdir(exist_ok=True);passed=[];errors=[];failed=[];writes=[]
 raw=(ROOT/'index.html').read_text();base=subprocess.check_output(['git','show','3e1405b:index.html'],cwd=ROOT,text=True)
 for name in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
  read=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+name+'=',1)[1])[0]
  assert read(raw)==read(base)
 assert 'KPIの絞り込みを解除' not in inner(raw)
 def done(s):passed.append(s);print('PASS',s,flush=True)
 with server() as url,sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1550,'height':1350});p.on('pageerror',lambda e:errors.append(str(e)));p.on('requestfailed',lambda r:failed.append(r.url));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization')
  def nav(d):f.locator('[data-page='+d+']').click()
  def w(d):return f.locator('#'+d+'-workspace')
  def tab(d,t):w(d).locator('.du-work-tabs').get_by_role('tab',name={'summary':'サマリー','bulk':'データ入力','detail':'案件詳細'}[t],exact=True).click()
  def business(d,key):w(d).locator('.du-business-tabs').get_by_role('tab',name=key,exact=True).click()
  def clear(d):w(d).locator('#dept-clear-'+d).click()
  def one(m):assert m.get_by_role('button',name='絞り込みを解除',exact=True).count()==1;assert m.locator('[data-dept-metric=""]').count()==0;assert m.get_by_role('button',name='KPIの絞り込みを解除',exact=True).count()==0
  def unselected(m):assert m.locator('.du-kpis [aria-pressed=true],.sl-kpis [aria-pressed=true],.pw-counts .is-selected').count()==0
  def ids(d,t):
   m=w(d)
   if t=='detail':return m.locator('[data-dept-select] option').evaluate_all('(es)=>es.map(e=>e.value)')
   if d=='sales' and m.locator('#sales-search').count():return m.locator('#sales-demo-cases tr').count() if t=='summary' else m.locator('[data-sales-row]').count()
   return m.locator('[data-dept-summary-row]' if t=='summary' else '[data-dept-row]').count()
  seen=0
  for d in DEPTS:
   nav(d)
   for business_name in ['蓄電池','太陽光','データセンター']:
    business(d,business_name)
    for t in ['summary','bulk']+(['detail'] if d=='realestate' else []):
     tab(d,t);m=w(d);clear(d);initial=ids(d,t);one(m)
     if t=='summary':
      cards=m.locator('[data-dept-metric]:not(:disabled),[data-sales-metric]:not(:disabled)')
      if cards.count():cards.first.click();one(m)
     m.locator('#dept-keyword-'+d).fill('NO-MATCH-RESET');search=m.locator('#sales-search' if m.locator('#sales-search').count() else '[data-dept-filter=search]');search.fill('G-00004');search.press('Tab')
     for select in m.locator('.du-keyword-filters select').all():
      if not select.is_disabled() and select.locator('option').count()>1:select.select_option(index=1)
     for date in m.locator('.du-keyword-filters input[type=date]').all():
      if not date.is_disabled():date.fill('2026-01-01');date.press('Tab')
     clear(d);one(m);unselected(m);assert ids(d,t)==initial,(d,business_name,t,ids(d,t),initial);assert m.locator('#dept-keyword-'+d).input_value()=='' and search.input_value()==''
     for select in m.locator('.du-keyword-filters select').all():assert select.input_value()==(select.evaluate('(e)=>e.options[0].value') if select.is_disabled() else 'id' if select.get_attribute('data-dept-filter')=='sort' or select.get_attribute('id')=='sales-sort' else ''),(d,select.input_value())
     for date in m.locator('.du-keyword-filters input[type=date]').all():assert date.input_value()==''
     assert m.locator('#dept-clear-'+d).evaluate('(e)=>e===document.activeElement');seen+=1
  assert seen==39;done('all 39 generic/legacy search areas across six departments and three businesses have exactly one reset, even after KPI clicks; one action clears search/keyword/owner/status/date/KPI/sort and selected styling, restoring scoped cases')
  for d in DEPTS:
   nav(d);business(d,'蓄電池');tab(d,'bulk');m=w(d);clear(d)
   if m.locator('[data-dept-group]').count():m.locator('[data-dept-group]').select_option('common')
   cell=m.locator('[data-dept-case="G-00004"][data-dept-field=owner]');original=cell.input_value();draft='UNSAVED-RESET-'+d;cell.fill(draft);tab(d,'summary');m.locator('[data-dept-metric]:not(:disabled)').first.click();m.locator('#dept-keyword-'+d).fill('NO-MATCH');clear(d);assert m.locator('[data-dept-summary-row]').count()==10;unselected(m);one(m);tab(d,'bulk');assert cell.input_value()==draft and 'du-dirty' in (cell.get_attribute('class') or '');m.locator('[data-dept-action=cancel]').click();assert cell.input_value()==original
  done('six department drafts survive KPI/search/reset and view changes without being saved; cancel still restores original saved values')
  nav('power');m=w('power');tab('power','bulk');m.locator('[data-power-action=clearFilters]').click();m.locator('#power-bulk-stage').select_option('connection');cell=m.locator('[data-power-bulk-row="G-00004"] [data-power-field="31"]');original=cell.input_value();cell.fill('UNSAVED-POWER-RESET');tab('power','summary')
  for key,value in [('owner','申請担当A'),('broker','missing'),('stage','1'),('equipment','高圧蓄電池'),('sort','number')]:m.locator('#power-summary-'+key).select_option(value)
  m.locator('#power-search').fill('G-00004');m.locator('#power-summary-keyword').fill('NO-MATCH');m.locator('[data-power-card=payment]').click();one(m);assert m.locator('[data-power-summary-row]').count()==0;m.locator('[data-power-action=clearFilters]').click();one(m);unselected(m);assert m.locator('[data-power-summary-row]').count()==10;assert m.locator('[data-power-card=""] strong').inner_text()=='10件';assert sum(int(x.inner_text().replace('件','')) for x in m.locator('[data-power-stage-count]').all())==10
  for key in ['owner','broker','stage','equipment']:assert m.locator('#power-summary-'+key).input_value()==''
  assert m.locator('#power-search').input_value()=='' and m.locator('#power-summary-keyword').input_value()=='' and m.locator('#power-summary-sort').input_value()=='progress';m.locator('[data-power-card=""]').click();assert m.locator('.pw-counts .is-selected').count()==1;m.locator('[data-power-action=clearFilters]').click();unselected(m)
  # A bulk reset clears summary-only hidden criteria and the independent input-stage criterion too.
  m.locator('#power-summary-broker').select_option('missing');m.locator('#power-summary-equipment').select_option('低圧蓄電池');m.locator('#power-summary-keyword').fill('NO-MATCH');m.locator('[data-power-card=answer]').click();tab('power','bulk');m.locator('#power-input-current-stage').select_option('market');m.locator('[data-power-filter=kind]').select_option('蓄電池');m.locator('[data-power-action=clearFilters]').click();assert m.locator('#power-input-current-stage').input_value()=='' and m.locator('[data-power-filter=kind]').input_value()=='';assert m.locator('[data-power-bulk-row]').count()==10;assert cell.input_value()=='UNSAVED-POWER-RESET';tab('power','summary');assert m.locator('#power-summary-keyword').input_value()=='' and m.locator('#power-summary-broker').input_value()=='' and m.locator('#power-summary-equipment').input_value()=='';assert m.locator('[data-power-summary-row]').count()==10;unselected(m);tab('power','bulk');m.locator('[data-power-action=cancelAll]').click();assert cell.input_value()==original;seen+=2
  done('power summary and bulk reset every visible/hidden criterion, current-stage types and KPI selection while preserving unsaved fields; all 10 cases/counts return; selecting the all-KPI then resetting leaves no selection')
  # Repeated card clicks never recreate a footer reset; reset stays within current business.
  nav('sales');business('sales','太陽光');tab('sales','summary');m=w('sales');m.locator('#dept-keyword-sales').fill('SOLAR-REMEMBER');business('sales','蓄電池');tab('sales','summary');clear('sales')
  for card in m.locator('[data-dept-metric]:not(:disabled)').all():
   key=card.get_attribute('data-dept-metric');m.locator('[data-dept-metric="'+key+'"]').click();one(m);clear('sales');one(m)
  business('sales','太陽光');tab('sales','summary');assert m.locator('#dept-keyword-sales').input_value()=='SOLAR-REMEMBER';clear('sales');p.reload(wait_until='networkidle');nav('sales');business('sales','太陽光');tab('sales','summary');clear('sales');p.screenshot(path=str(OUT/'sales-reset.png'));nav('realestate');business('realestate','蓄電池');tab('realestate','summary');m=w('realestate');m.locator('[data-dept-metric=acquiring]').click();one(m);p.screenshot(path=str(OUT/'realestate-kpi-active.png'));clear('realestate');p.screenshot(path=str(OUT/'realestate-reset.png'));nav('power');tab('power','summary');m=w('power');m.locator('[data-power-action=clearFilters]').click();p.screenshot(path=str(OUT/'power-reset.png'));assert seen==41 and not errors and not failed and not writes,(seen,errors,failed,writes);b.close();done('41 applicable screens verified; repeated KPI interactions do not recreate duplicate buttons; reset retains department/business and leaves other-business conditions intact; no JS/resource/write errors')
 (OUT/'results.json').write_text(json.dumps({'passed':passed,'areas':seen,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
