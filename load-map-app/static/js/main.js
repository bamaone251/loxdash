// Utility
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let currentId = null;
let pallets = [];       // length=30
let bulkheads = [];     // indices 1..15 per row put marker after position (1..14); we store absolute positions 1..14 per row (A=1..14, B=16..29) for simplicity
let totals = {
  frozen:0, chiller:0, ambient:0, eggs:0, bread:0, dp:0, flower:0, equip:0, total:0
};

function defaultPallets(){
  const arr = [];
  for (let r=0; r<2; r++){
    for (let c=0; c<15; c++){
      const pos = r*15 + c + 1;
      arr.push({pos, row:r+1, col:c+1, type:"", store:"", zone:""});
    }
  }
  return arr;
}

function typeToKey(t){
  if(!t) return null;
  const m = {
    "Frozen":"frozen",
    "Chiller":"chiller",
    "Ambient":"ambient",
    "Eggs":"eggs",
    "Bread":"bread",
    "DP":"dp",
    "Flower":"flower",
    "Equip":"equip"
  };
  return m[t] || null;
}

function recomputeTotals(){
  totals = {frozen:0, chiller:0, ambient:0, eggs:0, bread:0, dp:0, flower:0, equip:0, total:0};
  pallets.forEach(p=>{
    if(p && p.type){
      const k = typeToKey(p.type);
      if(k){ totals[k]++; totals.total++; }
    }
  });
  $("#t_frozen").textContent = totals.frozen;
  $("#t_chiller").textContent = totals.chiller;
  $("#t_ambient").textContent = totals.ambient;
  $("#t_eggs").textContent = totals.eggs;
  $("#t_bread").textContent = totals.bread;
  $("#t_dp").textContent = totals.dp;
  $("#t_flower").textContent = totals.flower;
  $("#t_equip").textContent = totals.equip;
  $("#t_total").textContent = totals.total;
}

async function fetchList(q=""){
  const res = await fetch(`/api/loadmaps${q?`?q=${encodeURIComponent(q)}`:""}`);
  const data = await res.json();
  const list = $("#mapsList");
  list.innerHTML = "";
  data.forEach(item=>{
    const div = document.createElement("div");
    div.className = "list-item";
    const left = document.createElement("div");
    left.innerHTML = `<div><strong>${item.title}</strong></div>
      <div style="opacity:.8;font-size:.9rem"> Run ${item.run_number||"-"} • Trailer ${item.trailer_number||"-"} • Updated ${new Date(item.updated_at).toLocaleString()}</div>`;
    const right = document.createElement("div");
    const openBtn = document.createElement("button");
    openBtn.className = "btn primary";
    openBtn.textContent = "Open";
    openBtn.onclick = ()=> openEditor(item.id);
    right.appendChild(openBtn);
    div.appendChild(left); div.appendChild(right);
    list.appendChild(div);
  });
}

function palletCard(p){
  const btn = document.createElement("div");
  btn.className = "pallet" + (p.type?` type-${p.type}`:"");
  btn.dataset.pos = p.pos;
  btn.innerHTML = `<div class="pos">${p.pos}</div>
                   <div class="store">${p.store||""}</div> <hr>
                   <div class="type">${p.type||""}</div>`;
  if(bulkheads.includes(p.pos)) {
    const b = document.createElement("div");
    b.className = "bulk";
    b.textContent = "Bulkhead";
    btn.appendChild(b);
  }
  btn.onclick = ()=> editPallet(p.pos);
  return btn;
}

function renderGrid(){
  const grid = $("#palletGrid");
  grid.innerHTML = "";
  // Row A label
  const row1 = document.createElement("div"); row1.className = "row-label"; row1.textContent = "(Nose → Door)";
  grid.appendChild(row1);
  for(let i=1;i<=30;i++){
    grid.appendChild(palletCard(pallets[i-1]));
 
}
}

