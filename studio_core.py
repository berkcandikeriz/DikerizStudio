import os, re, json, shutil, subprocess, time, wave, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
USER_FONTS = os.path.join(FONTS, "user")
FONT_EXT = (".ttf", ".otf")


def _font_name(path):
    from PIL import ImageFont
    fam, style = ImageFont.truetype(path, 40).getname()
    return (fam or os.path.splitext(os.path.basename(path))[0]).strip(), (style or "Regular").strip()


def _pick(items, prefs):
    plain = [x for x in items if "italic" not in x[0].lower() and "oblique" not in x[0].lower()] or items
    for pr in prefs:
        for st, p in plain:
            if st.lower().replace(" ", "").replace("-", "") == pr:
                return p
    return plain[0][1]


def list_fonts():
    out = [{"id": "poppins", "family": "Poppins", "user": False,
            "title": os.path.join(FONTS, "Poppins-Medium.ttf"), "handle": os.path.join(FONTS, "Poppins-Light.ttf"),
            "files": ["Poppins-Medium.ttf", "Poppins-Light.ttf"]}]
    groups = {}
    if os.path.isdir(USER_FONTS):
        for fn in sorted(os.listdir(USER_FONTS)):
            p = os.path.join(USER_FONTS, fn)
            if not fn.lower().endswith(FONT_EXT) or not os.path.isfile(p):
                continue
            try:
                fam, style = _font_name(p)
            except Exception:
                continue
            groups.setdefault(fam, []).append((style, p))
    for fam, items in sorted(groups.items(), key=lambda x: x[0].lower()):
        out.append({"id": "u:" + re.sub(r"[^0-9a-z]+", "-", ascii_tr(fam)).strip("-")[:60], "family": fam, "user": True,
                    "title": _pick(items, ["medium", "semibold", "demibold", "bold", "regular", "book", "normal", "roman"]),
                    "handle": _pick(items, ["light", "extralight", "regular", "book", "normal", "roman"]),
                    "files": [os.path.basename(p) for _, p in items]})
    return out


def font_files(font_id):
    fs = list_fonts()
    f = next((x for x in fs if x["id"] == font_id), fs[0])
    return f["title"], f["handle"]


def font_has_turkish(path):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(path, 48)

    def draw(ch):
        im = Image.new("L", (96, 96), 0)
        ImageDraw.Draw(im).text((20, 10), ch, font=f, fill=255)
        return im.tobytes()
    missing = draw("\U0010FFFD")
    return all(draw(ch) != missing for ch in "ğĞşŞıİ")


def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def trl(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def safe_id(v, n=1):
    v = re.sub(r"[^0-9A-Za-z_-]", "", str(v or ""))[:16]
    return v or f"{int(n):02d}"


def hex2rgb(h, default):
    try:
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else default
    except (ValueError, AttributeError):
        return default


def work_dir_for(video):
    stem = os.path.splitext(os.path.basename(video))[0]
    d = os.path.join(os.path.dirname(os.path.abspath(video)), "Dikey_" + stem)
    os.makedirs(d, exist_ok=True)
    return d


def probe(video):
    import cv2
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {"fps": fps, "frames": n, "w": w, "h": h, "dur": n / fps if fps else 0}


def _hidden():
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"startupinfo": si, "creationflags": 0x08000000}
    return {}


def run_ffmpeg(args, dur, progress, msg, stop=None):
    ff = find_ffmpeg()
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1"] + args
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace", **_hidden())
    for line in p.stdout:
        if stop and stop():
            p.kill()
            raise RuntimeError("Durduruldu")
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                us = int(line.split("=")[1])
                if dur:
                    progress(min(us / 1e6 / dur, 1.0), msg)
            except ValueError:
                pass
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg hatasi: " + err[-500:])


def step_shrink(video, wd, settings, progress, stop=None):
    out = os.path.join(wd, "kucuk.mp4")
    if not os.path.exists(video):
        if os.path.exists(out):
            progress(1.0, "Küçük kopya hazır, atlandı")
            return out
        raise RuntimeError("Kaynak video bulunamadı")
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(video) and os.path.getsize(out) > 1000:
        progress(1.0, "Küçük kopya zaten var, atlandı")
        return out
    info = probe(video)
    hgt = int(settings.get("shrink_h", 1080))
    crf = int(settings.get("shrink_crf", 26))
    tmp = out + ".tmp.mp4"
    run_ffmpeg(["-i", video, "-vf", f"scale=-2:'min({hgt},ih)'", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", str(crf), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", tmp],
               info["dur"], progress, "Video küçültülüyor", stop)
    os.replace(tmp, out)
    a, b = os.path.getsize(video), os.path.getsize(out)
    progress(1.0, f"Küçültüldü: {a/1e6:.0f} MB → {b/1e6:.0f} MB")
    return out


