"""Real Chromium checks for the shared department adapters; accepts --department."""
from pathlib import Path
import argparse
import json
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server

OUTPUT=Path('/tmp/ecokaku-departments-review')

def run(department):
    OUTPUT.mkdir(exist_ok=True)
    passed, errors, writes=[],[],[]
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1550,'height':1250})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:writes.append(r.method+' '+r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        page.goto(url,wait_until='networkidle')
        f=page.frame_locator('#codex-visualization')
        def done(name):passed.append(name);print('PASS',department,name,flush=True)
        f.locator('[data-page='+department+']').click()
        mount=f.locator('#'+department+'-workspace')
        def tab(key):mount.locator('.du-work-tabs [data-dept-tab='+key+']').click()
        def business(key):mount.locator('[data-dept-business='+key+']').click()
        def cell(pid,key):return mount.locator('[data-dept-case="'+pid+'"][data-dept-field="'+key+'"]')
        def action(key):mount.locator('[data-dept-action='+key+']').click()
        def section(key):
            el=mount.locator('[data-dept-section='+key+']')
            if el.get_attribute('open') is None:el.locator(':scope>summary').click()
            return el
        def shot(name,target='.du-business-tabs'):
            mount.locator(target).scroll_into_view_if_needed();page.screenshot(path=str(OUTPUT/(department+'-'+name+'.png')))
        expect(mount.locator('[data-dept-business=battery]')).to_have_attribute('aria-selected','true')
        expect(mount.locator('#du-'+department+'-tab-summary')).to_have_attribute('aria-selected','true')
        assert mount.locator('.du-business-tabs button').all_text_contents()==['蓄電池','太陽光','データセンター']
        assert mount.locator('.du-work-tabs button').all_text_contents()==['サマリー','データ入力','案件詳細']
        for business_id in ['solar','datacenter','battery']:
            business(business_id)
            for work in ['summary','bulk','detail']:
                tab(work)
                expect(mount.locator('#du-'+department+'-tab-'+work)).to_have_attribute('aria-selected','true')
            tab('bulk')
        expect(mount.locator('#du-'+department+'-tab-bulk')).to_have_attribute('aria-selected','true')
        for key,icon in [('battery','battery'),('solar','solar-panel'),('datacenter','server')]:
            svg=mount.locator('[data-dept-business='+key+'] svg');expect(svg).to_have_attribute('data-lucide',icon)
            assert 18<=svg.bounding_box()['width']<=20
        if department=='legal':business('solar')
        tab('summary')
        expected=3 if department=='legal' else 10
        assert mount.locator('[data-dept-summary-row]').count()==expected
        shot('summary')
        first=mount.locator('[data-dept-summary-row]').first
        pid=first.get_attribute('data-dept-summary-row')
        first.locator('td').first.locator('button').click()
        assert mount.locator('[data-dept-select]').input_value()==pid
        assert mount.locator('[data-dept-section]').count()==6
        mount.locator('[data-dept-tab=summary]').last.click()
        done('default, all business/work tabs, SVG icons, preserved tab and case-number detail navigation')
        if department in ['legal','maintenance']:pid='P-00001'
        tab('bulk')
        rs=mount.locator('[data-dept-row]');assert rs.count()==expected
        assert all(50<=r.bounding_box()['height']<=54 for r in rs.all())
        editors=mount.locator('.du-bulk-table [data-dept-field]')
        assert all(32<=e.bounding_box()['height']<=34 for e in editors.all())
        first=editors.first;first.press('Tab');expect(editors.nth(1)).to_be_focused();editors.nth(1).press('Shift+Tab');expect(first).to_be_focused()
        if department=='legal':
            key='contract';value='SC-DEPT-REVIEW';second='date';second_value='2026-10-06'
        else:key='owner';value='共通UI確認担当';second='due';second_value='2026-11-01'
        cell(pid,key).fill(value)
        cell(pid,second).fill(second_value)
        assert 'du-dirty' in cell(pid,key).get_attribute('class')
        tab('summary');business('datacenter');business('solar' if department=='legal' else 'battery');tab('bulk')
        expect(cell(pid,key)).to_have_value(value)
        row2='P-00002' if department=='legal' else rs.nth(1).get_attribute('data-dept-row')
        if department=='legal':cell(row2,'equipment').fill('12.5')
        else:cell(row2,'owner').fill('別案件担当')
        if department=='legal':
            action('save');assert '整数' in mount.locator('[data-dept-errors]').inner_text()
            assert 'du-invalid' in cell(row2,'equipment').get_attribute('class')
            cell(row2,'equipment').fill('22000000')
        mount.locator('[data-dept-filter=search]').fill(pid)
        mount.locator('[data-dept-group]').select_option('land' if department=='legal' else 'business')
        action('save')
        assert '保存しました' in mount.locator('[data-dept-message]').inner_text()
        mount.locator('[data-dept-group]').select_option('sale' if department=='legal' else 'common')
        expect(cell(pid,key)).to_have_value(value)
        assert not mount.locator('.du-dirty').count()
        mount.locator('[data-dept-filter=search]').fill('')
        if department!='legal':expect(cell(row2,'owner')).to_have_value('別案件担当')
        done('52px rows, 34px controls, Tab/Shift+Tab; drafts across business/tab/group/search; atomic save includes hidden rows')
        cell(pid,key).fill('取消対象')
        mount.locator('[data-dept-filter=search]').fill(row2)
        action('cancel');mount.locator('[data-dept-filter=search]').fill('')
        expect(cell(pid,key)).to_have_value(value)
        mount.locator('[data-dept-group]').select_option('land' if department=='legal' else 'business')
        controls=mount.locator('.du-bulk-table [data-dept-field]')
        number=mount.locator('.du-bulk-table input[type=number]')
        if number.count():
            n=number.first;old=n.input_value();n.fill('-1');action('save')
            assert '0以上' in mount.locator('[data-dept-errors]').inner_text()
            action('cancel')
        scroll=mount.locator('.du-table-scroll');left=mount.locator('td.du-pin-id').first.bounding_box()['x']
        scroll.evaluate('(e)=>e.scrollLeft=1000')
        assert abs(mount.locator('td.du-pin-id').first.bounding_box()['x']-left)<1
        assert mount.locator('td.du-pin-name').first.bounding_box()['x']>=left+109
        tab('summary')
        if department!='legal':
            mount.locator('[data-dept-filter=owner]').select_option(value)
            assert mount.locator('[data-dept-summary-row]').count()==1
            mount.locator('[data-dept-open="'+pid+'"]').first.click()
            mount.locator('[data-dept-tab=summary]').last.click()
            expect(mount.locator('[data-dept-filter=owner]')).to_have_value(value)
            mount.locator('[data-dept-filter=owner]').select_option('')
            if department!='maintenance':
                count=int(mount.locator('[data-dept-metric=overdue] strong').inner_text());mount.locator('[data-dept-metric=overdue]').click();assert mount.locator('[data-dept-summary-row]').count()==count
                mount.locator('[data-dept-metric=""]').click()
        mount.locator('[data-dept-open="'+pid+'"]').first.click()
        section('files').locator('input[type=file]').set_input_files({'name':department+'-sample.pdf','mimeType':'application/pdf','buffer':b'demo'})
        assert department+'-sample.pdf' in section('files').inner_text()
        assert value in section('changes').inner_text()
        mount.locator('[data-dept-select]').select_option(row2)
        assert department+'-sample.pdf' not in section('files').inner_text()
        mount.locator('[data-dept-select]').select_option(pid)
        assert department+'-sample.pdf' in section('files').inner_text()
        shot('detail')
        done('cancel hidden drafts, number validation, frozen columns, filters/KPIs, per-case file names and change history')
        if department=='legal':
            section('business');f.locator('[data-legal-tab=documents]').click();f.locator('#legal-demo-history').click()
            assert '版履歴' in f.locator('#legal-demo-panel').inner_text()
            f.locator('#legal-demo-file').set_input_files({'name':'legal-old-upload.pdf','mimeType':'application/pdf','buffer':b'demo'})
            assert 'legal-old-upload.pdf' in f.locator('#legal-demo-panel').inner_text()
            for t in ['land','coordination','change','contract']:
                f.locator('[data-legal-tab='+t+']').click();assert len(f.locator('#legal-demo-panel').inner_text())>30
            expect(f.locator('#legal-demo-number')).to_have_value(value)
            f.locator('[data-open-sales=contract]').click()
            assert value in f.locator('#sales-demo-panel').inner_text()
            f.locator('[data-page=legal]').click();business('solar');tab('bulk');mount.locator('[data-dept-group]').select_option('sale')
            cell(pid,'date').fill('2026-10-09')
            f.locator('[data-page=sales]').click();f.locator('#sales-workspace .du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click();f.locator('[data-sales-open="'+pid+'"]').first.click()
            f.locator('#sales-demo-date').fill('2026-10-08');f.locator('#sales-demo-save').click()
            f.locator('[data-page=legal]').click();business('solar');tab('bulk');action('save')
            assert '他部門' in mount.locator('[data-dept-errors]').inner_text();expect(cell(pid,'date')).to_have_value('2026-10-09')
            action('cancel');expect(cell(pid,'date')).to_have_value('2026-10-08')
            done('original legal document versions/files/land/coordination/refunds; shared sales data and concurrent edit conflict')
        elif department=='maintenance':
            section('events');text=section('events').inner_text();assert '設備ID・記録ID' in text and '監視サービス未接続' in text
            assert section('events').locator('li').count()==2
            done('multiple assets per case, separate equipment/inspection IDs and explicit unimplemented monitoring')
        tab('bulk');shot('input','.du-table-scroll')
        page.set_viewport_size({'width':800,'height':1000});shot('narrow','.du-table-scroll')
        page.reload(wait_until='networkidle');f.locator('[data-page='+department+']').click()
        if department=='legal':business('solar')
        tab('bulk')
        assert cell(pid,key).input_value()!=value
        assert not errors,errors
        assert not writes,writes
        done('reload resets mock; narrow layout; no JS errors or external writes')
        browser.close()
    (OUTPUT/(department+'-results.json')).write_text(json.dumps({'passed':passed,'js_errors':errors,'writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--department',required=True);run(parser.parse_args().department)
