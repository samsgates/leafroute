STUDIO_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>LeafRoute Studio</title>
<style>
:root { color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
body { margin:0; background:#0b0d10; color:#f3f5f7; }
header { padding:18px 24px; border-bottom:1px solid #2a2f36; display:flex; gap:18px; align-items:center; }
header b { font-size:20px; }
main { display:grid; grid-template-columns:minmax(320px, 40%) 1fr; min-height:calc(100vh - 65px); }
.panel { padding:20px; border-right:1px solid #2a2f36; overflow:auto; }
.panel:last-child { border-right:0; }
input, button { font:inherit; border:1px solid #3b424c; border-radius:8px; padding:11px; background:#11151a; color:inherit; }
input { width:calc(100% - 24px); }
button { cursor:pointer; margin-top:10px; }
button:hover { background:#1c222a; }
.card { border:1px solid #2b3139; border-radius:10px; padding:12px; margin:10px 0; background:#11151a; }
.small { color:#9ea7b3; font-size:12px; }
.score { font-variant-numeric:tabular-nums; font-weight:700; }
pre { white-space:pre-wrap; word-break:break-word; font-size:12px; }
.tree-node { padding:4px 0; }
@media(max-width:800px){ main{grid-template-columns:1fr}.panel{border-right:0;border-bottom:1px solid #2a2f36} }
</style>
</head>
<body>
<header><b>LeafRoute Studio</b><span class="small">Compiled retrieval debugger</span></header>
<main>
<section class="panel">
<h3>Document tree</h3>
<div id="info" class="small"></div>
<div id="tree"></div>
</section>
<section class="panel">
<h3>Search playground</h3>
<input id="q" placeholder="Ask a question about the document" />
<button onclick="runSearch()">Search</button>
<div id="summary"></div>
<div id="results"></div>
<details><summary>Execution trace</summary><pre id="trace"></pre></details>
<details><summary>QueryIR and plan</summary><pre id="plan"></pre></details>
</section>
</main>
<script>
function esc(v){return String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}
async function init(){
 const [info,tree]=await Promise.all([fetch('/v1/document').then(r=>r.json()),fetch('/v1/document/tree').then(r=>r.json())]);
 document.getElementById('info').textContent=`${info.pages} pages · ${info.nodes} nodes · ${info.numeric_facts} numeric facts`;
 const nodes=tree.nodes, root=nodes[tree.root_id];
 function render(id,depth){ const n=nodes[id]; let out=`<div class="tree-node" style="margin-left:${depth*14}px">${esc(n.title)} <span class="small">pp. ${n.page_start}-${n.page_end}</span></div>`; for(const c of n.child_ids||[]) out+=render(c,depth+1); return out; }
 document.getElementById('tree').innerHTML=render(root.id,0);
}
async function runSearch(){
 const q=document.getElementById('q').value.trim(); if(!q)return;
 const data=await fetch('/v1/search',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({query:q,mode:'fast',top_k:5,include_trace:true})}).then(r=>r.json());
 document.getElementById('summary').innerHTML=`<p>Confidence <b>${Number(data.evidence_pack.confidence).toFixed(3)}</b> · ${data.trace.total_latency_ms.toFixed(2)} ms · ${data.trace.llm_calls} retrieval LLM calls</p>`;
 document.getElementById('results').innerHTML=data.evidence_pack.evidence.map(e=>`<div class="card"><div><span class="score">${Number(e.score).toFixed(3)}</span> ${esc(e.section)}</div><div class="small">pp. ${e.page_start}-${e.page_end}</div><p>${esc(e.text.slice(0,900))}</p></div>`).join('');
 document.getElementById('trace').textContent=JSON.stringify(data.trace,null,2);
 document.getElementById('plan').textContent=JSON.stringify({query_ir:data.query_ir,plan:data.plan},null,2);
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')runSearch()});
init();
</script>
</body>
</html>'''
