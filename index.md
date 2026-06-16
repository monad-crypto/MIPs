---
layout: default
title: MIPs
---

# Monad Improvement Proposals

{% assign mips = site.pages | where_exp: "p", "p.mip and p.category != 'MRC'" | sort: "mip" %}
{% assign mrcs = site.pages | where_exp: "p", "p.mip and p.category == 'MRC'" | sort: "mip" %}

<div class="proposal-tabs" role="tablist" aria-label="Proposal type">
	<button type="button" class="proposal-tab is-active" id="tab-mips" role="tab" aria-selected="true" aria-controls="panel-mips" data-panel="mips">MIPs</button>
	<button type="button" class="proposal-tab" id="tab-mrcs" role="tab" aria-selected="false" aria-controls="panel-mrcs" data-panel="mrcs" tabindex="-1">MRCs</button>
</div>

{% if mips.size > 0 or mrcs.size > 0 %}
<div class="mip-search" role="search">
	<svg class="mip-search__icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
		<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M10.5 3a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15Zm10.5 18-5.4-5.4"/>
	</svg>
	<input class="mip-search__input" type="search" autocomplete="off" spellcheck="false" placeholder="Search MIPs and MRCs by number, title, author, or type…" aria-label="Search MIPs and MRCs" />
	<kbd class="mip-search__hint" aria-hidden="true">/</kbd>
	<button type="button" class="mip-search__clear" aria-label="Clear search" hidden>&times;</button>
</div>
<p class="mip-search__status muted" aria-live="polite" hidden></p>
{% endif %}

<section class="proposal-panel" id="panel-mips" role="tabpanel" aria-labelledby="tab-mips" data-collection="MIPs">
<h2 class="panel-label" hidden>MIPs</h2>
{% if mips.size > 0 %}
<table class="proposal-table">
	<thead>
		<tr>
			<th>Number</th>
			<th>Title</th>
			<th>Author</th>
			<th>Type</th>
			<th>Status</th>
		</tr>
	</thead>
	<tbody>
		{% for p in mips %}
			<tr>
				<td><a href="{{ p.url | relative_url }}">{{ p.mip | escape }}</a></td>
				<td>{{ p.title | escape }}</td>
				<td class="author-value">{{ p.author | default: "-" | escape }}</td>
				<td>{% if p.type and p.type != "" %}<span class="type-pill type-pill--{{ p.type | slugify }}">{{ p.type | escape }}</span>{% else %}<span class="muted">-</span>{% endif %}</td>
				<td>
					{% if p.status and p.status != "" %}
						{% assign status_slug = p.status | slugify %}
						<span class="status-pill{% if status_slug != "" %} status-pill--{{ status_slug }}{% endif %}">{{ p.status | escape }}</span>
					{% else %}
						<span class="muted">-</span>
					{% endif %}
				</td>
			</tr>
		{% endfor %}
	</tbody>
</table>
<p class="mip-search__empty muted" hidden>No MIPs match your search.</p>
{% else %}
<p class="muted">No MIPs found.</p>
{% endif %}
</section>

<section class="proposal-panel" id="panel-mrcs" role="tabpanel" aria-labelledby="tab-mrcs" data-collection="MRCs" hidden>
<h2 class="panel-label" hidden>MRCs</h2>
{% if mrcs.size > 0 %}
<table class="proposal-table">
	<thead>
		<tr>
			<th>Number</th>
			<th>Title</th>
			<th>Author</th>
			<th>Type</th>
			<th>Status</th>
		</tr>
	</thead>
	<tbody>
		{% for p in mrcs %}
			<tr>
				<td><a href="{{ p.url | relative_url }}">{{ p.mip | escape }}</a></td>
				<td>{{ p.title | escape }}</td>
				<td class="author-value">{{ p.author | default: "-" | escape }}</td>
				<td>{% if p.type and p.type != "" %}<span class="type-pill type-pill--{{ p.type | slugify }}">{{ p.type | escape }}</span>{% else %}<span class="muted">-</span>{% endif %}</td>
				<td>
					{% if p.status and p.status != "" %}
						{% assign status_slug = p.status | slugify %}
						<span class="status-pill{% if status_slug != "" %} status-pill--{{ status_slug }}{% endif %}">{{ p.status | escape }}</span>
					{% else %}
						<span class="muted">-</span>
					{% endif %}
				</td>
			</tr>
		{% endfor %}
	</tbody>
