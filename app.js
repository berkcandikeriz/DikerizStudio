"use strict";
const $=s=>document.querySelector(s);
const TOKEN=document.querySelector('meta[name="dz-token"]').content;
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const STEPS=[["shrink","küçült","kaynağı hafif kopyaya çevirir"],["analyze","analiz","yazıya döker, anları bulur"],["render","dikey çıkar","9:16 video + yazılar"]];
let state={}, clipsSig="", dirty=false, cfg={};
const api=(p,b)=>fetch(p,b===undefined?{headers:{"X-Token":TOKEN}}:{method:"POST",headers:{"Content-Type":"application/json","X-Token":TOKEN},body:JSON.stringify(b)}).then(r=>r.json());
const fmt=t=>{t=+t;const m=Math.floor(t/60),s=(t-m*60);return m+":"+(s<10?"0":"")+s.toFixed(1)};
const parseT=v=>{v=String(v).trim().replace(",",".");if(v.includes(":")){const[a,b]=v.split(":");return (+a)*60+(+b)}return +v};

$("#steps").innerHTML=STEPS.map(([k,n,d])=>`<div class="step" id="st_${k}">
  <div class="nm">${n}<small>${d}</small></div><div class="chip">bekliyor</div>
  <div class="bar"><i></i></div><div class="p">0%</div>
  <div><button data-run="${k}">yalnız bunu</button></div><div class="m"></div></div>`).join("");
document.querySelectorAll("[data-run]").forEach(b=>b.onclick=()=>run([b.dataset.run]));

