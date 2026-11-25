'use strict';
// Read-only field inspector. Values and CSV quoting come from the local export writer.
const startWithCSV = new URLSearchParams(location.search).get('view')==='question-csv';
const csvLens = (() => {
  let compare = startWithCSV, selected = '', question, rowOpen = false, timer, serial = 0;
  let cacheKey = '', snapshot = null, pending = '', failure = '', copyTimer;
  const columns = {type:'Prompt Type',name:'Name',content:'Content',priority:'Priority',total:'Total Quantity',limit:'LimitQuantity',pin:'Pin',check:'Data Check Flag'};
  const nodes = sel => [...document.querySelectorAll(sel)];
  const has = (obj,k) => Object.prototype.hasOwnProperty.call(obj,k);
  function mapping(path) {
    const [base,...rest] = path.split('.');
    const column = base==='attrs'?'Attributes':base==='inputs'?'Inputs':base==='group'?(c.mode==='STATIC'?'Script Name':'Theme Name'):columns[base];
    return {column, nested:!!rest.length, address:column+rest.map(k=>/^\d+$/.test(k)?`[${k}]`:'.'+k).join('')};
  }
  function bar() {
    return `<section id="csv-bar" class="csv-bar" aria-label="题目字段视图"><div class="csv-bar-top"><b>字段视图</b><div class="csv-switch" role="group" aria-label="字段视图"><button type="button" data-lens-mode="form">表单</button><button type="button" data-lens-mode="compare">CSV 对照</button></div></div><small>点字段旁的 CSV 看它如何写入文件，或切换到「CSV 对照」同时查看所有字段。</small><details id="csv-record"><summary>本题整行 CSV</summary><div class="csv-record-body"></div></details></section>`;
  }
  function decorate(input, attr) {
    const label = attr?input.closest('label'):input.labels?.[0];
    if (!label || label.closest('.csv-label')) return;
    const host = attr?input.closest('.prop'):input.parentElement;
    const path = attr?'attrs.'+input.dataset.enable:input.dataset.p.split('.').slice(2).join('.');
    const id = (attr?'attribute:':'field:')+path, title=label.textContent.trim();
    const wrap=document.createElement('div');wrap.className='csv-label';label.before(wrap);wrap.append(label);
    const button=document.createElement('button');button.type='button';button.className='csv-peek';button.dataset.lens=id;
    button.textContent='CSV';button.setAttribute('aria-label',`${title}：CSV 单元格`);wrap.append(button);
    const target=document.createElement('div');target.className='csv-slot';target.dataset.lensId=id;target.dataset.path=path;
    target.id='csv-detail-'+id;button.setAttribute('aria-controls',target.id);host.append(target);
  }
  function mount() {
    if (page!==1) {clearTimeout(timer);pending='';serial++;return;}
    if (q()!==question) {question=q();selected='';rowOpen=false;}
    if (!$('csv-bar')) {
      document.querySelector('#page .tools').insertAdjacentHTML('afterend',bar());
      const record=$('csv-record');record.open=rowOpen;
      record.addEventListener('toggle',()=>{if (!record.isConnected)return;rowOpen=record.open;refresh();});
    }
    nodes('#page [data-p^="questions."]').forEach(el=>decorate(el,false));
    nodes('#attrs [data-enable]').forEach(el=>decorate(el,true));
    refresh();
  }
  function cellValue(path, data, map) {
    const cell=data.cells[map.column];
    if (!cell) return {note:'本文件没有这一列',info:'所有题目都未填写此项，导出时会省略整列。'};
    if (map.nested && !has(data.parts,path)) return {note:'未写入此键',info:'当前单元格的 JSON 中没有这个键。'};
    if (path==='pin' && !data.first) return {note:'空单元格 · 非脚本首题',info:'同一脚本只在第一行写入 PIN。'};
    if (!map.nested && cell.text==='') return {note:'空单元格',info:'文件保留这一列，本题的这一格不写字符。'};
    return {text:map.nested?data.parts[path]:cell.text};
  }
  const escapedCode=(value,cls='')=>`<code class="${cls}">${esc(value)}</code>`;
  function display(slot, data, status) {
    const path=slot.dataset.path, map=mapping(path), detail=selected===slot.dataset.lensId;
    slot.hidden=!compare&&!detail;
    const button=slot.parentElement.querySelector('[data-lens]');
    button.setAttribute('aria-expanded',String(detail));button.classList.toggle('is-on',detail);
    if (slot.hidden) {slot.replaceChildren();return;}
    const value=data&&cellValue(path,data,map),cell=data?.cells[map.column];
    const valueHtml=status?`<span class="csv-empty">${esc(status)}</span>`:value.text!==undefined?escapedCode(value.text,'csv-fragment'):`<span class="csv-empty">${esc(value.note)}</span>`;
    const head=`<div class="csv-mapping"><code class="csv-address">${esc(map.address)}</code>${valueHtml}</div>`;
    let body='';
    if (detail && !status) {
      const explanation=value.info || (map.nested?'这个键和值放在同一个 JSON 单元格中。':'这个字段直接写入这一列。');
      body=`<div class="csv-detail"><small>${esc(explanation)}</small>${cell?`<div class="csv-caption">${esc(map.column)} 单元格原文</div>${cell.raw===''?'<span class="csv-empty">（空单元格）</span>':`<pre>${esc(cell.raw)}</pre>`}`:''}</div>`;
    }
    slot.classList.toggle('is-detail',detail);slot.innerHTML=head+body;
  }
  function paint() {
    if (page!==1 || !$('csv-bar')) return;
    const invalid=Object.keys(rawErrors).length>0, data=invalid?null:snapshot;
    const status=invalid?'当前输入有误，修正后显示 CSV。':failure||(!data?'正在生成…':'');
    nodes('[data-lens-mode]').forEach(b=>b.setAttribute('aria-pressed',String((b.dataset.lensMode==='compare')===compare)));
    nodes('.csv-slot').forEach(el=>display(el,data,status));
    if (rowOpen) {
      const body=document.querySelector('.csv-record-body');
      const key=status||cacheKey;
      if (body.dataset.renderKey!==key) {
        body.dataset.renderKey=key;
        body.innerHTML=status?`<small>${esc(status)}</small>`:`<div class="csv-legend"><span>第 ${idx+1} 题 · ${c.mode==='STATIC'?'静态脚本':'动态题库'} · 草稿</span><button type="button" data-copy-row>复制表头与本行</button></div><div class="csv-caption">表头</div><pre>${esc(data.header)}</pre><div class="csv-caption">本题数据</div><pre>${esc(data.row)}</pre><small>逗号分隔各列。单元格含逗号、换行或英文双引号时，CSV 用双引号包住整格；格内的双引号写两次。</small>`;
      }
    }
  }
  function refresh() {
    if (page!==1 || !$('csv-bar')) return;
    const key=`${version}/${idx}/${c.mode}`;
    if (key!==cacheKey) {cacheKey=key;snapshot=null;failure='';clearTimeout(timer);pending='';serial++;}
    paint();
    if ((!compare&&!selected&&!rowOpen)||Object.keys(rawErrors).length||snapshot||pending===key) return;
    const turn=++serial;pending=key;
    timer=setTimeout(async()=>{
      if (page!==1 || key!==cacheKey || turn!==serial) {if(turn===serial)pending='';return;}
      try {
        // Only the selected question needs content; other rows determine optional columns and the first script row.
        const data=await localQuestionCSV();
        if(turn===serial) {snapshot=data;failure='';}
      } catch(e) {if(turn===serial) failure='暂时无法生成对照：'+e.message;}
      finally {if(turn===serial) {pending='';paint();}}
    },100);
  }
  document.addEventListener('click',async e=>{
    const mode=e.target.closest('[data-lens-mode]'), peek=e.target.closest('[data-lens]'), copy=e.target.closest('[data-copy-row]');
    if (mode) {compare=mode.dataset.lensMode==='compare';selected='';refresh();}
    else if (peek) {selected=selected===peek.dataset.lens?'':peek.dataset.lens;refresh();}
    else if (copy && snapshot && !Object.keys(rawErrors).length) {
      try {await navigator.clipboard.writeText(snapshot.header+'\r\n'+snapshot.row+'\r\n');copy.textContent='已复制';}
      catch {copy.textContent='请选中下方原文复制';}
      clearTimeout(copyTimer);copyTimer=setTimeout(()=>{if(copy.isConnected)copy.textContent='复制表头与本行';},1800);
    }
  });
  return {mount,refresh};
})();

