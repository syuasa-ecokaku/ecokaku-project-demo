"""Independent power-business views. Run: python3 tests/power_business_smoke.py"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from verified_cdn import verified_cdn
from power_mock_smoke import server

OUTPUT=Path('/tmp/ecokaku-power-business-review')

def run():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'results.json').unlink(missing_ok=True)
    passed,errors,failed,writes,navigations=[],[],[],[],[]
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1300},timezone_id='Asia/Tokyo')
        verified_cdn(page)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('requestfailed',lambda r:failed.append({'url':r.url,'error':r.failure}))
        page.on('request',lambda r:writes.append(r.method+' '+r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        page.on('framenavigated',lambda fr:navigations.append(fr.url))
        assert page.goto(url,wait_until='networkidle').status==200
        f=page.frame_locator('#codex-visualization')
        f.locator('[data-page=power]').click()
        baseline_nav=len(navigations)
        header=f.locator('.s-top').inner_html()
        sidebar=f.locator('.s-sidebar').inner_html()
        def done(name):
            passed.append(name);print('PASS',name,flush=True)
        def no_cross_business_ui():
            assert f.locator('[data-power-business=all],#power-all-cases,#power-common-table,.pw-business-progress,.pw-cross-counts').count()==0
            assert '全事業' not in f.locator('#power-workspace').inner_text()
        def business(key):
            f.locator(f'[data-power-business="{key}"]').click()
            expect(f.locator(f'[data-power-business="{key}"]')).to_have_attribute('aria-selected','true')
            assert f.locator('.pw-business-selector [aria-selected=true]').count()==1
            no_cross_business_ui()
        def tab(key):
            f.locator(f'.pw-primary-tabs [data-power-tab="{key}"]').click()
            expect(f.locator(f'#power-tab-{key}')).to_have_attribute('aria-selected','true')
            no_cross_business_ui()
        def cell(pid,key):
            return f.locator(f'[data-power-field="{key}"][data-project="{pid}"]')
        def set_value(el,value):
            if el.evaluate('(e)=>e.tagName')=='SELECT':el.select_option(value)
            else:el.fill(value)
        def section(key):
            el=f.locator('#power-section-'+key)
            if el.get_attribute('open') is None:el.locator(':scope > summary').click()
            return el
        def shot(name,target='.pw-business-selector'):
            f.locator(target).scroll_into_view_if_needed()
            page.frames[1].evaluate('document.activeElement?.blur()')
            page.screenshot(path=str(OUTPUT/name))
        no_cross_business_ui()
        expect(f.locator('[data-power-business=battery]')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-tab-summary')).to_have_attribute('aria-selected','true')
        assert f.locator('.pw-business-selector button').all_text_contents()==['蓄電池','太陽光','データセンター']
        assert f.locator('.pw-primary-tabs [role=tab]').all_text_contents()==['サマリー','データ入力','案件詳細']
        assert f.locator('[data-power-summary-row]').count()==10
        assert set(f.locator('[data-power-summary-row]').evaluate_all('(els)=>els.map(e=>e.dataset.powerSummaryRow)'))=={'P-00001','P-00002',*(f'G-{i:05d}' for i in range(3,11))}
        assert sum(int(x.inner_text().replace('件','')) for x in f.locator('[data-power-stage-count]').all())==10
        selected=f.locator('[data-power-business=battery]')
        assert selected.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(234, 244, 255)'
        assert selected.evaluate('(e)=>getComputedStyle(e).borderBottomWidth')=='3px'
        for key,icon in [('battery','battery'),('solar','solar-panel'),('datacenter','server')]:
            svg=f.locator(f'[data-power-business={key}] .pw-business-icon svg')
            expect(svg).to_have_count(1)
            expect(svg).to_have_attribute('data-lucide',icon)
            assert 18<=svg.bounding_box()['width']<=20
        assert f.locator('.pw-primary-tabs svg').count()==0
        shot('power-battery-summary.png')
        done('battery summary default; exactly three unchanged SVG tabs; existing IDs, samples and stage totals retained; cross-business UI absent')
        tab('bulk')
        for key,message in [('solar','太陽光発電の業務項目は現在整理中です。確定後に実装します。'),('datacenter','データセンターの電力申請業務項目は現在整理中です。確定後に実装します。')]:
            for mode in ['summary','bulk','detail']:
                tab(mode);business(key)
                expect(f.locator(f'#power-tab-{mode}')).to_have_attribute('aria-selected','true')
                if mode=='bulk':
                    assert f.locator('#pin-nonbattery-group').is_visible()
                    assert '基本情報・設備' in f.locator('#power-view').inner_text()
                else:assert message in f.locator(f'[data-power-placeholder={key}]').inner_text()
                assert f.locator('[data-power-field],input[type=file],.pw-section').count()==0
                business('battery')
                expect(f.locator(f'#power-tab-{mode}')).to_have_attribute('aria-selected','true')
                business(key)
            shot('power-'+key+'-placeholder.png')
        tab('bulk')
        f.locator('[data-power-business=datacenter]').focus()
        f.locator('[data-power-business=datacenter]').press('ArrowRight')
        expect(f.locator('[data-power-business=battery]')).to_have_attribute('aria-selected','true')
        f.locator('[data-power-business=battery]').press('End')
        expect(f.locator('[data-power-business=datacenter]')).to_have_attribute('aria-selected','true')
        f.locator('[data-power-business=datacenter]').press('Home')
        expect(f.locator('[data-power-business=battery]')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-tab-bulk')).to_have_attribute('aria-selected','true')
        done('all three businesses and work tabs switch without all-state; placeholders and keyboard wrapping preserve selected work tab')
        f.locator('#power-bulk-stage').select_option('main')
        set_value(cell('P-00001','57'),'8765432')
        set_value(cell('P-00001','48'),'00012345')
        set_value(cell('P-00001','owner'),'申請担当B')
        set_value(cell('P-00001','commonStatus'),'保留')
        set_value(cell('P-00001','commonDue'),'2026-12-01')
        for key in ['solar','datacenter','battery']:
            business(key)
            expect(f.locator('#power-tab-bulk')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-bulk-stage')).to_have_value('main')
        expect(cell('P-00001','57')).to_have_value('8765432')
        f.locator('[data-power-action=saveAll]').click()
        assert f.locator('.pw-errors').count()==0
        tab('detail');f.locator('#power-detail-case').select_option('0');section('main')
        expect(f.locator('#power-value-57')).to_have_value('8765432')
        expect(f.locator('#power-value-48')).to_have_value('00012345')
        section('basic')
        expect(f.locator('#power-value-owner')).to_have_value('申請担当B')
        expect(f.locator('#power-value-commonStatus')).to_have_value('保留')
        expect(f.locator('#power-value-commonDue')).to_have_value('2026-12-01')
        expect(f.locator('#power-value-14')).to_have_value('1999')
        done('battery workflow data input, common columns, leading-zero numbers, drafts and save/detail synchronization preserved')
        tab('summary')
        f.locator('#power-search').fill('P-00001');f.locator('#power-search').press('Tab')
        f.locator('[data-power-filter=owner]').select_option('申請担当B')
        assert f.locator('[data-power-summary-row]').count()==1
        business('solar');business('battery')
        expect(f.locator('#power-search')).to_have_value('P-00001')
        expect(f.locator('[data-power-filter=owner]')).to_have_value('申請担当B')
        tab('bulk');f.locator('#power-bulk-stage').select_option('connection')
        set_value(cell('P-00001','31'),'000-MENU-DRAFT')
        business('solar')
        f.locator('.s-sidebar [data-page=home]').click()
        expect(f.locator('#sales-demo-home')).to_be_visible()
        f.locator('.s-sidebar [data-page=power]').click()
        expect(f.locator('[data-power-business=battery]')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-tab-summary')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-search')).to_have_value('P-00001')
        assert f.locator('[data-power-summary-row]').count()==1
        tab('bulk')
        expect(cell('P-00001','31')).to_have_value('000-MENU-DRAFT')
        f.locator('[data-power-action=cancelAll]').click()
        expect(cell('P-00001','31')).to_have_value('DEMO-RECEIPT-P-00001')
        f.locator('[data-power-action=clearFilters]').click()
        done('search/filter state retained; menu re-entry resets only business/tab to battery/summary and preserves pending drafts')
        tab('detail');f.locator('#power-detail-case').select_option('0');section('records')
        f.locator('#power-file-settings').set_input_files({'name':'事業別保持.pdf','mimeType':'application/pdf','buffer':b'filename only'})
        section('records');f.locator('#power-task-text').fill('事業別のタスク保持確認');f.locator('#power-task-due').fill('2026-11-30')
        f.locator('[data-power-action=taskAdd]').click()
        for key in ['solar','datacenter','battery']:business(key)
        section('records')
        assert '事業別のタスク保持確認' in f.locator('#power-section-records').inner_text()
        expect(f.locator('[data-power-filename=settings]')).to_have_text('事業別保持.pdf')
        f.locator('[data-power-action=saveCase]').first.click()
        assert f.locator('.pw-errors').count()==0
        f.locator('#power-detail-case').select_option('1');section('records')
        assert '事業別のタスク保持確認' not in f.locator('#power-section-records').inner_text()
        expect(f.locator('[data-power-filename=settings]')).to_have_text('未選択')
        assert f.locator('.s-top').inner_html()==header
        assert f.locator('.s-sidebar').inner_html()==sidebar
        assert len(navigations)==baseline_nav,navigations
        done('case-specific tasks/files/history, header and sidebar retained; switching stays within the same page')
        tab('bulk');shot('power-battery-input.png')
        page.set_viewport_size({'width':390,'height':900})
        for key in ['battery','solar','datacenter']:
            business(key)
            active=f.locator('[data-power-business='+key+']')
            assert active.evaluate('(e)=>{const r=e.closest(".pw-business-selector").getBoundingClientRect(),b=e.getBoundingClientRect();return b.left>=r.left-1&&b.right<=r.right+1;}')
        shot('power-business-mobile.png')
        assert not errors,errors
        assert not failed,failed
        assert not writes,writes
        done('mobile selection stays visible; no JavaScript errors, failed resources or upload/write requests')
        result={'passed':passed,'page_errors':errors,'failed_requests':failed,'write_requests':writes}
        (OUTPUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        browser.close()

if __name__=='__main__':run()
