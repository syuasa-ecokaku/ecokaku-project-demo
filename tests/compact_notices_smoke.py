"""Compact notice rows, complete detail, state/scroll/focus restoration and safe navigation."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from department_notices_smoke import inner,fixture
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-compact-notices-review');DEPTS=['realestate','power','sales','legal','procurement','construction','maintenance']
def run():
    OUT.mkdir(exist_ok=True);passed=[];errors=[];writes=[];failed=[];heights=[]
    raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','f816545:index.html'],cwd=ROOT,text=True)
    for var in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
        get=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+var+'=',1)[1])[0]
        assert get(raw)==get(baseline)
    def engine_function(text,name):
        source=inner(text);start=source.index(' function '+name+'(');end=source.index('\n function ',start+1);return source[start:end]
    for name in ['visible','related','list','rank','emit','snapshot','publishChanges','transactionAround','seed']:
        assert engine_function(raw,name)==engine_function(baseline,name),name
    def done(s):passed.append(s);print('PASS',s,flush=True)
    with server() as url,sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1550,'height':1250});p.on('pageerror',lambda e:errors.append(str(e)));p.on('requestfailed',lambda r:failed.append(r.url));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None);p.add_init_script("Notification.requestPermission=()=>{throw Error('Unexpected permission request');};")
        p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');dialog=f.locator('.nc-dialog');old=b.new_page(viewport={'width':1550,'height':1250});old.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=baseline));old.goto(url,wait_until='networkidle');of=old.frame_locator('#codex-visualization')
        def nav(fr,d):fr.locator('[data-page='+d+']').click();return fr.locator('#'+d+'-workspace')
        def biz(m,name):m.locator('.du-business-tabs').get_by_role('tab',name=name,exact=True).click()
        def card(m):return m.locator('.nc-card')
        def rows(m):return card(m).locator('.nc-row')
        def unread(m):return int(card(m).locator('.nc-unread-count').inner_text())
        def cat(m,key):card(m).locator('[data-notice-category='+key+']').click()
        def profile(m,key):card(m).locator('[data-notice-info]').click();dialog.locator('[data-notice-user]').select_option(key)
        def scroll():return {'parent':p.evaluate('({x:scrollX,y:scrollY})'),'frame':f.locator('html').evaluate('(e)=>({x:scrollX,y:scrollY})')}
        def expect_scroll(saved):
            p.wait_for_timeout(100);now=scroll()
            for key in saved:
                for axis in ['x','y']:assert abs(now[key][axis]-saved[key][axis])<=2,(saved,now)
        def screenshot(name,m=None):
            if m:card(m).scroll_into_view_if_needed()
            p.screenshot(path=str(OUT/name))
        for d in DEPTS:
            m=nav(f,d);om=nav(of,d)
            for business in ['蓄電池','太陽光','データセンター']:
                biz(m,business);biz(om,business);c=card(m);assert c.count()==1;assert rows(m).count()<=5
                assert rows(m).evaluate_all('(es)=>es.every(e=>e.tagName==="BUTTON"&&e.type==="button"&&!e.querySelector("button,a,input"))')
                assert rows(m).evaluate_all('(es)=>es.every(e=>e.children.length===6&&e.scrollWidth<=e.clientWidth+1&&e.getBoundingClientRect().height>=40&&e.getBoundingClientRect().height<=44)')
                assert not c.locator('.nc-subtype,.nc-case,.nc-meta,.nc-demo,.nc-body').count()
                assert not c.locator('.nc-rows').evaluate('(e)=>["auto","scroll"].includes(getComputedStyle(e).overflowY)')
                assert c.locator('.nc-row .nc-detail').count()==0
                ids=lambda mount:mount.locator('.nc-row').evaluate_all('(es)=>es.map(e=>[e.dataset.noticeId,e.dataset.unread])')
                assert ids(m)==ids(om) and unread(m)==int(card(om).locator('.nc-unread-count').inner_text())
                kpis='.du-kpis,.sl-kpis,.pw-counts';assert m.locator(kpis).all_inner_texts()==om.locator(kpis).all_inner_texts()
                if rows(m).count()==5:
                    height=c.bounding_box()['height'];heights.append(height);assert 280<=height<=320,(d,business,height)
                else:assert c.bounding_box()['height']<280
            assert not f.locator('.nc-toast').count()
        done('all 18 required summaries plus maintenance preserve KPI values, notice order/scope/counts; single 42px rows; five-row height 280–320px; no inner scroll')
        m=nav(f,'power');initial=unread(m);cat(m,'progress');assert unread(m)==initial
        row=rows(m).first;notice_id=row.get_attribute('data-notice-id');row.scroll_into_view_if_needed();saved=scroll();row.locator('.nc-category').click()
        assert unread(m)==initial-1 and '要対応' in dialog.inner_text();text=dialog.inner_text()
        for expected in ['ステータス変更','優先度：通常','P-00002','デモ第02蓄電所','発信部門','2026-11-04 14:00:00','日本時間','2026-11-06']:assert expected in text,expected
        assert dialog.locator('[data-notice-navigate]').count()==1;screenshot('notification-detail.png')
        p.keyboard.press('Escape');expect(dialog).not_to_be_visible();restored=card(m).locator('[data-notice-id='+notice_id+']');assert restored.evaluate('(e)=>document.activeElement===e');expect_scroll(saved)
        assert restored.get_attribute('data-unread')=='false' and '要対応' in restored.inner_text();assert restored.locator('.nc-category').evaluate('(e)=>getComputedStyle(e).color')=='rgb(21, 128, 61)'
        expect(card(m).locator('[data-notice-category=progress]')).to_have_attribute('aria-pressed','true')
        restored.press('Space');expect(dialog).to_be_visible();p.keyboard.press('Escape');restored.press('Enter');expect(dialog).to_be_visible();dialog.locator('[data-notice-close]').click();expect_scroll(saved)
        done('whole-row/category clicks and Enter/Space open complete details; reads stay separate from actions; Esc/close restores the same row, context, filter and scroll')
        cat(m,'all');card(m).locator('[data-notice-filter=unread]').check();card(m).locator('[data-notice-filter=action]').check();assert rows(m).count()==1;row=rows(m).first;row.click();p.keyboard.press('Escape');assert rows(m).count()==0;assert card(m).locator('[data-notice-filter=unread]').is_checked() and card(m).locator('[data-notice-filter=action]').is_checked();assert card(m).locator('[data-notice-category=all]').evaluate('(e)=>e===document.activeElement')
        assert card(m).bounding_box()['height']<180
        card(m).locator('[data-notice-filter=unread]').uncheck();card(m).locator('[data-notice-filter=action]').uncheck();cat(m,'company');row=rows(m).first;row.click();assert dialog.locator('[data-notice-navigate]').count()==0;assert '優先度：重要' in dialog.inner_text();p.keyboard.press('Escape');card(m).locator('[data-notice-all]').click();assert dialog.locator('[data-notice-category=company]').get_attribute('aria-pressed')=='true';assert dialog.locator('.nc-row').count()==3;dialog.locator('[data-notice-close]').click()
        profile(m,'none');assert rows(m).count()==0 and unread(m)==0 and card(m).bounding_box()['height']<180;screenshot('empty-notices.png',m)
        card(m).locator('[data-notice-info]').click();assert '再読み込み' in dialog.inner_text() and '権限制御ではありません' in dialog.inner_text();p.keyboard.press('Escape');assert card(m).locator('[data-notice-info]').evaluate('(e)=>e===document.activeElement')
        profile(m,'dual');cat(m,'all');screenshot('compact-power.png',m)
        done('AND filters and list state persist; filtered-out read rows fall back to a filter button; empty cards shrink; demo explanations remain in the info modal; company details have no case action')
        row=rows(m).filter(has_text='P-00002');row.click();dialog.locator('[data-notice-navigate]').click();expect(f.locator('#power-detail-case')).to_have_value('1');assert f.locator('#power-section-basic').get_attribute('open') is not None
        m=nav(f,'legal');profile(m,'manager');cat(m,'approval');pending=rows(m).filter(has_text='G-00010');pending.click();assert '要承認' in dialog.inner_text();dialog.locator('[data-notice-navigate]').click();expect(f.locator('#legal-workspace [data-dept-select]')).to_have_value('G-00010');expect(f.locator('#legal-workspace [data-dept-field=saleApproval]').first).to_have_value('承認待ち')
        done('case and approval buttons navigate only after explicit detail actions to the correct business/case/section; opening approval details does not approve')
        # A test-only large list checks modal scrolling, long titles and unavailable destinations.
        injection="""