const INFO={
 out_root:{t:"sürüklenen videoların çalışma klasörü",
  d:"Sürükle-bırak ile verdiğin videolar bu klasörde, her video için ayrı bir alt klasörde işlenir. Video önce buraya kopyalanır, küçültme bitince kopya silinir; hafif sürüm, transkript ve dikey klipler burada kalır.",
  ex:"Klasör <code>C:\\Users\\Ad\\Videos\\DikerizStudio</code> ise <code>Benim Videom.mp4</code> bırakıldığında klipler <code>…\\DikerizStudio\\Benim Videom\\dikey_01.mp4</code> olarak kaydedilir.",
  tip:"Alana <b>tıklayıp</b> seçtiğin videolarda bu klasör kullanılmaz; çıktılar videonun yanındaki <code>Dikey_&lt;ad&gt;</code> klasörüne yazılır."},
 n_clips:{t:"klip sayısı",
  d:"Analizden sonra otomatik olarak işaretli gelecek klip sayısı. Program bunun iki katı kadar aday önerir, en yüksek puanlıları seçili getirir.",
  ex:"<code>4</code> yazarsan 8 aday listelenir, en iyi 4'ü işaretli gelir. İşaretleri aday tablosundan istediğin gibi değiştirebilirsin.",
  tip:"Önerilen: <b>3–5</b>. Çok yüksek değer, zayıf anların da seçilmesine yol açar."},
 min_len:{t:"en kısa klip (sn)",
  d:"Bir aday anın olabileceği en kısa süre. Program cümleleri bölmeden, cümle başında başlayıp cümle sonunda biten parçalar arar; bu süreden kısa parçaları önermez.",
  ex:"<code>20</code> → 12 saniyelik tek cümlelik bir an önerilmez. <code>10</code> yaparsan kısa, vurucu cümleler de aday olur.",
  tip:"Önerilen: <b>15–20 sn</b>."},
 max_len:{t:"en uzun klip (sn)",
  d:"Bir aday anın olabileceği en uzun süre. Platform sınırlarını ve izleyicinin dikkat süresini düşünerek belirle.",
  ex:"<code>60</code> → Shorts sınırının altında kalır. <code>45</code> yaparsan daha tempolu klipler önerilir.",
  tip:"Önerilen: Shorts / Reels için <b>45–60 sn</b>, TikTok için 90'a kadar."},
 shrink_h:{t:"küçültme yüksekliği",
  d:"Kaynağın hafif kopyasının yüksekliği. Analiz ve dikey çıktı bu kopyadan üretilir; kaynak bundan küçükse büyütülmez.",
  ex:"4K (2160p) kaynak + <code>1080</code> → 1920×1080 kopya; dikey videodaki kart keskin görünür. <code>720</code> → daha hızlı ve küçük, ama kart biraz yumuşar.",
  tip:"Önerilen: <b>1080</b>."},
 shrink_crf:{t:"küçültme kalitesi (CRF)",
  d:"Hafif kopyanın sıkıştırma oranı. Değer düştükçe kalite ve dosya boyutu artar, yükseldikçe ikisi de azalır. Dikey çıktı bu kopyadan üretildiği için çok yüksek değer çıktıyı da etkiler.",
  ex:"<code>18</code> neredeyse kayıpsız ve büyük · <code>26</code> dengeli · <code>32</code> küçük ama bloklanma görülebilir. Testte 483 MB'lık bir video CRF 26 ile 172 MB oldu (oran videoya göre değişir).",
  tip:"Önerilen: <b>23–26</b>."},
 model:{t:"konuşma modeli",
  d:"Konuşmayı yazıya döken Whisper modeli. İlk kullanımda bir kez indirilir. Büyük model daha isabetli, küçük model daha hızlıdır.",
  ex:"<code>large-v3-turbo</code> Türkçede en iyi denge (6–7 dakikalık bir video bu bilgisayarda yaklaşık 1,5 dakikada çözüldü) · <code>medium</code> daha yavaş ve daha az isabetli · <code>small</code> en hızlı, özel isimlerde daha çok hata yapar.",
  tip:"Önerilen: <b>large-v3-turbo</b>."},
 skip_head:{t:"baştan atla (sn, intro)",
  d:"Videonun başındaki bu kadar saniye, aday an aranırken dikkate alınmaz. Intro, kolaj ya da jenerik varsa kliplere girmesini engeller.",
  ex:"Videon 40 saniyelik bir intro kolajıyla başlıyorsa <code>40</code> yaz; ilk aday en erken 0:40'tan başlar.",
  tip:"Intro yoksa <b>0</b> bırak."},
 handle:{t:"alttaki imza",
  d:"Dikey videonun en altına yazılan kullanıcı adı. Program adını da buradan tanır ve altyazıdaki yanlış yazımları otomatik düzeltir.",
  ex:"<code>@berkcandikeriz</code> → altta “@berkcandikeriz” yazar; ad “Berk Can Dikeriz” olarak tanınır, transkriptteki “Berkçen” → “Berk Can” olur.",
  tip:"Boş bırakırsan imza yazılmaz ve isim düzeltmesi yapılmaz."},
 lang:{t:"konuşma dili",
  d:"Videoda konuşulan dil. Model bu dile göre çözer; yanlış seçilirse transkript ve altyazı bozuk çıkar.",
  ex:"Türkçe anlatımlı bir video için <code>Türkçe</code>. İngilizce bir röportaj için <code>English</code>.",
  tip:"Ayarı değiştirdikten sonra analizi yeniden çalıştır."},
 font:{t:"yazı tipi",
  d:"Dikey videodaki başlık, altyazı ve imzanın yazı tipi. Listede her font kendi yazısıyla görünür. “+ yeni font ekle” ile bilgisayarındaki bir .ttf ya da .otf dosyasını ekleyebilirsin.",
  ex:"<code>Montserrat-SemiBold.ttf</code> ve <code>Montserrat-Light.ttf</code> eklersen listede tek bir “Montserrat” görünür; başlık ve altyazı SemiBold, imza Light ile yazılır. Tek dosya eklersen her yerde o kullanılır.",
  tip:"Fontta <b>ğ, ş, ı, İ</b> gibi Türkçe harfler yoksa eklerken uyarı çıkar; bu harfler videoda kutucuk olarak görünür. Ticari fontların lisansına dikkat et."},
 c_bg:{t:"zemin rengi",d:"Dikey videonun arka plan rengi; başlık, video kartı ve altyazı bu zeminin üzerinde durur.",
  ex:"Varsayılan krem <code>#F6F4EF</code>. Koyu tema için <code>#1A1A1A</code> seçip yazı rengini açık yap.",mini:"bg"},
 c_ink:{t:"yazı rengi",d:"Başlığın ve altyazının normal (vurgusuz) kelimelerinin rengi.",
  ex:"Varsayılan <code>#1A1A1A</code>. Zemin koyuysa <code>#F6F4EF</code> gibi açık bir renk seç.",mini:"ink"},
 c_acc:{t:"vurgu rengi",d:"Başlıkta <code>*yıldız*</code> içine aldığın kelimeler, altyazıda o an söylenen kelime ve alttaki ilerleme çubuğu bu renkte olur.",
  ex:"Varsayılan turuncu <code>#EF9230</code>. Başlık “vazgeçme, sadece *bir yerden başla*” ise “bir yerden başla” bu renkte yazar.",mini:"acc"},
 c_gray:{t:"imza rengi",d:"Videonun en altındaki imzanın rengi. Göze batmaması için zemine yakın, soluk bir ton önerilir.",
  ex:"Varsayılan gri <code>#5E5B55</code>.",mini:"gray"},
};
function miniPreview(which){
  const g=k=>(cfg[k]||"#000");
  const hl=k=>which===k?" hl":"";
  return `<div class="mini"><div class="ph${hl("bg")}" style="background:${g("c_bg")}">
   <div class="t${hl("ink")}" style="color:${g("c_ink")}">başlık <span class="${hl("acc").trim()}" style="color:${g("c_acc")}">vurgu</span></div>
   <div class="v"></div>
   <div class="c${hl("ink")}" style="color:${g("c_ink")}">alt <span class="${hl("acc").trim()}" style="color:${g("c_acc")}">yazı</span></div>
   <div class="h${hl("gray")}" style="color:${g("c_gray")}">@kullaniciadi</div>
   <div class="p${hl("acc")}" style="background:${g("c_acc")}"></div></div>
   <div class="muted">Mavi kesik çizgi, bu rengin kullanıldığı yeri gösterir. Renkler senin şu anki ayarlarınla çizildi.</div></div>`;
}
const dlg=$("#infoDlg");
function openInfo(k){const it=INFO[k];if(!it)return;
  $("#infoTitle").textContent=it.t;
  $("#infoBody").innerHTML=`<p>${it.d}</p><div class="m-ex"><b>örnek</b>${it.ex}</div>`+(it.tip?`<div class="m-tip">${it.tip}</div>`:"")+(it.mini?miniPreview(it.mini):"");
  dlg.showModal();$("#infoClose").focus();}
