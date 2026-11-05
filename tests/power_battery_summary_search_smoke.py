"""Battery summary saved-value search, broker/voltage classification, IME and scope isolation."""
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright,expect
from power_mock_smoke import server
from notice_snapshot import normalize_department_names
from department_notices_smoke import inner,fixture
ROOT=Path(__file__).resolve().parents[1];OUT=Path('/tmp/ecokaku-power-summary-search-review')
def run():
    OUT.mkdir(exist_ok=True);passed=[];errors=[];failed=[];writes=[]
    raw=(ROOT/'index.html').read_text();baseline=subprocess.check_output(['git','show','4f0c427:index.html'],cwd=ROOT,text=True)
    for var in ['batteryCaseSeedData','batteryDepartmentDefinitions']:
        parse=lambda text:json.JSONDecoder().raw_decode(inner(text).split('const '+var+'=',1)[1])[0]
        assert parse(raw)==parse(baseline)
    def done(s):passed.append(s);print('PASS',s,flush=True)
    with server() as url,sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page(viewport={'width':1550,'height':1350});p.on('pageerror',lambda e:errors.append(str(e)));p.on('requestfailed',lambda r:failed.append(r.url));p.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
        p.goto(url,wait_until='networkidle');f=p.frame_locator('#codex-visualization');f.locator('[data-page=power]').click();m=f.locator('#power-workspace')
        def ids(fr=f):return fr.locator('[data-power-summary-row]').evaluate_all('(es)=>es.map(e=>e.dataset.powerSummaryRow)')
        def clear(fr=f):fr.locator('[data-power-action=clearFilters]').click()
        def shot(name):m.locator('.pw-battery-summary-filters').scroll_into_view_if_needed();p.screenshot(path=str(OUT/name))
        labels=m.locator('.pw-battery-summary-filters>label').evaluate_all('(es)=>es.map(e=>e.firstChild.textContent)');assert labels==['案件検索','担当者','仲介者','現在工程','設備種別','並べ替え','キーワードで検索']
        assert m.locator('#power-summary-broker option').all_text_contents()==['すべて','未登録'];assert m.locator('#power-summary-equipment option').all_text_contents()==['すべて','特高蓄電池','高圧蓄電池','低圧蓄電池','未登録'];assert len(ids())==10
        m.locator('#power-summary-broker').select_option('missing');assert len(ids())==10;m.locator('#power-summary-equipment').select_option('高圧蓄電池');assert ids()==[];assert '条件に一致する案件はありません' in m.inner_text();clear();shot('desktop-initial.png')
        # Actual Chromium IME: keep the DOM/rows during composition and apply only the commit.
        search=m.locator('#power-search');search.focus();handle=search.element_handle();cdp=p.context.new_cdp_session(p)
        cdp.send('Input.imeSetComposition',{'text':'デモ','selectionStart':2,'selectionEnd':2});assert handle.evaluate('(e)=>e.isConnected') and len(ids())==10
        cdp.send('Input.imeSetComposition',{'text':'デモ第02','selectionStart':5,'selectionEnd':5});assert handle.evaluate('(e)=>e.isConnected') and len(ids())==10
        cdp.send('Input.insertText',{'text':'デモ第02'});assert ids()==['P-00002'];assert search.input_value()=='デモ第02';assert search.evaluate('(e)=>e===document.activeElement');clear()
        keyword=m.locator('#power-summary-keyword');keyword.press_sequentially('  DiStInCt  ',delay=20);assert ids()==[];assert keyword.input_value()=='  DiStInCt  ' and keyword.evaluate('(e)=>e===document.activeElement');clear()
        keyword=m.locator('#power-summary-keyword');keyword.focus();ime_keyword=keyword.element_handle();cdp.send('Input.imeSetComposition',{'text':'未確定','selectionStart':3,'selectionEnd':3});assert ime_keyword.evaluate('(e)=>e.isConnected') and len(ids())==10;cdp.send('Input.insertText',{'text':'存在しない日本語'});assert ids()==[] and keyword.evaluate('(e)=>e===document.activeElement');clear()
        done('specified filter order, honest missing defaults, three voltage choices and immediate input; real Chromium IME does not redraw until committed')
        injection="""
const data=[
 ['P-00001',['架空仲介A（検証専用）','Shared Broker（検証専用）'],'特高蓄電池'],
 ['P-00002',['架空仲介B（検証専用）','Shared Broker（検証専用）'],'高圧蓄電池'],
 ['G-00003',[],'低圧蓄電池'],['G-00004',['架空仲介A（検証専用）'],'特高蓄電池'],
 ['G-00005',['非常に長い仲介者名（検証専用）'.repeat(5)],'高圧蓄電池'],
 ['G-00006',['架空仲介A（検証専用）','別名C（検証専用）'],'低圧蓄電池'],
 ['G-00007',[],''],['G-00008',[],'既存・区分要確認（検証専用）'],['G-00009',['  '],''],['G-00010',[' Shared Broker（検証専用） '],'高圧蓄電池']];
for(const [id,brokers,type] of data){const d=batteryCaseMap[id].power;d.values.brokers=brokers;d.values.batteryEquipmentType=type;}
batteryCaseMap['P-00002'].power.values['7']='申請時独立名称（検証専用）';batteryCaseMap['P-00002'].power.memo='ACME RETEST 確認用メモ';
batteryCaseMap['P-00002'].power.history.push({at:'2026-11-04',text:'HiddenAdminToken'});
window.__searchFixtureState=()=>batteryCases.map(c=>({id:c.id,kind:c.power.values.kind,brokers:c.power.values.brokers,type:c.power.values.batteryEquipmentType,history:c.power.history,forecastHistory:c.power.forecastHistory,archives:c.power.archives}));
"""
        body=fixture(raw,injection);test_url=url+'?power-search-fixture';p.route(test_url,lambda r:r.fulfill(status=200,content_type='text/html',body=body));p.goto(test_url,wait_until='networkidle');f.locator('[data-page=power]').click();initial=p.frames[1].evaluate('window.__searchFixtureState()');initial_unread=m.locator('.nc-unread-count').inner_text();brokers=m.locator('#power-summary-broker option').all_text_contents();assert len(brokers)==7 and len(set(brokers))==7,brokers
        m.locator('#power-summary-broker').select_option(label='架空仲介A（検証専用）');assert set(ids())=={'P-00001','G-00004','G-00006'}
        m.locator('#power-search').fill('G-00004');assert ids()==['G-00004'];assert m.locator('#power-summary-broker option').all_text_contents()==brokers;clear();m.locator('#power-summary-broker').select_option('missing');assert set(ids())=={'G-00003','G-00007','G-00008','G-00009'};clear()
        for value,expected in [('特高蓄電池',{'P-00001','G-00004'}),('高圧蓄電池',{'P-00002','G-00005','G-00010'}),('低圧蓄電池',{'G-00003','G-00006'}),('missing',{'G-00007','G-00009'})]:m.locator('#power-summary-equipment').select_option(value);assert set(ids())==expected,(value,ids());clear()
        m.locator('#power-summary-keyword').fill('既存・区分要確認');assert ids()==['G-00008'];clear()
        done('deduplicated full-store broker options, multiple brokers and missing brokers; all three voltage types, missing and preserved unclassified values filter correctly')
        m.locator('#power-search').fill('サンプル地区02');m.locator('#power-summary-keyword').fill('  rEtEsT  ');assert ids()==['P-00002']
        m.locator('#power-summary-owner').select_option('申請担当B');m.locator('#power-summary-broker').select_option(label='Shared Broker（検証専用）');m.locator('#power-summary-stage').select_option('3');m.locator('#power-summary-equipment').select_option('高圧蓄電池');m.locator('#power-summary-sort').select_option('deadline');assert ids()==['P-00002'];assert m.locator('[data-power-card=""] strong').inner_text()=='1件';assert sum(int(x.inner_text().replace('件','')) for x in m.locator('[data-power-stage-count]').all())==1
        before_badge=m.locator('.nc-unread-count').inner_text();m.locator('[data-power-card=payment]').click();assert ids()==[];assert m.locator('[data-power-card=""] strong').inner_text()=='1件';assert m.locator('.nc-unread-count').inner_text()==before_badge
        clear();assert len(ids())==10;assert m.locator('#power-summary-sort').input_value()=='progress';assert all(m.locator(sel).input_value()=='' for sel in ['#power-search','#power-summary-owner','#power-summary-broker','#power-summary-stage','#power-summary-equipment','#power-summary-keyword']);assert m.locator('[data-power-action=clearFilters]').evaluate('(e)=>e===document.activeElement')
        m.locator('#power-summary-sort').select_option('number');assert ids()==['P-00001','P-00002']+['G-'+str(i).zfill(5) for i in range(3,11)];m.locator('#power-summary-sort').select_option('progress');assert ids().index('P-00001')<ids().index('P-00002')
        m.locator('#power-summary-sort').select_option('deadline');dues=m.locator('[data-power-summary-row] td:nth-child(5)').all_text_contents();assert [x if x!='未登録' else '9999' for x in dues]==sorted(x if x!='未登録' else '9999' for x in dues)
        assert p.frames[1].evaluate('window.__searchFixtureState()')==initial and m.locator('.nc-unread-count').inner_text()==initial_unread and not f.locator('.nc-toast').count()
        clear()
        for term in ['期限超過','並行作業','注意事項なし','申請から30日以上']:
            expected=m.locator('[data-power-summary-row]').evaluate_all('(es,q)=>es.filter(e=>e.querySelector("td:last-child").innerText.includes(q)).map(e=>e.dataset.powerSummaryRow)',term)
            m.locator('#power-summary-keyword').fill(term);assert set(ids())==set(expected),(term,ids(),expected);clear()
        done('all criteria combine with AND before sorting; KPI/stage baseline and status-card semantics unchanged; clear resets all conditions and existing progress sort; filters create no history/toast')
        clear();m.locator('#power-search').fill('デモ第02');assert ids()==[];m.locator('#power-search').fill('申請時独立名称');assert ids()==['P-00002'];clear()
        for excluded in ['申請時独立名称','DEMO-ANDPAD-P-00002','HiddenAdminToken','架空蓄電事業法人02','架空地権者02']:
            m.locator('#power-summary-keyword').fill(excluded);assert ids()==[],excluded
        clear();keyword=m.locator('#power-summary-keyword');keyword.press_sequentially('retest',delay=20);assert ids()==['P-00002'];keyword.evaluate('(e)=>e.setSelectionRange(0,2)');keyword.press_sequentially('RE');assert keyword.input_value()=='REtest';assert keyword.evaluate('(e)=>e===document.activeElement&&e.selectionStart===2&&e.selectionEnd===2')
        clear();m.locator('[data-power-summary-row=P-00002] [data-power-section=basic]').first.click();records=m.locator('#power-section-records');records.locator('summary').click();m.locator('#power-memo').fill('UNSAVED-ONLY');m.locator('#power-tab-summary').click();m.locator('#power-summary-keyword').fill('UNSAVED-ONLY');assert ids()==[];m.locator('#power-summary-keyword').fill('ACME');assert ids()==['P-00002']
        m.locator('[data-power-tab=bulk]').click();assert m.locator('[data-power-bulk-row]').count()==10;assert m.locator('[data-power-filter=kind] option').all_text_contents()==['すべて','太陽光','蓄電池'];assert not m.locator('[data-power-summary-filter]').count();m.locator('[data-power-action=cancelAll]').click();m.locator('#power-tab-summary').click();assert ids()==['P-00002'];clear()
        done('case search and keyword have distinct explicit fields; hidden IDs/history/customer/landowner and unsaved memo excluded; caret survives live edits; summary-only criteria never affect bulk input')
        # Exercise preserved memo save/cancel through the correct case route.
        m.locator('[data-power-summary-row=P-00002] [data-power-section=basic]').first.click();records=m.locator('#power-section-records')
        if records.get_attribute('open') is None:records.locator('summary').click()
        m.locator('#power-memo').fill('SAVED-SEARCH-MEMO');m.locator('[data-power-action=saveCase]').first.click();m.locator('#power-tab-summary').click();m.locator('#power-summary-keyword').fill('saved-search-memo');assert ids()==['P-00002'];assert not f.locator('.nc-toast').count();clear()
        longname=next(x for x in brokers if x.startswith('非常に'));m.locator('#power-summary-broker').select_option(label=longname);assert ids()==['G-00005'];assert m.locator('#power-summary-broker').get_attribute('title')==longname;shot('fixture-long-broker.png')
        p.set_viewport_size({'width':390,'height':1300});m.locator('.pw-battery-summary-filters').scroll_into_view_if_needed();assert m.locator('.pw-battery-summary-filters').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');assert m.locator('.pw-battery-summary-filters label').evaluate_all('(es)=>es.every(e=>e.scrollWidth<=e.clientWidth+1)');shot('mobile-filters.png')
        done('saved memo becomes searchable while cancel preserves values; long broker and 390px single-column controls stay within bounds')
        # Full unaffected-area snapshots against the starting main, from fresh production data.
        p.set_viewport_size({'width':1550,'height':1350});p.goto(url,wait_until='networkidle');old=b.new_page(viewport={'width':1550,'height':1350});old.route(url,lambda r:r.fulfill(status=200,content_type='text/html',body=baseline));old.goto(url,wait_until='networkidle');of=old.frame_locator('#codex-visualization')
        def state(frame,d,business,t):
            frame.locator('[data-page='+d+']').click();mount=frame.locator('#'+d+'-workspace');mount.locator('.du-business-tabs').get_by_role('tab',name=business,exact=True).click();mount.locator('.du-work-tabs').get_by_role('tab',name=t,exact=True).click();return normalize_department_names(mount.inner_html())
        for d in ['power','sales','legal','procurement','construction','maintenance']:
            for business in ['蓄電池','太陽光','データセンター']:
                for t in ['サマリー','データ入力','案件詳細']:
                    if d=='power' and business=='蓄電池' and t in ['サマリー','データ入力']:continue
                    assert state(f,d,business,t)==state(of,d,business,t),(d,business,t)
        for frame in [f,of]:frame.locator('[data-page=home]').click()
        assert normalize_department_names(f.locator('#sales-demo-home').inner_html())==normalize_department_names(of.locator('#sales-demo-home').inner_html());assert f.locator('.s-top').inner_html()==of.locator('.s-top').inner_html();old.close();f.locator('[data-page=power]').click();assert len(ids())==10;shot('desktop-initial.png')
        assert not errors,errors;assert not failed,failed;assert not writes,writes;done('all other 52 department/business/tab DOM snapshots, executive home and header unchanged; reload resets memory; no JS/resource/write errors')
        b.close()
    (OUT/'results.json').write_text(json.dumps({'passed':passed,'js_errors':errors,'failed_resources':failed,'external_writes':writes,'production_brokers':'10 unregistered','production_voltage_types':'10 unregistered; original kind preserved'},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