_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")

def ascii_tr(s):
    return s.translate(_TR).lower()

_NAMES = """Ahmet Mehmet Mustafa Ali Hüseyin Hasan İbrahim İsmail Osman Yusuf Murat Ömer Ramazan Halil Süleyman
Abdullah Mahmut Recep Salih Fatih Kadir Emre Hakan Adem Kemal Yaşar Bekir Musa Metin Serkan Erkan Orhan Burak
Volkan Gökhan Uğur Onur Emin Cem Can Berk Arda Ege Kaan Mert Efe Kerem Eren Deniz Umut Barış Tolga Tuncay Sinan
Serdar Selim Levent Tamer Tuna Kaya Alp Alper Batuhan Berkay Cenk Doruk Emir Enes Furkan Gökay Hamza Harun
İlker İlhan Kağan Koray Kutay Oğuz Oğuzhan Ozan Polat Rıza Sarp Semih Sercan Taylan Tarık Ufuk Yiğit Yunus
Yusuf Zafer Erdem Erdal Ercan Ersin Ertan Engin Egemen Baran Bora Bulut Çağan Çağrı Çağlar Doğan Doğa Görkem
Hakkı Hayri İlkay Kaan Kayra Kuzey Mete Necati Nihat Okan Onat Rüzgar Selçuk Şahin Şükrü Talha Tayfun Toprak
Utku Volkan Yasin Yavuz Yücel Zeki Ayşe Fatma Emine Hatice Zeynep Elif Meryem Şerife Zehra Sultan Hanife
Merve Özlem Esra Büşra Seda Ebru Derya Gamze Gizem Tuğba Burcu Pınar Aslı Aylin Ceren Cansu Damla Didem Duygu
Ece Eda Ezgi Gül Gülşen İrem Melek Melis Nur Selin Sena Sevgi Sibel Simge Şule Tuba Yağmur Yeliz Zerrin Ayça
Begüm Beril Dilara Ela Esin Feyza Hande İpek Lale Nazlı Nehir Neslihan Oya Rana Sude Su Tülay Yasemin Yonca
Ada Ahsen Azra Beren Defne Ecrin Eylül Hira Mira Nisa Öykü Rabia Sare Serra Zümra Aras Çınar Atlas Poyraz""".split()
NAMES = {}
for n in _NAMES:
    NAMES.setdefault(ascii_tr(n), n)


def _cap(s):
    return s[:1].upper() + s[1:]


def name_from_handle(handle):
    h = re.sub(r"[^a-z]", "", ascii_tr(handle or ""))
    if len(h) < 4:
        return ""
    best = None

    def rec(rest, parts):
        nonlocal best
        if len(parts) >= 1 and len(rest) >= 3:
            cand = parts + [_cap(rest)]
            if best is None or len(cand) > len(best):
                best = cand
        if len(parts) >= 3:
            return
        for L in range(2, min(len(rest), 10) + 1):
            if rest[:L] in NAMES:
                if L == len(rest):
                    cand = parts + [NAMES[rest]]
                    if best is None or len(cand) > len(best):
                        best = cand
                else:
                    rec(rest[L:], parts + [NAMES[rest[:L]]])
    rec(h, [])
    return " ".join(best) if best else ""


def _norm_word(w):
    return re.sub(r"[^a-z]", "", ascii_tr(w))


