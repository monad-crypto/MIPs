// Status, type and category glossary, condensed from MIP-1.
var TIPS = {
  "Standards Track": "A change affecting most or all Monad implementations: protocol rules, interfaces, or application standards.",
  "Meta": "Describes a process around Monad, or a change to one, rather than the protocol itself.",
  "Informational": "Design guidance or general information. Non-binding, so implementers may ignore it.",
  "Core": "Execution- or consensus-layer changes to protocol behavior. Requires a network upgrade.",
  "Networking": "The peer-to-peer layer: block propagation (RaptorCast) and transaction dissemination.",
  "Interface": "Client-level standards such as JSON-RPC method names and contract ABIs.",
  "MRC": "Application-level standards: token standards, registries, URI schemes, wallet formats.",
  "Process": "Procedures, guidelines, and the MIP process itself.",
  "Hardfork": "Lists the MIPs included in a named network upgrade and its activation timestamps.",
  "Draft": "The first formally tracked stage. Merged by an editor once properly formatted.",
  "Review": "The author has marked the MIP as ready for peer review.",
  "Last Call": "Final review window of typically 14 days before the MIP becomes Final.",
  "Final": "The adopted standard. Updated only for errata and non-normative clarifications.",
  "Stagnant": "Inactive in Draft, Review, or Last Call for three months or more. Can be revived by an author or editor.",
  "Withdrawn": "Withdrawn by the author. The number will not be reused.",
  "Living": "Continually updated and never reaches finality."
};

// Twin of the pair the citation button carries in _layouts/proposal.html.
var COPY_ICONS =
  '<svg class="ic-copy" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg>' +
  '<svg class="ic-done" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7"/></svg>';

// no async clipboard outside a secure context, and some WebViews never expose it
function legacyCopy(text) {
  var field = document.createElement("textarea");
  field.value = text;
  field.setAttribute("readonly", "");
  field.style.cssText = "position:fixed;top:-9999px";
  document.body.appendChild(field);
  field.select();
  var copied = false;
  try {
    copied = document.execCommand("copy");
  } catch (_) {}
  field.remove();
  return copied;
}

function copyText(text, button) {
  var payload = (text || "").trim();
  // only tick when the text is actually on the clipboard
  var done = function () {
    button.dataset.done = "true";
    clearTimeout(button.copyTimer);
    button.copyTimer = setTimeout(function () { button.dataset.done = "false"; }, 1800);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(payload).then(done, function () {
      if (legacyCopy(payload)) done();
    });
    return;
  }
  if (legacyCopy(payload)) done();
}

