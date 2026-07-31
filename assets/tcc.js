/* ============================================================
   TCC · MBA em IA & Negócios — comportamento compartilhado
   Abas, listas com checkbox e anotações (tudo em localStorage,
   com namespace por direção para as duas páginas não se misturarem).
   Defina window.TCC_NS antes de carregar este script. Ex.: 'a' ou 'b'.
   ============================================================ */
(function () {
  'use strict';
  var NS = window.TCC_NS || 'x';
  var k = function (nome) { return 'tcc_' + NS + '_' + nome; };

  /* Migração única das chaves antigas do hub (direção B herdou o conteúdo). */
  (function migra() {
    var de_para = { mba_ia_tasks: k('tasks'), mba_ia_pains: k('pains'), mba_ia_notes: k('notes') };
    if (NS !== 'b') return;
    Object.keys(de_para).forEach(function (antiga) {
      var nova = de_para[antiga];
      if (localStorage.getItem(nova) === null && localStorage.getItem(antiga) !== null) {
        localStorage.setItem(nova, localStorage.getItem(antiga));
      }
    });
  })();

  /* ------------------------------------------------------------ abas */
  var botoes = document.querySelectorAll('nav.tabs button');
  var painels = document.querySelectorAll('section.tab');
  var ids = Array.prototype.map.call(painels, function (s) { return s.id; });

  function mostra(id, empurraHash) {
    if (ids.indexOf(id) === -1) return false;
    Array.prototype.forEach.call(botoes, function (b) {
      b.classList.toggle('active', b.dataset.t === id);
      b.setAttribute('aria-selected', b.dataset.t === id ? 'true' : 'false');
    });
    Array.prototype.forEach.call(painels, function (s) { s.classList.toggle('active', s.id === id); });
    if (empurraHash) history.replaceState(null, '', '#' + id);
    return true;
  }

  Array.prototype.forEach.call(botoes, function (b) {
    b.onclick = function () {
      mostra(b.dataset.t, true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };
  });

  // hash inicial: só troca de aba se for um id de aba (âncoras do relatório seguem funcionando)
  if (location.hash) mostra(location.hash.slice(1), false);
  window.addEventListener('hashchange', function () { mostra(location.hash.slice(1), false); });

  /* -------------------------------------------- listas com checkbox */
  function lista(chave, idLista, idInput, idBotao, padroes, aoMudar) {
    var alvo = document.getElementById(idLista);
    if (!alvo) return;
    var itens = JSON.parse(localStorage.getItem(chave) || 'null');
    if (!itens) itens = (padroes || []).map(function (t) { return { t: t, done: false }; });

    function salva() { localStorage.setItem(chave, JSON.stringify(itens)); desenha(); }

    function desenha() {
      alvo.innerHTML = '';
      itens.forEach(function (item, i) {
        var li = document.createElement('li');
        if (item.done) li.className = 'done';
        var id = idLista + '-' + i;
        var cb = document.createElement('input');
        cb.type = 'checkbox'; cb.id = id; cb.checked = !!item.done;
        cb.onchange = function () { itens[i].done = !itens[i].done; salva(); };
        var lb = document.createElement('label');
        lb.htmlFor = id; lb.textContent = item.t;
        var del = document.createElement('button');
        del.className = 'del'; del.title = 'Remover'; del.textContent = '✕';
        del.onclick = function () { itens.splice(i, 1); salva(); };
        li.appendChild(cb); li.appendChild(lb); li.appendChild(del);
        alvo.appendChild(li);
      });
      if (typeof aoMudar === 'function') aoMudar(itens);
    }

    var input = document.getElementById(idInput);
    var botao = document.getElementById(idBotao);
    function adiciona() {
      if (input && input.value.trim()) {
        itens.push({ t: input.value.trim(), done: false });
        input.value = '';
        salva();
      }
    }
    if (botao) botao.onclick = adiciona;
    if (input) input.addEventListener('keydown', function (e) { if (e.key === 'Enter') adiciona(); });
    desenha();
  }

  /* ------------------------------------------------------- progresso */
  function progresso(itens) {
    var feitos = itens.filter(function (t) { return t.done; }).length;
    var total = itens.length;
    var pct = total ? Math.round(feitos / total * 100) : 0;
    var d = document.getElementById('s-done'), p = document.getElementById('s-pct'), b = document.getElementById('bar');
    if (d) d.textContent = feitos;
    if (p) p.textContent = pct + '%';
    if (b) b.style.width = pct + '%';
  }

  /* ------------------------------------------------------- anotações */
  function anotacoes(chave) {
    var ta = document.getElementById('notes');
    if (!ta) return;
    var aviso = document.getElementById('saved');
    ta.value = localStorage.getItem(chave) || '';
    var t;
    ta.addEventListener('input', function () {
      localStorage.setItem(chave, ta.value);
      if (!aviso) return;
      aviso.classList.add('show');
      clearTimeout(t);
      t = setTimeout(function () { aviso.classList.remove('show'); }, 1200);
    });
  }

  /* ------------------------------------------------------------ API */
  window.TCC = {
    chave: k,
    listaTarefas: function (padroes) { lista(k('tasks'), 'tasks', 'task-in', 'task-add', padroes, progresso); },
    listaDores: function (padroes) { lista(k('pains'), 'pains', 'pain-in', 'pain-add', padroes || []); },
    anotacoes: function () { anotacoes(k('notes')); },
    personas: function (idGrade, lista) {
      var g = document.getElementById(idGrade);
      if (!g) return;
      lista.forEach(function (p) {
        var el = document.createElement('div');
        el.className = 'card';
        var h = document.createElement('h3'); h.textContent = p.n;
        var lead = document.createElement('p'); lead.textContent = p.d || 'Quer:';
        var ul = document.createElement('ul');
        (p.w || []).forEach(function (x) { var li = document.createElement('li'); li.textContent = x; ul.appendChild(li); });
        el.appendChild(h); el.appendChild(lead); el.appendChild(ul);
        g.appendChild(el);
      });
    }
  };
})();