function openEditor(id){
  currentId = id || null;
  $("#listView").classList.add("hidden");
  $("#editor").classList.remove("hidden");
  if(!id){
    // new
    $("#title").value =  new Date().toLocaleString();
    $("#run_number").value = ""; 
    $("#trailer_number").value = "";
    $("#door").value = "";
    $("#fuel_level").value = "";
    $("#loaded_temp").value = "";
    $("#loader_name").value = "";
    $("#driver_name").value = "";
    $("#wol_olpn_count").value = 0;
    $("#date_field").valueAsDate = new Date();
    $(".stop-row .stop-loader");
    $$(".stop-row .stop-loader").forEach(el=>el.value="");
    $$(".stop-row .stop-driver").forEach(el=>el.value="");
    $("#plbs_loaded").value = 0;
    $("#plbs_created").value = 0;
    $("#dpr_rebuilds").value = 0;
    $("#dpr_rewraps").value = 0;
    $("#dpr_consolidations").value = 0;
    $("#loader_notes").value = "";
    $("#driver_notes").value = "";
    $("#san_q1").value = "";
    $("#san_q2").value = "";
    $("#san_q3").value = "";
    $("#san_q4").value = "";
    pallets = defaultPallets();
    bulkheads = [];
    renderGrid();
    recomputeTotals();
    return;
  }
  // existing
  fetch(`/api/loadmaps/${id}`).then(r=>r.json()).then(item=>{
    $("#title").value = item.title || "";
    $("#run_number").value = item.run_number || "";
    $("#trailer_number").value = item.trailer_number || "";
    $("#door").value = item.door || "";
    $("#fuel_level").value = item.fuel_level || "";
    $("#loaded_temp").value = item.loaded_temp || "";
    $("#loader_name").value = item.loader_name || "";
    $("#driver_name").value = item.driver_name || "";
    $("#wol_olpn_count").value = item.wol_olpn_count || 0;
    $$(".stop-row").forEach((row,idx)=>{
      const s = (item.stops_json||[])[idx] || {};
      row.querySelector(".stop-loader").value = s.loader || "";
      row.querySelector(".stop-driver").value = s.driver || "";
    });
    $("#plbs_loaded").value = item.plbs_loaded || 0;
    $("#plbs_created").value = item.plbs_created || 0;
    $("#dpr_rebuilds").value = item.dpr_rebuilds || 0;
    $("#dpr_rewraps").value = item.dpr_rewraps || 0;
    $("#dpr_consolidations").value = item.dpr_consolidations || 0;
    $("#loader_notes").value = item.loader_notes || "";
    $("#driver_notes").value = item.driver_notes || "";
    $("#san_q1").value = item.sanitary_q1==1?"Yes":(item.sanitary_q1==0?"No":"");
    $("#san_q2").value = item.sanitary_q2==1?"Yes":(item.sanitary_q2==0?"No":"");
    $("#san_q3").value = item.sanitary_q3==1?"Yes":(item.sanitary_q3==0?"No":"");
    $("#san_q4").value = item.sanitary_q4==1?"Yes":(item.sanitary_q4==0?"No":"");
    pallets = item.pallets_json || defaultPallets();
    bulkheads = item.bulkheads_json || [];
    renderGrid();
    recomputeTotals();
  });
}

function closeEditor(){
  $("#editor").classList.add("hidden");
  $("#listView").classList.remove("hidden");
  currentId = null;
}

function collectStops(){
  return $$(".stop-row").map((row, idx)=> ({
    stop: idx+1,
    loader: row.querySelector(".stop-loader").value.trim(),
    driver: row.querySelector(".stop-driver").value.trim(),
  }));
}

function ynToNum(v){
  if(v==="Yes") return 1;
  if(v==="No") return 0;
  return None;
}