$("#infoClose").addEventListener("click",()=>dlg.close());
dlg.addEventListener("click",e=>{if(e.target===dlg)dlg.close()});
document.querySelectorAll(".grid label").forEach(lb=>{
  const ctl=lb.querySelector(".cfg");if(!ctl)return;const k=ctl.id.slice(2);if(!INFO[k])return;
  const tn=[...lb.childNodes].find(n=>n.nodeType===3&&n.textContent.trim());if(!tn)return;
  const sp=document.createElement("span");sp.className="lt";sp.textContent=tn.textContent.trim();
  const b=document.createElement("button");b.type="button";b.className="info";b.textContent="i";b.setAttribute("aria-label",it_label(k));
  b.addEventListener("click",e=>{e.preventDefault();e.stopPropagation();openInfo(k)});
  sp.appendChild(b);lb.replaceChild(sp,tn);});
function it_label(k){return INFO[k].t+" hakkında bilgi"}
document.querySelectorAll(".info[data-k]").forEach(b=>b.addEventListener("click",e=>{e.preventDefault();openInfo(b.dataset.k)}));

const FEXT=[".ttf",".otf"];
let fonts=[];const loadedFaces=new Set();
const fontList=$("#fontList"),fontAddPop=$("#fontAddPop"),fontBtn=$("#fontBtn"),fontAddBtn=$("#fontAddBtn");
const faceName=f=>"dzf-"+f.id.replace(/[^a-z0-9]/gi,"_");
async function ensureFace(f){const n=faceName(f);if(loadedFaces.has(n))return n;loadedFaces.add(n);
  try{const ff=new FontFace(n,`url(${f.url})`);await ff.load();document.fonts.add(ff)}catch(_){}return n}
