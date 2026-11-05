"""Browser/data checks for the shared battery-only catalog; preserves other businesses."""
from pathlib import Path
from html.parser import HTMLParser
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from notice_snapshot import content_text

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=Path('/tmp/ecokaku-battery-shared-review')
DEPTS=['realestate','power','sales','legal','procurement','construction','maintenance']
class Inner(HTMLParser):
    value=''
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=='iframe' and d.get('id')=='codex-visualization':self.value=d['data-srcdoc']
def extract():
    p=Inner();p.feed((ROOT/'index.html').read_text());s=p.value
    return json.JSONDecoder().raw_decode(s.split('const batteryCaseSeedData=',1)[1])[0],json.JSONDecoder().raw_decode(s.split('const batteryDepartmentDefinitions=',1)[1])[0]

def run():
    OUTPUT.mkdir(exist_ok=True);cases,definitions=extract();byid={c['id']:c for c in cases}
    ids={'P-00001','P-00002',*(f'G-{i:05d}' for i in range(3,11))}
    passed=[];errors=[];writes=[];failed=[]
    def done(s):passed.append(s);print('PASS',s,flush=True)
    assert len(cases)==len(byid)==10 and set(byid)==ids
    assert len({c['phase'] for c in cases})==10
    for c in cases:
        assert c['businessId']=='battery' and c['name'].startswith('デモ') and c['common']['address'].startswith('架空')
        assert c['customer'].startswith('架空') and c['power']['values']['84'].endswith('@example.invalid')
        land=c['departments']['realestate'];build=c['departments']['construction'];power=c['power'];v=power['values']
        if c['id'].startswith('P-'):
            assert land['acquiredDate'] and c['powerConfirmedAt'] and c['formalApprovedAt']
            assert max(land['acquiredDate'],c['powerConfirmedAt'])<=c['formalApprovedAt']
        else:assert not c['formalApprovedAt'] and not build['startActual']
        for contract in c['contracts']:
            assert bool(contract['signedDate'])==(contract['state']=='締結済み')
            if contract['signedDate']:assert contract['approval']=='承認済み'
        if build['completionActual']:assert build['startActual']<=build['completionActual']<=build['inspectionActual']<=build['handoverActual']
        for record in c['records']['inspections']:
            assert record['assetId'] in [a['id'] for a in c['assets']]
            assert build['handoverActual'] and v['89'] and record['date']>=max(build['handoverActual'],v['89'])
        if v.get('102'):assert v['103']<v['102']
        if power['accounting']['26']:assert v['24']<=v['25']<=power['accounting']['26']<=v['connectionDue']
        for invoice,account,due in [('43','45','depositDue'),('56','58','burdenDue')]:
            if power['accounting'].get(account):assert v[invoice]<=power['accounting'][account]<=v[due]
    done('10 reused unique IDs, ten varied phases, formal-number conditions, fictional identities, contracts and chronological consistency')
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1550,'height':1250})
        page.on('pageerror',lambda e:errors.append(str(e)));page.on('requestfailed',lambda r:failed.append(r.url))
        page.on('request',lambda r:writes.append(r.method+' '+r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        page.goto(url,wait_until='networkidle');f=page.frame_locator('#codex-visualization')
        def nav(d):f.locator('[data-page='+d+']').click();return f.locator('#'+d+'-workspace')
        def tab(d,t):f.locator('#'+d+'-workspace .du-work-tabs').get_by_role('tab',name={'summary':'サマリー','bulk':'データ入力','detail':'案件詳細'}[t],exact=True).click()
        def cell(d,pid,k):return f.locator('#'+d+'-workspace [data-dept-case="'+pid+'"][data-dept-field="'+k+'"]')
        def action(d,key):f.locator('#'+d+'-workspace [data-dept-action='+key+']').click()
        def group(d,key):f.locator('#'+d+'-workspace [data-dept-group]').select_option(key)
        def section(d,key):
            loc=f.locator('#'+d+'-workspace [data-dept-section='+key+']')
            if loc.get_attribute('open') is None:loc.locator(':scope>summary').click()
            return loc
        def detail(d,pid):
            tab(d,'summary');f.locator('#'+d+'-workspace [data-dept-open="'+pid+'"]').first.click()
        def shot(d,t):
            f.locator('#'+d+'-workspace .du-business-tabs').scroll_into_view_if_needed();page.screenshot(path=str(OUTPUT/(d+'-'+t+'.png')))
        for d in DEPTS:
            m=nav(d)
            assert m.locator('.du-business-tabs button').all_text_contents()==['蓄電池','太陽光','データセンター']
            assert m.locator('.du-work-tabs button').all_text_contents()==['サマリー','データ入力','案件詳細']
            rows=m.locator('[data-power-summary-row]' if d=='power' else '[data-dept-summary-row]')
            observed=set(rows.evaluate_all('(rows)=>rows.map(r=>r.dataset.powerSummaryRow||r.dataset.deptSummaryRow)'))
            assert observed==ids,(d,observed)
            for row in rows.all():
                pid=row.get_attribute('data-power-summary-row' if d=='power' else 'data-dept-summary-row');assert byid[pid]['name'] in row.inner_text()
            expected={'realestate':['10','2','5','1'],'power':['10件','3件','4件','1件','1件'],'sales':['10','5','2','1','2'],'legal':['10','4','2','8'],'procurement':['10','2','1','0'],'construction':['10','1','1','0'],'maintenance':['10','2','1','1','—']}
            assert m.locator('.pw-count strong' if d=='power' else '.du-kpi strong').all_text_contents()==expected[d]
            if d=='power':
                assert m.locator('.pw-count strong').first.inner_text()=='10件'
                m.locator('[data-power-summary-row=P-00001] td button').first.click()
                basic=f.locator('#power-section-basic')
            else:
                assert m.locator('.du-kpi strong').first.inner_text()=='10'
                detail(d,'P-00001');basic=section(d,'basic')
            assert byid['P-00001']['name'] in basic.inner_text()
            assert byid['P-00001']['common']['address'] in basic.inner_text()
            tab(d,'bulk')
            r=m.locator('[data-power-bulk-row]' if d=='power' else '[data-dept-row]')
            assert r.count()==10
            assert all(50<=x.bounding_box()['height']<=54 for x in r.all())
            if d!='power':
                group(d,'common')
                for pid in ids:cell(d,pid,'owner').fill(d+'検証担当')
                assert m.locator('.du-dirty').count()==10
                cell(d,'G-00003','owner').press('Tab')
                editors=m.locator('.du-bulk-table [data-dept-field]')
                assert editors.evaluate_all('(els)=>els.includes(document.activeElement)')
                m.locator('[data-dept-filter=search]').fill('P-00001')
                action(d,'cancel');m.locator('[data-dept-filter=search]').fill('')
                for pid in ids:expect(cell(d,pid,'owner')).to_have_value(byid[pid]['departments'][d]['owner'])
            shot(d,'input')
        done('same 10 cases and common names/addresses in seven departments; 52px rows; all 60 non-power owner cells editable and cancel includes hidden rows')
        m=nav('sales');tab('sales','bulk');group('sales','common')
        cell('sales','G-00003','owner').fill('営業確認担当A');cell('sales','G-00004','owner').fill('営業確認担当B')
        m.locator('[data-dept-filter=search]').fill('P-00001');group('sales','contract');action('sales','save')
        m.locator('[data-dept-filter=search]').fill('');group('sales','common')
        expect(cell('sales','G-00003','owner')).to_have_value('営業確認担当A')
        expect(cell('sales','G-00004','owner')).to_have_value('営業確認担当B')
        assert not m.locator('.du-dirty').count()
        cell('sales','P-00001','customer').fill('架空共有確認法人（デモ）');action('sales','save')
        nav('legal');detail('legal','P-00001');assert '架空共有確認法人（デモ）' in section('legal','basic').inner_text()
        tab('legal','bulk');group('legal','sale');cell('legal','P-00001','saleAmount').fill('99900000');action('legal','save')
        nav('sales');tab('sales','bulk');group('sales','contract');expect(cell('sales','P-00001','saleAmount')).to_have_value('99900000')
        cell('sales','P-00001','saleAmount').fill('88800000')
        nav('legal');tab('legal','bulk');group('legal','sale');cell('legal','P-00001','saleAmount').fill('77700000');action('legal','save')
        nav('sales');tab('sales','bulk');group('sales','contract');action('sales','save')
        assert '他部門' in f.locator('#sales-workspace [data-dept-errors]').inner_text()
        expect(cell('sales','P-00001','saleAmount')).to_have_value('88800000')
        action('sales','cancel');expect(cell('sales','P-00001','saleAmount')).to_have_value('77700000')
        done('shared customer and contract objects update across departments; hidden multi-case save and concurrent-edit conflict preserve drafts')
        nav('realestate');tab('realestate','bulk');group('realestate','business')
        cell('realestate','G-00006','landNumber').fill('DEMO-LAND-SHARED-006');action('realestate','save')
        nav('legal');tab('legal','bulk');group('legal','land');expect(cell('legal','G-00006','landNumber')).to_have_value('DEMO-LAND-SHARED-006')
        nav('construction');tab('construction','bulk');group('construction','business')
        cell('construction','P-00002','completion').fill('2026-11-21');action('construction','save')
        nav('sales');tab('sales','bulk');group('sales','handover')
        assert '2026-11-21' in f.locator('#sales-workspace [data-dept-row=P-00002]').inner_text()
        nav('procurement');tab('procurement','bulk');group('procurement','common');cell('procurement','P-00002','owner').fill('購買確認担当')
        group('procurement','business');cell('procurement','P-00002','quantity').fill('1.5');action('procurement','save')
        assert '整数' in f.locator('#procurement-workspace [data-dept-errors]').inner_text()
        assert 'du-invalid' in cell('procurement','P-00002','quantity').get_attribute('class')
        cell('procurement','P-00002','quantity').fill('1');action('procurement','save');group('procurement','common')
        expect(cell('procurement','P-00002','owner')).to_have_value('購買確認担当')
        done('shared land contract and construction milestones; integer validation keeps unrelated edits; save clears highlights')
        nav('maintenance');tab('maintenance','bulk');group('maintenance','business')
        cell('maintenance','G-00003','inspectionDate').fill('2026-11-01');action('maintenance','save')
        assert '設備未導入' in f.locator('#maintenance-workspace [data-dept-errors]').inner_text();action('maintenance','cancel')
        cell('maintenance','P-00001','inspectionDate').fill('2026-11-04');cell('maintenance','P-00001','inspectionMemo').fill('デモ点検の追記');action('maintenance','save')
        detail('maintenance','P-00001');records=section('maintenance','events')
        assert 'CHECK-P-00001-002' in records.inner_text() and 'デモ点検の追記' in records.inner_text()
        assert records.locator('li').count()==2
        section('maintenance','files').locator('input[type=file]').set_input_files({'name':'DEMO-maintenance.pdf','mimeType':'application/pdf','buffer':b'demo'})
        assert 'DEMO-maintenance.pdf' in section('maintenance','files').inner_text()
        f.locator('#maintenance-workspace [data-dept-select]').select_option('G-00003')
        assert 'DEMO-maintenance.pdf' not in section('maintenance','files').inner_text()
        assert 'CHECK-P-00001-002' not in section('maintenance','events').inner_text()
        done('pre-installation inspection blocked; equipment and record IDs/history kept separate; files remain names only and case-specific')
        # Retained power workflow: numeric rules, missing bases/month-end calculation, tasks, attachments and point comparison.
        m=nav('power');tab('power','detail');f.locator('#power-detail-case').select_option('0')
        for key in ['basic','preparation','records']:
            el=f.locator('#power-section-'+key)
            if el.get_attribute('open') is None:el.locator(':scope>summary').click()
        count=f.locator('[data-power-field="18"]').first;count.fill('1.5');f.locator('[data-power-action=saveCase]').first.click();assert '整数' in f.locator('.pw-errors').inner_text()
        count.fill('1');f.locator('[data-power-action=saveCase]').first.click()
        assert '一致' in f.locator('#power-point-match').inner_text()
        f.locator('[data-power-field="追加3"]').fill('0000000000000000000099');f.locator('[data-power-action=saveCase]').first.click()
        assert '不一致' in f.locator('#power-point-match').inner_text()
        f.locator('#power-task-text').fill('デモの追加タスク');f.locator('#power-task-due').fill('2026-11-12');f.locator('[data-power-action=taskAdd]').click();f.locator('[data-power-action=saveCase]').first.click()
        assert 'デモの追加タスク' in f.locator('#power-section-records').inner_text()
        shot('power','detail')
        done('existing power integer validation, number comparison, task operations and save remain usable')
        # Same-window isolation matters: reload must not hide a cross-business write.
        m=nav('sales');m.locator('.du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click()
        tab('sales','detail');f.locator('#sales-detail-case').select_option('P-00001');f.locator('[data-section=contract]').click()
        assert 'サンプルエナジー株式会社' in f.locator('#sales-demo-panel').inner_text()
        assert '33,000,000' in f.locator('#sales-demo-panel').inner_text()
        f.locator('[data-section=handover]').click();assert '2026-11-13' in f.locator('#sales-demo-panel').inner_text()
        f.locator('#sales-detail-case').select_option('P-00002');assert '2026-10-23' in f.locator('#sales-demo-panel').inner_text()
        m.locator('.du-business-tabs').get_by_role('tab',name='蓄電池',exact=True).click();tab('sales','bulk');group('sales','contract')
        expect(cell('sales','P-00001','saleAmount')).to_have_value('77700000')
        done('same-window battery edits preserve solar customer, contract amount and construction dates with overlapping IDs')
        # Before/after snapshots: original non-battery fields and all three tabs must match.
        baseline_html=subprocess.check_output(['git','show','cd93477:index.html'],cwd=ROOT,text=True)
        old=browser.new_page(viewport={'width':1550,'height':1250});old.route(url,lambda route:route.fulfill(status=200,content_type='text/html',body=baseline_html))
        old.goto(url,wait_until='networkidle');old_f=old.frame_locator('#codex-visualization')
        page.reload(wait_until='networkidle')
        def snapshot(frame,d,business,t):
            frame.locator('[data-page='+d+']').click();mount=frame.locator('#'+d+'-workspace')
            mount.locator('.du-business-tabs').get_by_role('tab',name={'solar':'太陽光','datacenter':'データセンター'}[business],exact=True).click()
            mount.locator('.du-work-tabs').get_by_role('tab',name={'summary':'サマリー','bulk':'データ入力','detail':'案件詳細'}[t],exact=True).click()
            # Fix the selected legacy case to the same ID for detail comparisons.
            if t=='detail':
                select=mount.locator('#sales-detail-case,[data-dept-select]')
                if select.count():select.select_option('P-00001' if d in ['sales','legal','construction','maintenance'] else 'R-00004' if d=='realestate' else 'P-00006')
            return {'text':content_text(mount),'controls':mount.locator('input:not([type=file]),select').evaluate_all('(els)=>els.filter(e=>!e.closest(".nc-card")).map(e=>({tag:e.tagName,type:e.type,value:e.value,disabled:e.disabled,options:e.tagName==="SELECT"?[...e.options].map(o=>[o.value,o.text]):undefined}))')}
        for d in DEPTS:
            for business in ['solar','datacenter']:
                for t in ['summary','bulk','detail']:
                    a=snapshot(old_f,d,business,t);b=snapshot(f,d,business,t)
                    assert a==b,(d,business,t)
        old.close()
        done('all 42 solar/datacenter department-tab snapshots and editable values match pre-change production baseline')
        page.reload(wait_until='networkidle')
        for d in ['realestate','sales','legal','procurement','construction','maintenance']:
            nav(d);shot(d,'summary');detail(d,'P-00001');shot(d,'detail')
        page.set_viewport_size({'width':800,'height':1050});nav('sales');tab('sales','bulk');shot('sales','narrow-input')
        f.locator('[data-page=home]').click();assert f.locator('#home-kpi-list').get_attribute('data-total-count')=='10'
        f.locator('[data-page=settings]').click();f.locator('[data-setting=users]').click();assert f.locator('#settings-user-name').is_visible()
        assert not errors,errors
        assert not failed,failed
        assert not writes,writes
        done('reload resets in-memory edits; desktop/narrow screenshots; dashboard/settings preserved; no JS/resource/write errors')
        browser.close()
    (OUTPUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
