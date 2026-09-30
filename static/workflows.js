"use strict";

function odontogramHtml(field,value){
  const data=typeof value==='object'&&value?value:{};
  const options=['Hígido','Cárie','Restaurado','Ausente','Tratamento indicado','Tratado'];
  const quadrants=[1,2,3,4,5,6,7,8];
  return `<div class="span-two dental-field" data-care="Odontologia"><h3>${esc(field.label)}</h3><p class="muted">Registre a avaliação. Campos vazios significam não avaliado.</p><input type="hidden" name="odontogram" value="${esc(JSON.stringify(data))}"><div class="odontogram">${quadrants.map(q=>`<fieldset><legend>${q<=4?'Permanentes':'Decíduos'} · quadrante ${q}</legend>${Array.from({length:q<=4?8:5},(_,i)=>String(q*10+i+1)).map(tooth=>`<label>Dente ${tooth}<select data-tooth="${tooth}" aria-label="Dente ${tooth}"><option value="">Não avaliado</option>${options.map(o=>`<option ${data[tooth]===o?'selected':''}>${o}</option>`).join('')}</select></label>`).join('')}</fieldset>`).join('')}</div></div>`;
}

function bindClinicalFields(){
  const form=$('#record-form');
  const care=$('[name=care_type]',form);
  const update=()=>form.querySelectorAll('[data-care]').forEach(el=>{
    const types=el.dataset.care.split('|').filter(Boolean);
    el.hidden=types.length>0&&!types.includes(care?.value);
    el.querySelectorAll('input,select,textarea').forEach(input=>input.disabled=el.hidden);
  });
  care?.addEventListener('change',update);update();
  form.querySelectorAll('[data-tooth]').forEach(el=>el.onchange=()=>{
    const data={};form.querySelectorAll('[data-tooth]').forEach(select=>{if(select.value)data[select.dataset.tooth]=select.value;});
    $('[name=odontogram]',form).value=JSON.stringify(data);
  });
}