async function loadFonts(){fonts=await api("/api/fonts");for(const f of fonts)ensureFace(f);drawFontCur();if(!fontList.hidden)drawFontList()}
function curFont(){return fonts.find(f=>f.id===cfg.font)||fonts[0]}
function drawFontCur(){const f=curFont();if(!f)return;$("#fontCur").textContent=f.family;$("#fontCur").style.fontFamily=`"${faceName(f)}",Poppins`}
function drawFontList(){
  fontList.innerHTML=fonts.map(f=>`<div class="fopt${f.id===(curFont()||{}).id?" sel":""}" role="option" tabindex="0" data-id="${esc(f.id)}">
    <span class="ck">${f.id===(curFont()||{}).id?"✓":""}</span>
    <div class="fx"><div class="fn">${esc(f.family)}${f.user?"":" · varsayılan"}</div>
    <div class="fs" style="font-family:'${faceName(f)}',Poppins">deneyimle <b>öğren</b>, tecrübeyle <b>anlat</b></div></div>
    ${f.user?`<button type="button" class="del" data-del="${esc(f.id)}" title="Fontu kaldır" aria-label="${esc(f.family)} fontunu kaldır">×</button>`:""}</div>`).join("");
  fontList.querySelectorAll(".fopt").forEach(o=>{
    const pick=async()=>{cfg=await api("/api/config",{font:o.dataset.id});drawFontCur();closePops()};
    o.addEventListener("click",e=>{if(!e.target.closest(".del"))pick()});
    o.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();pick()}});});
  fontList.querySelectorAll("[data-del]").forEach(b=>b.addEventListener("click",async e=>{e.stopPropagation();
    const f=fonts.find(x=>x.id===b.dataset.del);if(!f||!confirm(`“${f.family}” fontu kaldırılsın mı?`))return;
    const r=await api("/api/font/delete",{id:f.id});if(r.error)return alert(r.error);cfg.font=r.font;await loadFonts();}));
}
function closePops(){[fontList,fontAddPop].forEach(p=>p.hidden=true);fontBtn.setAttribute("aria-expanded","false");fontAddBtn.setAttribute("aria-expanded","false")}
function togglePop(pop,btn){const open=pop.hidden;closePops();if(open){pop.hidden=false;btn.setAttribute("aria-expanded","true");if(pop===fontList)drawFontList()}}
fontBtn.addEventListener("click",e=>{e.stopPropagation();togglePop(fontList,fontBtn)});
fontAddBtn.addEventListener("click",e=>{e.stopPropagation();$("#fontMsg").textContent="";togglePop(fontAddPop,fontAddBtn)});
[fontList,fontAddPop].forEach(p=>p.addEventListener("click",e=>e.stopPropagation()));
document.addEventListener("click",closePops);
document.addEventListener("keydown",e=>{if(e.key==="Escape")closePops()});
const fontDrop=$("#fontDrop"),fontIn=$("#fontIn");
fontDrop.addEventListener("click",()=>fontIn.click());
fontDrop.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();fontIn.click()}});
["dragenter","dragover"].forEach(ev=>fontDrop.addEventListener(ev,()=>fontDrop.classList.add("over")));
["dragleave","drop"].forEach(ev=>fontDrop.addEventListener(ev,()=>fontDrop.classList.remove("over")));
fontIn.addEventListener("change",()=>{addFonts([...fontIn.files]);fontIn.value=""});
async function addFonts(files){
  const msg=$("#fontMsg");fontAddPop.hidden=false;fontAddBtn.setAttribute("aria-expanded","true");
  const lines=[];let lastId="";
  const show=extra=>{msg.className="fmsg";msg.innerHTML=lines.concat(extra?[`<span>${extra}</span>`]:[]).join("<br>")};
  const add=(cls,html)=>lines.push(`<span class="${cls}">${html}</span>`);
  for(const f of files){
    if(!FEXT.some(x=>f.name.toLowerCase().endsWith(x))){add("err","✕ "+esc(f.name)+": yalnızca .ttf / .otf");continue}
    show(esc(f.name)+" ekleniyor…");
    const r=await fetch("/api/font?name="+encodeURIComponent(f.name),{method:"PUT",headers:{"X-Token":TOKEN,"Content-Type":"application/octet-stream"},body:f}).then(x=>x.json()).catch(()=>({error:"Bağlantı hatası"}));
    if(r.error){add("err","✕ "+esc(f.name)+": "+esc(r.error));continue}
    if(r.turkish){lastId=r.id;add("ok","✓ "+esc(r.family+" "+r.style)+" eklendi")}
    else add("warn","⚠ "+esc(r.family+" "+r.style)+" eklendi — Türkçe harfler (ğ, ş, ı…) eksik, videoda kutucuk görünebilir");
  }
  if(lastId){cfg=await api("/api/config",{font:lastId});add("ok","Seçili font: "+esc((fonts.find(f=>f.id===lastId)||{}).family||""))}
  await loadFonts();if(lastId)lines[lines.length-1]=`<span class="ok">Seçili font: ${esc(curFont().family)}</span>`;
  show();
}


