// Tiny markdown → HTML for the inline DETAILS.md content shown in the explorer.
// We don't want a full markdown library — just enough for headings, lists,
// callouts (> [!note]/etc.), bold/italic, code, and tables.
// Keep the output safe: no raw HTML pass-through.

function escape(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function inline(s: string): string {
  // Order matters: code first to lock substrings
  s = s.replace(/`([^`]+)`/g, (_m, c) => `<code class="px-1 py-0.5 rounded bg-slate-700/50 text-bone-100 text-[0.9em]">${escape(c)}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-bone-50">$1</strong>');
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  s = s.replace(/_([^_]+)_/g, '<em>$1</em>');
  // Wikilinks [[Target]] or [[Target|alias]]
  s = s.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_m, t, alias) => `<span class="underline decoration-dotted decoration-bone-300/40">${alias || t}</span>`);
  // Links
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, t, u) => `<a class="text-ember underline-offset-2 decoration-ember/30 underline" href="${u}">${t}</a>`);
  return s;
}

export function renderDetails(md: string): string {
  if (!md) return '';
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  const out: string[] = [];
  let i = 0;
  let inList = false;
  let listType: 'ul' | 'ol' | null = null;
  let inTable = false;
  let inCode = false;
  let inCallout = false;
  let calloutKind = 'note';

  const closeList = () => {
    if (inList) { out.push(`</${listType}>`); inList = false; listType = null; }
  };
  const closeTable = () => { if (inTable) { out.push('</tbody></table>'); inTable = false; } };
  const closeCallout = () => { if (inCallout) { out.push('</div>'); inCallout = false; } };
  const closeAll = () => { closeList(); closeTable(); closeCallout(); };

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.replace(/\s+$/, '');

    // Code fences
    if (/^```/.test(line)) {
      closeAll();
      if (!inCode) { out.push('<pre class="bg-slate-900/50 border border-slate-700/40 rounded p-4 text-sm overflow-x-auto"><code>'); inCode = true; }
      else { out.push('</code></pre>'); inCode = false; }
      i++; continue;
    }
    if (inCode) { out.push(escape(raw)); i++; continue; }

    // Headings
    let m = line.match(/^(#{1,4})\s+(.*)$/);
    if (m) {
      closeAll();
      const lvl = m[1].length;
      const tag = `h${Math.min(lvl + 1, 6)}`; // shift down one level inside the panel
      const cls = ['mt-6 mb-2 font-serif text-bone-50','mt-5 mb-2 font-serif text-bone-100 text-xl','mt-4 mb-1 text-base font-medium text-bone-100','mt-3 mb-1 text-sm font-medium text-bone-200'][lvl - 1] ?? '';
      out.push(`<${tag} class="${cls}">${inline(escape(m[2]))}</${tag}>`);
      i++; continue;
    }

    // Callouts: `> [!note] Title?` followed by `> body lines`
    let cm = line.match(/^>\s*\[!(\w+)\]\s*(.*)$/);
    if (cm) {
      closeAll();
      calloutKind = cm[1].toLowerCase();
      inCallout = true;
      const title = cm[2];
      const palette = ({
        note: 'border-sky-700/40 bg-sky-950/20 text-sky-200',
        tip:  'border-emerald-700/40 bg-emerald-950/20 text-emerald-200',
        warning: 'border-amber-700/40 bg-amber-950/20 text-amber-200',
        info: 'border-bone-300/20 bg-slate-800/40 text-bone-100',
        idea: 'border-ember/40 bg-ember/5 text-ember',
        todo: 'border-violet-700/40 bg-violet-950/20 text-violet-200',
        question: 'border-cyan-700/40 bg-cyan-950/20 text-cyan-200',
      } as Record<string,string>)[calloutKind] ?? 'border-slate-700/40 bg-slate-800/40 text-bone-100';
      out.push(`<div class="my-4 border-l-2 ${palette} pl-4 py-2 rounded-r-md text-sm">`);
      if (title) out.push(`<div class="font-medium mb-1 uppercase tracking-wider text-[10px]">${inline(escape(title))}</div>`);
      i++; continue;
    }
    if (inCallout && /^>\s*/.test(line)) {
      out.push(`<p class="mb-1 last:mb-0">${inline(escape(line.replace(/^>\s?/, '')))}</p>`);
      i++; continue;
    }
    if (inCallout && line.trim() === '') {
      closeCallout();
      i++; continue;
    }

    // Tables
    if (/^\|.*\|/.test(line) && i + 1 < lines.length && /^\|[\s\-|:]+\|/.test(lines[i + 1])) {
      closeList();
      const headers = line.split('|').slice(1, -1).map(s => s.trim());
      out.push('<table class="text-sm border-collapse my-4 w-full"><thead><tr>');
      headers.forEach(h => out.push(`<th class="text-left text-bone-200 font-medium border-b border-slate-700/60 py-1.5 pr-4">${inline(escape(h))}</th>`));
      out.push('</tr></thead><tbody>');
      i += 2;
      while (i < lines.length && /^\|.*\|/.test(lines[i])) {
        const cells = lines[i].split('|').slice(1, -1).map(s => s.trim());
        out.push('<tr>');
        cells.forEach(c => out.push(`<td class="text-bone-200 border-b border-slate-700/30 py-1.5 pr-4 align-top">${inline(escape(c))}</td>`));
        out.push('</tr>');
        i++;
      }
      out.push('</tbody></table>');
      continue;
    }

    // Lists
    let lm = line.match(/^(\s*)([-*])\s+(.*)$/);
    if (lm) {
      if (!inList || listType !== 'ul') { closeList(); out.push('<ul class="list-disc list-outside ml-5 my-2 space-y-1 text-bone-200">'); inList = true; listType = 'ul'; }
      out.push(`<li>${inline(escape(lm[3]))}</li>`);
      i++; continue;
    }
    let om = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (om) {
      if (!inList || listType !== 'ol') { closeList(); out.push('<ol class="list-decimal list-outside ml-5 my-2 space-y-1 text-bone-200">'); inList = true; listType = 'ol'; }
      out.push(`<li>${inline(escape(om[2]))}</li>`);
      i++; continue;
    }

    // HR
    if (/^---+\s*$/.test(line)) { closeAll(); out.push('<hr class="my-5 border-0 h-px bg-slate-700/50"/>'); i++; continue; }

    // Paragraph (collect until blank or new block)
    if (line.trim() === '') { closeList(); i++; continue; }
    closeTable();
    out.push(`<p class="my-2 text-bone-200 leading-relaxed">${inline(escape(line))}</p>`);
    i++;
  }
  if (inCode) out.push('</code></pre>');
  if (inCallout) out.push('</div>');
  if (inList) out.push(`</${listType}>`);
  if (inTable) out.push('</tbody></table>');
  return out.join('\n');
}
