"""Regressão de requisições presas, logout com resposta atrasada e canal SSE cheio."""
import os
from playwright.sync_api import sync_playwright, expect

URL=os.environ.get('INTEGRA_TEST_URL','http://127.0.0.1:8081')

with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    context=browser.new_context()
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(URL+'/cidadao')
    page.locator('#demo-access').click()
    page.get_by_role('heading',name='Olá, Maria.').wait_for()
    page.evaluate('stopCitizenEvents()')

    # Simula fetch sem resposta e mantém o AbortSignal real para testar o prazo.
    result=page.evaluate('''async()=>{
        const original=window.fetch;
        window.fetch=(_url,options)=>new Promise((_resolve,reject)=>{
            options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));
        });
        try {
            const errors=[];
            for(const method of ['GET','POST']) {
                try { await api('/health',{method,timeoutMs:30}); }
                catch(error){errors.push(error.message);}
            }
            return errors;
        } finally {window.fetch=original;}
    }''')
    assert 'demorou a responder' in result[0]
    assert 'Confira se a operação foi registrada' in result[1]

    # Inicia leitura, sai da conta e só então libera a resposta antiga.
    result=page.evaluate('''async()=>{
        const original=window.fetch;
        const data=await (await original('/api/citizen')).json();
        let release;
        window.fetch=(url,options)=>url==='/api/citizen'
            ?new Promise(resolve=>{release=()=>resolve(new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}}));})
            :original(url,options);
        try {
            const pending=renderCitizen();
            await logout();
            release();
            await pending;
            return {loggedOut:state.user===null,loginVisible:!!document.querySelector('#login-form'),portalVisible:!!document.querySelector('.citizen-app')};
        } finally {window.fetch=original;}
    }''')
    assert result=={'loggedOut':True,'loginVisible':True,'portalVisible':False},result
    expect(page.locator('#login-form')).to_be_visible()

    # Várias abas não devem ocupar todos os workers do servidor.
    page.locator('#demo-access').click()
    page.get_by_role('heading',name='Olá, Maria.').wait_for()
    page.evaluate('stopCitizenEvents()')
    streams=[]
    try:
        for _ in range(6):
            other=context.new_page();other.on('pageerror',lambda e:errors.append(str(e)))
            other.goto(URL+'/cidadao')
            other.get_by_role('heading',name='Olá, Maria.').wait_for()
            streams.append(other)
        assert context.request.get(URL+'/api/health',timeout=5000).status==200
        headers={'Authorization':'Bearer '+page.evaluate('authToken')}
        assert context.request.get(URL+'/api/citizen',headers=headers,timeout=5000).status==200
    finally:
        for other in streams:other.close()
    assert not errors,errors
    print('OK: timeout de leitura/gravação, logout com resposta atrasada e servidor responsivo com seis portais.')
    browser.close()