async function loadRecordTools(key,record,readonly){
  const container=$('#record-tools');
  try{
    const [files,history]=await Promise.all([api(`/records/${record.id}/attachments`),api(`/records/${record.id}/history`)]);
    if(!container.isConnected)return;
    container.innerHTML=`<div class="section-title"><h3>Documentos e rastreabilidade</h3><button type="button" class="btn small" id="print-record">${icon('download')} Imprimir relatório</button></div>${history.seal_valid!==null?`<div class="notice ${history.seal_valid?'success':'danger'}">${history.seal_valid?'Integridade do documento verificada':'Falha de integridade'} · autor #${esc(record.signed_by)} · ${new Date(record.signed_at).toLocaleString('pt-BR')}. Registro de autoria local; não é assinatura qualificada.</div>`:''}<ul class="attachment-list">${files.items.map(f=>`<li><a class="text-link" href="/api/attachments/${f.id}">${esc(f.name)}</a> · ${Math.ceil(f.size/1024)} KB <small>SHA-256: ${esc(f.sha256)}</small></li>`).join('')||'<li>Nenhum anexo.</li>'}</ul>${readonly?'':`<form id="attachment-form"><label>Anexar PDF, PNG ou JPEG · até 1 MB<input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg" required></label><p class="form-error" role="alert"></p><button class="btn" type="submit">Enviar anexo</button></form>`}<div class="record-action-buttons">${key==='assets'?'<button class="btn" id="asset-event">Transferência / inventário</button><button class="btn" id="asset-value">Calcular depreciação</button>':''}${key==='prescriptions'&&record.status==='Ativa'?'<button class="btn" id="administer-dose">Checar dose</button>':''}${['pharmacy','warehouse'].includes(key)?'<button class="btn" id="transfer-stock">Transferir entre unidades</button>':''}${['support','training','judicial','regulation'].includes(key)?'<button class="btn" id="add-comment">Adicionar acompanhamento</button>':''}</div>${key==='transport'?`<p><strong>Custeio TFD deste paciente:</strong> ${fmtMoney(record.total_cost||0)}</p>`:''}<details><summary>Histórico de versões (${history.versions.length}) e eventos (${history.events.length})</summary>${history.events.map(e=>`<article class="history-entry"><strong>${esc(e.kind)}</strong> · ${new Date(e.created_at).toLocaleString('pt-BR')} · usuário #${e.created_by}<pre>${esc(JSON.stringify(e.payload,null,2))}</pre></article>`).join('')}${history.versions.map(v=>`<details class="history-entry"><summary>Versão ${v.version} · ${esc(v.status)} · ${new Date(v.updated_at).toLocaleString('pt-BR')}</summary><dl>${state.meta.modules[key].fields.filter(f=>v[f.key]!==''&&v[f.key]!=null).map(f=>`<dt>${esc(f.label)}</dt><dd>${esc(typeof v[f.key]==='object'?JSON.stringify(v[f.key]):v[f.key])}</dd>`).join('')}</dl></details>`).join('')}</details>`;
    $('#print-record').onclick=()=>printRecord(key,record,files.items);
    $('#attachment-form')?.addEventListener('submit',async e=>{e.preventDefault();const button=$('button',e.target);button.disabled=true;try{await api(`/records/${record.id}/attachments`,{method:'POST',body:new FormData(e.target)});await loadRecordTools(key,record,readonly);}catch(err){$('.form-error',e.target).textContent=err.message;button.disabled=false;}});
    $('#asset-event')?.addEventListener('click',()=>assetEventForm(record));
    $('#asset-value')?.addEventListener('click',async()=>{try{const r=await api('/assets/valuation');const v=r.items.find(i=>i.id===record.id);toast(v.depreciation===null?'Informe a vida útil no cadastro para calcular.':`Depreciação: ${fmtMoney(v.depreciation)} · Valor líquido: ${fmtMoney(v.book_value)} · ${r.method}`);}catch(err){toast(err.message,true);}});
    $('#administer-dose')?.addEventListener('click',()=>doseForm(record));
    $('#transfer-stock')?.addEventListener('click',()=>stockTransferForm(record));
    $('#add-comment')?.addEventListener('click',()=>openModal('Acompanhamento',`<form id="comment-form"><label>Registro de acompanhamento<textarea name="text" required maxlength="3000"></textarea></label><p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="btn cancel-modal">Cancelar</button><button class="btn primary" type="submit">Registrar</button></div></form>`,()=>bindSave('#comment-form',data=>api(`/records/${record.id}/comments`,{method:'POST',body:data}),'Acompanhamento registrado.')));
  }catch(err){if(container.isConnected)container.innerHTML=`<p class="form-error">${esc(err.message)}</p>`;}
}

function printRecord(key,record,files){
  const spec=state.meta.modules[key];
  openModal('Relatório do registro',`<article class="print-report"><h2>${esc(spec.singular)} #${record.id}</h2><p>${esc(patientName(record.patient_id))} · ${esc(unitName(record.unit_id))}</p><p>Situação: ${esc(record.status)} · Versão ${record.version}</p><dl>${spec.fields.filter(f=>record[f.key]!==''&&record[f.key]!=null).map(f=>`<dt>${esc(f.label)}</dt><dd>${esc(typeof record[f.key]==='object'?Object.entries(record[f.key]).map(([k,v])=>`${k}: ${v}`).join('; '):record[f.key])}</dd>`).join('')}</dl><p>Registrado por #${record.created_by} em ${new Date(record.created_at).toLocaleString('pt-BR')}</p>${record.seal?`<p>Verificador de integridade local: ${esc(record.seal)}</p>`:''}<p>Anexos: ${files.map(f=>esc(f.name)).join(', ')||'Nenhum'}</p></article><button class="btn primary" id="print-now">Imprimir / salvar PDF</button>`,()=>$('#print-now').onclick=()=>window.print(),true);
}

