// The index: MIPs / MRCs tabs, one search box across both, and a status filter.
(function () {
  var ORDER = ["Draft", "Review", "Last Call", "Final", "Stagnant", "Withdrawn", "Living"];

  function slug(s) {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function escapeRegex(v) {
    return v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function highlightCell(cell, re) {
    var walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    var n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var text = node.nodeValue || "";
      re.lastIndex = 0;
      if (!re.test(text)) return;
      re.lastIndex = 0;
      var frag = document.createDocumentFragment();
      var lastIndex = 0;
      var m;
      while ((m = re.exec(text)) !== null) {
        if (m[0].length === 0) { re.lastIndex++; continue; }
        if (m.index > lastIndex) frag.appendChild(document.createTextNode(text.slice(lastIndex, m.index)));
        var mark = document.createElement("mark");
        mark.textContent = m[0];
        frag.appendChild(mark);
        lastIndex = re.lastIndex;
      }
      if (lastIndex < text.length) frag.appendChild(document.createTextNode(text.slice(lastIndex)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  function start() {
    var panels = {
      mips: document.getElementById("panel-mips"),
      mrcs: document.getElementById("panel-mrcs")
    };
    if (!panels.mips) return;

    var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
    var input = document.getElementById("proposal-search");
    var clearButton = document.getElementById("search-clear");
    var hint = document.getElementById("search-hint");
    var filterButton = document.getElementById("filter-button");
    var filterMenu = document.getElementById("filter-menu");
    var emptyState = document.getElementById("no-results");
    var statuses = [];
    var active = "mips";

    var groups = Object.keys(panels).map(function (key) {
      var table = panels[key] && panels[key].querySelector(".ledger");
      if (!table || !table.tBodies[0]) return null;
      return {
        key: key,
        table: table,
        rows: Array.prototype.slice.call(table.tBodies[0].rows).map(function (row) {
          var cells = Array.prototype.slice.call(row.cells);
          return {
            row: row,
            status: row.dataset.status || "",
            cells: cells,
            originals: cells.map(function (cell) { return cell.innerHTML; }),
            text: (row.textContent || "").toLowerCase()
          };
        })
      };
    }).filter(Boolean);

    function activate(name, focusTab) {
      active = panels[name] ? name : "mips";
      tabs.forEach(function (tab) {
        var on = tab.dataset.panel === active;
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
        if (on && focusTab) tab.focus();
      });
      Object.keys(panels).forEach(function (key) {
        if (panels[key]) panels[key].hidden = key !== active;
      });
    }

    function renderMenu(counts, total) {
      filterButton.firstChild.nodeValue = statuses.length === 0 ? "All"
        : statuses.length === 1 ? statuses[0]
        : statuses.length + " statuses";

      filterMenu.textContent = "";
      filterMenu.appendChild(menuItem("All statuses", "", total, statuses.length === 0));
      var sep = document.createElement("div");
      sep.className = "fsep";
      filterMenu.appendChild(sep);
      ORDER.filter(function (name) { return counts[name]; }).forEach(function (name) {
        filterMenu.appendChild(menuItem(name, name, counts[name], statuses.indexOf(name) !== -1));
      });
    }

    function menuItem(label, status, count, on) {
      var item = document.createElement("button");
      item.type = "button";
      item.className = "fitem";
      item.setAttribute("role", "menuitemcheckbox");
      item.setAttribute("aria-checked", on ? "true" : "false");
      if (status) item.dataset.status = status;
      item.dataset.st = slug(status || "all");
      // Dot first so every label starts at the same left edge; the check sits
      // at the end, where its empty space costs nothing.
      item.innerHTML = '<span class="dot"></span>';
      item.appendChild(document.createTextNode(label));
      var n = document.createElement("span");
      n.className = "n";
      n.textContent = count;
      item.appendChild(n);
      item.insertAdjacentHTML("beforeend",
        '<svg class="ck" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7"/></svg>');
      item.addEventListener("click", function (e) {
        // The menu is multi-select, so a pick must not reach the close-on-
        // outside-click handler; renderMenu has already replaced this node.
        e.stopPropagation();
        if (!status) statuses = [];
        else if (statuses.indexOf(status) === -1) statuses = statuses.concat([status]);
        else statuses = statuses.filter(function (s) { return s !== status; });
        apply();
      });
      return item;
    }

    function apply() {
      var q = input.value.trim();
      var ql = q.toLowerCase();
      var re = q ? new RegExp("(" + escapeRegex(q) + ")", "gi") : null;
      var counts = {};
      var pool = 0;
      var visible = {};

      groups.forEach(function (g) {
        var shown = 0;
        g.rows.forEach(function (d) {
          var matches = !ql || d.text.indexOf(ql) !== -1;
          // The status menu counts what the query alone leaves, so unpicking a
          // status always shows the number the menu promised.
          if (matches && g.key === active) {
            pool++;
            counts[d.status] = (counts[d.status] || 0) + 1;
          }
          var on = matches && (statuses.length === 0 || statuses.indexOf(d.status) !== -1);
          d.row.classList.toggle("is-hidden", !on);
          if (on) shown++;
          d.cells.forEach(function (cell, i) {
            cell.innerHTML = d.originals[i];
            if (re && on) highlightCell(cell, re);
          });
        });
        visible[g.key] = shown;
      });

      // A query searches every collection, so never leave a match stranded
      // behind an empty tab.
      if (ql && !visible[active]) {
        var other = active === "mips" ? "mrcs" : "mips";
        if (visible[other]) {
          activate(other);
          apply();
          return;
        }
      }

      clearButton.hidden = q.length === 0;
      hint.hidden = q.length > 0;
      renderMenu(counts, pool);
      emptyState.hidden = visible[active] !== 0;
      groups.forEach(function (g) { g.table.hidden = g.key === active && visible[active] === 0; });
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () {
        statuses = [];
        activate(tab.dataset.panel);
        apply();
        var hash = tab.dataset.panel === "mrcs" ? "#mrcs" : "";
        history.replaceState(null, "", location.pathname + location.search + hash);
      });
      tab.addEventListener("keydown", function (e) {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        tabs[(i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length].click();
      });
    });

    input.addEventListener("input", apply);
    input.addEventListener("search", apply);
    clearButton.addEventListener("click", function () {
      input.value = "";
      input.focus();
      apply();
    });
    document.getElementById("reset-filters").addEventListener("click", function () {
      input.value = "";
      statuses = [];
      apply();
    });

    function closeMenu() {
      filterMenu.hidden = true;
      filterButton.setAttribute("aria-expanded", "false");
    }

    filterButton.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = filterMenu.hidden;
      filterMenu.hidden = !open;
      filterButton.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("click", function (e) {
      if (!filterMenu.hidden && !filterMenu.contains(e.target)) closeMenu();
    });

    // Clicking a row opens its proposal. Links inside it keep their targets,
    // and a click is ignored while a text selection touches the row, so
    // drag-selecting across rows doesn't navigate.
    document.addEventListener("click", function (e) {
      var row = e.target.closest("tr[data-href]");
      if (!row || e.target.closest("a[href]")) return;
      var selection = window.getSelection ? window.getSelection() : null;
      if (selection && !selection.isCollapsed && selection.containsNode(row, true)) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey) window.open(row.dataset.href, "_blank", "noopener");
      else location.assign(row.dataset.href);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !filterMenu.hidden) { closeMenu(); return; }
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      var t = e.target;
      var tag = t && t.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
      e.preventDefault();
      input.focus();
    });

    activate(location.hash === "#mrcs" ? "mrcs" : "mips");
    apply();
  }

  // Waits for the shared script's DOMContentLoaded work (author links and the
  // glossary tooltips), so the row HTML captured for filtering includes both.
  document.addEventListener("DOMContentLoaded", function () {
    setTimeout(start, 0);
  });
})();
