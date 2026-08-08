// In-page extraction engine for fetch-open-chat-tab.
//
// Runs two ways:
//   1. Inside Safari via `do JavaScript` (no `module` global) — exposes
//      `window.__focLib` and is driven by safari_driver.js.
//   2. Under plain Node for unit tests (no DOM) — only the pure functions
//      (detectSite, fingerprint) are exercised there; anything touching
//      `document`/`window` is skipped when those globals don't exist.
//
// Design notes (verified empirically against live chatgpt.com, claude.ai,
// and gemini.google.com tabs before writing this):
//   - Long conversations are DOM-virtualized on claude.ai and (very likely,
//     same "infinite-scroller" custom element family) gemini.google.com:
//     scrolling away un-mounts earlier message nodes, scrolling back
//     re-mounts them. A single querySelectorAll() snapshot therefore misses
//     most of a long conversation. The fix is `loadFullHistory` (scroll to
//     top repeatedly until scrollHeight stops growing) followed by
//     `sweepCollect` (walk top→bottom in overlapping steps, accumulating
//     whatever is mounted at each step into a de-duplicated, ordered list).
//   - `do JavaScript` does NOT await returned promises — it evaluates the
//     source and returns immediately. All async work here therefore runs
//     as a fire-and-forget IIFE that writes its result to
//     `window.__foc_result`, polled from the driver script via repeated
//     synchronous `do JavaScript` calls.