function workflowForm(title,id,body,save){
  openModal(title,`<form id="${id}"><div class="form-grid">${body}</div><p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="btn cancel-modal">Cancelar</button><button type="submit" class="btn primary">Confirmar</button></div></form>`,()=>bindSave('#'+id,save,'Operação registrada com sucesso.'));
}
function assetEventForm(record){
  workflowForm('Movimentação patrimonial','asset-form',fieldHtml({key:'kind',label:'Operação',type:'select',required:true,options:['Transferência','Inventário']})+fieldHtml({key:'unit_id',label:'Unidade de destino',type:'unit'},record.unit_id)+fieldHtml({key:'responsible',label:'Responsável de destino',type:'text'},record.responsible)+fieldHtml({key:'condition',label:'Resultado do inventário',type:'select',options:['Localizado','Divergência','Não localizado']})+fieldHtml({key:'notes',label:'Observações / documento',type:'textarea',required:true}),data=>api(`/assets/${record.id}/events`,{method:'POST',body:{...data,version:record.version}}));
}
function doseForm(record){
  workflowForm('Checagem de dose','dose-form',`<p class="span-two">${esc(record.medication)} · ${esc(record.dose)} · ${esc(record.route)} · ${esc(record.frequency)}</p>`+fieldHtml({key:'scheduled_at',label:'Data e horário da dose',type:'datetime-local',required:true})+fieldHtml({key:'outcome',label:'Checagem',type:'select',required:true,options:['Administrada','Não administrada']})+fieldHtml({key:'notes',label:'Observação da checagem',type:'textarea',required:true}),data=>api(`/prescriptions/${record.id}/administrations`,{method:'POST',body:data}));
}
function stockTransferForm(record){
  workflowForm('Transferência de estoque','transfer-form',`<p class="span-two">${esc(record.name)} · lote ${esc(record.batch)} · saldo ${record.quantity}</p>`+fieldHtml({key:'unit_id',label:'Unidade de destino',type:'unit',required:true})+fieldHtml({key:'quantity',label:'Quantidade',type:'number',required:true})+fieldHtml({key:'reason',label:'Motivo / documento',type:'textarea',required:true}),data=>api(`/stock/${record.id}/transfer`,{method:'POST',body:data}));
}