async function loadCfg(){cfg=await api("/api/config");
  document.querySelectorAll(".cfg").forEach(el=>{const k=el.id.slice(2);if(cfg[k]!==undefined)el.value=cfg[k]});}
document.querySelectorAll(".cfg").forEach(el=>el.onchange=async()=>{
  const k=el.id.slice(2);let v=el.value;if(el.type==="number"||k==="shrink_h")v=+v;
  cfg=await api("/api/config",{[k]:v});});

const VEXT=[".mp4",".mov",".mkv",".m4v"];
const drop=$("#drop"), fileIn=$("#fileIn");
let uploading=false;
const busy=()=>uploading||state.running||state.uploading;
function dzText(main,sub){$("#dzMain").innerHTML=main;$("#dzSub").textContent=sub||""}
function dzReset(){dzText('videoyu buraya <b>sürükle-bırak</b>','ya da tıklayıp seç · mp4, mov, mkv, m4v');$("#upBar").hidden=true;drop.classList.remove("busy")}
["dragenter","dragover"].forEach(ev=>window.addEventListener(ev,e=>{e.preventDefault();if(!busy())document.body.classList.add("dragging")}));
["dragleave","drop"].forEach(ev=>window.addEventListener(ev,e=>{e.preventDefault();if(ev==="drop"||!e.relatedTarget)document.body.classList.remove("dragging")}));
window.addEventListener("drop",e=>{const fs=e.dataTransfer&&e.dataTransfer.files;if(!fs||!fs.length)return;
  const all=[...fs];const fontsDropped=all.filter(f=>[".ttf",".otf"].some(x=>f.name.toLowerCase().endsWith(x)));
  if(fontsDropped.length){const st=document.querySelector("details");if(st)st.open=true;addFonts(fontsDropped);return}
  takeFile(all[0],all.length)});
