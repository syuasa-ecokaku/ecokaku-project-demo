"""Notification integration for existing handover, contract-state and mock request actions."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
OUT=Path('/tmp/ecokaku-notices-review')
def run():
    passed=[];errors=[]
    def done(s):passed.append(s);print('PASS',s,flush=True)
    with server() as url,sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1550,'height':1300});p.on('pageerror',lambda e:errors.append(str(e)));p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');dialog=f.locator('.nc-dialog')
        def nav(d):f.locator('[data-page='+d+']').click();return f.locator('#'+d+'-workspace')
        def tab(m,name):m.locator('.du-work-tabs').get_by_role('tab',name=name,exact=True).click()
        def all(m):m.locator('[data-notice-all]').click();return dialog.locator('.nc-row')
        def close():dialog.locator('[data-notice-close]').click()
        def profile(m,user):
            panel=m.locator('.nc-demo');panel.locator('summary').click();panel.locator('[data-notice-user]').select_option(user)
        def save(m):m.locator('[data-dept-action=save]').first.click()
        m=nav('construction');tab(m,'データ入力');m.locator('[data-dept-group]').select_option('business')
        for key,value in [('completionActual','2026-11-20'),('inspectionActual','2026-11-25'),('handoverActual','2026-11-30')]:m.locator('[data-dept-row=P-00002] [data-dept-field='+key+']').fill(value)
        save(m);assert f.locator('.nc-toast').count()==3
        m=nav('maintenance');rr=all(m).filter(has_text='引渡実績日');assert rr.count()==1 and '引き継ぎ' in rr.inner_text()
        rr.locator('[data-notice-open]').first.click();dialog.locator('[data-notice-navigate]').click();expect(f.locator('#construction-workspace [data-dept-select]')).to_have_value('P-00002')
        done('actual construction handover notifies maintenance and opens the source case; separate completion events stay distinct')
        p.reload(wait_until='networkidle');m=nav('legal');profile(m,'manager');tab(m,'データ入力');m.locator('[data-dept-group]').select_option('sale');field=m.locator('[data-dept-row=G-00010] [data-dept-field=saleApproval]');field.select_option('差戻し');save(m);tab(m,'サマリー');rr=all(m).filter(has_text='承認待ち → 差戻し');assert rr.count()==1 and '差し戻し' in rr.inner_text();close()
        tab(m,'データ入力');field.select_option('承認待ち');save(m);tab(m,'サマリー');rr=all(m);requests=rr.filter(has_text='承認依頼');assert requests.count()==2
        assert requests.filter(has_text='要承認').count()==1 and requests.filter(has_text='参考（過去の通知）').count()==1
        close();tab(m,'データ入力');save(m);tab(m,'サマリー');assert all(m).filter(has_text='差戻し → 承認待ち').count()==1;close()
        profile(m,'dual');assert not m.locator('.nc-card .nc-row').filter(has_text='差戻し → 承認待ち').count()
        done('contract return and resubmission notify once; only the current request stays actionable; requests target the demo approver role')
        p.reload(wait_until='networkidle');m=nav('procurement');tab(m,'データ入力');m.locator('[data-dept-group]').select_option('business');m.locator('[data-dept-row=P-00002] [data-dept-field=quantity]').fill('1.5');save(m);assert '整数' in m.locator('[data-dept-errors]').inner_text();assert not f.locator('.nc-toast').count();m.locator('[data-dept-action=cancel]').click()
        m=nav('power');m.locator('[data-power-open="1"]').first.click();section=m.locator('#power-section-connection')
        if section.get_attribute('open') is None:section.locator('summary').click()
        m.locator('[data-power-action=reconnect]').click();m.locator('[data-power-action=reconnectCancel]').click();assert not f.locator('.nc-toast').count()
        m.locator('[data-power-action=reconnect]').click();m.locator('[data-power-action=reconnectConfirm]').click();assert f.locator('.nc-toast').count()==1;tab(m,'サマリー');assert all(m).filter(has_text='申請回').count()==1;close()
        done('invalid saves and reconnection cancellation emit nothing; confirmed reconnection emits one event instead of reset-field noise')
        p.reload(wait_until='networkidle');m=nav('sales');m.locator('.du-business-tabs').get_by_role('tab',name='太陽光',exact=True).click();m.locator('[data-sales-open=P-00001]').first.click();f.locator('[data-section=invoice]').click();f.locator('#sales-demo-request').click();f.locator('#sales-demo-confirm').click();assert f.locator('.nc-toast').count()==1
        f.locator('#sales-demo-request').click();f.locator('#sales-demo-confirm').click();assert f.locator('.nc-toast').count()==1
        tab(m,'サマリー');assert all(m).filter(has_text='請求指示').count()==1;close()
        done('existing solar mock billing request emits only on its first actual state change; no real invoice or external request is created')
        p.reload(wait_until='networkidle');m=nav('legal');tab(m,'データ入力');m.locator('[data-dept-group]').select_option('sale');m.locator('[data-dept-row=G-00008] [data-dept-field=saleReview]').select_option('確認済み');save(m);assert f.locator('.nc-toast').count()==1;tab(m,'サマリー');assert all(m).filter(has_text='契約確認状況').count()==1;close()
        done('shared contract review status changes notify once through the common contract binding')
        assert not errors,errors;b.close()
    (OUT/'event-results.json').write_text(json.dumps({'passed':passed,'js_errors':errors},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