let analyticsStart='',analyticsEnd='';
async function renderAnalytics(requestId){
  const today=new Date();
  if(!analyticsEnd)analyticsEnd=today.toLocaleDateString('en-CA');
  if(!analyticsStart){today.setDate(today.getDate()-29);analyticsStart=today.toLocaleDateString('en-CA');}
  const params=new URLSearchParams({start:analyticsStart,end:analyticsEnd,unit:state.unit});
  const data=await api('/analytics?'+params);if(requestId!==state.requestId)return;
  const stats=[['Atendimentos concluídos',data.summary.completed],['Absenteísmo',data.summary.absence_rate===null?'Sem base':data.summary.absence_rate+'%'],['Espera média da fila',data.summary.average_wait_days===null?'Sem fila':data.summary.average_wait_days+' dias'],['Produção conferida',fmtMoney(data.summary.billing_approved)],['Custeio TFD',fmtMoney(data.summary.transport_cost)],['Despesas da frota',fmtMoney(data.summary.fleet_cost)]];
  $('#main').innerHTML=pageHeader('INTELIGÊNCIA E GESTÃO','Indicadores e relatórios','Produção, epidemiologia e metas calculadas sobre os registros da rede.',`<a class="btn" href="/api/analytics?${esc(params)}&format=csv">${icon('download')} Exportar este recorte</a>`)+`<form id="analytics-filter" class="analytics-filters"><label>Início<input name="start" type="date" value="${data.start}" required></label><label>Fim<input name="end" type="date" value="${data.end}" required></label>${fieldHtml({key:'unit',label:'Unidade',type:'unit'},state.unit)}<button class="btn primary" type="submit">Aplicar filtros</button></form><div class="stats-grid">${stats.map(([label,value])=>`<article class="stat-card"><span>${label}</span><strong>${value}</strong></article>`).join('')}</div><section class="card padded"><h2>Distribuição da produção</h2><label>Agrupar por<select id="analytics-dimension"><option value="module">Módulo</option><option value="unit_id">Unidade</option><option value="status">Situação</option><option value="care_type">Linha de cuidado</option><option value="month">Mês</option></select></label><div id="analytics-groups"></div></section><section class="card padded report-section"><h2>Indicadores epidemiológicos</h2><p class="muted">Casos confirmados distintos por agravo e território. Cadastre a população e sua fonte em Territórios e população.</p><div class="table-scroll"><table><thead><tr><th>Território / agravo</th><th>Notificações</th><th>Confirmados</th><th>Óbitos registrados</th><th>População / fonte</th><th>Casos / 100 mil</th></tr></thead><tbody>${data.epidemiology.map(r=>`<tr><td>${esc(r.territory)} · ${esc(r.condition)}</td><td>${r.notifications}</td><td>${r.confirmed_patients}</td><td>${r.deaths}</td><td>${r.population??'Não informada'}<br>${esc(r.source||'')}</td><td>${r.rate_per_100k??'Sem denominador aplicável'}</td></tr>`).join('')}</tbody></table>${data.epidemiology.length?'':empty('Sem notificações no período')}</div></section><section class="card padded report-section"><h2>Metas e resultados</h2><div class="table-scroll"><table><thead><tr><th>Indicador</th><th>Período da meta</th><th>Meta</th><th>Realizado</th><th>Atingimento</th></tr></thead><tbody>${data.goals.map(r=>`<tr><td>${esc(r.indicator)}<br>${esc(r.unit_id?unitName(r.unit_id):'Rede municipal')}</td><td>${fmtDate(r.start)} a ${fmtDate(r.end)}</td><td>${r.target}</td><td>${r.actual}</td><td>${r.percent??0}%</td></tr>`).join('')}</tbody></table>${data.goals.length?'':empty('Nenhuma meta para o período','Cadastre as metas no menu Metas de gestão.')}</div></section><p class="notice">${esc(data.methodology)}</p><section class="card padded"><h2>Exportações por módulo</h2><p class="muted">Base completa de cada módulo; para o recorte acima use Exportar este recorte.</p><div class="report-grid">${Object.entries(state.meta.modules).map(([k,v])=>`<a class="report-link" href="/api/export/${k}">${esc(v.title)} ${icon('download')}</a>`).join('')}</div></section>`;
  const draw=()=>{const dim=$('#analytics-dimension').value;const rows=data.dimensions[dim];const max=Math.max(1,...rows.map(r=>r.count));$('#analytics-groups').innerHTML=rows.map(r=>`<div class="analytics-bar"><span>${esc(dim==='module'?state.meta.modules[r.label]?.title||r.label:dim==='unit_id'?unitName(r.label):r.label)}</span><meter min="0" max="${max}" value="${r.count}">${r.count}</meter><strong>${r.count}</strong></div>`).join('');};
  $('#analytics-dimension').onchange=draw;draw();
  $('#analytics-filter').onsubmit=e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.target));analyticsStart=values.start;analyticsEnd=values.end;state.unit=values.unit;route();};
}