drop.addEventListener("click",pickFile);
drop.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();pickFile()}});
fileIn.addEventListener("change",()=>{if(fileIn.files.length)takeFile(fileIn.files[0],1);fileIn.value=""});
async function pickFile(){
  if(busy())return;
  const r=await api("/api/browse",{});
  if(r.error)return alert(r.error);
  if(r.unsupported)return fileIn.click();
  if(r.path){const o=await api("/api/open",{video:r.path});if(o.error)alert(o.error);clipsSig="";dirty=false;poll()}
}
async function takeFile(f,count){
  if(busy())return alert("Bir işlem sürüyor, bitmesini bekle.");
  if(count>1)alert("Birden fazla dosya bırakıldı, yalnızca ilki alınacak: "+f.name);
  if(!VEXT.some(x=>f.name.toLowerCase().endsWith(x)))return alert("Desteklenmeyen dosya türü: "+f.name);
  const pr=await api("/api/prepare",{name:f.name,size:f.size});
  if(pr.error)return alert(pr.error);
  clipsSig="";dirty=false;
  if(pr.reuse){poll();return}
  uploading=true;drop.classList.add("busy");$("#upBar").hidden=false;
  dzText("<b>"+esc(f.name)+"</b> alınıyor…","0%");
  await new Promise(res=>{
    const x=new XMLHttpRequest();
    x.open("PUT","/api/upload?id="+encodeURIComponent(pr.id));
    x.setRequestHeader("X-Token",TOKEN);x.setRequestHeader("Content-Type","application/octet-stream");
    x.upload.onprogress=e=>{if(e.lengthComputable){const p=Math.round(e.loaded/e.total*100);
      $("#upBar i").style.width=p+"%";$("#dzSub").textContent=p+"% · "+(e.loaded/1e6).toFixed(0)+" / "+(e.total/1e6).toFixed(0)+" MB"}};
    x.onload=()=>{if(x.status!==200){let m="Yükleme başarısız";try{m=JSON.parse(x.responseText).error||m}catch(_){}alert(m)}res()};
    x.onerror=()=>{alert("Yükleme sırasında bağlantı kesildi");res()};
    x.send(f);
  });
  uploading=false;dzReset();poll();
}

async function run(steps){
  if(steps.includes("render")&&!(state.clips||[]).some(c=>c.use)&&!steps.includes("analyze")){alert("Önce analiz yap ya da en az bir klip seç.");return}
  const r=await api("/api/run",{steps,clips:collectClips()});if(r.error)alert(r.error);poll();}
$("#btnAll").onclick=()=>run($("#pause").checked?["shrink","analyze"]:["shrink","analyze","render"]);
$("#btnStop").onclick=()=>api("/api/stop",{});
$("#btnFolder").onclick=()=>api("/api/folder",{});
$("#btnQuit").onclick=async()=>{if(confirm("Dikeriz Studio kapatılsın mı?")){await api("/api/quit",{});document.body.innerHTML='<div class="wrap"><h1>dikeriz <b>studio</b> kapatıldı</h1><p class="muted">Tekrar açmak için DikerizStudio.bat dosyasına çift tıkla.</p></div>'}};
$("#btnAdd").onclick=()=>{const cs=collectClips();const id=String(cs.length+1).padStart(2,"0");
  cs.push({id,use:true,start:0,end:30,score:0,baslik:"yeni *başlık*",metin:""});saveClips(cs,true)};

function collectClips(){return [...document.querySelectorAll("#clipsBox tr[data-i]")].map(tr=>{
  const c={...(state.clips||[])[+tr.dataset.i]};
  c.use=tr.querySelector(".use").checked;c.start=parseT(tr.querySelector(".ts").value);c.end=parseT(tr.querySelector(".te").value);
  c.baslik=tr.querySelector(".title").value;return c;});}
let saveT;function saveClips(cs,rerender){state.clips=cs;dirty=false;
  api("/api/clips",{clips:cs});if(rerender){clipsSig="";drawClips(cs)}}