def fix_names(segs, full_name, log=print):
    if not full_name:
        return 0
    parts = full_name.split()
    first = parts[:-1] or parts
    targets = []
    targets.append(("".join(_norm_word(p) for p in parts), parts))
    if len(parts) > 1:
        targets.append(("".join(_norm_word(p) for p in first), first))
    changes = 0
    for s in segs:
        ws = s.get("words") or []
        i = 0
        while i < len(ws):
            done = False
            for tgt, good in targets:
                for n in (3, 2, 1):
                    if i + n > len(ws):
                        continue
                    span = ws[i:i + n]
                    raw = "".join(_norm_word(x["w"]) for x in span)
                    if len(raw) < 4 or abs(len(raw) - len(tgt)) > 2:
                        continue
                    if not span[0]["w"].strip()[:1].isupper():
                        continue
                    r = difflib.SequenceMatcher(None, raw, tgt).ratio()
                    if r < 0.84:
                        continue
                    old = " ".join(x["w"].strip() for x in span)
                    trail = re.search(r"[^\w]*$", span[-1]["w"].strip()).group(0)
                    new_txt = " ".join(good) + trail
                    if old == new_txt:
                        i += n; done = True; break
                    k = len(good)
                    texts = ([" ".join(good[:k - n + 1])] + good[k - n + 1:]) if k >= n else (good + [""] * (n - k))
                    last = max(j for j, t in enumerate(texts) if t)
                    texts[last] += trail
                    for x, t in zip(span, texts):
                        x["w"] = (" " + t) if t else ""
                    s["text"] = s["text"].replace(old.rstrip(".,!?;:"), " ".join(good), 1)
                    log(f"İsim düzeltildi: '{old}' → '{' '.join(good)}{trail}'")
                    changes += 1
                    i += n; done = True
                    break
                if done:
                    break
            if not done:
                i += 1
        s["words"] = [w for w in ws if w["w"].strip()]
    return changes


def title_hint(video):
    stem = os.path.splitext(os.path.basename(video))[0]
    stem = re.sub(r"([a-zçğıöşü])([A-ZÇĞİÖŞÜ])", r"\1 \2", stem)
    words = [w for w in re.split(r"[\s_\-.]+", stem) if w and not re.search(r"\d", w)]
    t = " ".join(words)
    return t if re.search(r"[çğıöşüÇĞİÖŞÜ]", t) and len(words) >= 2 else ""


def second_pass(model, audio, segs, lang, hints, progress, stop=None, log=print, thr=0.45):
    sr = 16000
    todo = [i for i, s in enumerate(segs)
            if s.get("words") and any(w.get("p", 1) < thr for w in s["words"]) and s["end"] - s["start"] < 30]
    fixed = 0
    for k, i in enumerate(todo):
        if stop and stop():
            raise RuntimeError("Durduruldu")
        s = segs[i]
        progress(k / max(len(todo), 1), f"İkinci geçiş: belirsiz cümleler {k+1}/{len(todo)}")
        a0 = max(s["start"] - 0.25, 0); a1 = s["end"] + 0.25
        clip = audio[int(a0 * sr):int(a1 * sr)]
        prev = segs[i - 1]["text"] if i > 0 else ""
        prompt = (hints + ". " if hints else "") + prev
        try:
            it, _ = model.transcribe(clip, language=lang, word_timestamps=True, beam_size=10, temperature=0.0,
                                     initial_prompt=prompt or None, condition_on_previous_text=False,
                                     vad_filter=False, without_timestamps=False)
            nw = []
            for ns in it:
                for w in (ns.words or []):
                    nw.append({"s": w.start + a0, "e": w.end + a0, "w": w.word, "p": w.probability})
        except Exception as e:
            log(f"İkinci geçiş atlandı: {e}")
            continue
        if not nw:
            continue
        old_p = sum(w.get("p", 1) for w in s["words"]) / len(s["words"])
        new_p = sum(w["p"] for w in nw) / len(nw)
        ratio = len(nw) / len(s["words"])
        if new_p > old_p + 0.03 and 0.6 <= ratio <= 1.5:
            old_t = s["text"]
            nw = [w for w in nw if s["start"] - 0.3 <= w["s"] <= s["end"] + 0.3]
            if not nw:
                continue
            s["words"] = nw
            s["text"] = "".join(w["w"] for w in nw).strip()
            if s["text"] != old_t:
                fixed += 1
                log(f"Düzeltildi ({old_p:.2f}→{new_p:.2f}): '{old_t}' → '{s['text']}'")
    progress(1.0, f"İkinci geçiş: {fixed} cümle iyileştirildi")
    return fixed


