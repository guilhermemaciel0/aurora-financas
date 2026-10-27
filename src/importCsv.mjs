import {validDate,today,validateTransaction} from './finance.mjs';
import {pay} from './cards.mjs';
export const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase().replace(/\s+/g,' ');
export function parseCsv(text){
 if(typeof text!=='string'||text.length>1000000)throw Error('Use um CSV de até 1 MB.');
 text=text.replace(/^\uFEFF/,'');if(text.includes('\uFFFD')||text.includes('\0'))throw Error('Salve o arquivo como CSV UTF-8 antes de importar.');
 const line=text.split(/\r?\n/).find(l=>l.trim())||'';
 let quoted=false,commas=0,semis=0;for(let i=0;i<line.length;i++){if(line[i]==='"')quoted=!quoted;else if(!quoted){if(line[i]===',')commas++;if(line[i]===';')semis++;}}
 const sep=semis>commas?';':',';let rows=[],row=[],cell='',inQuotes=false,closed=false;
 const flush=()=>{row.push(cell);if(row.some(x=>x.trim()))rows.push(row);row=[];cell='';closed=false;};
 for(let i=0;i<text.length;i++) {const c=text[i];if(inQuotes){if(c==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{inQuotes=false;closed=true;}}else cell+=c;}
 else if(c==='"'){if(cell.trim()||closed)throw Error('Aspas inválidas no CSV.');cell='';inQuotes=true;}
 else if(c===sep){row.push(cell);cell='';closed=false;}
 else if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;flush();}
 else{if(closed&&!/\s/.test(c))throw Error('Separador inválido depois de aspas.');cell+=c;}}
 if(inQuotes)throw Error('O CSV terminou com aspas abertas.');if(cell||row.length)flush();
 if(rows.length<2)throw Error('O arquivo precisa ter cabeçalho e pelo menos um lançamento.');
 if(rows.length>501)throw Error('Importe até 500 lançamentos por vez.');
 const headers=rows.shift().map(s=>s.trim());
 if(headers.length<3||headers.length>30)throw Error('Use um extrato tabular com colunas de data, descrição e valor.');
 return {headers,rows,separator:sep};
}
export function guessMapping(headers){const names=headers.map(normalize);const find=opts=>String(names.findIndex(x=>opts.includes(x)));return {date:find(['data','date','data de lancamento','data lancamento']),description:find(['descricao','description','historico','lancamento']),amount:find(['valor','amount','valor (r$)']),externalId:find(['identificador','id','transaction id','id da transacao'])};}
export function csvAmount(value,decimal='comma'){
 let s=String(value).trim().replace(/^R\$\s*/i,'').replace(/\s/g,'');let sign=1;
 if(/^\(.*\)$/.test(s)){sign=-1;s=s.slice(1,-1);}else if(/^[+-]/.test(s)){if(s[0]==='-')sign=-1;s=s.slice(1);}
 const pattern=decimal==='comma'?/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/:/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/;
 if(!pattern.test(s))throw Error('Valor inválido para o formato decimal escolhido.');
 const clean=s.replaceAll(decimal==='comma'?'.':',','');const parts=clean.split(decimal==='comma'?',':'.');
 const n=Number(parts[0])*100+Number((parts[1]||'').padEnd(2,'0'));
 if(!Number.isSafeInteger(n)||n===0||n>100000000000)throw Error('Valor deve ser diferente de zero e estar dentro do limite.');return n*sign;
}
export function csvDate(value){let s=String(value).trim();const br=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s);if(br)s=`${br[3]}-${br[2]}-${br[1]}`;if(!validDate(s)||s>today())throw Error('Data inválida ou futura. Use DD/MM/AAAA ou AAAA-MM-DD.');return s;}
function signedOn(t,accountId){if(t.type==='transfer'&&t.toAccountId===accountId)return t.amount;if(t.accountId===accountId)return t.type==='income'?t.amount:-t.amount;return null;}
export function duplicate(s,r,accountId){
 const exact=s.transactions.find(t=>r.sourceId&&t.importSourceId===r.sourceId&&t.importAccountId===accountId);
 if(exact)return {hard:true,message:'Identificador já importado nesta conta.'};
 const hits=s.transactions.filter(t=>t.date===r.date&&signedOn(t,accountId)===r.signedAmount);
 if(hits.some(t=>normalize(t.description)===normalize(r.description)))return {hard:false,message:'Mesma data, valor e descrição de um registro existente.'};
 if(hits.length)return {hard:false,message:'Mesmo valor e data de outro registro. Confira se já foi lançado.'};
 return null;
}
export function previewCsv(s,table,mapping,accountId,decimal='comma',positive='income'){
 if(!s.accounts.some(a=>a.id===accountId))throw Error('Escolha a conta do extrato.');
 const cols=['date','description','amount'].map(k=>Number(mapping[k]));if(cols.some(n=>!Number.isInteger(n)||n<0||n>=table.headers.length)||new Set(cols).size!==3)throw Error('Escolha três colunas diferentes para data, descrição e valor.');
 const external=Number(mapping.externalId);const seen=new Set(),ids=new Set(),amounts=new Set();
 return table.rows.map((cells,i)=>{try{
 if(cells.length!==table.headers.length)throw Error('Quantidade de colunas diferente do cabeçalho.');
 const date=csvDate(cells[cols[0]]),description=cells[cols[1]].trim();if(!description||description.length>500)throw Error('Descrição vazia ou maior que 500 caracteres.');
 const amount=csvAmount(cells[cols[2]],decimal);const signedAmount=positive==='expense'?-amount:amount;
 const sourceId=external>=0?String(cells[external]||'').trim():'';
 const r={key:String(i),line:i+2,date,description,signedAmount,sourceId,type:signedAmount>0?'income':'expense',category:signedAmount>0?'Receitas':'Outros',otherAccountId:'',cardId:'',invoiceMonth:''};
 const fp=JSON.stringify([date,normalize(description),signedAmount]);let dup=duplicate(s,r,accountId);
 if(sourceId&&ids.has(sourceId))dup={hard:true,message:'Identificador repetido no arquivo.'};else if(seen.has(fp))dup={hard:false,message:'Linha semelhante repetida neste arquivo.'};else if(amounts.has(date+'|'+signedAmount))dup={hard:false,message:'Mesmo valor e data de outra linha do arquivo. Confira antes de incluir.'};
 if(sourceId)ids.add(sourceId);seen.add(fp);amounts.add(date+'|'+signedAmount);
 const warning=/transfer|pix|aplica|resgate|fatura/.test(normalize(description))?'Confira se é transferência própria, aplicação ou pagamento de fatura.':'';
 return {...r,duplicate:dup,warning,selected:!dup,reviewed:false};
 }catch(e){return {key:String(i),line:i+2,error:e.message,selected:false,description:cells.join(' · ').slice(0,160)};}});
}
export function applyImport(s,rows,accountId,batchId){
 const next={...s,transactions:[...s.transactions]};let added=0;
 for(const r of rows.filter(x=>x.selected)){
 if(r.error)throw Error(`Linha ${r.line}: corrija ou desmarque o registro.`);
 const check=duplicate(next,r,accountId);if(check?.hard)throw Error(`Linha ${r.line}: ${check.message}`);
 if((check||r.duplicate)&&!r.reviewed)throw Error(`Linha ${r.line}: confirme a possível duplicidade antes de importar.`);
 let t;const amount=Math.abs(r.signedAmount);const sourceId=r.signedAmount>0?r.otherAccountId:accountId,destId=r.signedAmount>0?accountId:r.otherAccountId;
 if(r.type==='card_payment'){
 if(r.signedAmount>=0)throw Error('Pagamento de fatura precisa ser uma saída.');
 t=pay(next,r.cardId,r.invoiceMonth,accountId,amount,r.date);t.description=r.description;
 }else t=validateTransaction(next,{id:`${batchId}-${r.key}`,description:r.description,date:r.date,amount,type:r.type,category:r.category,accountId:r.type==='transfer'?sourceId:accountId,toAccountId:r.type==='transfer'?destId:null});
 if(r.type==='income'&&r.signedAmount<0||r.type==='expense'&&r.signedAmount>0)throw Error('Tipo incompatível com o sinal do valor.');
 next.transactions.push({...t,importBatchId:batchId,importAccountId:accountId,...(r.sourceId?{importSourceId:r.sourceId}:{})});added++;
 }
 if(!added)throw Error('Selecione pelo menos um lançamento válido.');
 return {state:next,added};
}
export function undoImport(s,batchId){return {...s,transactions:s.transactions.filter(t=>t.importBatchId!==batchId)};}
