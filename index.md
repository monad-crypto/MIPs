---
layout: default
title: MIPs
---

# Monad Improvement Proposals (MIPs)

{% assign mips = site.pages | where_exp: "p", "p.mip" | sort: "mip" %}

{% if mips.size > 0 %}
<div class="mip-search" role="search">
	<svg class="mip-search__icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
		<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M10.5 3a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15Zm10.5 18-5.4-5.4"/>
	</svg>
	<input id="mip-search-input" type="search" autocomplete="off" spellcheck="false" placeholder="Search MIPs by number, title, author, or type…" aria-label="Search MIPs" />
	<button type="button" class="mip-search__clear" aria-label="Clear search" hidden>&times;</button>
</div>
<p class="mip-search__status muted" id="mip-search-status" aria-live="polite" hidden></p>

<table id="mip-table">
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
				<td>{{ p.type | default: "-" | escape }}</td>
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
<p class="mip-search__empty muted" id="mip-search-empty" hidden>No MIPs match your search.</p>
{% else %}
No MIPs found.
{% endif %}

<style>
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
	.mip-search__status {
		margin: 0.25rem 0.15rem 0;
		font-size: 0.875rem;
	}
	#mip-table tr.is-hidden {
		display: none;
	}
	#mip-table mark {
		background: #fef3c7;
		color: inherit;
		padding: 0 0.1rem;
		border-radius: 3px;
	}
	.status-pill {
		display: inline-block;
		padding: 0.15rem 0.55rem;
		border-radius: 999px;
		font-size: 0.82rem;
		font-weight: 500;
		line-height: 1.4;
		border: 1px solid var(--border);
		background: var(--bg-soft);
		color: var(--muted);
		white-space: nowrap;
	}
	.status-pill--draft { background: #fef3c7; border-color: #fde68a; color: #92400e; }
	.status-pill--review, .status-pill--last-call { background: #dbeafe; border-color: #bfdbfe; color: #1e40af; }
	.status-pill--final, .status-pill--living { background: #dcfce7; border-color: #bbf7d0; color: #166534; }
	.status-pill--stagnant, .status-pill--withdrawn { background: #f3f4f6; border-color: #e5e7eb; color: #4b5563; }
</style>

<script>
	document.addEventListener("DOMContentLoaded", function () {
		var input = document.getElementById("mip-search-input");
		var table = document.getElementById("mip-table");
		if (!input || !table) return;

		var clearBtn = document.querySelector(".mip-search__clear");
		var status = document.getElementById("mip-search-status");
		var empty = document.getElementById("mip-search-empty");
		var rows = Array.prototype.slice.call(table.tBodies[0].rows);
		var rowData = null;

		function captureRows() {
			rowData = rows.map(function (row) {
				var cells = Array.prototype.slice.call(row.cells);
				return {
					row: row,
					cells: cells,
					originals: cells.map(function (cell) { return cell.innerHTML; }),
					texts: cells.map(function (cell) { return (cell.textContent || "").toLowerCase(); })
				};
			});
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

		function apply() {
			if (!rowData) return;
			var q = input.value.trim();
			var ql = q.toLowerCase();
			var visible = 0;
			var highlightRe = q ? new RegExp("(" + escapeRegex(q) + ")", "gi") : null;

			rowData.forEach(function (d) {
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

			if (clearBtn) clearBtn.hidden = q.length === 0;
			if (status) {
				if (q.length === 0) {
					status.hidden = true;
					status.textContent = "";
				} else {
					status.hidden = false;
					status.textContent = visible + (visible === 1 ? " match" : " matches");
				}
			}
			if (empty) empty.hidden = visible !== 0;
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

		// Defer row capture + initial apply() past any other DOMContentLoaded
		// listeners (notably the default layout's @username linkification),
		// then sync UI to the current input value (handles bfcache restores).
		setTimeout(function () {
			captureRows();
			apply();
		}, 0);
	});
</script>

<footer class="home-footer muted">
	<p>
		<a href="https://github.com/monad-crypto/MIPs" target="_blank" rel="noopener noreferrer" aria-label="Open GitHub repository">
			<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false" style="vertical-align: text-bottom; margin-right: 0.35rem; fill: currentColor;">
				<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.65 7.65 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z"></path>
			</svg>
		    monad-crypto/MIPs
		</a>
		|
		<a href="{{ '/LICENSE.md' | relative_url }}">license</a>
	</p>
</footer>