document.addEventListener("DOMContentLoaded", function () {
  if (window.Prism && typeof Prism.highlightElement === "function") {
    document.querySelectorAll("pre > code").forEach(function (code) {
      var pre = code.parentElement;
      if (!pre) return;

      var languageClass = Array.from(code.classList).find(function (cls) {
        return cls.indexOf("language-") === 0;
      });

      if (!languageClass) {
        var wrapper = code.closest("[class*='language-']");
        if (wrapper) {
          languageClass = Array.from(wrapper.classList).find(function (cls) {
            return cls.indexOf("language-") === 0;
          });
        }
      }

      if (!languageClass || languageClass === "language-plaintext") return;

      code.classList.add(languageClass);
      pre.classList.add(languageClass);
      Prism.highlightElement(code);
    });
  }

  // Relative links between proposals are written with the .md extension so
  // they resolve on GitHub too; the published pages have none.
  document.querySelectorAll("a[href]").forEach(function (link) {
    var href = link.getAttribute("href");
    if (!href || /^(https?:|mailto:|#)/.test(href)) return;
    if (/(^|\/)(MIP|MRC)-\d+\.md(#.*)?$/.test(href)) {
      link.setAttribute("href", href.replace(/\.md(?=#|$)/, ""));
    }
  });

  function escapeHtml(value) {
    return value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function linkifyAuthor(value) {
    var pattern = /([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})|@([a-z\d](?:[a-z\d-]{0,38}))/gi;
    var output = "";
    var lastIndex = 0;
    var match;

    while ((match = pattern.exec(value)) !== null) {
      output += escapeHtml(value.slice(lastIndex, match.index));
      if (match[1]) {
        output += '<a href="mailto:' + match[1] + '">' + escapeHtml(match[1]) + "</a>";
      } else {
        output += '<a href="https://github.com/' + match[2] + '">@' + escapeHtml(match[2]) + "</a>";
      }
      lastIndex = pattern.lastIndex;
    }

    output += escapeHtml(value.slice(lastIndex));
    return output;
  }

  function linkifyMentionsInText(value) {
    var pattern = /(^|[^a-z\d_])@([a-z\d](?:[a-z\d-]{0,38}))/gi;
    var output = "";
    var lastIndex = 0;
    var match;

    while ((match = pattern.exec(value)) !== null) {
      output += escapeHtml(value.slice(lastIndex, match.index));
      output += escapeHtml(match[1]);
      output += '<a href="https://github.com/' + match[2] + '">@' + escapeHtml(match[2]) + "</a>";
      lastIndex = pattern.lastIndex;
    }

    output += escapeHtml(value.slice(lastIndex));
    return output;
  }

  document.querySelectorAll(".author-value").forEach(function (field) {
    field.innerHTML = linkifyAuthor(field.textContent || "");
  });

  // Runs before the index's deferred search captures cell HTML, so the
  // tooltips survive filter and highlight redraws.
  document.querySelectorAll(".tip").forEach(function (el) {
    var tip = TIPS[(el.textContent || "").trim()];
    if (!tip) return;
    el.setAttribute("data-tip", tip);
    // Mouse users get the tooltip on hover regardless. Only make a term
    // keyboard-focusable outside the index tables, which would otherwise add
    // two tab stops per row. Generated ::after content isn't reliably exposed
    // to assistive tech, so fold the explanation into the accessible name.
    if (!el.closest(".ledger")) {
      el.setAttribute("tabindex", "0");
      el.setAttribute("aria-label", (el.textContent || "").trim() + ": " + tip);
    }
  });

  // Tooltips are CSS-driven; this only picks the side and alignment that fit
  // the viewport at the moment of hover.
  document.addEventListener("pointerover", function (e) {
    var el = e.target.closest && e.target.closest(".tip[data-tip]");
    if (!el) return;
    var r = el.getBoundingClientRect();
    var align = "";
    var cx = r.left + r.width / 2;
    if (cx + 126 > window.innerWidth - 12) align = "end";
    else if (cx - 126 < 12) align = "start";
    if (align) el.setAttribute("data-tip-align", align);
    else el.removeAttribute("data-tip-align");
    if (r.top < 90) el.setAttribute("data-tip-side", "bottom");
    else el.removeAttribute("data-tip-side");
  });

  var prose = document.querySelector(".prose");

  if (prose) {
    var walker = document.createTreeWalker(prose, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        var tag = parent.tagName;
        if (tag === "A" || tag === "CODE" || tag === "PRE" || tag === "SCRIPT" || tag === "STYLE") {
          return NodeFilter.FILTER_REJECT;
        }
        if (!node.nodeValue || node.nodeValue.indexOf("@") === -1) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });

    var textNodes = [];
    var current;
    while ((current = walker.nextNode())) textNodes.push(current);

    textNodes.forEach(function (node) {
      var raw = node.nodeValue || "";
      var linked = linkifyMentionsInText(raw);
      if (linked === escapeHtml(raw)) return;
      var replacement = document.createElement("span");
      replacement.innerHTML = linked;
      node.parentNode.replaceChild(replacement, node);
    });

    // Wide specification tables scroll in their own box rather than dragging
    // the whole page sideways.
    prose.querySelectorAll("table").forEach(function (table) {
      var box = document.createElement("div");
      box.className = "table-scroll";
      table.parentNode.insertBefore(box, table);
      box.appendChild(table);
    });

    prose.querySelectorAll("pre").forEach(function (pre) {
      var box = document.createElement("div");
      box.className = "codeblock";
      pre.parentNode.insertBefore(box, pre);
      box.appendChild(pre);

      var button = document.createElement("button");
      button.type = "button";
      button.className = "cbtn copy";
      button.title = "Copy code";
      button.setAttribute("aria-label", "Copy code");
      button.innerHTML = COPY_ICONS;
      button.addEventListener("click", function () { copyText(pre.textContent, button); });
      box.appendChild(button);
    });
  }

  var tocNav = document.getElementById("page-toc");
  var tocList = document.getElementById("page-toc-list");
  var progressBar = document.getElementById("toc-progress-bar");
  var tocItems = [];
  var headings = prose
    ? Array.prototype.slice.call(prose.querySelectorAll("h2[id], h3[id], h4[id]"))
    : [];

  headings.forEach(function (heading) {
    var anchor = document.createElement("a");
    anchor.className = "anchor";
    anchor.href = "#" + heading.id;
    anchor.textContent = "#";
    anchor.setAttribute("aria-label", "Link to this section");
    heading.insertBefore(anchor, heading.firstChild);

    if (headings.length < 3) return;

    var item = document.createElement("a");
    item.className = "toc-item toc-item--" + heading.tagName.toLowerCase();
    item.href = "#" + heading.id;
    var label = document.createElement("span");
    label.className = "toc-label";
    label.textContent = (heading.textContent || "").replace(/^#/, "").trim();
    var tick = document.createElement("span");
    tick.className = "toc-tick";
    tick.setAttribute("aria-hidden", "true");
    item.appendChild(label);
    item.appendChild(tick);
    tocList.appendChild(item);
    tocItems.push({ item: item, heading: heading });
  });

  var activeIndex = -1;
  var peekTimer;

  // Long documents overflow the rail's max height, so keep the active tick in
  // view when the panel scrolls.
  function followToc(index) {
    if (tocList.scrollHeight <= tocList.clientHeight + 1) return;
    var el = tocItems[index].item;
    var target = el.offsetTop - tocList.clientHeight / 2 + el.offsetHeight / 2;
    tocList.scrollTop = Math.max(0, Math.min(tocList.scrollHeight - tocList.clientHeight, target));
  }

  function syncActive() {
    if (!tocItems.length) return;

    var next = 0;
    for (var i = 0; i < tocItems.length; i++) {
      if (tocItems[i].heading.getBoundingClientRect().top > 120) break;
      next = i;
    }

    // Trailing sections are shorter than the viewport, so they never cross the
    // line; at the foot of the page the last heading is the current one.
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) {
      next = tocItems.length - 1;
    }

    if (next === activeIndex) return;
    if (activeIndex >= 0) {
      tocItems[activeIndex].item.classList.remove("is-active");
      tocItems[activeIndex].item.removeAttribute("aria-current");
    }
    activeIndex = next;
    tocItems[activeIndex].item.classList.add("is-active");
    tocItems[activeIndex].item.setAttribute("aria-current", "true");
    followToc(activeIndex);
  }

  function syncProgress() {
    var max = document.documentElement.scrollHeight - window.innerHeight;
    var pct = max > 0 ? Math.min(100, Math.max(0, (window.scrollY / max) * 100)) : 0;
    progressBar.style.height = pct.toFixed(2) + "%";
  }

  var queued = false;
  function onScroll() {
    if (!queued) {
      queued = true;
      window.requestAnimationFrame(function () {
        queued = false;
        syncActive();
        syncProgress();
      });
    }
    // While the reader is moving, the current section names itself.
    tocNav.dataset.peek = "true";
    clearTimeout(peekTimer);
    peekTimer = setTimeout(function () { tocNav.dataset.peek = "false"; }, 1400);
  }

  if (tocItems.length) {
    document.body.classList.add("has-toc");
    tocNav.hidden = false;
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", function () { syncActive(); syncProgress(); }, { passive: true });
    syncActive();
    syncProgress();
  }

  function hashTarget() {
    try {
      return document.getElementById(decodeURIComponent(location.hash.slice(1)));
    } catch (_) {
      return null;
    }
  }

  function flash(target) {
    target.classList.remove("anchor-flash");
    void target.offsetWidth;
    target.classList.add("anchor-flash");
  }

  // The browser lands on the fragment before highlighting and images settle,
  // leaving the section off-screen; realign here and again after load, unless
  // the reader has taken over.
  function alignToHash() {
    var target = hashTarget();
    if (!target) return;
    // behavior:auto defers to html { scroll-behavior: smooth }, which would
    // animate the reader down the whole document; suppress it for this call
    var root = document.documentElement;
    root.style.scrollBehavior = "auto";
    target.scrollIntoView({ block: "start", behavior: "auto" });
    root.style.scrollBehavior = "";
    flash(target);
    syncActive();
  }

  var readerMoved = false;
  ["wheel", "touchstart", "pointerdown", "keydown"].forEach(function (name) {
    window.addEventListener(name, function () { readerMoved = true; }, { passive: true, once: true });
  });

  alignToHash();
  window.addEventListener("load", function () {
    if (!readerMoved) alignToHash();
    if (tocItems.length) { syncActive(); syncProgress(); }
  });

  window.addEventListener("hashchange", function () {
    var target = hashTarget();
    if (target) flash(target);
    if (tocItems.length) { syncActive(); syncProgress(); }
  });

  var copyButton = document.getElementById("copy-citation");
  if (copyButton) {
    copyButton.addEventListener("click", function () {
      copyText(document.getElementById("citation-text").textContent, copyButton);
    });
  }
});

// Prefetch selected internal links on hover or focus.
var prefetched = new Set();
var hoverTimer;

function linkFrom(e) {
  return e.target instanceof Element ? e.target.closest("a[href], [data-href]") : null;
}

function maybePrefetchLink(link) {
  var href = link.getAttribute("data-href") || link.getAttribute("href");
  if (!href || href.charAt(0) === "#") return;
  if (!link.hasAttribute("data-prefetch-on-hover") && !/(MIP|MRC)-\d+/.test(href)) return;
  try {
    var url = new URL(href, location.href);
  } catch (_) {
    return;
  }
  if ((url.protocol !== "http:" && url.protocol !== "https:") || url.origin !== location.origin) return;
  if (prefetched.has(url.href)) return;
  prefetched.add(url.href);

  // A plain <link rel=prefetch> only warms the HTTP cache, which the navigation
  // is free to ignore, and does. A speculation rule feeds the navigation itself;
  // as=document is the closest the fallback gets.
  if (typeof HTMLScriptElement.supports === "function" && HTMLScriptElement.supports("speculationrules")) {
    var rules = document.createElement("script");
    rules.type = "speculationrules";
    rules.textContent = JSON.stringify({
      prefetch: [{ source: "list", urls: [url.href], eagerness: "immediate" }]
    });
    document.head.appendChild(rules);
    return;
  }

  var prefetchLink = document.createElement("link");
  prefetchLink.rel = "prefetch";
  prefetchLink.as = "document";
  prefetchLink.href = url.href;
  document.head.appendChild(prefetchLink);
}

// Hover waits a beat so sweeping down the index doesn't prefetch every row it
// passes; focus is deliberate, so it's immediate.
document.addEventListener("mouseover", function (e) {
  var link = linkFrom(e);
  clearTimeout(hoverTimer);
  if (link) hoverTimer = setTimeout(function () { maybePrefetchLink(link); }, 45);
});

document.addEventListener("mouseout", function () {
  clearTimeout(hoverTimer);
});

document.addEventListener("focusin", function (e) {
  var link = linkFrom(e);
  if (link) maybePrefetchLink(link);
});
