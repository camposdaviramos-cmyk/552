"""Validação de navegação e responsividade em Chrome instalado localmente."""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent
ARTIFACTS=ROOT/'artifacts'
ARTIFACTS.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(os.environ.get('INTEGRA_TEST_URL','http://127.0.0.1:8080'))
    page.get_by_role('button',name='Acessar demonstração').click()
    page.get_by_role('heading',name='Painel da rede',exact=True).wait_for()
    page.screenshot(path=str(ARTIFACTS/'dashboard-desktop.png'),full_page=True)
    page.get_by_role('link',name='Cadastro de pacientes',exact=True).click()
    page.get_by_role('heading',name='Cadastro de pacientes',exact=True).wait_for()
    page.locator('#table-search').fill('Maria')
    assert page.locator('#table-content tbody tr').count()>0
    page.locator('.patient-open').first.click()
    page.get_by_role('heading',name='Prontuário municipal',exact=True).wait_for()
    page.screenshot(path=str(ARTIFACTS/'prontuario.png'),full_page=True)
    page.get_by_role('button',name='Editar cadastro',exact=True).click()
    page.get_by_role('heading',name='Atualizar cadastro',exact=True).wait_for()
    page.locator('#close-modal').click()
    modules=['appointments','encounters','hospital','regulation','exams','surveillance','pharmacy','warehouse','assets','transport','fleet','billing','judicial','messages','support','training','reports','audit','integrations','compliance','migration','users','units']
    for module in modules:
        page.evaluate('(m)=>location.hash=m',module)
        page.wait_for_timeout(250)
        page.locator('#main h1').wait_for()
        assert 'Não foi possível carregar' not in page.locator('#main').inner_text(),module
        if page.locator('#new-record').count():
            page.locator('#new-record').click()
            page.locator('#record-form').wait_for()
            page.locator('#close-modal').click()
    page.evaluate("location.hash='pharmacy'")
    page.locator('#new-record').wait_for()
    page.locator('.stock-move').first.click()
    page.get_by_role('heading',name='Movimentar estoque').wait_for()
    page.locator('#close-modal').click()
    page.evaluate("location.hash='dashboard'")
    page.get_by_role('heading',name='Painel da rede',exact=True).wait_for()
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(350)
    page.screenshot(path=str(ARTIFACTS/'dashboard-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Overflow horizontal em mobile'
    page.locator('#user-menu').click()
    page.locator('#logout').click()
    page.get_by_role('button',name='Sou cidadão',exact=True).click()
    page.get_by_role('button',name='Acessar demonstração').click()
    page.get_by_role('heading',name='Olá, Maria.').wait_for()
    page.screenshot(path=str(ARTIFACTS/'cidadao-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors,errors
    print('OK: login, painel, busca, prontuário, 23 módulos/páginas, estoque, mobile e portal do cidadão; sem erros JavaScript.')
    browser.close()