function drawClips(cs){
  if(!cs||!cs.length){$("#clipsBox").innerHTML='<div class="empty">Analizden sonra burada öne çıkan anlar listelenecek.</div>';$("#clipInfo").textContent="";return}
  $("#clipInfo").textContent=`· ${cs.filter(c=>c.use).length}/${cs.length} seçili`;
  $("#clipsBox").innerHTML=`<table><tr><th></th><th>#</th><th>başla</th><th>bitir</th><th>süre</th><th>puan</th><th style="width:38%">başlık</th><th>konuşma</th></tr>`+
  cs.map((c,i)=>`<tr data-i="${i}" class="${c.use?"":"off"}"><td><input type="checkbox" class="use" ${c.use?"checked":""}></td><td>${esc(c.id)}</td>
  <td><input class="t ts" value="${fmt(c.start)}"></td><td><input class="t te" value="${fmt(c.end)}"></td>
  <td class="score dur">${Math.round(c.end-c.start)} sn</td><td class="score">${(+c.score||0).toFixed(1)}</td>
  <td><input class="title" value="${esc(c.baslik)}"></td><td><div class="txt">${esc(c.metin)}</div></td></tr>`).join("")+"</table>";
  $("#clipsBox").querySelectorAll("input").forEach(el=>{el.oninput=()=>{dirty=true;clearTimeout(saveT);saveT=setTimeout(()=>{const cs=collectClips();saveClips(cs,false);
     document.querySelectorAll("#clipsBox tr[data-i]").forEach((tr,i)=>{tr.className=cs[i].use?"":"off";tr.querySelector(".dur").textContent=Math.round(cs[i].end-cs[i].start)+" sn"});
     $("#clipInfo").textContent=`· ${cs.filter(c=>c.use).length}/${cs.length} seçili`;clipsSig=JSON.stringify(cs)},500)};el.onchange=el.oninput});
  $("#clipsBox").querySelectorAll(".txt").forEach(el=>el.onclick=()=>el.classList.toggle("open"));
}
function drawOuts(outs){
  const box=$("#outs");const sig=outs.join("|");if(box.dataset.sig===sig)return;box.dataset.sig=sig;
  box.innerHTML=outs.length?outs.map(p=>{const n=p.split(/[\\/]/).pop();return `<div class="out"><video src="/media?p=${encodeURIComponent(p)}&t=${TOKEN}&v=${Date.now()}#t=0.6" controls preload="metadata"></video><div>${esc(n)}</div></div>`}).join(""):'<div class="empty">Henüz çıktı yok.</div>';
}
async function poll(){
  try{state=await api("/api/state")}catch(e){$("#status").textContent="Sunucuya ulaşılamıyor";return}
  $("#curVideo").textContent=state.video?("Proje: "+state.name+(state.upload?"":"  ("+state.video+")")+"   →   çıktı klasörü: "+state.wd):"Henüz proje açılmadı.";
  if(!uploading){drop.classList.toggle("busy",!!(state.running||state.uploading));
    if(state.video&&!state.running)dzText('<b>'+esc(state.name)+'</b> açık','başka bir video için sürükle-bırak ya da tıkla');
    else if(!state.video)dzReset();}
  const ov=Math.round(state.overall*100);$("#ovBar i").style.width=ov+"%";$("#ovPct").textContent=ov+"%";
  $("#ovBar").classList.toggle("run",state.running);
  for(const [k] of STEPS){const s=state.steps[k],el=$("#st_"+k);
    el.querySelector(".chip").textContent=s.state;el.querySelector(".chip").className="chip "+s.state;
    el.querySelector(".bar i").style.width=Math.round(s.pct*100)+"%";el.querySelector(".bar").classList.toggle("run",s.state==="çalışıyor");
    el.querySelector(".p").textContent=Math.round(s.pct*100)+"%";el.querySelector(".m").textContent=s.msg||"";
    el.querySelector("button").disabled=state.running||state.uploading||uploading||!state.video;}
  $("#btnAll").disabled=state.running||!state.video;$("#btnStop").disabled=!state.running;
  $("#status").textContent=state.msg;$("#status").className=state.error?"err":"";
  const sig=JSON.stringify(state.clips);
  if(sig!==clipsSig&&!dirty&&!document.activeElement.closest("#clipsBox")){clipsSig=sig;drawClips(state.clips)}
  drawOuts(state.outputs||[]);
  const lg=$("#log"),atEnd=lg.scrollTop+lg.clientHeight>=lg.scrollHeight-20;lg.textContent=(state.log||[]).join("\n");if(atEnd)lg.scrollTop=lg.scrollHeight;
}
(async()=>{await loadCfg();await loadFonts();await poll();setInterval(poll,800)})();
