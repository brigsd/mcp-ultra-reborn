// Helpers de DOM injetados no webview do Qwen Chat (chat.qwen.ai) via CDP.
//
// Cada Runtime.evaluate antepoe este arquivo e chama window.__qwen.<fn>(). A atribuicao
// e SEM guarda de existencia, de proposito: reinjeta fresco a cada chamada, para que
// mudancas neste arquivo sempre valham (uma guarda manteria a versao antiga na pagina).
// Tudo vive dentro da IIFE porque const/let no topo de um Runtime.evaluate persistem
// entre chamadas e colidem; uma atribuicao a window nao colide.
//
// Cliques NAO sao feitos aqui: estes helpers so leem o DOM, preenchem campos e
// devolvem o centro {x,y} dos elementos. O clique de verdade sai do Python via
// Input.dispatchMouseEvent (evento confiavel), que abre menus que o clique sintetico
// nao abre.
//
// Seletores calibrados no DOM real do Qwen desktop (jun/2026). Se a UI mudar, ajuste SEL.

window.__qwen = (function () {
    const SEL = {
      editor: 'textarea.message-input-textarea, textarea[placeholder]',
      sendBtn: 'button.send-button',
      userMsg: '.qwen-chat-message-user',
      assistant: '.qwen-chat-message-assistant',
      respAnswer: '.response-message-content.phase-answer',
      done: '.copy-response-button, .response-message-footer',
      editBtn: '.qwen-chat-package-comp-new-action-control-container-edit',
      editArea: 'textarea.qwen-edit-content-textarea',
      modelSelector: '[class*="model-selector"]',
      modelItem: '[class*="model-item"]',
      modelItemName: '[class*="model-item-name"]',
      viewMore: '[class*="view-more"]',
      novaConversa: '.sidebar-entry-fixed-list-content',
      novaConversaAlt: '.sidebar-entry-fixed-list',
    };

    const q = (s, r) => (r || document).querySelector(s);
    const qa = (s, r) => Array.from((r || document).querySelectorAll(s));
    const vis = (el) => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const norm = (s) => (s || "").replace(/\s+/g, " ").trim();

    function centro(el) {
      if (!el || !vis(el)) return null;
      el.scrollIntoView({ block: "center", inline: "center" });
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }

    // Textarea controlado por React: setter nativo + evento input.
    function preencherTextarea(field, text) {
      field.focus();
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
      setter.call(field, "");
      setter.call(field, text);
      field.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function hover(el) {
      ["pointerover", "mouseover", "mouseenter", "pointermove", "mousemove"].forEach((t) =>
        el.dispatchEvent(new MouseEvent(t, { bubbles: true }))
      );
    }

    const usuarios = () => qa(SEL.userMsg).filter(vis);
    const assistentes = () => qa(SEL.assistant).filter(vis);

    // Texto da resposta. Ancora SO na fase de resposta (.phase-answer), nunca no bloco
    // de "Pensamento": durante o raciocinio .phase-answer nao existe e isto devolve "",
    // entao a espera nao estabiliza no placeholder de pensamento. Em A/B pega o primeiro.
    function respTexto(el) {
      if (!el) return "";
      const ans = el.querySelector(SEL.respAnswer);
      if (!ans) return "";
      const t = norm(ans.innerText);
      // Durante o pensamento o .phase-answer mostra um placeholder ("A pensar...");
      // trata como vazio para a espera nao estabilizar nele.
      if (/^(a pensar|pensando|thinking|raciocinando|reasoning|carregando|loading)[.…]*$/i.test(t)) return "";
      return t;
    }

    // Resposta concluida: o rodape com o botao de copiar so aparece quando o texto
    // final esta pronto. Sinal de fim confiavel, alem da estabilizacao por tempo.
    function prontoResp(el) {
      return !!(el && el.querySelector(SEL.respAnswer) && el.querySelector(SEL.done));
    }

    function temAB() {
      return qa("button").some((b) => vis(b) && /prefiro esta resposta|prefer this/i.test(b.innerText || ""));
    }

    function descreverEl(el) {
      const o = { tag: el.tagName.toLowerCase() };
      ["id", "role", "aria-label", "title", "type", "placeholder", "contenteditable"].forEach((a) => {
        const v = el.getAttribute && el.getAttribute(a); if (v) o[a] = v;
      });
      if (typeof el.className === "string" && el.className.trim())
        o.cls = el.className.trim().split(/\s+/).slice(0, 5).join(".");
      o.vis = vis(el);
      const t = norm(el.innerText); if (t) o.txt = t.slice(0, 80);
      return o;
    }

    return {
      // ---- estado ----
      info() {
        return {
          usuarios: usuarios().length,
          assistentes: assistentes().length,
          temEditor: !!q(SEL.editor),
        };
      },
      // Tudo que a espera precisa, em uma evaluate so.
      snapshot() {
        const a = assistentes();
        const el = a[a.length - 1] || null;
        return {
          assistentes: a.length,
          usuarios: usuarios().length,
          texto: respTexto(el),
          pronto: prontoResp(el),
          ab: temAB(),
        };
      },
      qtdAssistentes() { return assistentes().length; },
      ultimaResposta() {
        const a = assistentes();
        return respTexto(a[a.length - 1] || null);
      },
      temAB,

      // ---- composer ----
      preencherComposer(text) {
        const ta = q(SEL.editor);
        if (!ta) return { erro: "sem editor" };
        preencherTextarea(ta, text);
        return { ok: true };
      },
      centroEnvio() { return centro(q(SEL.sendBtn)); },

      // ---- edicao (fluxo API) ----
      centroEditar(index) {
        const u = usuarios();
        const alvo = index == null ? u[u.length - 1] : u[index];
        if (!alvo) return null;
        hover(alvo);
        return centro(alvo.querySelector(SEL.editBtn));
      },
      preencherEdicao(text) {
        const ta = q(SEL.editArea);
        if (!ta) return { erro: "sem area de edicao" };
        preencherTextarea(ta, text);
        return { ok: true };
      },
      centroEnviarEdicao() {
        const btn = qa("button").find((b) =>
          vis(b) && /^(enviar|update|atualizar|发送)$/i.test(norm(b.innerText)) &&
          /brandprimary|primary/i.test(b.className || "")
        ) || qa("button").find((b) => vis(b) && /^(enviar|发送)$/i.test(norm(b.innerText)));
        return centro(btn);
      },

      // ---- modelo ----
      centroSeletorModelo() { return centro(q(SEL.modelSelector)); },
      centroModelo(nome) {
        const alvo = qa(SEL.modelItem).filter(vis).find((it) => {
          const nm = it.querySelector(SEL.modelItemName) || it;
          return norm(nm.innerText).toLowerCase().startsWith((nome || "").toLowerCase());
        });
        return centro(alvo);
      },
      modelosDisponiveis() {
        return qa(SEL.modelItemName).filter(vis).map((n) => norm(n.innerText)).filter(Boolean);
      },
      centroExpandirModelos() {
        let el = q(SEL.viewMore);
        if (!el) {
          const all = qa('div, span, button');
          el = all.find(x => x.innerText && x.innerText.includes("Expandir"));
        }
        return centro(el);
      },

      // ---- nova conversa ----
      centroNova() {
        return centro(q(SEL.novaConversa) || q(SEL.novaConversaAlt));
      },

      // ---- A/B ----
      centroPreferir() {
        const b = qa("button").filter((x) => vis(x) && /prefiro esta resposta|prefer this/i.test(x.innerText || ""))[0];
        return centro(b);
      },

      // ---- diagnostico ----
      inspecionar(seletor, max) {
        max = max || 40;
        const rep = { url: location.href };
        if (seletor) {
          const all = qa(seletor);
          rep.seletor = seletor;
          rep.count = all.length;
          rep.matches = all.slice(0, max).map(descreverEl);
        } else {
          rep.interativos = qa('button, [role="button"], textarea, [contenteditable="true"], [class*="model-selector"]')
            .filter(vis).slice(0, max).map(descreverEl);
          const counts = {};
          qa("*").forEach((el) => { const t = el.tagName.toLowerCase(); if (t.includes("-")) counts[t] = (counts[t] || 0) + 1; });
          rep.customElements = counts;
        }
        return JSON.stringify(rep, null, 2);
      },
    };
})();
