"""Business-selector browser checks. Run: python3 tests/power_business_smoke.py"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from power_mock_smoke import server

OUTPUT=Path('/tmp/ecokaku-power-business-review')

def run():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'results.json').unlink(missing_ok=True)
    passed,errors,failed,writes,navigations=[],[],[],[],[]
    with server() as url,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1300},timezone_id='Asia/Tokyo')
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
        def business(key):
            f.locator(f'[data-power-business="{key}"]').click()
            expect(f.locator(f'[data-power-business="{key}"]')).to_have_attribute('aria-selected','true')
            assert f.locator('.pw-business-selector [aria-selected=true]').count()==1
        def tab(key):
            f.locator(f'.pw-primary-tabs [data-power-tab="{key}"]').click()
            expect(f.locator(f'#power-tab-{key}')).to_have_attribute('aria-selected','true')
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
        expect(f.locator('[data-power-business=all]')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-tab-summary')).to_have_attribute('aria-selected','true')
        assert f.locator('.pw-business-selector button').all_text_contents()==['全事業','蓄電池','太陽光','データセンター']
        assert f.locator('.pw-primary-tabs [role=tab]').all_text_contents()==['サマリー','一括入力','詳細管理']
        selected=f.locator('[data-power-business=all]')
        assert selected.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(234, 244, 255)'
        assert selected.evaluate('(e)=>getComputedStyle(e).color')=='rgb(22, 95, 159)'
        assert selected.evaluate('(e)=>getComputedStyle(e).borderBottomWidth')=='3px'
        for key,icon in [('all','layout-grid'),('battery','battery'),('solar','solar-panel'),('datacenter','server')]:
            button=f.locator(f'[data-power-business={key}]')
            svg=button.locator('.pw-business-icon svg')
            expect(svg).to_have_count(1)
            expect(svg).to_have_attribute('data-lucide',icon)
            assert 18<=svg.bounding_box()['width']<=20
            assert button.locator('.pw-business-icon').get_attribute('aria-hidden')=='true'
        assert f.locator('.pw-primary-tabs svg, .pw-primary-tabs [data-lucide]').count()==0
        assert f.locator('.pw-business-selector').evaluate('(e)=>e.compareDocumentPosition(document.querySelector(".pw-primary-tabs")) & Node.DOCUMENT_POSITION_FOLLOWING')
        assert f.locator('.pw-primary-tabs').evaluate('(e)=>e.compareDocumentPosition(document.querySelector(".pw-demo-note")) & Node.DOCUMENT_POSITION_FOLLOWING')
        selected.focus();selected.press('End')
        expect(f.locator('[data-power-business=datacenter]')).to_have_attribute('aria-selected','true')
        f.locator('[data-power-business=datacenter]').press('ArrowRight')
        expect(f.locator('[data-power-business=all]')).to_have_attribute('aria-selected','true')
        f.locator('[data-power-business=all]').press('ArrowLeft')
        expect(f.locator('[data-power-business=datacenter]')).to_have_attribute('aria-selected','true')
        f.locator('[data-power-business=datacenter]').press('Home')
        expect(f.locator('[data-power-business=all]')).to_have_attribute('aria-selected','true')
        done('four unified SVG icons, blue underline, text-only secondary tabs, layout order and keyboard navigation')
        assert 'Meiryo' in f.locator('#power-demo-main').evaluate('(e)=>getComputedStyle(e).fontFamily')
        assert f.locator('[data-power-cross-kpi=total]').get_attribute('data-count')=='3'
        assert f.locator('[data-power-all-row]').count()==3
        for key in ['solar','datacenter']:
            assert f.locator(f'[data-power-business-progress={key}] td').all_text_contents()==['—']*4
        assert f.locator('[data-power-business-progress=battery] [data-metric=total]').inner_text()=='3'
        assert f.locator('#power-all-cases [data-business=battery]').count()==3
        shot('power-all-summary.png')
        done('all-business summary default, distinct controls/colors/font, registered-only totals and unknown business counts')
        for key,message in [('solar','太陽光発電の業務項目は現在整理中です。確定後に実装します。'),('datacenter','データセンターの電力申請業務項目は現在整理中です。確定後に実装します。')]:
            for mode in ['summary','bulk','detail']:
                tab(mode);business(key)
                expect(f.locator(f'#power-tab-{mode}')).to_have_attribute('aria-selected','true')
                assert message in f.locator(f'[data-power-placeholder={key}]').inner_text()
                assert f.locator('[data-power-field], input[type=file], .pw-section').count()==0
                business('all')
                expect(f.locator(f'#power-tab-{mode}')).to_have_attribute('aria-selected','true')
                business(key)
                expect(f.locator(f'#power-tab-{mode}')).to_have_attribute('aria-selected','true')
            shot('power-'+key+'-placeholder.png')
        done('solar/datacenter placeholders in all three tabs; business changes preserve selected tab without invented forms')
        business('battery');tab('bulk')
        f.locator('#power-bulk-stage').select_option('connection')
        set_value(cell('P-00001','31'),'000-BUSINESS-DRAFT')
        set_value(cell('P-00001','34'),'1.5')
        assert cell('P-00001','31').input_value()=='000-BUSINESS-DRAFT'
        for key in ['solar','datacenter','all','battery']:
            business(key)
            expect(f.locator('#power-tab-bulk')).to_have_attribute('aria-selected','true')
        expect(cell('P-00001','31')).to_have_value('000-BUSINESS-DRAFT')
        expect(cell('P-00001','34')).to_have_value('1.5')
        business('all')
        assert f.locator('#power-bulk-stage').count()==0
        assert set(f.locator('[data-power-field]').evaluate_all('(els)=>els.map(e=>e.dataset.powerField)'))=={'owner','commonStatus','commonDue'}
        assert f.locator('[data-power-field="24"], input[type=file]').count()==0
        set_value(cell('P-00001','owner'),'申請担当B')
        set_value(cell('P-00001','commonStatus'),'完了')
        set_value(cell('P-00001','commonDue'),'2026-11-12')
        expect(f.locator('.pw-draft-count')).to_contain_text('3件')
        f.locator('[data-power-action=saveCommon]').click()
        assert f.locator('.pw-errors').count()==0
        expect(f.locator('.pw-draft-count')).to_contain_text('0件')
        tab('summary')
        expect(f.locator('[data-power-all-row=P-00001]')).to_contain_text('完了')
        assert f.locator('[data-power-cross-kpi=active]').get_attribute('data-count')=='2'
        business('battery');tab('bulk')
        expect(cell('P-00001','31')).to_have_value('000-BUSINESS-DRAFT')
        expect(cell('P-00001','34')).to_have_value('1.5')
        expect(cell('P-00001','owner')).to_have_value('申請担当B')
        expect(cell('P-00001','commonStatus')).to_have_value('完了')
        f.locator('[data-power-action=saveAll]').click()
        assert '整数' in f.locator('.pw-errors').inner_text()
        set_value(cell('P-00001','34'),'3')
        f.locator('[data-power-action=saveAll]').click()
        assert f.locator('.pw-errors').count()==0
        expect(cell('P-00001','31')).to_have_value('000-BUSINESS-DRAFT')
        business('all');tab('summary')
        assert f.locator('[data-power-cross-kpi=active]').get_attribute('data-count')=='2'
        done('business switching preserves battery drafts; common save excludes invalid business-specific drafts and prevents stale overwrites')
        business('battery');tab('bulk')
        set_value(cell('P-00001','31'),'000-KEEP-ON-CANCEL')
        business('all')
        set_value(cell('P-00001','owner'),'未割当')
        f.locator('[data-power-action=cancelCommon]').click()
        expect(cell('P-00001','owner')).to_have_value('申請担当B')
        business('battery')
        expect(cell('P-00001','31')).to_have_value('000-KEEP-ON-CANCEL')
        f.locator('[data-power-action=cancelAll]').click()
        expect(cell('P-00001','31')).to_have_value('000-BUSINESS-DRAFT')
        tab('detail');f.locator('#power-detail-case').select_option('0');section('records')
        f.locator('#power-file-settings').set_input_files({'name':'事業切替テスト.pdf','mimeType':'application/pdf','buffer':b'filename only'})
        section('records');f.locator('#power-task-text').fill('事業切替後も保持するタスク');f.locator('#power-task-due').fill('2026-11-30')
        f.locator('[data-power-action=taskAdd]').click()
        for key in ['solar','datacenter','all','battery']:business(key)
        section('records')
        assert '事業切替後も保持するタスク' in f.locator('#power-section-records').inner_text()
        expect(f.locator('[data-power-filename=settings]')).to_have_text('事業切替テスト.pdf')
        f.locator('[data-power-action=saveCase]').first.click()
        assert f.locator('.pw-errors').count()==0
        business('all')
        f.locator('[data-power-all-row=P-00001] [data-power-business-detail=battery]').click()
        expect(f.locator('[data-power-business=battery]')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-tab-detail')).to_have_attribute('aria-selected','true')
        expect(f.locator('#power-detail-case')).to_have_value('0')
        done('common cancel preserves specific drafts; task/file drafts and saved data survive every business; cross-business detail links work')
        assert len(navigations)==baseline_nav, navigations
        assert f.locator('.s-top').inner_html()==header
        assert f.locator('.s-sidebar').inner_html()==sidebar
        done('business/tab switches never navigate or reload; header and side menu unchanged')
        business('all');tab('bulk');shot('power-all-common-bulk.png')
        page.set_viewport_size({'width':390,'height':900})
        assert f.locator('.pw-business-selector').evaluate('(e)=>e.scrollWidth>e.clientWidth')
        y_positions=f.locator('.pw-business-selector button').evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().y)')
        assert max(y_positions)-min(y_positions)<2
        for key in ['all','battery','solar','datacenter']:
            business(key)
            active=f.locator('[data-power-business='+key+']')
            assert active.is_visible()
            assert active.evaluate('(e)=>{const r=e.closest(".pw-business-selector").getBoundingClientRect(),b=e.getBoundingClientRect();return b.left>=r.left-1&&b.right<=r.right+1;}')
        shot('power-business-mobile.png')
        assert not errors,errors
        assert not failed,failed
        assert not writes,writes
        done('mobile controls usable; no JavaScript errors, failed resources or upload/write requests')
        result={'passed':passed,'page_errors':errors,'failed_requests':failed,'write_requests':writes}
        (OUTPUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        browser.close()

if __name__=='__main__':run()
