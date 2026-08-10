---
layout: default
title: MIPs
description: Monad Improvement Proposals (MIPs) describe standards for the Monad ecosystem, such as protocol specifications.
---

{% assign mips = site.pages | where_exp: "p", "p.mip and p.category != 'MRC'" | sort: "mip" %}
{% assign mrcs = site.pages | where_exp: "p", "p.mip and p.category == 'MRC'" | sort: "mip" %}

<main class="shell page">
<h1 class="sr-only">Monad Improvement Proposals</h1>

<div class="tabs" role="tablist" aria-label="Proposal type">
	<button type="button" class="tab" id="tab-mips" role="tab" aria-selected="true" aria-controls="panel-mips" data-panel="mips">MIPs <span class="n">{{ mips.size }}</span></button>
	<button type="button" class="tab" id="tab-mrcs" role="tab" aria-selected="false" aria-controls="panel-mrcs" data-panel="mrcs" tabindex="-1">MRCs <span class="n">{{ mrcs.size }}</span></button>
</div>

<div class="controls">
	<div class="search-box" role="search">
		<svg class="ic" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.5 3a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15Zm10.5 18-5.4-5.4"/></svg>
		<input id="proposal-search" type="search" autocomplete="off" spellcheck="false" placeholder="Search by number, title, author, or type…" aria-label="Search MIPs and MRCs" />
		<button type="button" class="xbtn" id="search-clear" aria-label="Clear search" title="Clear search" hidden><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
		<kbd id="search-hint" aria-hidden="true">/</kbd>
	</div>
	<div class="filter" id="status-filter">
		<button type="button" class="fbtn" id="filter-button" aria-haspopup="true" aria-expanded="false">All<svg class="chev" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>
		<div class="fmenu" id="filter-menu" role="menu" hidden></div>
	</div>
</div>

<section class="panel" id="panel-mips" role="tabpanel" aria-labelledby="tab-mips" data-collection="MIPs">
{% if mips.size > 0 %}
	{% include ledger.html rows=mips %}
{% else %}
	<p class="eyebrow">No MIPs found.</p>
{% endif %}
</section>

<section class="panel" id="panel-mrcs" role="tabpanel" aria-labelledby="tab-mrcs" data-collection="MRCs" hidden>
{% if mrcs.size > 0 %}
	{% include ledger.html rows=mrcs %}
{% else %}
	<p class="eyebrow">No MRCs found.</p>
{% endif %}
</section>

<div class="empty" id="no-results" hidden>
	<div class="label">No results</div>
	<h2>Nothing matches these filters.</h2>
	<p>Try a different status or clear the search bar.</p>
	<button type="button" class="reset" id="reset-filters">Reset filters</button>
</div>

<footer class="site-footer">
	<a href="https://github.com/monad-crypto/MIPs" target="_blank" rel="noopener noreferrer">monad-crypto/MIPs</a>
	<a href="https://forum.monad.xyz/c/mips/8" target="_blank" rel="noopener noreferrer">Discussions</a>
	<a href="{{ '/LICENSE.md' | relative_url }}">License</a>
</footer>
</main>

<noscript>
	<style>
		/* Without JS the tabs, search, and status filter can't work: show both
		   collections stacked and hide the dead controls. */
		.tabs, .controls { display: none; }
		.panel[hidden] { display: block; }
	</style>
</noscript>

<script defer src="{{ '/assets/js/index.js' | relative_url }}"></script>
