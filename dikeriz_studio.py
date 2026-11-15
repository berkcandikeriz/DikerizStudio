import os, re, sys, json, glob, shutil, threading, time, traceback, webbrowser, mimetypes, socket, secrets, hmac
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import studio_core as core

APP_ID = "dikeriz-studio"
VERSION = "1.0.0"
PORT = int(os.environ.get("DIKERIZ_PORT", "8765"))
for _i, _a in enumerate(sys.argv):
    if _a == "--port" and _i + 1 < len(sys.argv):
        PORT = int(sys.argv[_i + 1])
TOKEN = secrets.token_urlsafe(32)
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
MAX_BODY = 2 * 1024 * 1024
MAX_FONT = 15 * 1024 * 1024
MAX_UPLOAD = 64 * 1024 ** 3
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".m4v")
PENDING = {}

CFG_PATH = os.path.join(HERE, "ayarlar.json")
DEFAULTS = {
    "out_root": os.path.join(os.path.expanduser("~"), "Videos", "DikerizStudio"),
    "shrink_h": 1080, "shrink_crf": 26, "model": "large-v3-turbo", "lang": "tr",
    "n_clips": 4, "min_len": 20, "max_len": 60, "skip_head": 0,
    "handle": "", "font": "poppins",
    "c_bg": "#F6F4EF", "c_ink": "#1A1A1A", "c_acc": "#EF9230", "c_gray": "#5E5B55",
}
SCHEMA = {
    "out_root": (str, 1, 1024), "shrink_h": (int, 360, 2160), "shrink_crf": (int, 16, 36),
    "model": (str, ["large-v3-turbo", "large-v3", "medium", "small", "base"]),
    "lang": (str, 0, 8), "n_clips": (int, 1, 20), "min_len": (float, 5, 180), "max_len": (float, 10, 180),
    "skip_head": (float, 0, 36000), "handle": (str, 0, 60), "font": (str, 1, 64),
    "c_bg": ("color",), "c_ink": ("color",), "c_acc": ("color",), "c_gray": ("color",),
}


def _valid(k, v):
    sc = SCHEMA.get(k)
    if sc is None:
        return None
    if sc[0] == "color":
        v = str(v)
        return v if len(v) == 7 and v[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in v[1:]) else None
    if isinstance(sc[1], list):
        return v if v in sc[1] else None
    try:
        v = sc[0](v)
    except (TypeError, ValueError):
        return None
    if sc[0] is str:
        if k == "lang" and not re.fullmatch(r"[a-z]{2,3}", v):
            return None
        return v if len(v) <= sc[2] else None
    if v != v:
        return None
    return min(max(v, sc[1]), sc[2])


def load_cfg():
    c = dict(DEFAULTS)
    try:
        for k, v in json.load(open(CFG_PATH, encoding="utf-8")).items():
            vv = _valid(k, v)
            if vv is not None:
                c[k] = vv
    except Exception:
        pass
    return c


def save_cfg(c):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


STEPS = ["shrink", "analyze", "render"]
STEP_NAMES = {"shrink": "Küçültme", "analyze": "Analiz", "render": "Dikey render"}
STEP_W = {"shrink": 0.2, "analyze": 0.4, "render": 0.4}
LOCK = threading.Lock()
S = {
    "video": "", "name": "", "upload": False, "uploading": False, "wd": "", "running": False, "stop": False, "step": "", "msg": "Hazır",
    "steps": {k: {"pct": 0.0, "state": "bekliyor", "msg": ""} for k in STEPS},
    "overall": 0.0, "log": [], "clips": [], "outputs": [], "error": "",
}