</table>
<p class="mip-search__empty muted" hidden>No MRCs match your search.</p>
{% else %}
<p class="muted">No MRCs found yet.</p>
{% endif %}
</section>

<style>
	.proposal-tabs {
		display: flex;
		gap: 0.25rem;
		margin: 1.25rem 0 0;
		border-bottom: 1px solid var(--border);
	}
	.proposal-tab {
		appearance: none;
		border: 0;
		background: transparent;
		font: inherit;
		font-weight: 500;
		color: var(--muted);
		padding: 0.55rem 0.95rem;
		cursor: pointer;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		border-radius: 6px 6px 0 0;
	}
	.proposal-tab:hover {
		color: var(--text);
		background: var(--bg-soft);
	}
	.proposal-tab.is-active {
		color: var(--link);
		border-bottom-color: var(--link);
	}
	.proposal-tab:focus-visible {
		outline: 2px solid var(--link);
		outline-offset: 2px;
	}
	.proposal-panel[hidden] {
		display: none;
	}
	.mip-search {
		position: relative;
		display: flex;
		align-items: center;
		margin: 1.25rem 0 0.5rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: #fff;
		box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
		transition: border-color 0.15s ease, box-shadow 0.15s ease;
	}
	.mip-search:focus-within {
		border-color: var(--link);
		box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
	}
	.mip-search__icon {
		color: var(--muted);
		margin-left: 0.75rem;
		flex-shrink: 0;
	}
	.mip-search input {
		flex: 1;
		border: 0;
		outline: none;
		background: transparent;
		padding: 0.65rem 0.5rem 0.65rem 0.5rem;
		font: inherit;
		color: var(--text);
		min-width: 0;
	}
	.mip-search input::placeholder {
		color: var(--muted);
	}
	.mip-search input::-webkit-search-cancel-button {
		-webkit-appearance: none;
		appearance: none;
	}
	.mip-search__clear {
		margin-right: 0.5rem;
		padding: 0 0.5rem;
		border: 0;
		background: transparent;
		color: var(--muted);
		font-size: 1.25rem;
		line-height: 1;
		cursor: pointer;
		border-radius: 6px;
	}
	.mip-search__clear:hover {
		color: var(--text);
		background: var(--bg-soft);
	}
	.mip-search__hint {
		flex-shrink: 0;
		margin-right: 0.6rem;
		padding: 0.05rem 0.45rem;
		font-family: inherit;
		font-size: 0.8rem;
		line-height: 1.4;
		color: var(--muted);
		background: var(--bg-soft);
		border: 1px solid var(--border);
		border-radius: 6px;
		box-shadow: 0 1px 0 rgba(17, 24, 39, 0.05);
		pointer-events: none;
	}
	/* The hint only advertises the shortcut; hide it once the box is in use. */
	.mip-search:focus-within .mip-search__hint,
	.mip-search.is-active .mip-search__hint {
		display: none;
	}
	.mip-search__status {
		margin: 0.25rem 0.15rem 0;
		font-size: 0.875rem;
	}
	.proposal-table tr.is-hidden {
		display: none;
	}
	/* Always let long author strings (multiple authors with emails) wrap
	   instead of forcing the column wide or overflowing the viewport. */
	.proposal-table td.author-value {
		overflow-wrap: anywhere;
	}
	/* On wide viewports, use fixed layout with explicit column widths so a
	   long Author string can't stretch its column excessively. max-width on
	   cells is unreliable under auto layout. On narrow screens we keep the
	   default auto layout so columns size to their content and stay readable. */
	@media (min-width: 700px) {
		.proposal-table {
			table-layout: fixed;
		}
		.proposal-table th,
		.proposal-table td {
			box-sizing: border-box;
		}
		.proposal-table th:nth-child(1), .proposal-table td:nth-child(1) { width: 7%; }   /* Number */
		.proposal-table th:nth-child(2), .proposal-table td:nth-child(2) { width: 38%; }  /* Title  */
		.proposal-table th:nth-child(3), .proposal-table td:nth-child(3) { width: 25%; }  /* Author */
		.proposal-table th:nth-child(4), .proposal-table td:nth-child(4) { width: 15%; }  /* Type   */
		.proposal-table th:nth-child(5), .proposal-table td:nth-child(5) { width: 15%; }  /* Status */
	}
	.proposal-table mark {
		background: #fef3c7;
		color: inherit;
		padding: 0 0.1rem;
		border-radius: 3px;
	}
	/* Status & type pills and their tooltips are defined in the default layout
	   so the MIP/MRC pages share them. */
	.panel-label { margin-top: 1.5rem; }
