export const money = cents => (cents / 100).toLocaleString('pt-BR', {style:'currency',currency:'BRL'});
export const today = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
export function parseMoney(input) {
 const s=String(input).trim();
 if(!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(s)) throw Error('Use um valor como 125,90.');
 const [a,b='']=s.replaceAll('.','').split(','); const n=Number(a)*100+Number(b.padEnd(2,'0'));
 if(!Number.isSafeInteger(n)||n<=0||n>100000000000) throw Error('Informe um valor positivo válido.'); return n;
}
export function validDate(value) {if(!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false; const d=new Date(value+'T12:00:00Z'); return !isNaN(d)&&d.toISOString().slice(0,10)===value;}
export const emptyState = () => ({version:1, demo:false,accounts:[{id:'main',name:'Conta principal',opening:0},{id:'reserve',name:'Reserva',opening:0}],transactions:[],goals:[],cards:[],purchases:[]});
export function demoState() {
 const s=emptyState(); s.demo=true; s.accounts[0].opening=150000; const month=today().slice(0,7);
 const rows=[['Salário',320000,'income','Receitas',2],['Supermercado',32580,'expense','Alimentação',4],['Internet',9990,'expense','Moradia',5],['Transporte',18400,'expense','Transporte',7],['Cinema',6800,'expense','Lazer',9],['Almoço',4250,'expense','Alimentação',10],['Reserva do mês',50000,'transfer','Transferência',11]];
 s.transactions=rows.map(([description,amount,type,category,day],i)=>({id:'demo'+i,description,amount,type,category,date:month+'-'+String(Math.min(day,Number(today().slice(-2)))).padStart(2,'0'),accountId:'main',toAccountId:type==='transfer'?'reserve':null}));
 s.goals=[{id:'g1',name:'Minha reserva',target:1000000,accountId:'reserve'}]; return s;
}
export function validateTransaction(s,t) {
 if(!['income','expense','transfer'].includes(t.type)) throw Error('Tipo inválido.');
 if(!Number.isSafeInteger(t.amount)||t.amount<=0) throw Error('Valor inválido.');
 if(!t.description?.trim()) throw Error('Preencha a descrição.');
 if(!validDate(t.date)) throw Error('Data inválida. Use AAAA-MM-DD.');
 if(t.date>today()) throw Error('Esta versão aceita somente movimentações já realizadas.');
 if(!s.accounts.some(a=>a.id===t.accountId)) throw Error('Conta inválida.');
 if(t.type==='transfer'&&(!s.accounts.some(a=>a.id===t.toAccountId)||t.accountId===t.toAccountId)) throw Error('Escolha outra conta de destino.');
 return {...t,description:t.description.trim(),category:t.type==='transfer'?'Transferência':t.type==='income'?'Receitas':t.category||'Outros'};
}
export function balance(s,id) {return s.transactions.reduce((n,t)=>n+(t.toAccountId===id&&t.type==='transfer'?t.amount:0)+(t.accountId===id?(t.type==='income'?t.amount:-t.amount):0),s.accounts.find(a=>a.id===id)?.opening||0);}
export function summary(s,month=today().slice(0,7)) {
 const ts=s.transactions.filter(t=>t.date.startsWith(month)); let income=0,expense=0; const cats=Object.create(null);
 for(const t of ts){if(t.type==='income')income+=t.amount; if(t.type==='expense'){expense+=t.amount;cats[t.category]=(cats[t.category]||0)+t.amount;}}
 for(const p of s.purchases||[])if(p.date.startsWith(month)){expense+=p.amount;cats[p.category]=(cats[p.category]||0)+p.amount;}
 return {income,expense,net:income-expense,categories:Object.entries(cats).sort((a,b)=>b[1]-a[1]),count:ts.length+(s.purchases||[]).filter(p=>p.date.startsWith(month)).length};
}
export function answer(s,question) {
 const q=question.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
 const d=new Date(); if(q.includes('mes passado'))d.setMonth(d.getMonth()-1,1);
 const month=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; const r=summary(s,month);
 if(/saldo|quanto tenho/.test(q))return {text:`Seu saldo registrado é ${money(s.accounts.reduce((n,a)=>n+balance(s,a.id),0))}. Inclui todas as contas, inclusive reservas.`,month};
 if(/meta|reserva|cofrinho/.test(q)) return {text:s.goals.length?s.goals.map(g=>`${g.name}: ${money(balance(s,g.accountId))} de ${money(g.target)}.`).join('\n'):'Você ainda não criou metas. Abra a aba Metas para começar.',month};
 if(/gast|despes|categor|resumo|entrad|receit|compar/.test(q)) {
 let text=`Em ${month.split('-').reverse().join('/')}, você registrou ${money(r.expense)} em despesas e ${money(r.income)} em receitas. Compras no cartão entram pelo valor total na data da compra. Transferências e pagamentos de fatura não duplicam despesas.`;
 if(r.categories.length)text+=` A maior categoria é ${r.categories[0][0]}: ${money(r.categories[0][1])} (${Math.round(r.categories[0][1]/r.expense*100)}%).`;
 if(q.includes('compar')) {const p=new Date(d.getFullYear(),d.getMonth()-1,1);const pm=`${p.getFullYear()}-${String(p.getMonth()+1).padStart(2,'0')}`;const old=summary(s,pm);text+=old.count?` O mês anterior tem ${money(old.expense)} em despesas registradas. Comparação de meses completos registrados; o mês atual pode estar incompleto.`:' Ainda não há registros do mês anterior para comparar.';}
 return {text,month,chart:r.categories};
 }
 return {text:'Nesta versão, sou um assistente local de consultas, sem IA externa. Posso mostrar gastos, maiores categorias, receitas, saldo, metas e comparar meses. Experimente “Quanto gastei neste mês?”.',month};
}