def log(m):
    with LOCK:
        S["log"].append(time.strftime("%H:%M:%S ") + m)
        S["log"] = S["log"][-400:]
        wd = S["wd"]
    if wd:
        try:
            with open(os.path.join(wd, "studio_log.txt"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")
        except Exception:
            pass


def recompute_overall():
    S["overall"] = sum(STEP_W[k] * (1.0 if S["steps"][k]["state"] == "tamam" else S["steps"][k]["pct"])
                       for k in STEPS)


def _num(x, default=0.0):
    try:
        v = float(x)
        return v if v == v and abs(v) < 1e7 else default
    except (TypeError, ValueError):
        return default


def sanitize_clips(clips):
    out = []
    for i, c in enumerate(clips if isinstance(clips, list) else []):
        if not isinstance(c, dict):
            continue
        out.append({
            "id": core.safe_id(c.get("id"), i + 1),
            "use": bool(c.get("use")),
            "start": round(max(_num(c.get("start")), 0.0), 3),
            "end": round(max(_num(c.get("end")), 0.0), 3),
            "score": round(_num(c.get("score")), 2),
            "baslik": str(c.get("baslik", ""))[:200],
            "metin": str(c.get("metin", ""))[:5000],
        })
    return out[:50]


def set_project(video, wd=None, upload=False, name=None):
    wd = wd or core.work_dir_for(video)
    with LOCK:
        S["video"], S["wd"], S["upload"] = video, wd, upload
        S["name"] = name or os.path.basename(video)
        S["log"], S["error"] = [], ""
        S["outputs"] = sorted(glob.glob(os.path.join(wd, "dikey_*.mp4")))
        S["clips"] = []
        cp = os.path.join(wd, "adaylar.json")
        if os.path.exists(cp):
            try:
                S["clips"] = sanitize_clips(json.load(open(cp, encoding="utf-8")))
            except Exception:
                pass
        small = os.path.exists(os.path.join(wd, "kucuk.mp4"))
        tr = os.path.exists(os.path.join(wd, "transkript.json"))
        S["steps"]["shrink"] = {"pct": float(small), "state": "tamam" if small else "bekliyor", "msg": ""}
        S["steps"]["analyze"] = {"pct": float(tr), "state": "tamam" if tr and S["clips"] else "bekliyor", "msg": ""}
        S["steps"]["render"] = {"pct": float(bool(S["outputs"])), "state": "tamam" if S["outputs"] else "bekliyor", "msg": ""}
        recompute_overall()
        S["msg"] = "Proje açıldı: " + S["name"]


def worker(steps, cfg):
    stopf = lambda: S["stop"]
    try:
        video, wd = S["video"], S["wd"]
        small = os.path.join(wd, "kucuk.mp4")
        for st in steps:
            with LOCK:
                S["step"] = st
                S["steps"][st] = {"pct": 0.0, "state": "çalışıyor", "msg": ""}

            def prog(p, m, st=st):
                with LOCK:
                    S["steps"][st]["pct"] = max(0.0, min(1.0, float(p)))
                    S["steps"][st]["msg"] = m
                    S["msg"] = m
                    recompute_overall()

            log("▶ " + STEP_NAMES[st] + " başladı")
            src = small if os.path.exists(small) else video
            if st == "shrink":
                core.step_shrink(video, wd, cfg, prog, stopf)
                if S["upload"] and os.path.isfile(video) and _inside(video, wd) and os.path.exists(small):
                    os.remove(video)
                    log("Geçici kaynak kopyası silindi, hafif kopya saklandı")
            elif st == "analyze":
                clips = core.step_analyze(src, wd, cfg, prog, stopf, log, video_name=S["name"])
                with LOCK:
                    S["clips"] = sanitize_clips(clips)
            elif st == "render":
                with LOCK:
                    clips = [dict(c) for c in S["clips"]]
                with open(os.path.join(wd, "adaylar.json"), "w", encoding="utf-8") as f:
                    json.dump(clips, f, ensure_ascii=False, indent=1)
                outs = core.step_render(src, wd, clips, cfg, prog, stopf, log)
                with LOCK:
                    S["outputs"] = sorted(set(S["outputs"]) | set(outs))
            with LOCK:
                S["steps"][st]["state"] = "tamam"; S["steps"][st]["pct"] = 1.0
                recompute_overall()
            log("✓ " + S["steps"][st]["msg"])
        with LOCK:
            S["msg"] = "Tamamlandı ✓"
    except Exception as e:
        log("HATA: " + str(e))
        log(traceback.format_exc())
        with LOCK:
            S["error"] = str(e)
            S["msg"] = "Hata: " + str(e)
            if S["step"]:
                S["steps"][S["step"]]["state"] = "hata"
    finally:
        with LOCK:
            S["running"] = False; S["stop"] = False; S["step"] = ""


def _safe_stem(name):
    stem = os.path.splitext(os.path.basename(str(name)))[0]
    stem = re.sub(r"[^\w\- ]+", "_", stem).strip(" _")[:80]
    return stem or "video"


def prepare_upload(name, size, out_root):
    ext = os.path.splitext(str(name))[1].lower()
    if ext not in VIDEO_EXT:
        raise ValueError("Desteklenmeyen dosya türü (mp4, mov, mkv, m4v)")
    if not isinstance(size, int) or size <= 0 or size > MAX_UPLOAD:
        raise ValueError("Geçersiz dosya boyutu")
    os.makedirs(out_root, exist_ok=True)
    base = _safe_stem(name)
    for k in range(1, 100):
        wd = os.path.join(out_root, base if k == 1 else f"{base}_{k}")
        meta_p = os.path.join(wd, "kaynak.json")
        if not os.path.exists(wd):
            break
        try:
            meta = json.load(open(meta_p, encoding="utf-8"))
        except Exception:
            meta = None
        if meta and meta.get("name") == os.path.basename(str(name)) and meta.get("size") == size:
            if os.path.exists(os.path.join(wd, "kucuk.mp4")):
                return {"reuse": True, "wd": wd, "src": os.path.join(wd, "kaynak" + ext)}
            break
    else:
        raise ValueError("Çok fazla aynı adlı proje var")
    os.makedirs(wd, exist_ok=True)
    free = shutil.disk_usage(wd).free
    if free < size * 1.3:
        raise ValueError(f"Diskte yeterli yer yok ({free/1e9:.1f} GB boş, {size*1.3/1e9:.1f} GB gerekli)")
    return {"reuse": False, "wd": wd, "src": os.path.join(wd, "kaynak" + ext)}


def fonts_for_ui():
    out = []
    for f in core.list_fonts():
        base = "/fonts/user/" if f["user"] else "/fonts/"
        out.append({"id": f["id"], "family": f["family"], "user": f["user"],
                    "url": base + os.path.basename(f["title"]), "files": f["files"]})
    return out


def _font_magic_ok(head):
    return head[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1")


def browse_file():
    try:
        import tkinter as tk
        from tkinter import filedialog
        r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True)
        p = filedialog.askopenfilename(title="Kaynak video seç",
                                       filetypes=[("Video", " ".join("*" + e for e in VIDEO_EXT)), ("Hepsi", "*.*")])
        r.destroy()
        return p or ""
    except Exception:
        return None


def _inside(path, folder):
    try:
        a, b = os.path.realpath(path), os.path.realpath(folder)
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "media-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


class H(BaseHTTPRequestHandler):
    server_version = "DikerizStudio"
    sys_version = ""

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self):
        if self.headers.get("Host", "") not in ALLOWED_HOSTS:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + h for h in ALLOWED_HOSTS}:
            return False
        return True

    def _token_ok(self, q=None):
        t = self.headers.get("X-Token") or ((q or {}).get("t", [""])[0])
        return hmac.compare_digest(t.encode(), TOKEN.encode())

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("geçersiz uzunluk")
        if n < 0 or n > MAX_BODY:
            raise ValueError("istek çok büyük")
        if n and not self.headers.get("Content-Type", "").startswith("application/json"):
            raise ValueError("yalnızca JSON kabul edilir")
        d = json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}
        if not isinstance(d, dict):
            raise ValueError("geçersiz istek")
        return d

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"forbidden")
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            html = open(os.path.join(HERE, "index.html"), encoding="utf-8").read().replace("__TOKEN__", TOKEN)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8",
                              {"Content-Security-Policy": CSP})
        if u.path == "/app.js":
            return self._send(200, open(os.path.join(HERE, "app.js"), "rb").read(),
                              "text/javascript; charset=utf-8")
        if u.path.startswith("/fonts/user/"):
            name = os.path.basename(u.path)
            if name.lower().endswith(core.FONT_EXT) and _inside(os.path.join(core.USER_FONTS, name), core.USER_FONTS):
                return self._file(os.path.join(core.USER_FONTS, name))
            return self._send(404)
        if u.path.startswith("/fonts/"):
            name = os.path.basename(u.path)
            if name.endswith(".ttf"):
                return self._file(os.path.join(HERE, "fonts", name))
            return self._send(404)
        if u.path == "/api/ping":
            return self._json({"app": APP_ID, "version": VERSION})
        if not self._token_ok(q):
            return self._send(401, b"unauthorized")
        if u.path == "/api/state":
            with LOCK:
                st = {k: S[k] for k in ("video", "name", "upload", "uploading", "wd", "running", "step", "msg", "steps", "overall",
                                        "clips", "outputs", "error")}
                st["log"] = S["log"][-150:]
            return self._json(st)
        if u.path == "/api/config":
            return self._json(load_cfg())
        if u.path == "/api/fonts":
            return self._json(fonts_for_ui())
        if u.path == "/media":
            p = q.get("p", [""])[0]
            wd = S["wd"]
            if wd and os.path.basename(p).startswith("dikey_") and p.lower().endswith(".mp4") and _inside(p, wd):
                return self._file(p)
            return self._send(403, b"forbidden")
        return self._send(404)

    def _file(self, p):
        if not os.path.isfile(p):
            return self._send(404)
        size = os.path.getsize(p)
        ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            try:
                a, _, b = rng[6:].split(",")[0].strip().partition("-")
                if a:
                    start = int(a); end = int(b) if b else size - 1
                else:
                    start = max(size - int(b), 0)
                end = min(end, size - 1)
                if start > end or start < 0:
                    raise ValueError
                code = 206
            except ValueError:
                return self._send(416, extra={"Content-Range": f"bytes */{size}"})
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(p, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk); left -= len(chunk)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass

    def do_PUT(self):
        if not self._host_ok() or not self._token_ok():
            return self._send(403, b"forbidden")
        u = urlparse(self.path)
        if u.path == "/api/font":
            return self._put_font(parse_qs(u.query).get("name", [""])[0])
        if u.path != "/api/upload":
            return self._send(404)
        job = PENDING.pop(parse_qs(u.query).get("id", [""])[0], None)
        if not job:
            return self._json({"error": "Geçersiz yükleme"}, 400)
        try:
            n = int(self.headers.get("Content-Length") or -1)
        except ValueError:
            n = -1
        if n != job["size"]:
            return self._json({"error": "Boyut uyuşmuyor"}, 400)
        with LOCK:
            if S["running"] or S["uploading"]:
                return self._json({"error": "Bir işlem sürüyor"}, 409)
            S["uploading"] = True
            S["msg"] = "Video alınıyor…"
        part = job["src"] + ".part"
        left = n
        try:
            with open(part, "wb") as f:
                while left > 0:
                    chunk = self.rfile.read(min(4 << 20, left))
                    if not chunk:
                        raise IOError("bağlantı kesildi")
                    f.write(chunk); left -= len(chunk)
            os.replace(part, job["src"])
        except Exception as e:
            try:
                os.remove(part)
            except OSError:
                pass
            with LOCK:
                S["uploading"] = False; S["msg"] = "Yükleme yarıda kaldı"
            return self._json({"error": "Yükleme tamamlanamadı: " + str(e)}, 400)
        with open(os.path.join(job["wd"], "kaynak.json"), "w", encoding="utf-8") as f:
            json.dump({"name": job["name"], "size": job["size"]}, f, ensure_ascii=False)
        set_project(job["src"], job["wd"], upload=True, name=job["name"])
        with LOCK:
            S["uploading"] = False
        log(f"Video alındı: {job['name']} ({job['size']/1e6:.0f} MB)")
        return self._json({"ok": True})

    def _put_font(self, name):
        name = os.path.basename(name)
        stem, ext = os.path.splitext(name)
        if ext.lower() not in core.FONT_EXT:
            return self._json({"error": "Yalnızca .ttf ve .otf font dosyaları eklenebilir"}, 400)
        try:
            n = int(self.headers.get("Content-Length") or -1)
        except ValueError:
            n = -1
        if n <= 0 or n > MAX_FONT:
            return self._json({"error": "Font dosyası boş ya da çok büyük (en fazla 15 MB)"}, 400)
        data = self.rfile.read(n)
        if len(data) != n or not _font_magic_ok(data):
            return self._json({"error": "Bu dosya geçerli bir font değil"}, 400)
        os.makedirs(core.USER_FONTS, exist_ok=True)
        safe = re.sub(r"[^\w\- ]+", "_", stem).strip(" _")[:60] or "font"
        dest = os.path.join(core.USER_FONTS, safe + ext.lower())
        k = 2
        while os.path.exists(dest):
            if open(dest, "rb").read() == data:
                break
            dest = os.path.join(core.USER_FONTS, f"{safe}_{k}{ext.lower()}"); k += 1
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        try:
            fam, style = core._font_name(tmp)
            tr_ok = core.font_has_turkish(tmp)
        except Exception:
            os.remove(tmp)
            return self._json({"error": "Font okunamadı; dosya bozuk ya da desteklenmiyor"}, 400)
        os.replace(tmp, dest)
        fid = next((f["id"] for f in core.list_fonts() if f["user"] and f["family"] == fam), "")
        log(f"Font eklendi: {fam} {style}" + ("" if tr_ok else " (Türkçe harfler eksik!)"))
        return self._json({"ok": True, "id": fid, "family": fam, "style": style, "turkish": tr_ok})

    def do_POST(self):
        if not self._host_ok() or not self._token_ok():
            return self._send(403, b"forbidden")
        try:
            b = self._body()
        except Exception as e:
            return self._json({"error": str(e)}, 400)
        p = urlparse(self.path).path
        if p == "/api/config":
            c = load_cfg()
            for k, v in b.items():
                vv = _valid(k, v)
                if vv is not None:
                    c[k] = vv
            save_cfg(c)
            return self._json(c)
        if p == "/api/font/delete":
            fid = str(b.get("id", ""))
            f = next((x for x in core.list_fonts() if x["id"] == fid and x["user"]), None)
            if not f:
                return self._json({"error": "Font bulunamadı"}, 400)
            for fn in f["files"]:
                pth = os.path.join(core.USER_FONTS, os.path.basename(fn))
                if _inside(pth, core.USER_FONTS) and os.path.isfile(pth):
                    os.remove(pth)
            c = load_cfg()
            if c.get("font") == fid:
                c["font"] = "poppins"; save_cfg(c)
            log(f"Font silindi: {f['family']}")
            return self._json({"ok": True, "font": c.get("font")})
        if p == "/api/browse":
            if S["running"] or S["uploading"]:
                return self._json({"error": "Bir işlem sürüyor"}, 409)
            path = browse_file()
            return self._json({"path": path or "", "unsupported": path is None})
        if p == "/api/prepare":
            if S["running"] or S["uploading"]:
                return self._json({"error": "Bir işlem sürüyor"}, 409)
            try:
                size = b.get("size")
                r = prepare_upload(b.get("name", ""), int(size) if isinstance(size, (int, float)) else -1,
                                   load_cfg()["out_root"])
            except (ValueError, OSError) as e:
                return self._json({"error": str(e)}, 400)
            name = os.path.basename(str(b.get("name")))
            if r["reuse"]:
                set_project(r["src"], r["wd"], upload=True, name=name)
                return self._json({"reuse": True})
            uid = secrets.token_urlsafe(16)
            PENDING.clear()
            PENDING[uid] = {"wd": r["wd"], "src": r["src"], "size": int(size), "name": name}
            return self._json({"reuse": False, "id": uid})
        if p == "/api/open":
            v = str(b.get("video", ""))
            if not (os.path.isfile(v) and v.lower().endswith(VIDEO_EXT)):
                return self._json({"error": "Video bulunamadı ya da desteklenmeyen tür"}, 400)
            if S["running"] or S["uploading"]:
                return self._json({"error": "Bir işlem sürüyor"}, 409)
            set_project(os.path.abspath(v))
            return self._json({"ok": True})
        if p == "/api/clips":
            with LOCK:
                S["clips"] = sanitize_clips(b.get("clips"))
                if S["wd"]:
                    with open(os.path.join(S["wd"], "adaylar.json"), "w", encoding="utf-8") as f:
                        json.dump(S["clips"], f, ensure_ascii=False, indent=1)
            return self._json({"ok": True})
        if p == "/api/run":
            steps = [s for s in b.get("steps", []) if s in STEPS] if isinstance(b.get("steps"), list) else []
            with LOCK:
                if S["running"] or S["uploading"]:
                    return self._json({"error": "Zaten çalışıyor"}, 409)
                if not S["video"]:
                    return self._json({"error": "Önce bir video seç"}, 400)
                if not steps:
                    return self._json({"error": "Adım seçilmedi"}, 400)
                if "clips" in b:
                    S["clips"] = sanitize_clips(b["clips"])
                S["running"], S["stop"], S["error"] = True, False, ""
                for s in steps:
                    S["steps"][s] = {"pct": 0.0, "state": "sırada", "msg": ""}
                recompute_overall()
            threading.Thread(target=worker, args=(steps, load_cfg()), daemon=True).start()
            return self._json({"ok": True})
        if p == "/api/stop":
            S["stop"] = True
            return self._json({"ok": True})
        if p == "/api/folder":
            wd = S["wd"]
            if wd and os.path.isdir(wd):
                if os.name == "nt":
                    os.startfile(wd)
                else:
                    import subprocess
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", wd])
            return self._json({"ok": True})
        if p == "/api/quit":
            self._json({"ok": True})
            threading.Thread(target=lambda: (time.sleep(0.4), os._exit(0)), daemon=True).start()
            return
        return self._send(404)