async function renderRecordMigration(){
  const container=document.createElement('section');container.className='card padded report-section';container.id='record-migration';$('#main').append(container);
  container.innerHTML=`<h2>Migração de históricos e módulos</h2><p class="muted">JSON com origem, identificador estável e registros. Pacientes, unidades, profissionais e veículos referenciados precisam estar cadastrados. A simulação verifica o lote inteiro antes de gravar.</p><a class="text-link" href="/api/migration/records/template" download="modelo-registros.json">Baixar modelo JSON</a><form id="record-import-form"><label>Arquivo JSON · até 1.000 registros<input type="file" name="file" accept=".json" required></label><div class="form-actions"><button class="btn" type="submit">Simular importação</button><button class="btn primary" type="button" id="record-import" disabled>Importar registros validados</button></div></form><div id="record-import-result" role="status"></div><div id="migration-receipts"></div>`;
  const form=$('#record-import-form');const button=$('#record-import');let validated=false;
  const receipts=async()=>{const r=await api('/migration/runs');$('#migration-receipts').innerHTML='<h3>Recibos de reconciliação</h3>'+r.items.map(run=>`<details><summary>#${run.id} · ${esc(run.source)} · ${run.imported} registros · ${fmtDate(run.created_at)}</summary><pre>${esc(JSON.stringify(run,null,2))}</pre></details>`).join('');};
  receipts().catch(err=>toast(err.message,true));
  $('[name=file]',form).onchange=()=>{validated=false;button.disabled=true;};
  form.onsubmit=async e=>{e.preventDefault();validated=false;button.disabled=true;try{const r=await api('/migration/records/validate',{method:'POST',body:new FormData(form)});validated=!r.errors.length;button.disabled=!validated;$('#record-import-result').innerHTML=`<p>${r.valid} de ${r.total} registros válidos. Nenhum registro gravado nesta simulação.</p><ul class="error-list">${r.errors.map(v=>`<li>Registro ${v.line}: ${esc(v.error)}</li>`).join('')}</ul>`;}catch(err){toast(err.message,true);}};
  button.onclick=async()=>{if(!validated)return;button.disabled=true;validated=false;try{const r=await api('/migration/records/import',{method:'POST',body:new FormData(form)});$('#record-import-result').textContent=`${r.imported} registros importados. Recibo #${r.receipt_id}.`;await receipts();}catch(err){toast(err.message,true);}};
}

let citizenEvents=null,citizenRevision='',citizenRefreshPending=false,installPrompt=null;
function stopCitizenEvents(){citizenEvents?.close();citizenEvents=null;citizenRevision='';}
function startCitizenEvents(){
  if(citizenEvents||state.user?.role!=='cidadao'||document.hidden)return;
  const controller=new AbortController();
  const stream={connected:false,close:()=>controller.abort()};citizenEvents=stream;
  const tokenAtStart=authToken;
  // Native EventSource cannot send Authorization; read SSE with authenticated fetch.
  (async()=>{
    const timeout=setTimeout(()=>controller.abort(),65000);
    try{
      const response=await fetch(API_BASE+'/citizen/events',{credentials:'include',headers:authHeaders({'Last-Event-ID':citizenRevision}),signal:controller.signal});
      if(citizenEvents!==stream)return;
      if(response.status===401){if(authToken===tokenAtStart){clearAuth();renderLogin();}return;}
      if(!response.ok)return; // Periodic refresh remains available if SSE slots are full.
      stream.connected=true;
      const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';
      while(!controller.signal.aborted){
        const {value,done}=await reader.read();if(done)break;
        buffer+=decoder.decode(value,{stream:true}).replace(/\r\n/g,'\n');
        let boundary;
        while((boundary=buffer.indexOf('\n\n'))!==-1){
          const block=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);
          if(citizenEvents!==stream)return;
          const kind=block.match(/^event: ?(.*)$/m)?.[1];const revision=block.match(/^id: ?(.*)$/m)?.[1];
          if(kind==='revoked'){clearAuth();renderLogin();return;}
          if(kind==='refresh'&&revision&&citizenRevision!==revision){citizenRevision=revision;if($('#modal').open)citizenRefreshPending=true;else renderCitizen();}
        }
      }
    }catch(error){/* Reconnect on the next periodic/visibility refresh. */}
    finally{clearTimeout(timeout);controller.abort();if(citizenEvents===stream)citizenEvents=null;}
  })();
}
document.addEventListener('visibilitychange',()=>{if(document.hidden){citizenEvents?.close();citizenEvents=null;}else if(state.user?.role==='cidadao'){renderCitizen();startCitizenEvents();}});
$('#modal').addEventListener('close',()=>{if(citizenRefreshPending&&state.user?.role==='cidadao'){citizenRefreshPending=false;renderCitizen();}});
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;showInstallButton();});
function showInstallButton(){
  if(!installPrompt||!$('.citizen-header')||$('#install-app'))return;
  const button=document.createElement('button');button.className='btn';button.id='install-app';button.textContent='Instalar aplicativo';
  button.onclick=async()=>{await installPrompt.prompt();await installPrompt.userChoice;installPrompt=null;button.remove();};$('.citizen-header').append(button);
}
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});

