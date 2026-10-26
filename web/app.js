'use strict';
// Apenas caminhos relativos da allowlist local. Nenhum conector de produção.
const $ = (id) => document.getElementById(id);
const labels = {nome: 'Nome', email: 'E-mail', data: 'Data', hora: 'Hora', assunto: 'Assunto'};
let state = null;
let selectedId = null;
let pipelineId = null;
let busy = false;
let slots = [];
let availabilityVersion = 0;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function option(value, text) {
  const node = element('option', text);
  node.value = value;
  return node;
}
function currentLead() {
  return state?.oportunidades.find((lead) => lead.id === selectedId);
}
function feedback(message, error = false) {
  $('feedback').textContent = message;
  $('feedback').classList.toggle('error', error);
}
function syncControls() {
  document.querySelectorAll('button, input, select, textarea').forEach((node) => {
    node.disabled = busy || !state;
  });
  const lead = currentLead();
  const paused = !lead || lead.opt_out || lead.handoff;
  $('message').disabled = busy || !state || paused;
  document.querySelectorAll('#message-form button, [data-example]').forEach((node) => {
    node.disabled = busy || !state || paused;
  });
  document.querySelectorAll('#reserve-form input, #reserve-form select, #reserve-form button').forEach((node) => {
    node.disabled = busy || !state || paused || (node.id === 'reserve-submit' && !slots.length);
  });
  document.body.setAttribute('aria-busy', String(busy));
}
async function api(path, payload) {
  const options = {cache: 'no-store'};
  if (payload !== undefined) {
    options.method = 'POST';
    options.headers = {'Content-Type': 'application/json'};
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.erro || 'Requisição local recusada.');
  return data;
}
async function act(path, payload, message) {
  if (busy) return false;
  busy = true;
  syncControls();
  feedback('Processando somente na sessão local…');
  try {
    const data = await api(path, payload);
    state = data.estado;
    render();
    await refreshAvailability();
    feedback(data.resultado.resposta || message);
    return true;
  } catch (error) {
    feedback(error.message, true);
    return false;
  } finally {
    busy = false;
    syncControls();
  }
}
function renderBoard() {
  const pipeline = state.pipelines.find((item) => item.id === pipelineId);
  $('board').replaceChildren();
  for (const stage of pipeline.etapas) {
    const column = element('section', undefined, 'kanban-column');
    const leads = state.oportunidades.filter((lead) => lead.pipeline_id === pipelineId && lead.etapa === stage);
    const heading = element('h3', stage);
    heading.append(element('span', String(leads.length), 'count'));
    column.append(heading);
    if (!leads.length) column.append(element('p', 'Sem oportunidades', 'empty-column'));
    for (const lead of leads) {
      const card = element('button', undefined, 'lead-card');
      card.type = 'button';
      card.setAttribute('aria-pressed', String(lead.id === selectedId));
      card.append(element('span', lead.id, 'mono'), element('strong', lead.nome));
      card.append(element('span', lead.opt_out ? 'Opt-out · automação pausada' : lead.handoff ? 'Handoff · automação pausada' : 'Oportunidade fictícia', 'card-status'));
      card.addEventListener('click', () => selectLead(lead.id));
      column.append(card);
    }
    $('board').append(column);
  }
}
function renderDetail() {
  const lead = currentLead();
  const pipeline = state.pipelines.find((item) => item.id === lead.pipeline_id);
  $('lead-id').textContent = lead.id;
  $('lead-name').textContent = lead.nome;
  $('lead-status').textContent = `${pipeline.nome} / ${lead.etapa} · ${lead.opt_out ? 'Opt-out: automação pausada' : lead.handoff ? 'Handoff simulado: automação pausada, nenhum humano notificado' : 'Automação local disponível'}`;
  $('fields').replaceChildren();
  for (const [key, label] of Object.entries(labels)) {
    $('fields').append(element('dt', label), element('dd', lead.campos[key] || 'Não coletado'));
  }
  $('stage').replaceChildren(...pipeline.etapas.map((stage) => option(stage, stage)));
  $('stage').value = lead.etapa;
  $('conversation').replaceChildren();
  if (!lead.conversa.length) $('conversation').append(element('p', 'Sem mensagens. Consulte a etapa ou use um exemplo fictício abaixo.', 'empty-state'));
  for (const message of lead.conversa) {
    const bubble = element('div', undefined, `bubble ${message.papel === 'pessoa' ? 'person' : 'assistant'}`);
    bubble.append(element('span', message.papel === 'pessoa' ? 'Pessoa fictícia' : 'Assistente local', 'bubble-author'), element('p', message.texto));
    $('conversation').append(bubble);
  }
  $('conversation').scrollTop = $('conversation').scrollHeight;
}
function fillReservation() {
  const lead = currentLead();
  $('reserve-name').value = lead.campos.nome || lead.nome;
  $('reserve-email').value = lead.campos.email || `${lead.id.slice(-1) === '1' ? 'a' : lead.id.slice(-1) === '2' ? 'b' : 'c'}@example.com`;
  $('reserve-subject').value = lead.campos.assunto || 'Atendimento digital';
  const previous = $('reserve-date').value;
  $('reserve-date').replaceChildren(...state.dias_disponiveis.map((day) => option(day, day.split('-').reverse().join('/'))));
  $('reserve-date').value = state.dias_disponiveis.includes(lead.campos.data) ? lead.campos.data : state.dias_disponiveis.includes(previous) ? previous : state.dias_disponiveis[0];
}
function tableEmpty(target, columns, message) {
  const row = element('tr');
  const cell = element('td', message, 'empty-state');
  cell.colSpan = columns;
  row.append(cell);
  target.append(row);
}
function renderTables() {
  $('reservations').replaceChildren();
  for (const reservation of state.reservas) {
    const row = element('tr');
    for (const text of [reservation.id, reservation.lead_id, `${reservation.data} / ${reservation.hora}`, reservation.assunto, 'SIMULADA · 30 min']) row.append(element('td', text));
    $('reservations').append(row);
  }
  if (!state.reservas.length) tableEmpty($('reservations'), 5, 'Nenhuma reserva simulada nesta sessão.');
  $('audit').replaceChildren();
  for (const event of [...state.eventos].reverse()) {
    const row = element('tr');
    for (const text of [String(event.sequencia), event.acao, event.lead_id, JSON.stringify(event.detalhe)]) row.append(element('td', text));
    $('audit').append(row);
  }
  if (!state.eventos.length) tableEmpty($('audit'), 4, 'Nenhuma ação registrada. Movimente, converse ou simule uma reserva.');
}
function render() {
  if (!state.pipelines.some((pipeline) => pipeline.id === pipelineId)) pipelineId = state.pipelines[0].id;
  if (!state.oportunidades.some((lead) => lead.id === selectedId && lead.pipeline_id === pipelineId)) {
    selectedId = state.oportunidades.find((lead) => lead.pipeline_id === pipelineId).id;
  }
  $('pipeline').replaceChildren(...state.pipelines.map((pipeline) => option(pipeline.id, pipeline.nome)));
  $('pipeline').value = pipelineId;
  $('reference').textContent = `Relógio fixo: ${state.referencia.split('-').reverse().join('/')} · ${state.oportunidades.length} oportunidades fictícias em ${state.pipelines.length} funis`;
  renderBoard();
  renderDetail();
  fillReservation();
  renderTables();
  syncControls();
}
async function refreshAvailability() {
  const version = ++availabilityVersion;
  const day = $('reserve-date').value;
  slots = [];
  $('reserve-time').replaceChildren(option('', 'Consultando…'));
  $('availability').textContent = 'Consultando horários da agenda fictícia…';
  syncControls();
  try {
    const data = await api(`/api/disponibilidade?data=${encodeURIComponent(day)}`);
    if (version !== availabilityVersion) return;
    slots = data.horarios;
    $('reserve-time').replaceChildren(...(slots.length ? slots.map((slot) => option(slot, slot)) : [option('', 'Sem horários') ]));
    $('availability').textContent = `${slots.length} horários livres na agenda simulada deste dia. A disponibilidade é validada novamente ao reservar.`;
  } catch (error) {
    if (version !== availabilityVersion) return;
    $('reserve-time').replaceChildren(option('', 'Falha na consulta'));
    $('availability').textContent = error.message;
    feedback(error.message, true);
  } finally {
    if (version === availabilityVersion) syncControls();
  }
}
async function selectLead(id) {
  if (busy) return;
  selectedId = id;
  $('message').value = '';
  render();
  await refreshAvailability();
  feedback('Ficha fictícia selecionada. Ações afetam somente a demo local.');
}
$('pipeline').addEventListener('change', async () => {
  pipelineId = $('pipeline').value;
  selectedId = null;
  $('message').value = '';
  render();
  await refreshAvailability();
  feedback('Funil local selecionado. Todas as etapas aparecem no quadro.');
});
$('reserve-date').addEventListener('change', refreshAvailability);
$('move-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  await act('/api/mover', {lead_id: selectedId, etapa: $('stage').value, pipeline_id: currentLead().pipeline_id}, 'Etapa atualizada somente na sessão local.');
});
$('message-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (await act('/api/mensagem', {lead_id: selectedId, texto: $('message').value}, 'Mensagem processada na demo.')) $('message').value = '';
});
$('reserve-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const campos = Object.fromEntries(new FormData($('reserve-form')));
  await act('/api/reservar', {lead_id: selectedId, campos}, 'Reserva SIMULADA registrada. Nenhum e-mail, Meet ou aviso a humano enviado.');
});
$('reset').addEventListener('click', async () => {
  if (window.confirm('Descartar as interações e reservas fictícias desta sessão local? O CRM real não é acessado.')) {
    if (await act('/api/reset', {}, 'Demonstração reiniciada. Somente dados locais foram descartados.')) $('message').value = '';
  }
});
document.querySelectorAll('[data-example]').forEach((button) => {
  button.addEventListener('click', () => {
    const lead = currentLead();
    const email = $('reserve-email').value;
    const examples = {
      status: 'Qual o status da minha oportunidade?',
      complete: `Sou ${lead.nome}, quero marcar uma reunião dia 03/11 às 15h sobre atendimento. Meu email é ${email}`,
      human: 'Quero falar com um humano',
      optout: 'Não quero mais receber mensagens'
    };
    $('message').value = examples[button.dataset.example];
    $('message').focus();
    feedback('Exemplo preenchido; clique em Enviar na demo para executar.');
  });
});
(async () => {
  busy = true;
  syncControls();
  try {
    state = await api('/api/estado');
    render();
    await refreshAvailability();
    feedback('Demo pronta. Nenhuma conexão com o CRM real.');
  } catch (error) {
    feedback(`Não foi possível carregar a demo local: ${error.message}. Recarregue a página para tentar novamente.`, true);
  } finally {
    busy = false;
    syncControls();
  }
})();