(function (root) {
  'use strict';

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  // --- Pure functions (unit-tested under Node) ---------------------------

  function detectSite(hostname, pathname) {
    hostname = String(hostname || '').toLowerCase();
    pathname = String(pathname || '');
    if (/(^|\.)chatgpt\.com$/.test(hostname) || /(^|\.)chat\.openai\.com$/.test(hostname)) {
      return 'chatgpt';
    }
    if (/(^|\.)claude\.ai$/.test(hostname)) {
      return 'claude';
    }
    if (/(^|\.)gemini\.google\.com$/.test(hostname)) {
      return 'gemini';
    }
    return null;
  }

  // Exact-content dedup key. Full text (not a truncated preview) so two
  // genuinely different messages never collide; the one accepted, disclosed
  // edge case is two *identical* messages with no distinguishing id, which
  // collapse into a single entry (see SKILL.md).
  function fingerprint(role, text, id) {
    if (id) return role + ' id ' + id;
    return role + ' text ' + text;
  }

  // Virtualized sites (claude.ai) mount turns out of visitation order as the
  // sweep scrolls through overlapping windows, so first-seen insertion order
  // is NOT reading order there. When every message carries a purely-numeric
  // id (Claude's aria-posinset), that id IS the reading order and is
  // authoritative; otherwise (ChatGPT's UUID ids, or no id) the original
  // insertion order — already correct there — is left untouched.
  function orderMessages(messages) {
    var allNumeric = messages.length > 0 && messages.every(function (m) {
      return typeof m.id === 'string' && /^\d+$/.test(m.id);
    });
    if (!allNumeric) return messages;
    return messages.slice().sort(function (a, b) { return parseInt(a.id, 10) - parseInt(b.id, 10); });
  }

  // --- DOM-dependent helpers (only reachable inside a real page) ---------

  function cleanClone(el) {
    var clone = el.cloneNode(true);
    var junk = clone.querySelectorAll(
      '.cdk-visually-hidden, .sr-only, [aria-hidden="true"], button, [role="toolbar"], svg'
    );
    for (var i = 0; i < junk.length; i++) junk[i].remove();
    return clone;
  }

  function findGenericScrollRoot() {
    var all = document.querySelectorAll('body *');
    var best = null;
    var bestArea = 0;
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var cs;
      try {
        cs = getComputedStyle(el);
      } catch (e) {
        continue;
      }
      if (!/(auto|scroll)/.test(cs.overflowY)) continue;
      if (el.scrollHeight - el.clientHeight < 100) continue;
      if (el.clientHeight < 150) continue;
      var area = el.clientWidth * el.clientHeight;
      if (area > bestArea) {
        bestArea = area;
        best = el;
      }
    }
    return best || document.scrollingElement || document.documentElement;
  }

  var SITE_CONFIGS = {
    chatgpt: {
      getMessages: function () {
        var nodes = document.querySelectorAll('[data-message-author-role]');
        var out = [];
        for (var i = 0; i < nodes.length; i++) {
          var el = nodes[i];
          var role = el.getAttribute('data-message-author-role');
          if (role === 'system') continue;
          var id = el.getAttribute('data-message-id');
          var text = cleanClone(el).innerText.trim();
          if (!text) continue;
          out.push({ role: role, id: id, text: text });
        }
        return out;
      }
    },
    claude: {
      // `[data-test-render-count]` is NOT an assistant-only signal — Claude.ai
      // runs every turn's content through the same markdown renderer, so a
      // first attempt keying off it duplicated every user turn as a second,
      // byte-identical "assistant" entry (verified live). The reliable unit
      // is instead `[role="article"][aria-posinset]`: one such element per
      // conversation turn (both roles), with a stable, globally-unique
      // position (`aria-posinset`) that survives virtualization remounts —
      // used directly as the dedup id instead of a content fingerprint.
      getMessages: function () {
        var articles = document.querySelectorAll('[role="article"][aria-posinset]');
        var out = [];
        for (var i = 0; i < articles.length; i++) {
          var a = articles[i];
          var pos = a.getAttribute('aria-posinset');
          var role = a.querySelector('[data-testid="user-message"]') ? 'user' : 'assistant';
          var contentEl = a.querySelector('[data-test-render-count]') || a;
          var text = cleanClone(contentEl).innerText.trim();
          if (!text) continue;
          out.push({ role: role, id: pos, text: text });
        }
        return out;
      }
    },
    gemini: {
      getMessages: function () {
        var userNodes = document.getElementsByTagName('user-query');
        var modelNodes = document.getElementsByTagName('model-response');
        var merged = [];
        for (var i = 0; i < userNodes.length; i++) merged.push({ role: 'user', el: userNodes[i] });
        for (var j = 0; j < modelNodes.length; j++) merged.push({ role: 'assistant', el: modelNodes[j] });
        merged.sort(function (a, b) {
          var pos = a.el.compareDocumentPosition(b.el);
          return pos & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
        });
        var out = [];
        for (var k = 0; k < merged.length; k++) {
          var text = cleanClone(merged[k].el).innerText.trim();
          if (!text) continue;
          out.push({ role: merged[k].role, id: null, text: text });
        }
        return out;
      }
    }
  };

  // --- Scroll-and-collect engine ------------------------------------------

  function loadFullHistory(scrollRoot, deadline) {
    return (async function () {
      var lastHeight = -1;
      var stableRounds = 0;
      var maxRounds = 60;
      for (var i = 0; i < maxRounds; i++) {
        if (Date.now() > deadline) break;
        scrollRoot.scrollTop = 0;
        await sleep(450);
        var h = scrollRoot.scrollHeight;
        if (h === lastHeight) {
          stableRounds++;
          if (stableRounds >= 2) break;
        } else {
          stableRounds = 0;
        }
        lastHeight = h;
      }
    })();
  }

  function sweepCollect(scrollRoot, collectFn, deadline) {
    return (async function () {
      var seen = {};
      var order = [];
      function finalize(partial) {
        return { messages: orderMessages(order.map(function (k) { return seen[k]; })), partial: partial };
      }
      scrollRoot.scrollTop = 0;
      await sleep(300);
      var lastTop = -1;
      var stuck = 0;
      var maxSteps = 300;
      for (var i = 0; i < maxSteps; i++) {
        var batch = collectFn();
        for (var b = 0; b < batch.length; b++) {
          var m = batch[b];
          var key = fingerprint(m.role, m.text, m.id);
          if (!Object.prototype.hasOwnProperty.call(seen, key)) {
            seen[key] = m;
            order.push(key);
          }
        }
        var atBottom = scrollRoot.scrollTop + scrollRoot.clientHeight >= scrollRoot.scrollHeight - 2;
        if (atBottom || Date.now() > deadline) {
          return finalize(Date.now() > deadline);
        }
        scrollRoot.scrollTop = Math.min(scrollRoot.scrollHeight, scrollRoot.scrollTop + scrollRoot.clientHeight * 0.7);
        await sleep(380);
        if (scrollRoot.scrollTop === lastTop) {
          stuck++;
          if (stuck > 3) break;
        } else {
          stuck = 0;
        }
        lastTop = scrollRoot.scrollTop;
      }
      return finalize(Date.now() > deadline);
    })();
  }

  function computeFallbackText() {
    try {
      var clone = cleanClone(document.body);
      return clone.innerText.trim().slice(0, 100000);
    } catch (e) {
      return '';
    }
  }

  async function runExtraction() {
    var deadline = Date.now() + 90000; // hard wall-clock budget for the whole extraction
    var host = location.hostname;
    var title = document.title || 'Untitled';
    var siteKey = detectSite(host, location.pathname);

    if (!siteKey) {
      return {
        ok: false,
        reason: 'Unrecognized host "' + host + '" — no site-specific extractor for this chat UI (supported: chatgpt.com, claude.ai, gemini.google.com).',
        host: host,
        title: title,
        fallbackText: computeFallbackText()
      };
    }

    var config = SITE_CONFIGS[siteKey];
    var scrollRoot;
    try {
      scrollRoot = findGenericScrollRoot();
    } catch (e) {
      scrollRoot = document.scrollingElement || document.documentElement;
    }

    await loadFullHistory(scrollRoot, deadline);
    var swept = await sweepCollect(scrollRoot, config.getMessages, deadline);

    if (swept.messages.length === 0) {
      return {
        ok: false,
        reason: 'No messages found via the ' + siteKey + ' extractor — the page structure may have changed, the conversation may not be fully loaded, or this is not actually a conversation page.',
        host: host,
        title: title,
        site: siteKey,
        fallbackText: computeFallbackText()
      };
    }

    return {
      ok: true,
      host: host,
      title: title,
      site: siteKey,
      messages: swept.messages,
      partial: swept.partial
    };
  }

  root.__focLib = {
    detectSite: detectSite,
    fingerprint: fingerprint,
    orderMessages: orderMessages,
    runExtraction: runExtraction
  };
})(typeof window !== 'undefined' ? window : this);

// Node/CommonJS export for unit tests — no-op inside Safari (no `module`).
if (typeof module !== 'undefined' && module.exports) {
  var lib = (typeof window !== 'undefined' ? window : this).__focLib;
  module.exports = {
    detectSite: lib.detectSite,
    fingerprint: lib.fingerprint,
    orderMessages: lib.orderMessages
  };
}
