import io
from PIL import Image, ImageFile
import os, re, sys, json, shutil, struct, subprocess, zipfile, zlib, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
WINSCP = r"C:\Program Files (x86)\WinSCP\WinSCP.com"
SRC = os.path.join(HERE, "generated.zip")
WORK = os.path.join(HERE, "work")
LIGHT_TEXT = True
CACHE = os.path.join(HERE, "cache.zip")
PS = os.path.join(HERE, "tool", "packsquash.exe")
REPO = "brejein/rizzcity-pack"
REPO_DIR = os.path.join(HERE, "repo")
VEH_NS = "nusa_vehicles"
VEH_MAX = 256
VEH_COLOR_ALIAS = {"silver": "white", "yellow": "white", "green": "blue", "orange": "red"}
UI_DROP = ("hud_bodyhealth_",)
LOGO = ("assets/minecraft/textures/gui/title/mojangstudios.png", 1024)
STRIP = (
    "assets/betterhud/font/hud_rizz_wheel_image.json",
    "assets/betterhud/textures/image_rizzcity_ref_ktprizz.png",
)
STRIP_RE = re.compile(r"assets/betterhud/textures/image_rizz_(w\d+|center)_")


def download():
    if os.path.exists(SRC):
        os.remove(SRC)
    r = subprocess.run(f'"{WINSCP}" /command "open rizzcity2" "get /plugins/ItemsAdder/output/generated.zip ""{SRC}""" "exit"',
                       capture_output=True, text=True)
    if not os.path.exists(SRC) or r.returncode != 0:
        sys.exit("Gagal download generated.zip dari server:\n" + r.stdout[-500:])


def fixpng(d):
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return d
    chunks = []
    idat = b""
    p = 8
    while p + 12 <= len(d):
        ln = struct.unpack(">I", d[p:p + 4])[0]
        body = d[p + 4:p + 8 + ln]
        p += 12 + ln
        if body[:4] == b"IDAT":
            if not idat:
                chunks.append(None)
            idat += body[4:]
        else:
            chunks.append(body)
        if body[:4] == b"IEND":
            break
    if idat:
        try:
            zlib.decompress(idat)
        except zlib.error:
            try:
                idat = zlib.compress(zlib.decompressobj(-15).decompress(idat[2:]), 9)
            except zlib.error:
                pass
    out = bytearray(d[:8])
    for body in chunks:
        if body is None:
            body = b"IDAT" + idat
        out += struct.pack(">I", len(body) - 4) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
    return bytes(out)


def fixjson(d):
    try:
        t = d.decode("utf-8-sig").strip()
        json.loads(t)
        return d
    except Exception:
        pass
    try:
        obj, _ = json.JSONDecoder().raw_decode(t)
        return json.dumps(obj, separators=(",", ":")).encode("utf-8")
    except Exception:
        return d


def same(dst, data, name):
    old = open(dst, "rb").read()
    if old == data:
        return True
    if not name.lower().endswith(".png"):
        return False
    try:
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        a = Image.open(io.BytesIO(old))
        b = Image.open(io.BytesIO(data))
        if a.size != b.size:
            return False
        a = a.convert("RGBA")
        b = b.convert("RGBA")
        return a.tobytes() == b.tobytes()
    except Exception:
        return False


def extract():
    seen = set()
    changed = 0
    names = []
    raw = open(SRC, "rb").read()
    z = zipfile.ZipFile(SRC)
    n = 0
    for i in z.infolist():
        name = i.filename.replace("\\", "/")
        if name.endswith("/") or ".." in name or name.startswith("/"):
            continue
        off = i.header_offset
        if raw[off:off + 4] != b"PK\x03\x04":
            continue
        ln, le = struct.unpack("<HH", raw[off + 26:off + 30])
        data = raw[off + 30 + ln + le: off + 30 + ln + le + i.compress_size]
        if i.compress_type == zipfile.ZIP_DEFLATED:
            data = zlib.decompressobj(-15).decompress(data)
        elif i.compress_type != zipfile.ZIP_STORED:
            continue
        if name.lower().endswith(".png"):
            if data[:4] != b"\x89PNG":
                print("Skip PNG rusak: " + name)
                continue
            data = fixpng(data)
        elif name.lower().endswith((".json", ".mcmeta")):
            data = fixjson(data)
        dst = os.path.join(WORK, *name.split("/"))
        seen.add(os.path.normcase(dst))
        n += 1
        if os.path.exists(dst) and same(dst, data, name):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
        changed += 1
        names.append(name)
    for root, dirs, files in os.walk(WORK, topdown=False):
        for f in files:
            p = os.path.join(root, f)
            if os.path.normcase(p) not in seen:
                os.remove(p)
                changed += 1
        if not os.listdir(root):
            os.rmdir(root)
    print(f"Extracted {n} files, {changed} berubah")
    if changed:
        print("Berubah: " + ", ".join(names[:15]) + (" ..." if len(names) > 15 else ""))