KEY = {
    "önemli": 3, "vazgeç": 3, "başla": 2, "hayat": 2, "motivasyon": 2, "aslında": 1, "gerçekten": 2,
    "kısaca": 2, "unutma": 3, "ders": 2, "öğren": 2, "öğret": 2, "tecrübe": 2, "deneyim": 2, "tavsiye": 3,
    "hata": 2, "pişman": 3, "keşke": 3, "sır": 2, "kural": 2, "neden": 1, "nasıl": 1, "asla": 2, "hiç": 1,
    "herkes": 1, "sakın": 3, "mutlaka": 2, "fark": 1, "değiş": 1, "karar": 2, "zor": 2, "kolay": 1,
    "ölüm": 3, "kaybet": 3, "korku": 3, "mutlu": 2, "üzül": 2, "sars": 2, "ayrılık": 3, "acı": 2,
    "hayal": 2, "başar": 2, "para": 1, "fiyat": 1, "ücret": 1, "sıfırdan": 2,
}
SECOND_PERSON = re.compile(r"\b(sen|sana|senin|seni|siz|size|sizin)\b|(sın|sin|sun|sün)\b")
CTA = ["abone", "beğen", "yorum", "kanala", "kanalıma", "hoş geldiniz", "görüşürüz", "hoşçakal",
       "selamlar", "merhaba", "bildirim", "zil", "linki", "açıklama"]


def _seg_score(text):
    t = trl(text)
    s = 0.0
    for k, w in KEY.items():
        if k in t:
            s += w
    if SECOND_PERSON.search(t):
        s += 1.0
    for c in CTA:
        if c in t:
            s -= 4.0
    return s


def find_candidates(segs, dur, settings):
    mn, mx = float(settings.get("min_len", 20)), float(settings.get("max_len", 60))
    n_want = int(settings.get("n_clips", 4))
    skip_head = float(settings.get("skip_head", 0))
    segs = [s for s in segs if s["text"].strip()]
    seen = {}
    for s in segs:
        k = trl(s["text"]).strip(" .!?,")
        seen[k] = seen.get(k, 0) + 1
    base = []
    for s in segs:
        sc = _seg_score(s["text"])
        if seen[trl(s["text"]).strip(" .!?,")] > 1:
            sc -= 5
        base.append(sc)
    cands = []
    for i, s in enumerate(segs):
        if s["start"] < skip_head:
            continue
        for j in range(i, len(segs)):
            L = segs[j]["end"] - s["start"]
            if L > mx:
                break
            if L < mn:
                continue
            if not re.search(r"[.!?]$", segs[j]["text"].strip()):
                continue
            if i > 0 and not re.search(r"[.!?]$", segs[i - 1]["text"].strip()):
                continue
            sc = sum(base[i:j + 1])
            words = sum(len(x["text"].split()) for x in segs[i:j + 1])
            sc = sc / (L ** 0.5) * 6
            sc += 0.15 * words / L
            if segs[i]["text"].strip().endswith("?"):
                sc += 2.0
            if base[j] >= 2:
                sc += 1.0
            if s["start"] > dur * 0.85:
                sc -= 1.0
            cands.append({"start": s["start"], "end": segs[j]["end"], "score": round(sc, 2),
                          "i": i, "j": j})
    cands.sort(key=lambda c: -c["score"])
    chosen = []
    for c in cands:
        if all(c["end"] <= d["start"] or c["start"] >= d["end"] for d in chosen):
            chosen.append(c)
        if len(chosen) >= max(n_want * 2, 8):
            break
    out = []
    for k, c in enumerate(chosen):
        part = segs[c["i"]:c["j"] + 1]
        out.append({
            "id": f"{k+1:02d}",
            "use": k < n_want,
            "start": round(max(c["start"] - 0.05, 0), 2),
            "end": round(c["end"] + 0.15, 2),
            "score": c["score"],
            "baslik": make_title(part),
            "metin": " ".join(x["text"].strip() for x in part),
        })
    out.sort(key=lambda c: (not c["use"], -c["score"]))
    for k, c in enumerate(out):
        c["id"] = f"{k+1:02d}"
    return out


