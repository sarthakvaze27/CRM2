const orders=[
 {id:'#1048',name:'Olivia Rhye',initials:'OR',color:'#fce5d7',date:'Oct 13, 2026',status:'processing',total:'$124.00'},
 {id:'#1047',name:'Phoenix Baker',initials:'PB',color:'#e5e7ff',date:'Oct 13, 2026',status:'completed',total:'$89.50'},
 {id:'#1046',name:'Lana Steiner',initials:'LS',color:'#fce4ef',date:'Oct 12, 2026',status:'completed',total:'$210.00'},
 {id:'#1045',name:'Demi Wilkinson',initials:'DW',color:'#e0f3e8',date:'Oct 12, 2026',status:'pending',total:'$56.00'},
 {id:'#1044',name:'Candice Wu',initials:'CW',color:'#fff0d9',date:'Oct 11, 2026',status:'refunded',total:'$42.00'}
];
let customers=[
 {name:'Olivia Rhye',email:'olivia.rhye@email.com',initials:'OR',color:'#fce5d7',location:'Brooklyn, NY',orders:4,spent:'$486.00',last:'Oct 13, 2026'},
 {name:'Phoenix Baker',email:'phoenix.baker@email.com',initials:'PB',color:'#e5e7ff',location:'Los Angeles, CA',orders:2,spent:'$194.50',last:'Oct 13, 2026'},
 {name:'Lana Steiner',email:'lana.steiner@email.com',initials:'LS',color:'#fce4ef',location:'Austin, TX',orders:6,spent:'$1,205.00',last:'Oct 12, 2026'},
 {name:'Demi Wilkinson',email:'demi.wilkinson@email.com',initials:'DW',color:'#e0f3e8',location:'Portland, OR',orders:1,spent:'$56.00',last:'Oct 12, 2026'},
 {name:'Candice Wu',email:'candice.wu@email.com',initials:'CW',color:'#fff0d9',location:'Seattle, WA',orders:3,spent:'$248.00',last:'Oct 11, 2026'}
];
const el=id=>document.getElementById(id);
function renderOrders(rows=orders){el('orderRows').innerHTML=rows.map(o=>`<tr><td class="order-id">${o.id}</td><td><div class="customer-cell"><span class="avatar mini-avatar" style="background:${o.color}">${o.initials}</span><b>${o.name}</b></div></td><td>${o.date}</td><td><span class="status ${o.status}">${o.status[0].toUpperCase()+o.status.slice(1)}</span></td><td class="amount">${o.total}</td></tr>`).join('')}
function renderCustomers(rows=customers){el('customerRows').innerHTML=rows.map(c=>`<tr class="customer-row"><td><div class="customer-cell"><span class="avatar mini-avatar" style="background:${c.color}">${c.initials}</span><div><b>${c.name}</b><div class="email">${c.email}</div></div></div></td><td class="location">${c.location}</td><td>${c.orders}</td><td class="amount">${c.spent}</td><td>${c.last}</td><td>···</td></tr>`).join('')}
renderOrders();renderCustomers();
el('customerSearch').addEventListener('input',e=>{const q=e.target.value.toLowerCase();renderCustomers(customers.filter(c=>(c.name+c.email+c.location).toLowerCase().includes(q)))});
el('syncBtn').addEventListener('click',async()=>{const btn=el('syncBtn');btn.disabled=true;btn.innerHTML='<span>⟳</span> Syncing…';try{const response=await fetch('./data.json?'+Date.now());if(response.ok){const data=await response.json();if(data.orders?.length)renderOrders(data.orders.slice(0,5).map(o=>({id:'#'+o.number,name:o.billing?.first_name+' '+o.billing?.last_name,initials:(o.billing?.first_name?.[0]||'C')+(o.billing?.last_name?.[0]||''),color:'#e5e7ff',date:new Date(o.date_created).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}),status:o.status,total:new Intl.NumberFormat('en-US',{style:'currency',currency:o.currency||'USD'}).format(Number(o.total))})));if(data.customers?.length){customers=data.customers.slice(0,5).map(c=>({name:(c.first_name+' '+c.last_name).trim()||c.username,email:c.email,initials:((c.first_name?.[0]||'')+(c.last_name?.[0]||''))||'CU',color:'#eee9ff',location:[c.billing?.city,c.billing?.state].filter(Boolean).join(', ')||'—',orders:c.orders_count||0,spent:'$'+Number(c.total_spent||0).toFixed(2),last:c.date_modified?new Date(c.date_modified).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'—'}));renderCustomers();el('customerCount').textContent=String(data.customers.length)}}}catch(e){}setTimeout(()=>{btn.disabled=false;btn.innerHTML='<span>⟳</span> Sync store';el('toast').classList.add('show');setTimeout(()=>el('toast').classList.remove('show'),2500)},450)});