</style>

<noscript>
	<style>
		/* Without JS the tab switcher and search can't work: show both
		   collections stacked with headings, and hide the dead controls. */
		.proposal-tabs { display: none; }
		.proposal-panel[hidden] { display: block; }
		.panel-label[hidden] { display: block; }
		.mip-search { display: none; }
	</style>
</noscript>

<script>
	document.addEventListener("DOMContentLoaded", function () {
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
					if (m.index > lastIndex) {
						frag.appendChild(document.createTextNode(text.slice(lastIndex, m.index)));
					}
					var mark = document.createElement("mark");
					mark.textContent = m[0];
					frag.appendChild(mark);
					lastIndex = re.lastIndex;
				}
				if (lastIndex < text.length) {
					frag.appendChild(document.createTextNode(text.slice(lastIndex)));
				}
				node.parentNode.replaceChild(frag, node);
			});
		}

		// A single search box filters both the MIPs and MRCs tables at once.
		// `panels` and `activate` (declared below) are assigned before this
		// runs; it is only invoked from the deferred init.
		function initGlobalSearch() {
			var input = document.querySelector(".mip-search__input");
			if (!input) return;

			var clearBtn = document.querySelector(".mip-search__clear");
			var status = document.querySelector(".mip-search__status");
			var box = input.closest(".mip-search");
			var labels = { mips: "MIPs", mrcs: "MRCs" };

			var groups = ["mips", "mrcs"].map(function (key) {
				var panel = panels[key];
				if (!panel) return null;
				var table = panel.querySelector(".proposal-table");
				if (!table || !table.tBodies[0]) return null;
				var rows = Array.prototype.slice.call(table.tBodies[0].rows);
				return {
					key: key,
					empty: panel.querySelector(".mip-search__empty"),
					rowData: rows.map(function (row) {
						var cells = Array.prototype.slice.call(row.cells);
						return {
							row: row,
							cells: cells,
							originals: cells.map(function (cell) { return cell.innerHTML; }),
							texts: cells.map(function (cell) { return (cell.textContent || "").toLowerCase(); })
						};
					})
				};
			}).filter(Boolean);

			function apply() {
				var q = input.value.trim();
				var ql = q.toLowerCase();
				var highlightRe = q ? new RegExp("(" + escapeRegex(q) + ")", "gi") : null;
				var counts = {};

				groups.forEach(function (g) {
					var visible = 0;
					g.rowData.forEach(function (d) {
						var match = !ql || d.texts.some(function (t) { return t.indexOf(ql) !== -1; });
						if (match) {
							visible++;
							d.row.classList.remove("is-hidden");
						} else {
							d.row.classList.add("is-hidden");
						}
						d.cells.forEach(function (cell, i) {
							cell.innerHTML = d.originals[i];
							if (highlightRe && match) highlightCell(cell, highlightRe);
						});
					});
					counts[g.key] = visible;
					if (g.empty) g.empty.hidden = visible !== 0;
				});

				if (clearBtn) clearBtn.hidden = q.length === 0;
				if (box) box.classList.toggle("is-active", q.length > 0);

				// Dynamically switch to a tab that has matches when the active
				// one has none, so a query is never silently hidden behind a tab.
				if (ql) {
					var activeKey = (panels.mrcs && !panels.mrcs.hidden) ? "mrcs" : "mips";
					if (!counts[activeKey]) {
						var other = activeKey === "mips" ? "mrcs" : "mips";
						if (counts[other]) activate(other);
					}
				}

				if (status) {
					if (q.length === 0) {
						status.hidden = true;
						status.textContent = "";
					} else {
						var parts = [];
						groups.forEach(function (g) {
							if (counts[g.key]) parts.push(counts[g.key] + " in " + labels[g.key]);
						});
						status.hidden = false;
						status.textContent = parts.length ? parts.join(" · ") : "No matches";
					}
				}
			}

			input.addEventListener("input", apply);
			input.addEventListener("search", apply);
			if (clearBtn) {
				clearBtn.addEventListener("click", function () {
					input.value = "";
					input.focus();
					apply();
				});
			}

			apply();
		}

		// Tab switching between MIPs and MRCs.
		var tabs = Array.prototype.slice.call(document.querySelectorAll(".proposal-tab"));
		var panels = {
			mips: document.getElementById("panel-mips"),
			mrcs: document.getElementById("panel-mrcs")
		};

		function activate(name, focusTab) {
			if (!panels[name]) name = "mips";
			tabs.forEach(function (tab) {
				var isActive = tab.dataset.panel === name;
				tab.classList.toggle("is-active", isActive);
				tab.setAttribute("aria-selected", isActive ? "true" : "false");
				tab.tabIndex = isActive ? 0 : -1;
				if (isActive && focusTab) tab.focus();
			});
			Object.keys(panels).forEach(function (key) {
				if (panels[key]) panels[key].hidden = key !== name;
			});
		}

		tabs.forEach(function (tab, i) {
			tab.addEventListener("click", function () {
				var name = tab.dataset.panel;
				activate(name);
				var newHash = name === "mrcs" ? "#mrcs" : "";
				if (history.replaceState) {
					history.replaceState(null, "", location.pathname + location.search + newHash);
				} else {
					location.hash = newHash;
				}
			});
			tab.addEventListener("keydown", function (e) {
				if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
				e.preventDefault();
				var dir = e.key === "ArrowRight" ? 1 : -1;
				var next = tabs[(i + dir + tabs.length) % tabs.length];
				activate(next.dataset.panel, true);
			});
		});

		// Press "/" anywhere to jump to the search box.
		document.addEventListener("keydown", function (e) {
			if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
			var t = e.target;
			var tag = t && t.tagName;
			if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) {
				return;
			}
			var input = document.querySelector(".mip-search__input");
			if (!input) return;
			e.preventDefault();
			input.focus();
		});

		// Defer search init + initial activation past the default layout's
		// DOMContentLoaded work (@username linkification and the status/type
		// tooltip tagging), so the row HTML captured for filtering includes the
		// linkified authors and the tooltip attributes.
		setTimeout(function () {
			activate(location.hash === "#mrcs" ? "mrcs" : "mips");
			initGlobalSearch();
		}, 0);
	});
</script>

<footer class="home-footer muted">
	<p>
		<a href="https://github.com/monad-crypto/MIPs" target="_blank" rel="noopener noreferrer" aria-label="Open GitHub repository">
			<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false" style="vertical-align: text-bottom; margin-right: 0.35rem; fill: currentColor;">
				<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.65 7.65 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z"></path>
			</svg>monad-crypto/MIPs
		</a>
		|
		<a href="https://forum.monad.xyz/c/mips/8" target="_blank" rel="noopener noreferrer">discussions</a>
		|
		<a href="{{ '/LICENSE.md' | relative_url }}">license</a>
	</p>
</footer>