async function renderAuditMatrix(requestId){
  const data=await api('/compliance');if(requestId!==state.requestId)return;
  const local=data.items.filter(r=>!r.external_dependency),external=data.items.filter(r=>r.external_dependency);
  const implemented=local.filter(r=>r.status==='Implementado localmente').length;
  const percent=local.length?Math.round(implemented/local.length*100):0;
  $('#main').innerHTML=pageHeader('AUDITORIA DO TERMO DE REFERÊNCIA','Matriz de aderência','Critérios locais e dependências externas separados por referência do PDF.',`<a class="btn" href="/api/compliance/document" target="_blank" rel="noopener">Abrir TR original</a><button class="btn" id="export-compliance">Exportar auditoria</button>`)+`<div class="notice">${esc(data.notice)}</div><div class="compliance-summary"><div><strong>${data.items.length}</strong><span>Critérios e dependências mapeados · 13 páginas</span></div><div><strong>${local.length}</strong><span>Critérios locais implementados</span></div><div><strong style="color:#b91c1c">${external.length}</strong><span>Dependências externas · vermelho</span></div><div><strong>${percent}%</strong><span>Dos critérios locais descritos · não do contrato</span></div></div><div class="compliance-filters"><input type="search" id="compliance-search" placeholder="Buscar requisito, referência ou dependência" aria-label="Buscar na auditoria"><select id="compliance-filter" aria-label="Filtrar aderência"><option value="all">Todos os itens</option><option value="local">Implementados localmente</option><option value="external">Dependências externas</option></select></div><p id="compliance-count" class="muted"></p><section class="card"><div class="table-scroll"><table class="compliance-table"><thead><tr><th>Referência</th><th>Requisito / critério de aceite</th><th>Situação</th><th>Evidências / dependência e ação necessária</th></tr></thead><tbody id="compliance-rows"></tbody></table></div></section>`;
  const draw=()=>{
    const q=$('#compliance-search').value.toLocaleLowerCase('pt-BR');const filter=$('#compliance-filter').value;
    const items=data.items.filter(r=>(filter==='all'||r.scope===filter)&&JSON.stringify(r).toLocaleLowerCase('pt-BR').includes(q));
    $('#compliance-count').textContent=`${items.length} itens exibidos · auditoria ${fmtDate(data.audited_at)}`;
    $('#compliance-rows').innerHTML=items.map(r=>`<tr class="${r.external_dependency?'compliance-external':'compliance-local'}" data-audit-id="${esc(r.id)}"><td class="mono">${esc(r.ref)}<small>${esc(r.id)}</small></td><td><strong>${esc(r.requirement)}</strong>${r.criterion?`<small>${esc(r.criterion)}</small>`:''}</td><td><span class="badge ${r.external_dependency?'red':'green'}">${esc(r.status)}</span></td><td>${r.external_dependency?`<strong>${esc(r.dependency)}</strong><small>Responsável: ${esc(r.owner)}</small><small>Próxima ação: ${esc(r.next_step)}</small>`:`${esc(r.evidence)}<small>Validação: ${esc(r.validation)}</small>`}</td></tr>`).join('');
  };
  $('#compliance-search').oninput=draw;$('#compliance-filter').onchange=draw;draw();
  $('#export-compliance').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='auditoria-TR.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
}