def git(*a):
    r = subprocess.run(["git", "-C", REPO_DIR, *a], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("git gagal: " + " ".join(a) + "\n" + r.stderr[-500:])
    return r.stdout.strip()


def publish(out, ver):
    d = os.path.join(HERE, "publish")
    os.makedirs(d, exist_ok=True)

    def g(*a):
        r = subprocess.run(["git", "-C", d, *a], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("git gagal: " + " ".join(a) + "\n" + r.stderr[-500:])
        return r.stdout.strip()

    if not os.path.isdir(os.path.join(d, ".git")):
        g("init", "-q")
    g("checkout", "-q", "--orphan", f"p{ver}")
    shutil.copyfile(out, os.path.join(d, "RizzCity.zip"))
    g("add", "RizzCity.zip")
    g("-c", "user.name=rizzcity-build", "-c", "user.email=build@rizzcity.local", "commit", "-q", "-m", f"RizzCity V{ver}")
    g("push", "-q", "-f", f"https://github.com/{REPO}.git", f"p{ver}:pack")
    return f"https://raw.githubusercontent.com/{REPO}/{g('rev-parse', 'HEAD')}/RizzCity.zip"


def set_url(url):
    tmp = os.path.join(HERE, "iacfg")
    os.makedirs(tmp, exist_ok=True)
    for host in ("rizzcity2", "rizzcitylobby"):
        f = os.path.join(tmp, host + ".yml")
        sc = os.path.join(tmp, host + ".txt")
        open(sc, "w").write(f'open {host}\noption batch abort\nget /plugins/ItemsAdder/config.yml "{f}"\nexit\n')
        subprocess.run(f'"{WINSCP}" /script="{sc}"', capture_output=True, text=True, check=True)
        s = open(f, encoding="utf-8").read()
        lobby = False
        s = re.sub(r"(external-host:\s*\n\s*enabled: )\w+(\s*\n\s*url: ).*", lambda m: m.group(1) + ("true" if lobby else "false") + m.group(2) + url, s)
        s = re.sub(r"(no-host:\s*\n\s*enabled: )\w+", r"\1" + ("false" if lobby else "true"), s)
        s = re.sub(r"(self-host:\s*\n\s*enabled: )\w+", r"\1false", s)
        s = re.sub(r"skip_url_file_type_check: \w+", "skip_url_file_type_check: true", s)
        open(f, "w", encoding="utf-8", newline="\n").write(s)
        open(sc, "w").write(f'open {host}\noption batch abort\nput "{f}" /plugins/ItemsAdder/config.yml\nexit\n')
        subprocess.run(f'"{WINSCP}" /script="{sc}"', capture_output=True, text=True, check=True)
    f = os.path.join(tmp, "pack.properties")
    sc = os.path.join(tmp, "proxy.txt")
    open(f, "w", encoding="utf-8", newline="\n").write(f"url={url}\nuuid=d69238f2-b7ce-30b0-8262-17cd9490f29d\nforce=false\n")
    open(sc, "w").write(f'open rizzcityproxy\noption batch abort\nput "{f}" /plugins/rizzpack/pack.properties\nexit\n')
    subprocess.run(f'"{WINSCP}" /script="{sc}"', capture_output=True, text=True, check=True)
    print("URL pack di-set di proxy (RizzPack) + ItemsAdder RizzCity/Lobby.")


def dev_mode():
    tmp = os.path.join(HERE, "iacfg")
    os.makedirs(tmp, exist_ok=True)
    f = os.path.join(tmp, "rizzcity.yml")
    sc = os.path.join(tmp, "dev.txt")
    open(sc, "w").write(f'open rizzcity2\noption batch abort\nget /plugins/ItemsAdder/config.yml "{f}"\nexit\n')
    subprocess.run(f'"{WINSCP}" /script="{sc}"', capture_output=True, text=True, check=True)
    s = open(f, encoding="utf-8").read()
    s = re.sub(r"(external-host:\s*\n\s*enabled: )\w+", r"\1false", s)
    s = re.sub(r"(no-host:\s*\n\s*enabled: )\w+", r"\1false", s)
    s = re.sub(r"(self-host:\s*\n\s*enabled: )\w+", r"\1true", s)
    open(f, "w", encoding="utf-8", newline="\n").write(s)
    open(sc, "w").write(f'open rizzcity2\noption batch abort\nput "{f}" /plugins/ItemsAdder/config.yml\nexit\n')
    subprocess.run(f'"{WINSCP}" /script="{sc}"', capture_output=True, text=True, check=True)
    print("RizzCity sekarang DEV MODE (self-host). Jalankan /iareload lalu /iazip di RizzCity.")


def sync_lobby():
    tmp = os.path.join(HERE, "lobbysync")
    os.makedirs(tmp, exist_ok=True)
    dirs = ["assets", "backgrounds", "compasses", "fonts", "heads", "huds", "images", "layouts", "placeholders", "popups", "shaders", "texts"]
    down = ["open rizzcity2", "option batch abort", "option confirm off"]
    for d in dirs:
        os.makedirs(os.path.join(tmp, "bh", d), exist_ok=True)
        down.append(f'synchronize local -delete -filemask=|*.tar.gz "{os.path.join(tmp, "bh", d)}" /plugins/BetterHud/{d}')
    down.append(f'get /plugins/ItemsAdder/storage/font_images_unicode_cache.yml /plugins/ItemsAdder/storage/items_ids_cache.yml "{tmp}\\"')
    down.append("exit")
    up = ["open rizzcitylobby", "option batch abort", "option confirm off"]
    for d in dirs:
        up.append(f'synchronize remote -delete "{os.path.join(tmp, "bh", d)}" /plugins/BetterHud/{d}')
    up.append(f'put "{os.path.join(tmp, "font_images_unicode_cache.yml")}" "{os.path.join(tmp, "items_ids_cache.yml")}" /plugins/ItemsAdder/storage/')
    up.append("exit")
    for name, lines in (("down", down), ("up", up)):
        sc = os.path.join(tmp, name + ".txt")
        open(sc, "w").write("\n".join(lines) + "\n")
        r = subprocess.run(f'"{WINSCP}" /script="{sc}"', capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("Sync lobby gagal:\n" + r.stdout[-800:])
    print("Lobby BetterHud + ItemsAdder cache disamakan dengan RizzCity.")


def fonts():
    d = os.path.join(WORK, "assets", "rcui", "font")
    os.makedirs(d, exist_ok=True)
    for name, ttf, size in (("small", "poppins", 20), ("body", "poppins", 24), ("bold", "poppins_semibold", 24), ("title", "poppins_semibold", 36)):
        prov = {"providers": [{"type": "ttf", "file": f"minecraft:{ttf}.ttf", "shift": [0, 0], "size": size, "oversample": 4.0 if size > 30 else 8.0}]}
        open(os.path.join(d, name + ".json"), "w", encoding="utf-8").write(json.dumps(prov))


def shaders():
    core = os.path.join("assets", "minecraft", "shaders", "core")
    bh = os.path.join(WORK, "betterhud_1_21_6", core, "rendertype_text.vsh")
    uui_dir = os.path.join(WORK, "uui_1_21_x")
    uui = os.path.join(uui_dir, core, "rendertype_text.vsh")
    if os.path.exists(bh) and os.path.exists(uui):
        src = open(bh, encoding="utf-8").read()
        if "make_hud()" not in src:
            i = src.index("void main()")
            j = src.index("{", i) + 1
            glsl = os.path.join(uui_dir, "assets", "minecraft", "shaders", "include", "hud.glsl")
            clip = os.path.exists(glsl) and "uui_clip_distance" in open(glsl, encoding="utf-8").read()
            decl = "\nout float uuiClipDistance;" if clip else ""
            init = "uuiClipDistance = 1.0;" if clip else ""
            setc = "uuiClipDistance = uui_clip_distance(UV2, Color); " if clip else ""
            mfile = os.path.join(WORK, "assets", "minecraft", "shaders", "include", "uui_mask.glsl")
            mask = os.path.exists(mfile) and "uui_mask_inside" in open(mfile, encoding="utf-8").read()
            mimp = "\n#moj_import <minecraft:uui_mask.glsl>" if mask else ""
            mchk = ("if (uui_mask_inside(uui_mask_window(ProjMat, GameTime), (ModelViewMat * vec4(Position, 1.0)).xy)) "
                    "{gl_Position = vec4(2.0, 2.0, 2.0, 1.0); vertexColor = vec4(0.0); texCoord0 = vec2(0.0); "
                    "applyColor = 0; return;}") if mask else ""
            usrc = open(uui, encoding="utf-8").read()
            bb = ""
            bchk = ""
            if "bool uui_bb()" in usrc and "out vec3 uuiBbCorner;" in usrc:
                bb = "\n" + usrc[usrc.index("out vec3 uuiBbCorner;"):usrc.index("void main()")]
                init = "uuiBbCorner = vec3(-1.0, -1.0, -1.0);" + init
                bchk = ("vec2 uuiUi = ceil(2 / vec2(ProjMat[0][0], -ProjMat[1][1])); "
                        "bool uuiBh = Position.y >= uuiUi.y && ProjMat[3].x == -1 && "
                        "(((int(Position.y) >> HEIGHT_BIT) >> MAX_BIT) & 1) == 1; "
                        "if (!uuiBh && uui_bb()) {applyColor = 0; sphericalVertexDistance = -1.0e6; "
                        "cylindricalVertexDistance = -1.0e6; return;}")
            smap = ""
            scall = ""
            if "uui_smap_vertex(" in usrc and "out vec2 uuiMapUv;" in usrc:
                a = usrc.index("out vec2 uuiMapUv;")
                b = usrc.index("flat out vec4 uuiMapPaintB;") + len("flat out vec4 uuiMapPaintB;")
                smap = "\n" + usrc[a:b] + "\n#moj_import <minecraft:uui_screenmap_vertex.glsl>"
                k = usrc.index("if (uui_smap_vertex(")
                d = 0
                e = usrc.index("{", k)
                for e in range(e, len(usrc)):
                    if usrc[e] == "{":
                        d += 1
                    elif usrc[e] == "}":
                        d -= 1
                        if d == 0:
                            break
                scall = usrc[k:e + 1].replace("vertexColor = vec4(1.0);", "vertexColor = vec4(1.0); applyColor = 0;")
            bb += smap
            hook = (init + scall + mchk + bchk + "if (make_hud()) {" + setc + "vertexColor = Color; texCoord0 = UV0; applyColor = 0; "
                    "sphericalVertexDistance = -1.0e6; cylindricalVertexDistance = -1.0e6; return;}")
            src = src[:i] + decl + "\n#moj_import <hud.glsl>" + mimp + bb + "\n" + src[i:j] + hook + src[j:]
        for dst in (bh, uui):
            if open(dst, encoding="utf-8").read() != src:
                open(dst, "w", encoding="utf-8", newline="\n").write(src)
        print("Shader rendertype_text digabung (BetterHud + UltimateUI).")
    if LIGHT_TEXT:
        for name in ("rendertype_text.fsh", "rendertype_text_intensity.fsh"):
            f = os.path.join(uui_dir, core, name)
            if not os.path.exists(f):
                continue
            s = open(f, encoding="utf-8").read()
            if "UUI_BB_MASK_LEFT" not in s:
                continue
            s = re.sub(r"const float UUI_BB_MASK_(LEFT|RIGHT)\[256\] = float\[256\]\([^;]*\);\n", "", s)
            s = re.sub(r"float uui_bb_corner_alpha\(vec3 corner\) \{.*?\n\}\n", "", s, flags=re.S)
            s = re.sub(r"\s*if \(uuiBbCorner\.x >= 0\.0\) \{\s*color\.a \*= uui_bb_corner_alpha\(uuiBbCorner\);\s*\}", "", s)
            open(f, "w", encoding="utf-8", newline="\n").write(s)
            print(f"Shader {name} diringankan (tanpa mask sudut UUI).")
    meta = json.loads(open(os.path.join(WORK, "pack.mcmeta"), encoding="utf-8").read())
    entries = meta.get("overlays", {}).get("entries", [])
    names = [e.get("directory") for e in entries]
    if "uui_1_21_x" not in names:
        return
    after = names[names.index("uui_1_21_x") + 1:]
    fmt = meta["pack"].get("pack_format", 64)
    for e in entries:
        d = e.get("directory")
        if d not in after:
            continue
        lo = e.get("min_format")
        hi = e.get("max_format")
        f = e.get("formats")
        if isinstance(f, dict):
            lo, hi = f.get("min_inclusive", lo), f.get("max_inclusive", hi)
        elif isinstance(f, list) and len(f) == 2:
            lo, hi = f
        if lo is None or hi is None or not (lo <= fmt <= hi):
            continue
        for name in ("entity.vsh", "entity.fsh"):
            src_f = os.path.join(uui_dir, core, name)
            dst_f = os.path.join(WORK, d, core, name)
            if os.path.exists(src_f) and os.path.exists(dst_f):
                data = open(src_f, "rb").read()
                if open(dst_f, "rb").read() != data:
                    open(dst_f, "wb").write(data)
                print(f"Shader {name} di {d} diganti versi UltimateUI.")


def extras():
    junk = os.path.join(WORK, "assets", "rizz", "resourcepack")
    if os.path.isdir(junk):
        shutil.rmtree(junk)
        print("Folder salah tempat dihapus: assets/rizz/resourcepack")
    src = os.path.join(HERE, "extra")
    if not os.path.isdir(src):
        return
    n = 0
    for root, dirs, files in os.walk(src):
        for f in files:
            sp = os.path.join(root, f)
            dp = os.path.join(WORK, os.path.relpath(sp, src))
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            data = open(sp, "rb").read()
            if not os.path.exists(dp) or open(dp, "rb").read() != data:
                open(dp, "wb").write(data)
            n += 1
    print(f"Extra assets: {n} file")


def wpath(rel):
    return os.path.join(WORK, *rel.split("/"))


def wrel(p):
    return os.path.relpath(p, WORK).replace(os.sep, "/")


def wjson(p, obj):
    open(p, "w", encoding="utf-8").write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def shrink(p, cap):
    im = Image.open(p)
    w, h = im.size
    if max(w, h) <= cap:
        return False
    f = cap / max(w, h)
    size = (max(1, round(w * f)), max(1, round(h * f)))
    im.convert("RGBA").convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA").save(p)
    return True


def nsid(v):
    return v if ":" in v else "minecraft:" + v


def vehicles():
    mdir = wpath(f"assets/{VEH_NS}/models/item")
    if not os.path.isdir(mdir):
        return
    names = {f[:-5] for f in os.listdir(mdir) if f.endswith(".json")}
    alias = 0
    for n in sorted(names):
        for c, k in VEH_COLOR_ALIAS.items():
            if n.endswith("_" + c):
                t = n[:-len(c)] + k
                if t in names:
                    wjson(os.path.join(mdir, n + ".json"), {"parent": f"{VEH_NS}:item/{t}"})
                    alias += 1
                break
    groups = {}
    for n in sorted(names):
        j = json.load(open(os.path.join(mdir, n + ".json"), encoding="utf-8"))
        if "elements" not in j:
            continue
        base = {k: j[k] for k in ("parent", "ambientocclusion", "gui_light", "display", "elements") if k in j}
        key = json.dumps(base, sort_keys=True, separators=(",", ":"))
        groups.setdefault(key, []).append((n, j))
    geo = 0
    for key, items in groups.items():
        if len(items) < 2:
            continue
        gid = "geo_" + hashlib.md5(key.encode()).hexdigest()[:10]
        open(os.path.join(mdir, gid + ".json"), "w", encoding="utf-8").write(key)
        for n, j in items:
            child = {"parent": f"{VEH_NS}:item/{gid}"}
            if "textures" in j:
                child["textures"] = j["textures"]
            wjson(os.path.join(mdir, n + ".json"), child)
        geo += 1
    refs = set()
    for root, dirs, files in os.walk(WORK):
        if os.path.basename(root) != "models" and os.sep + "models" + os.sep not in root + os.sep:
            continue
        for f in files:
            if not f.endswith(".json"):
                continue
            try:
                j = json.load(open(os.path.join(root, f), encoding="utf-8"))
            except Exception:
                continue
            tex = j.get("textures") if isinstance(j, dict) else None
            for v in (tex or {}).values():
                if isinstance(v, str) and not v.startswith("#"):
                    refs.add(nsid(v))
    cut = set()
    for root, dirs, files in os.walk(WORK):
        if os.path.basename(root) != "atlases":
            continue
        for f in files:
            if not f.endswith(".json"):
                continue
            p = os.path.join(root, f)
            j = json.load(open(p, encoding="utf-8"))
            out = []
            for s in j.get("sources", []):
                r = nsid(s.get("resource", ""))
                if s.get("type") == "single" and r.startswith(VEH_NS + ":"):
                    sp = nsid(s.get("sprite", r))
                    if sp not in refs and r not in refs:
                        cut.add(r)
                        continue
                out.append(s)
            if len(out) != len(j.get("sources", [])):
                j["sources"] = out
                wjson(p, j)
    keep = set()
    for root, dirs, files in os.walk(WORK):
        if os.path.basename(root) == "atlases":
            for f in files:
                if f.endswith(".json"):
                    for s in json.load(open(os.path.join(root, f), encoding="utf-8")).get("sources", []):
                        keep.add(nsid(s.get("resource", "")))
    tdir = wpath(f"assets/{VEH_NS}/textures")
    dropped = shrunk = 0
    for root, dirs, files in os.walk(tdir):
        for f in files:
            if not f.endswith(".png"):
                continue
            p = os.path.join(root, f)
            r = VEH_NS + ":" + wrel(p)[len(f"assets/{VEH_NS}/textures/"):-4]
            if r in cut and r not in keep and r not in refs:
                os.remove(p)
                dropped += 1
            elif shrink(p, VEH_MAX):
                shrunk += 1
    print(f"Kendaraan: {alias} model warna dialihkan, {geo} geometri digabung, {dropped} texture dibuang, {shrunk} texture jadi max {VEH_MAX}px")


def optimize():
    gone = 0
    for root, dirs, files in os.walk(WORK):
        for f in files:
            p = os.path.join(root, f)
            r = wrel(p)
            if r in STRIP or any(r.startswith(s) for s in STRIP if s.endswith("/")) or STRIP_RE.match(r):
                os.remove(p)
                gone += 1
    ui = wpath("assets/minecraft/font/uiimages.json")
    if os.path.exists(ui):
        j = json.load(open(ui, encoding="utf-8"))
        keep = []
        for pr in j.get("providers", []):
            m = re.match(r"minecraft:font/images/(.+\.png)$", pr.get("file", ""))
            if m and m.group(1).startswith(UI_DROP):
                t = wpath("assets/minecraft/textures/font/images/" + m.group(1))
                if os.path.exists(t):
                    os.remove(t)
                    gone += 1
                continue
            keep.append(pr)
        if len(keep) != len(j.get("providers", [])):
            j["providers"] = keep
            wjson(ui, j)
    logo = wpath(LOGO[0])
    if os.path.exists(logo) and shrink(logo, LOGO[1]):
        print(f"Logo loading diperkecil ke {LOGO[1]}px")
    print(f"Optimasi: {gone} file dibuang")
    vehicles()


def squash(out):
    opts = os.path.join(HERE, "options.toml")
    with open(opts, "w", encoding="utf-8") as f:
        f.write(f"""pack_directory = '{WORK.replace(os.sep, "/")}'
output_file_path = '{CACHE.replace(os.sep, "/")}'
recompress_compressed_files = true
zip_compression_iterations = 1
zip_spec_conformance_level = 'disregard'
size_increasing_zip_obfuscation = true

['assets/riizzweapons/sounds/**/*.ogg']
channels = 1

['**/*.png']
image_data_compression_iterations = 1
color_quantization_target = 'none'
skip_alpha_optimizations = true

['**/*?.{{vsh,fsh,glsl}}']
shader_source_transformation_strategy = 'keep_as_is'

['betterhud_*/**']
force_include = true

['ia_overlay_*/**']
force_include = true

['1_2*/**']
force_include = true

['26_*/**']
force_include = true

['uui_*/**']
force_include = true

['**/*.ttf']
force_include = true

['assets/minecraft/optifine/**']
force_include = true

['assets/misc/**']
force_include = true
""")
    r = subprocess.run([PS, opts])
    if r.returncode != 0:
        if os.path.exists(CACHE):
            os.remove(CACHE)
        sys.exit("PackSquash gagal (lihat pesan di atas).")
    shutil.copyfile(CACHE, out)


if __name__ == "__main__":
    ver = sys.argv[1] if len(sys.argv) > 1 else input("Versi pack (contoh 1.0): ").strip()
    out = os.path.join(HERE, f"RizzCityV{ver}.zip")
    download()
    before = os.path.getsize(SRC)
    extract()
    fonts()
    shaders()
    extras()
    optimize()
    squash(out)
    after = os.path.getsize(out)
    os.remove(SRC)
    url = publish(out, ver)
    print(f"Uploaded: {url}")
    set_url(url)
    sync_lobby()
    print("Sekarang: /hud reload + /iareload di RizzCity DAN Lobby, lalu relog.")
    print(f"\nSelesai: {out}\n{before / 1e6:.2f} MB -> {after / 1e6:.2f} MB")