async function save(){
  const body = {
    title: $("#title").value.trim() || "Load Map",
    run_number: $("#run_number").value.trim(),
    trailer_number: $("#trailer_number").value.trim(),
    door: $("#door").value.trim(),
    fuel_level: $("#fuel_level").value.trim(),
    loaded_temp: $("#loaded_temp").value.trim(),
    loader_name: $("#loader_name").value.trim(),
    driver_name: $("#driver_name").value.trim(),
    wol_olpn_count: Number($("#wol_olpn_count").value || 0),
    stops_json: collectStops(),
    pallets_json: pallets,
    bulkheads_json: bulkheads,
    plbs_loaded: Number($("#plbs_loaded").value || 0),
    plbs_created: Number($("#plbs_created").value || 0),
    dpr_rebuilds: Number($("#dpr_rebuilds").value || 0),
    dpr_rewraps: Number($("#dpr_rewraps").value || 0),
    dpr_consolidations: Number($("#dpr_consolidations").value || 0),
    loader_notes: $("#loader_notes").value,
    driver_notes: $("#driver_notes").value,
    sanitary_q1: $("#san_q1").value==="Yes"?1:($("#san_q1").value==="No"?0:null),
    sanitary_q2: $("#san_q2").value==="Yes"?1:($("#san_q2").value==="No"?0:null),
    sanitary_q3: $("#san_q3").value==="Yes"?1:($("#san_q3").value==="No"?0:null),
    sanitary_q4: $("#san_q4").value==="Yes"?1:($("#san_q4").value==="No"?0:null),
    totals_json: totals
  };
  let res;
  if(currentId){
    res = await fetch(`/api/loadmaps/${currentId}`, {method:"PUT", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  } else {
    res = await fetch(`/api/loadmaps`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
  }
  if(res.ok){
    await fetchList();
    closeEditor();
  } else {
    alert("Save failed");
  }
}

function del(){
  if(!currentId){ closeEditor(); return; }
  if(!confirm("Delete this load map?")) return;
  fetch(`/api/loadmaps/${currentId}`, {method:"DELETE"})
    .then(r=>{
      if(r.ok){ fetchList(); closeEditor(); }
      else alert("Delete failed");
    });
}

function editPallet(pos){
  const p = pallets[pos-1];
  $("#modalPos").textContent = `#${pos}`;
  $("#p_store").value = p.store || "";
  $("#p_type").value = p.type || "";
  $("#p_zone").value = p.zone || "";
  $("#p_bulk").checked = bulkheads.includes(pos);
  $("#palletModal").classList.remove("hidden");
  $("#p_save").onclick = ()=>{
    p.store = $("#p_store").value.trim();
    p.type = $("#p_type").value;
    p.zone = $("#p_zone").value;
    const idx = bulkheads.indexOf(pos);
    const mark = $("#p_bulk").checked;
    if(mark && idx===-1) bulkheads.push(pos);
    if(!mark && idx!==-1) bulkheads.splice(idx,1);
    renderGrid();
    recomputeTotals();
    $("#palletModal").classList.add("hidden");
  };
  $("#p_clear").onclick = ()=>{
    p.store = ""; p.type = ""; p.zone = "";
    const idx = bulkheads.indexOf(pos);
    if(idx!==-1) bulkheads.splice(idx,1);
    renderGrid();
    recomputeTotals();
    $("#palletModal").classList.add("hidden");
  };
  $("#p_close").onclick = ()=> $("#palletModal").classList.add("hidden");
}

$("#newMapBtn").onclick = ()=> openEditor(null);
$("#cancelBtn").onclick = ()=> closeEditor();
$("#saveBtn").onclick = ()=> save();
$("#deleteBtn").onclick = ()=> del();
$("#searchBtn").onclick = ()=> fetchList($("#search").value.trim());
// Print helper: scale content to fit one PDF page when possible
function computePrintScaleAndWrap(){
  // Ensure we have a wrapper around the main content we want to print
  let wrapper = document.querySelector('.print-scale-wrapper');
  const container = document.querySelector('main.container');
  if(!container) return 1;
  if(!wrapper){
    wrapper = document.createElement('div');
    wrapper.className = 'print-scale-wrapper';
    // move the container into the wrapper
    container.parentNode.insertBefore(wrapper, container);
    wrapper.appendChild(container);
  }

  // Try to compute a scale so the wrapper fits roughly on one A4/Letter page.
  // We'll use an approximate printable page size in px at 96dpi.
  const DPI = 76;
  // A4 size in inches: 8.27 x 11.69 (landscape or portrait) - use portrait height
  const pageWidthIn = 8.5;
  const pageHeightIn = 11;
  const pageWidthPx = pageWidthIn * DPI;
  const pageHeightPx = pageHeightIn * DPI;

  // measure wrapper content size
  // temporarily reset transform to measure natural size
  wrapper.style.transform = '';
  wrapper.style.width = '';
  const rect = wrapper.getBoundingClientRect();
  const contentW = rect.width;
  const contentH = rect.height;

  // compute scale to fit within pageWidthPx x pageHeightPx
  const scaleW = pageWidthPx / contentW;
  const scaleH = pageHeightPx / contentH;
  // choose smaller scale (fit both width and height)
  const scale = Math.min(1, Math.min(scaleW, scaleH));

  // Store scale as CSS variable used by print styles
  wrapper.style.setProperty('--print-scale', String(scale));
  return scale;
}

async function printSinglePage(){
  const wrapper = document.querySelector('.print-scale-wrapper') || document.querySelector('main.container');
  if(!wrapper) { window.print(); return; }

  // compute scale and set inline style so @media print uses it
  const scale = computePrintScaleAndWrap();

  // Wait a tick to allow layout to update
  await new Promise(r=>setTimeout(r, 50));

  // Print, then clean up scale (in case user returns to UI)
  window.print();

  // after print dialog closes (no reliable event), remove inline scale after short delay
  setTimeout(()=>{
    const w = document.querySelector('.print-scale-wrapper');
    if(w){ w.style.removeProperty('--print-scale'); }
  }, 1000);
}

$("#printBtn").onclick = ()=> printSinglePage();

// Init
fetchList();

