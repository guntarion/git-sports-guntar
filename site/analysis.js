/* analysis.js — the on-demand AI analysis panel, shared by Performance and
 * Analytics.
 *
 * Deliberately button-triggered rather than daily: this answers "what does all
 * of this mean together?", which is a question you ask when you want it, and
 * every run bills the model.
 *
 * Reads are public (a visitor sees the last analysis); generating requires the
 * access token, so the button unlocks via GS.ready() before its first call.
 *
 * Usage:  GSAnalysis.mount(hostEl, { kind: 'performance', days: () => 180 })
 */
(function (window, document) {
  'use strict';

  var API = (window.GS_API_BASE || '/api').replace(/\/$/, '');

  var CSS = [
    '.gsa{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin-bottom:14px}',
    '.gsa-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}',
    '.gsa-title{font-size:13px;font-weight:700;display:flex;align-items:center;gap:8px}',
    '.gsa-sub{font-size:10px;color:#94a3b8}',
    '.gsa-btn{margin-left:auto;background:#00bbf9;border:none;color:#000;font-family:inherit;font-size:12px;',
    '  font-weight:700;padding:8px 16px;border-radius:8px;cursor:pointer;transition:.15s;white-space:nowrap}',
    '.gsa-btn:hover{background:#38bdf8}',
    '.gsa-btn:disabled{opacity:.5;cursor:default}',
    '.gsa-btn.ghost{background:transparent;border:1px solid #334155;color:#94a3b8;font-weight:400;margin-left:8px}',
    '.gsa-btn.ghost:hover{color:#f1f5f9;border-color:#94a3b8;background:transparent}',
    '.gsa-body{margin-top:14px;font-size:12px;line-height:1.65}',
    '.gsa-headline{font-size:14px;font-weight:700;color:#f1f5f9;line-height:1.5}',
    '.gsa-verdict{display:inline-block;font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;',
    '  text-transform:uppercase;letter-spacing:.05em;margin-right:8px;vertical-align:middle}',
    '.v-improving{background:rgba(34,197,94,.16);color:#22c55e}',
    '.v-declining{background:rgba(239,68,68,.16);color:#ef4444}',
    '.v-stagnating,.v-mixed{background:rgba(148,163,184,.16);color:#94a3b8}',
    '.gsa-means{color:#cbd5e1;margin:12px 0 4px;padding:12px 14px;background:#0f172a;border-radius:9px;',
    '  border-left:3px solid #00bbf9}',
    '.gsa-sec{margin-top:16px}',
    '.gsa-sec h4{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:#94a3b8;',
    '  font-weight:700;margin-bottom:8px}',
    '.gsa-item{background:#243048;border-radius:9px;padding:11px 13px;margin-bottom:7px}',
    '.gsa-item .t{font-weight:700;color:#f1f5f9;display:flex;align-items:center;gap:7px;flex-wrap:wrap}',
    '.gsa-item .d{color:#94a3b8;margin-top:4px}',
    '.gsa-item .m{color:#cbd5e1;margin-top:5px;font-style:italic;font-size:11px;',
    '  border-left:2px solid #334155;padding-left:9px}',
    '.gsa-tag{font-size:9px;padding:2px 7px;border-radius:10px;font-weight:700;text-transform:uppercase}',
    '.t-helping{background:rgba(34,197,94,.16);color:#22c55e}',
    '.t-hurting{background:rgba(239,68,68,.16);color:#ef4444}',
    '.t-high{background:rgba(0,187,249,.16);color:#00bbf9}',
    '.t-medium,.t-low{background:rgba(148,163,184,.16);color:#94a3b8}',
    '.gsa-empty{color:#94a3b8;font-size:11px;padding:14px 0}',
    '.gsa-err{color:#f87171;font-size:11px;padding:10px 0}',
    '.gsa-stale{font-size:10px;color:#fbbf24}',
    '.gsa-spin{display:inline-block;width:12px;height:12px;border:2px solid rgba(0,0,0,.25);',
    '  border-top-color:#000;border-radius:50%;animation:gsaspin .7s linear infinite;vertical-align:-2px;margin-right:6px}',
    '@keyframes gsaspin{to{transform:rotate(360deg)}}'
  ].join('');

  var styled = false;
  function injectStyle() {
    if (styled) return;
    var s = document.createElement('style');
    s.textContent = CSS;
    document.head.appendChild(s);
    styled = true;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]);
    });
  }

  function ago(iso) {
    if (!iso) return '';
    var mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + ' min ago';
    var h = Math.round(mins / 60);
    if (h < 24) return h + 'h ago';
    return Math.round(h / 24) + 'd ago';
  }

  function list(items, render) {
    if (!items || !items.length) return '';
    return items.map(render).join('');
  }

  function renderPerformance(a) {
    var h = '';
    h += '<div class="gsa-headline">'
      + (a.verdict ? '<span class="gsa-verdict v-' + esc(a.verdict) + '">' + esc(a.verdict) + '</span>' : '')
      + esc(a.headline || '') + '</div>';
    if (a.what_it_means) h += '<div class="gsa-means">' + esc(a.what_it_means) + '</div>';

    if (a.drivers && a.drivers.length) {
      h += '<div class="gsa-sec"><h4>What drove it</h4>' + list(a.drivers, function (d) {
        return '<div class="gsa-item"><div class="t">' + esc(d.factor)
          + (d.direction ? '<span class="gsa-tag t-' + esc(d.direction) + '">' + esc(d.direction) + '</span>' : '')
          + (d.confidence ? '<span class="gsa-tag t-' + esc(d.confidence) + '">' + esc(d.confidence) + '</span>' : '')
          + '</div>'
          + (d.evidence ? '<div class="d">' + esc(d.evidence) + '</div>' : '')
          + (d.mechanism ? '<div class="m">' + esc(d.mechanism) + '</div>' : '')
          + '</div>';
      }) + '</div>';
    }

    if (a.contradictions && a.contradictions.length) {
      h += '<div class="gsa-sec"><h4>Where the metrics disagree</h4>' + list(a.contradictions, function (c) {
        return '<div class="gsa-item"><div class="t">' + esc(c.tension) + '</div>'
          + (c.explanation ? '<div class="d">' + esc(c.explanation) + '</div>' : '')
          + (c.which_to_trust ? '<div class="m">Trust: ' + esc(c.which_to_trust) + '</div>' : '')
          + '</div>';
      }) + '</div>';
    }

    if (a.connections && a.connections.length) {
      h += '<div class="gsa-sec"><h4>How they connect</h4>' + list(a.connections, function (c) {
        return '<div class="gsa-item"><div class="t">'
          + esc((c.between || []).join('  ↔  ')) + '</div>'
          + (c.observation ? '<div class="d">' + esc(c.observation) + '</div>' : '')
          + (c.so_what ? '<div class="m">' + esc(c.so_what) + '</div>' : '')
          + '</div>';
      }) + '</div>';
    }

    if (a.what_to_do && a.what_to_do.length) {
      h += '<div class="gsa-sec"><h4>What to do</h4>' + list(a.what_to_do, function (d) {
        return '<div class="gsa-item"><div class="t">' + esc(d.action)
          + (d.priority ? '<span class="gsa-tag t-' + esc(d.priority) + '">' + esc(d.priority) + '</span>' : '')
          + '</div>' + (d.why ? '<div class="d">' + esc(d.why) + '</div>' : '') + '</div>';
      }) + '</div>';
    }

    if (a.watch_next && a.watch_next.length) {
      h += '<div class="gsa-sec"><h4>Watch next</h4>' + list(a.watch_next, function (w) {
        return '<div class="gsa-item"><div class="t">' + esc(w.metric)
          + (w.timeframe ? '<span class="gsa-tag t-medium">' + esc(w.timeframe) + '</span>' : '')
          + '</div>' + (w.expect ? '<div class="d">' + esc(w.expect) + '</div>' : '') + '</div>';
      }) + '</div>';
    }
    return h;
  }

  function renderAnalytics(a) {
    var h = '<div class="gsa-headline">' + esc(a.headline || '') + '</div>';
    var b = a.block_review;
    if (b) {
      h += '<div class="gsa-means">'
        + [['Volume', b.volume], ['Intensity', b.intensity_distribution],
           ['Consistency', b.consistency], ['Progression', b.progression]]
          .filter(function (x) { return x[1]; })
          .map(function (x) { return '<b>' + x[0] + ':</b> ' + esc(x[1]); }).join('<br>')
        + (b.absorbed ? '<br><b>Absorbed:</b> ' + esc(b.absorbed)
            + (b.evidence ? ' — ' + esc(b.evidence) : '') : '')
        + '</div>';
    }
    if (a.limiter) {
      h += '<div class="gsa-sec"><h4>Current limiter</h4><div class="gsa-item">'
        + '<div class="t">' + esc(a.limiter.what) + '</div>'
        + (a.limiter.why ? '<div class="d">' + esc(a.limiter.why) + '</div>' : '')
        + (a.limiter.evidence ? '<div class="m">' + esc(a.limiter.evidence) + '</div>' : '')
        + '</div></div>';
    }
    var n = a.next_block;
    if (n) {
      h += '<div class="gsa-sec"><h4>Next block</h4><div class="gsa-item">'
        + '<div class="t">' + esc(n.focus || '')
        + (n.duration_weeks ? '<span class="gsa-tag t-high">' + esc(n.duration_weeks) + ' weeks</span>' : '')
        + '</div>'
        + (n.weekly_structure ? '<div class="d">' + esc((n.weekly_structure || []).join(' · ')) + '</div>' : '')
        + '<div class="m">' + esc([n.volume_guidance, n.intensity_guidance].filter(Boolean).join(' ')) + '</div>'
        + '</div></div>';
    }
    if (a.do_now && a.do_now.length) {
      h += '<div class="gsa-sec"><h4>Do now</h4>' + list(a.do_now, function (d) {
        return '<div class="gsa-item"><div class="t">' + esc(d.action)
          + (d.priority ? '<span class="gsa-tag t-' + esc(d.priority) + '">' + esc(d.priority) + '</span>' : '')
          + '</div>' + (d.why ? '<div class="d">' + esc(d.why) + '</div>' : '') + '</div>';
      }) + '</div>';
    }
    if (a.avoid && a.avoid.length) {
      h += '<div class="gsa-sec"><h4>Avoid</h4>' + list(a.avoid, function (d) {
        return '<div class="gsa-item"><div class="t">' + esc(d.thing) + '</div>'
          + (d.why ? '<div class="d">' + esc(d.why) + '</div>' : '') + '</div>';
      }) + '</div>';
    }
    return h;
  }

  function mount(host, opts) {
    injectStyle();
    var kind = opts.kind || 'performance';
    var daysFn = opts.days || function () { return 180; };
    var title = opts.title || (kind === 'analytics' ? 'Training Block Review' : 'What does this all mean?');
    var sub = opts.subtitle || (kind === 'analytics'
      ? 'AI review of the block and what the next one should be'
      : 'AI reads every metric on this page together and explains why the period went the way it did');

    var box = document.createElement('div');
    box.className = 'gsa';
    box.innerHTML =
      '<div class="gsa-head">'
      + '<div><div class="gsa-title">✨ ' + esc(title) + '</div>'
      + '<div class="gsa-sub">' + esc(sub) + '</div></div>'
      + '<button class="gsa-btn" data-go>Analyse this period</button>'
      + '<button class="gsa-btn ghost" data-regen style="display:none">Regenerate</button>'
      + '</div><div class="gsa-body"><div class="gsa-empty">Loading…</div></div>';
    host.appendChild(box);

    var body = box.querySelector('.gsa-body');
    var goBtn = box.querySelector('[data-go]');
    var regenBtn = box.querySelector('[data-regen]');

    function paint(payload) {
      var a = payload && payload.analysis;
      if (!a) {
        body.innerHTML = '<div class="gsa-empty">No analysis yet for this period. '
          + 'Press <b>Analyse this period</b> to generate one.</div>';
        goBtn.style.display = '';
        regenBtn.style.display = 'none';
        return;
      }
      var meta = '<div class="gsa-sub" style="margin-bottom:10px">Generated ' + esc(ago(payload.generated_at))
        + (payload.model ? ' · ' + esc(payload.model) : '')
        + (payload.stale ? ' · <span class="gsa-stale">new data since — regenerate for an up-to-date read</span>' : '')
        + '</div>';
      body.innerHTML = meta + (kind === 'analytics' ? renderAnalytics(a) : renderPerformance(a));
      goBtn.style.display = 'none';
      regenBtn.style.display = '';
    }

    function load() {
      fetch(API + '/analyze?kind=' + kind + '&days=' + daysFn())
        .then(function (r) { return r.json(); })
        .then(paint)
        .catch(function () {
          body.innerHTML = '<div class="gsa-err">Could not load the saved analysis.</div>';
        });
    }

    function generate(btn) {
      var label = btn.textContent;
      btn.disabled = true;
      btn.innerHTML = '<span class="gsa-spin"></span>Analysing…';
      body.innerHTML = '<div class="gsa-empty">Reading your metrics and working out how they connect. '
        + 'This takes about 10–20 seconds.</div>';

      // Generating costs money, so it needs the access token.
      var ready = (window.GS && window.GS.ready) ? window.GS.ready() : Promise.resolve();
      ready.then(function () {
        var tok = '';
        try { tok = localStorage.getItem('gs_api_token') || ''; } catch (e) {}
        return fetch(API + '/analyze?kind=' + kind + '&days=' + daysFn() + '&force=1', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + tok },
        });
      }).then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, j: j }; });
      }).then(function (res) {
        if (!res.ok) throw new Error(res.j.detail || res.j.error || 'failed');
        paint(res.j);
      }).catch(function (e) {
        body.innerHTML = '<div class="gsa-err">Could not generate: ' + esc(e.message) + '</div>';
      }).finally(function () {
        btn.disabled = false;
        btn.textContent = label;
      });
    }

    goBtn.addEventListener('click', function () { generate(goBtn); });
    regenBtn.addEventListener('click', function () { generate(regenBtn); });
    load();
    return { reload: load };
  }

  window.GSAnalysis = { mount: mount };
})(window, document);