const c=homeBusinessCases('battery').find(r=>r.id==='P-00002'),ref=[...noticeCenter.snapshot().values()].find(w=>w.ref.source===c.source).ref;
for(let i=0;i<30;i++)noticeCenter.emit({eventId:'compact-fixture-'+i,category:'progress',subtype:'引き継ぎ',subject:'長い件名の検証'.repeat(20)+' '+i,body:'本文は詳細画面だけに表示するテストです。',business:'battery',caseId:ref.internalId,caseNumber:'P-00002',sourceDepartment:'power',targetDepartments:['power'],priority:'urgent',destination:{department:'power',unimplemented:true},occurredAt:'2026-11-05T09:'+String(i).padStart(2,'0')+':00+09:00'},true);
"""
        body=fixture(raw,injection);extra=b.new_page(viewport={'width':1550,'height':1250});extra.on('pageerror',lambda e:errors.append(str(e)));u=url+'?compact-fixture';extra.route(u,lambda r:r.fulfill(status=200,content_type='text/html',body=body));extra.goto(u,wait_until='networkidle');ff=extra.frame_locator('#codex-visualization');ff.locator('[data-page=power]').click();cc=ff.locator('#power-workspace .nc-card');dd=ff.locator('.nc-dialog')
        assert cc.locator('.nc-row').first.locator('.nc-subject').evaluate('(e)=>e.scrollWidth>e.clientWidth&&getComputedStyle(e).textOverflow==="ellipsis"')
        cc.locator('.nc-row').first.click();assert dd.locator('[data-notice-navigate]').count()==0 and '未実装' in dd.inner_text();extra.screenshot(path=str(OUT/'long-unimplemented-detail.png'));dd.locator('[data-notice-close]').click();cc.locator('[data-notice-all]').click();assert dd.locator('.nc-row').count()==36;assert dd.locator('.nc-rows').evaluate('(e)=>!["auto","scroll"].includes(getComputedStyle(e).overflowY)')
        dd.evaluate('(e)=>e.scrollTop=250');selected=dd.locator('.nc-row').nth(10);selected_id=selected.get_attribute('data-notice-id');saved_list_scroll=dd.evaluate('(e)=>e.scrollTop');selected.click();dd.locator('[data-notice-back]').click();assert dd.locator('[data-notice-id='+selected_id+']').evaluate('(e)=>e===document.activeElement');assert abs(dd.evaluate('(e)=>e.scrollTop')-saved_list_scroll)<2
        extra.screenshot(path=str(OUT/'all-notices.png'));dd.locator('[data-notice-close]').click();extra.set_viewport_size({'width':800,'height':1100});cc.scroll_into_view_if_needed();assert cc.locator('.nc-time-date').first.is_visible();assert not cc.locator('.nc-time-full').first.is_visible();extra.set_viewport_size({'width':390,'height':1000});cc.scroll_into_view_if_needed();assert not cc.locator('.nc-row-time').first.is_visible();assert cc.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');assert cc.locator('.nc-row').evaluate_all('(es)=>es.every(e=>e.getBoundingClientRect().height===42&&e.scrollWidth<=e.clientWidth+1)');extra.screenshot(path=str(OUT/'mobile-long-notices.png'));extra.close()
        done('long subjects ellipsize without horizontal scrolling; 36-item list scrolls as one modal and restores its selected row; unavailable destinations show no button; medium/mobile date rules work')
        p.reload(wait_until='networkidle');m=nav(f,'power');assert unread(m)==6 and rows(m).count()==5 and not f.locator('.nc-toast').count();screenshot('compact-power.png',m);assert not errors,errors;assert not failed,failed;assert not writes,writes
        done('reload resets memory-only reads/profile; no draw/switch toasts, JavaScript errors, failed resources or external writes')
        old.close();b.close()
    (OUT/'results.json').write_text(json.dumps({'passed':passed,'five_row_heights':heights,'js_errors':errors,'failed_resources':failed,'external_writes':writes},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
