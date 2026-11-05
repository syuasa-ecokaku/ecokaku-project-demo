"""Cross-department isolation and shared-contract/milestone regression checks."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server

OUT=Path('/tmp/ecokaku-departments-review')

def run():
    OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[];failed=[]
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1500,'height':1200})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('requestfailed',lambda r:failed.append(r.url))
        page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        page.goto(url,wait_until='networkidle');f=page.frame_locator('#codex-visualization')
        header=f.locator('.s-top').inner_html();home=f.locator('#sales-demo-home').inner_text()
        new=['realestate','legal','procurement','construction','maintenance']
        def nav(d):f.locator('[data-page='+d+']').click()
        def cell(d,pid,k):return f.locator('#'+d+'-workspace [data-dept-case="'+pid+'"][data-dept-field="'+k+'"]')
        def bulk(d,business='battery'):
            nav(d);f.locator('#'+d+'-workspace [data-dept-business='+business+']').click();f.locator('#'+d+'-workspace .du-work-tabs [data-dept-tab=bulk]').click()
        def done(s):passed.append(s);print('PASS',s,flush=True)
        assert f.locator('.s-sidebar [data-page]').all_text_contents()[1:8]==['01不動産開発','02電力申請','03営業','04法務','05購買','06工事','07メンテナンス']
        for d in ['realestate','power','sales','legal','procurement','construction','maintenance']:
            nav(d);workspace=f.locator('#'+d+'-workspace')
            assert workspace.locator('.du-business-tabs button').all_text_contents()==['蓄電池','太陽光','データセンター']
            assert workspace.locator('.du-work-tabs button').all_text_contents()==['サマリー','データ入力','案件詳細']
            expect(workspace.locator('.du-business-tabs [aria-selected=true]')).to_have_text('蓄電池')
            expect(workspace.locator('.du-work-tabs [aria-selected=true]')).to_have_text('サマリー')
            assert f.locator('.s-top').inner_html()==header
            assert f.locator('#'+d+'-demo-main').is_visible()
            if d=='power':
                assert workspace.locator('[data-power-summary-row]').count()==10
                workspace.locator('[data-power-summary-row=P-00001] td').first.locator('button').click()
                expect(f.locator('#power-detail-case')).to_have_value('0')
            elif d=='sales':
                workspace.locator('.du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click()
                workspace.locator('#sales-demo-cases tr').filter(has_text='P-00001').locator('td').first.locator('button').click()
                assert f.locator('[data-sales-standard-section]').count()==6
        done('all seven sidebar routes, identical business/work tabs, defaults, preserved header and case IDs/details')
        for d in ['realestate','procurement','construction','maintenance']:
            bulk(d);cell(d,'G-00004','owner').fill(d+'独立下書き')
        bulk('legal','solar');cell('legal','P-00001','contract').fill('SC-ISOLATION-DRAFT')
        nav('sales');f.locator('#sales-workspace .du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click();f.locator('.sl-work-tabs [data-sales-tab=bulk]').click()
        f.locator('[data-sales-project=P-00001][data-sales-field=customer]').fill('営業独立下書き')
        nav('power');f.locator('.pw-primary-tabs [data-power-tab=bulk]').click()
        f.locator('[data-power-field=owner][data-project=G-00004]').select_option('申請担当A')
        for d in ['realestate','procurement','construction','maintenance']:
            bulk(d);expect(cell(d,'G-00004','owner')).to_have_value(d+'独立下書き')
            if d=='procurement':f.locator('#procurement-workspace [data-dept-action=save]').click()
            if d=='realestate':f.locator('#realestate-workspace [data-dept-action=cancel]').click()
        bulk('realestate');expect(cell('realestate','G-00004','owner')).to_have_value('不動産デモ担当B')
        bulk('procurement');expect(cell('procurement','G-00004','owner')).to_have_value('procurement独立下書き')
        assert f.locator('#procurement-workspace .du-dirty').count()==0
        bulk('construction');assert f.locator('#construction-workspace .du-dirty').count()==1
        bulk('legal','solar');expect(cell('legal','P-00001','contract')).to_have_value('SC-ISOLATION-DRAFT')
        nav('sales');f.locator('#sales-workspace .du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click();f.locator('.sl-work-tabs [data-sales-tab=bulk]').click()
        expect(f.locator('[data-sales-project=P-00001][data-sales-field=customer]')).to_have_value('営業独立下書き')
        nav('power');f.locator('.pw-primary-tabs [data-power-tab=bulk]').click()
        expect(f.locator('[data-power-field=owner][data-project=G-00004]')).to_have_value('申請担当A')
        done('same case IDs across departments have isolated drafts, saves and cancels; sales and power drafts retained')
        bulk('construction','solar');f.locator('#construction-workspace [data-dept-group]').select_option('business')
        cell('construction','P-00001','completion').fill('2026-11-16')
        f.locator('#construction-workspace [data-dept-action=save]').click()
        nav('sales');f.locator('#sales-workspace .du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click();f.locator('[data-sales-open=P-00001]').first.click()
        f.locator('[data-section=handover]').click();assert '2026-11-16' in f.locator('#sales-demo-panel').inner_text()
        nav('legal');f.locator('#legal-workspace [data-dept-business=solar]').click();f.locator('#legal-workspace [data-dept-open=P-00001]').first.click();f.locator('[data-legal-tab=coordination]').click()
        assert '2026-11-16' in f.locator('#legal-demo-panel').inner_text()
        done('explicitly shared construction planned milestones remain consistent in sales and legal')
        bulk('maintenance');f.locator('#maintenance-workspace [data-dept-group]').select_option('business')
        cell('maintenance','P-00001','inspectionDate').fill('2026-11-04')
        cell('maintenance','P-00001','inspectionMemo').fill('代表設備の点検更新')
        f.locator('#maintenance-workspace [data-dept-action=save]').click()
        f.locator('#maintenance-workspace [data-dept-open=P-00001]').first.click()
        events=f.locator('#maintenance-workspace [data-dept-section=events]');events.locator('summary').click()
        assert 'CHECK-P-00001-002' in events.inner_text() and '代表設備の点検更新' in events.inner_text()
        f.locator('#maintenance-workspace [data-dept-select]').select_option('G-00005')
        events=f.locator('#maintenance-workspace [data-dept-section=events]');events.locator('summary').click()
        assert 'CHECK-P-00001-002' not in events.inner_text()
        done('maintenance saves generate separate inspection record IDs, without contaminating other cases/equipment')
        nav('home');assert f.locator('#sales-demo-home h2').is_visible()
        assert f.locator('[data-home-ring-total]').inner_text()=='10'
        nav('settings');f.locator('[data-setting=users]').click();assert f.locator('#settings-user-name').is_visible()
        assert not errors,errors
        assert not writes,writes
        assert not failed,failed
        done('dashboard/settings retained; no JavaScript errors, failed resources, writes or uploads')
        browser.close()
    (OUT/'integration-results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'writes':writes,'failed_resources':failed},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