let draftCSVKey='', draftCSVRequest;
function localQuestionCSV() {
  const key=`${version}/${idx}/${c.mode}`;
  if(key!==draftCSVKey || !draftCSVRequest) {
    draftCSVKey=key;
    const questions=c.questions.map((r,i)=>i===idx?r:{group:r.group,pin:r.pin,check:r.check});
    draftCSVRequest=api('/question-csv',{mode:c.mode,index:idx,questions}).catch(e=>{if(key===draftCSVKey)draftCSVRequest=null;throw e;});
  }
  return draftCSVRequest;
}

const specimen=(()=>{
  let face=0, lastPage=-1, lastKey='', timer, tick=0;
  const names=['题面','属性','导出行'];
  function sync() {
    const deck=$('specimen');if(!deck || !q()) return;
    const cards=[...deck.querySelectorAll('.deck-card')],it=q();
    cards.forEach((card,i)=>{card.dataset.rank=String((i-face+3)%3);});
    cards[0].querySelector('.deck-body').textContent=it.content||'尚未填写题面';
    const invalid=Object.keys(rawErrors).length>0;
    cards[1].querySelector('.deck-body').textContent=invalid?'当前输入待修正':JSON.stringify(it.attrs);
    const cell=cards[2].querySelector('.deck-body'), stamp=`${version}/${idx}/${c.mode}/${face}/${invalid}`;
    if (stamp!==lastKey) {
      lastKey=stamp;const id=++tick;clearTimeout(timer);
      if (face===2 && !invalid) {
        cell.textContent='正在生成…';
        timer=setTimeout(async()=>{try{const d=await localQuestionCSV();if(tick===id)cell.textContent=d.row;}
          catch{if(tick===id)cell.textContent='暂时无法读取本地草稿';}},110);
      } else {cell.textContent=invalid?'当前输入待修正':'';}
    }
    $('deck-count').textContent=`0${face+1} / 03 · ${names[face]}`;
    const current=cards[face].querySelector('.deck-body').textContent;
    deck.setAttribute('aria-label',`当前卡片：${names[face]}。${current.slice(0,90)}。翻到${names[(face+1)%3]}。`);
  }
  function mount() {
    const deck=$('specimen');deck.onclick=()=>{face=(face+1)%3;sync();};
    if(page!==lastPage) {lastPage=page;const title=document.querySelector('#page h2');if(title)title.classList.add('arrive');}
    document.body.dataset.stage=page;sync();
  }
  return {sync,mount};
})();