def notify(msg, error=False):
    if sys.stdout is not None:
        print(msg, flush=True)
    elif os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "Dikeriz Studio", 0x10 if error else 0x40)


def _running_instance(url):
    try:
        with urllib.request.urlopen(url + "api/ping", timeout=1.5) as r:
            return json.loads(r.read().decode()).get("app") == APP_ID
    except Exception:
        return False


def main():
    url = f"http://127.0.0.1:{PORT}/"
    s = socket.socket()
    busy = s.connect_ex(("127.0.0.1", PORT)) == 0
    s.close()
    if busy:
        if _running_instance(url):
            webbrowser.open(url)
            return
        notify(f"{PORT} portu başka bir program tarafından kullanılıyor.\n"
               f"Farklı bir port için DIKERIZ_PORT ortam değişkenini ya da --port 8766 seçeneğini kullan.", True)
        sys.exit(1)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    srv.daemon_threads = True
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    if sys.stdout is not None:
        print(f"Dikeriz Studio {VERSION}: {url}  (kapatmak için arayüzdeki 'kapat' düğmesi ya da Ctrl+C)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        err = traceback.format_exc()
        try:
            with open(os.path.join(HERE, "studio_hata.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S\n") + err + "\n")
        except OSError:
            pass
        notify("Dikeriz Studio başlatılamadı. Ayrıntılar: studio_hata.log\n\n" + err[-600:], True)
        sys.exit(1)