def make_title(part):
    sents = []
    for s in part:
        for x in re.split(r"(?<=[.!?])\s+", s["text"].strip()):
            if x:
                sents.append(x)
    q = [x for x in sents if x.endswith("?") and 2 <= len(x.split()) <= 8]
    if q:
        t = q[0]
    else:
        t = max(sents, key=lambda x: _seg_score(x) - 0.1 * abs(len(x.split()) - 6))
        w = t.split()
        if len(w) > 7:
            t = " ".join(w[:7]) + "…"
    words = trl(t).split()
    hit = [k for k, w in enumerate(words) if any(key in w for key in KEY)]
    if hit:
        a = hit[0]; b = min(a + 1, len(words) - 1)
    else:
        a, b = max(len(words) - 2, 0), len(words) - 1
    words[a] = "*" + words[a]
    words[b] = words[b] + "*"
    return " ".join(words)


def step_analyze(video_small, wd, settings, progress, stop=None, log=print, video_name=""):
    info = probe(video_small)
    raw_path = os.path.join(wd, "transkript_ham.json")
    tr_path = os.path.join(wd, "transkript.json")
    lang = settings.get("lang", "tr")
    name = name_from_handle(settings.get("handle", ""))
    hints = ", ".join(x for x in (name, title_hint(video_name or video_small)) if x)
    if name:
        log(f"İmzadan tanınan isim: {name}")
    if os.path.exists(raw_path) and os.path.getmtime(raw_path) > os.path.getmtime(video_small):
        segs = json.load(open(raw_path, encoding="utf-8"))
        progress(0.9, "Transkript önbellekten okundu")
    else:
        wav = os.path.join(wd, "ses.wav")
        progress(0.01, "Ses çıkarılıyor")
        run_ffmpeg(["-i", video_small, "-vn", "-ac", "1", "-ar", "16000", wav], info["dur"],
                   lambda p, m: progress(0.04 * p, m), "Ses çıkarılıyor", stop)
        import numpy as np
        with wave.open(wav, "rb") as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        dur = len(audio) / 16000
        from faster_whisper import WhisperModel
        model_name = settings.get("model", "large-v3-turbo")
        progress(0.05, f"Model yükleniyor ({model_name}) – ilk seferde indirilir")
        m = WhisperModel(model_name, device="cpu", compute_type="int8",
                         cpu_threads=max(4, (os.cpu_count() or 8) - 2))
        kw = dict(language=lang, word_timestamps=True, vad_filter=True, beam_size=5)
        if hints:
            kw["hotwords"] = hints
        it, _ = m.transcribe(audio, **kw)
        segs = []
        for s in it:
            if stop and stop():
                raise RuntimeError("Durduruldu")
            segs.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                         "words": [{"s": w.start, "e": w.end, "w": w.word, "p": round(w.probability, 3)}
                                   for w in (s.words or [])]})
            progress(0.06 + 0.7 * min(s.end / dur, 1), f"Yazıya dökülüyor  {s.end/60:.1f}/{dur/60:.1f} dk")
            log(f"[{s.start:6.1f}] {s.text.strip()}")
        try:
            second_pass(m, audio, segs, lang, hints, lambda p, msg: progress(0.76 + 0.17 * p, msg), stop, log)
        except RuntimeError:
            raise
        except Exception as e:
            log(f"İkinci geçiş yapılamadı, ilk sonuç kullanılıyor: {e}")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(segs, f, ensure_ascii=False)
        try:
            os.remove(wav)
        except OSError:
            pass
    segs = json.loads(json.dumps(segs))
    n = fix_names(segs, name, log)
    if n:
        progress(0.95, f"{n} isim yazımı düzeltildi")
    with open(tr_path, "w", encoding="utf-8") as f:
        json.dump(segs, f, ensure_ascii=False)
    cands = find_candidates(segs, info["dur"], settings)
    json.dump(cands, open(os.path.join(wd, "adaylar.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    progress(1.0, f"{len(cands)} aday an bulundu")
    return cands


W, H = 1080, 1920
BG = (0xF6, 0xF4, 0xEF); INK = (0x1A, 0x1A, 0x1A); ACC = (0xEF, 0x92, 0x30); GRAY = (0x5E, 0x5B, 0x55)
VX, VY, VW, VH = 40, 470, 1000, 1000
SLANT = 50
CAP_Y = VY + VH + 60


def _rich_lines(text, font, maxw, INK=INK, ACC=ACC):
    toks = []
    for part in re.split(r"(\*[^*]+\*)", text):
        if not part:
            continue
        acc = part.startswith("*")
        for w in part.strip("*").split():
            toks.append((trl(w), ACC if acc else INK))
    lines, cur = [], []
    sp = font.getlength(" ")
    for t in toks:
        trial = cur + [t]
        wsum = sum(font.getlength(x[0]) for x in trial) + sp * (len(trial) - 1)
        if cur and wsum > maxw:
            lines.append(cur); cur = [t]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _caption_chunks(words, t0, t1):
    ws = []
    for w in words:
        if w["e"] <= t0 or w["s"] >= t1:
            continue
        txt = w["w"].strip()
        if not txt:
            continue
        ws.append({"s": max(w["s"], t0) - t0, "e": min(w["e"], t1) - t0, "w": trl(txt)})
    chunks, cur = [], []
    for w in ws:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            ln = len(" ".join(x["w"] for x in cur + [w]))
            if len(cur) >= 3 or ln > 20 or gap > 0.6 or re.search(r"[.,!?;:]$", cur[-1]["w"]):
                chunks.append(cur); cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        end = chunks[i + 1][0]["s"] if i + 1 < len(chunks) else c[-1]["e"] + 0.4
        out.append({"s": c[0]["s"], "e": min(end, c[-1]["e"] + 0.8), "words": c})
    return out


def render_clip(src, clip, words, wd, settings, progress, stop=None):
    import numpy as np, cv2
    from PIL import Image, ImageDraw, ImageFont
    ff = find_ffmpeg()
    BG = hex2rgb(settings.get("c_bg"), globals()["BG"]); INK = hex2rgb(settings.get("c_ink"), globals()["INK"])
    ACC = hex2rgb(settings.get("c_acc"), globals()["ACC"]); GRAY = hex2rgb(settings.get("c_gray"), globals()["GRAY"])
    handle = (settings.get("handle") or "").strip()
    cid = safe_id(clip.get("id")); t0, t1 = float(clip["start"]), float(clip["end"]); dur = t1 - t0
    seg = os.path.join(wd, f"_seg_{cid}.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-i", src, "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-c:a", "aac", "-b:a", "192k", seg],
                   check=True, **_hidden())
    cap = cv2.VideoCapture(seg)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    sw, sh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    nfr = max(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
    ch = sh; cw = min(int(ch * VW / VH), sw)

    f_med, f_light = font_files(settings.get("font", "poppins"))
    base = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(base)
    hook_font = ImageFont.truetype(f_med, 70)
    lines = _rich_lines(clip.get("baslik", ""), hook_font, 940, INK, ACC)
    lh = int(hook_font.size * 1.25)
    y = max(90, (VY - 40 - lh * len(lines)) // 2 + 20)
    sp = hook_font.getlength(" ")
    for ln in lines:
        wsum = sum(hook_font.getlength(x[0]) for x in ln) + sp * (len(ln) - 1)
        x = (W - wsum) / 2
        for w, c in ln:
            d.text((x, y), w, font=hook_font, fill=c); x += hook_font.getlength(w) + sp
        y += lh
    if handle:
        hf = ImageFont.truetype(f_light, 34)
        d.text(((W - hf.getlength(handle)) / 2, H - 110), handle, font=hf, fill=GRAY)
    base = np.array(base)[..., ::-1].astype(np.float32)
    m = Image.new("L", (VW, VH), 0)
    ImageDraw.Draw(m).polygon([(SLANT, 0), (VW, 0), (VW - SLANT, VH), (0, VH)], fill=255)
    mask = np.array(m, dtype=np.float32)[..., None] / 255.0

    chunks = _caption_chunks(words, t0, t1)
    cap_font = ImageFont.truetype(f_med, 66)
    cache = {}

    def cap_img(ci, ai):
        if (ci, ai) in cache:
            return cache[(ci, ai)]
        ws = [re.sub(r"[.,;:]+$", "", w["w"]) for w in chunks[ci]["words"]]
        spc = cap_font.getlength(" ")
        lns, cur = [], []
        for i in range(len(ws)):
            tr = cur + [i]
            if cur and sum(cap_font.getlength(ws[j]) for j in tr) + spc * (len(tr) - 1) > 960:
                lns.append(cur); cur = [i]
            else:
                cur = tr
        if cur:
            lns.append(cur)
        img = Image.new("RGBA", (W, 90 * len(lns)), (0, 0, 0, 0)); dd = ImageDraw.Draw(img)
        yy = 0
        for ln in lns:
            tw = sum(cap_font.getlength(ws[j]) for j in ln) + spc * (len(ln) - 1)
            x = (W - tw) / 2
            for j in ln:
                dd.text((x, yy), ws[j], font=cap_font, fill=(ACC if j == ai else INK) + (255,))
                x += cap_font.getlength(ws[j]) + spc
            yy += 90
        a = np.array(img)
        r = (a[..., :3][..., ::-1].astype(np.float32), a[..., 3:].astype(np.float32) / 255.0)
        cache[(ci, ai)] = r
        return r

    casc = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))

    out = os.path.join(wd, f"dikey_{cid}.mp4")
    enc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", f"{fps}", "-i", "-", "-i", seg, "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE, **_hidden())
    cx = target = sw / 2
    i = 0
    try:
        while True:
            if stop and stop():
                raise RuntimeError("Durduruldu")
            ok, fr = cap.read()
            if not ok:
                break
            t = i / fps
            if i % 5 == 0 and not casc.empty():
                g = cv2.cvtColor(cv2.resize(fr, None, fx=0.33, fy=0.33), cv2.COLOR_BGR2GRAY)
                fs = casc.detectMultiScale(g, 1.1, 5, minSize=(30, 30))
                if len(fs):
                    x, y_, w_, h_ = max(fs, key=lambda r: r[2] * r[3])
                    target = (x + w_ / 2) / 0.33
            if abs(target - cx) > cw * 0.06:
                cx += (target - cx) * 0.08
            x0 = int(min(max(cx - cw / 2, 0), sw - cw)); y0 = (sh - ch) // 2
            crop = cv2.resize(fr[y0:y0 + ch, x0:x0 + cw], (VW, VH),
                              interpolation=cv2.INTER_AREA if ch > VH else cv2.INTER_CUBIC)
            frame = base.copy()
            reg = frame[VY:VY + VH, VX:VX + VW]
            frame[VY:VY + VH, VX:VX + VW] = reg * (1 - mask) + crop.astype(np.float32) * mask
            for ci, c in enumerate(chunks):
                if c["s"] <= t < c["e"]:
                    ai = 0
                    for k, w in enumerate(c["words"]):
                        if t >= w["s"]:
                            ai = k
                    rgb, a = cap_img(ci, ai)
                    hh = rgb.shape[0]
                    r = frame[CAP_Y:CAP_Y + hh]
                    frame[CAP_Y:CAP_Y + hh] = r * (1 - a) + rgb * a
                    break
            frame[H - 14:H, :int(W * min(t / dur, 1.0))] = ACC[::-1]
            enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
            i += 1
            if i % 15 == 0:
                progress(i / nfr, f"Klip {cid} işleniyor  {i}/{nfr} kare")
    finally:
        cap.release()
        try:
            enc.stdin.close()
        except Exception:
            pass
        enc.wait()
        try:
            os.remove(seg)
        except OSError:
            pass
    progress(1.0, f"Klip {cid} hazır")
    return out


def step_render(src, wd, clips, settings, progress, stop=None, log=print):
    tp = os.path.join(wd, "transkript.json")
    if not os.path.exists(tp):
        raise RuntimeError("Önce analiz adımını çalıştır")
    segs = json.load(open(tp, encoding="utf-8"))
    words = [w for s in segs for w in s.get("words", [])]
    vdur = probe(src)["dur"]
    sel = []
    for c in clips:
        if not c.get("use"):
            continue
        st, en = max(float(c["start"]), 0.0), min(float(c["end"]), vdur)
        if en - st < 1.0:
            log(f"Atlandı (geçersiz zaman aralığı): klip {c.get('id')}")
            continue
        sel.append(dict(c, start=st, end=en))
    if not sel:
        raise RuntimeError("Geçerli klip seçilmedi")
    total = sum(float(c["end"]) - float(c["start"]) for c in sel)
    done = 0.0
    outs = []
    for c in sel:
        L = float(c["end"]) - float(c["start"])
        o = render_clip(src, c, words, wd, settings,
                        lambda p, m, d0=done, L=L: progress((d0 + p * L) / total, m), stop)
        done += L
        outs.append(o)
        log("Yazıldı: " + o)
    progress(1.0, f"{len(outs)} dikey klip hazır")
    return outs
