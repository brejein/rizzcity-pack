import os
import posixpath
import stat
import subprocess
import sys
import time

import paramiko

import build


def env(name):
    v = os.environ.get(name, "")
    if not v:
        sys.exit(f"Secret {name} belum di-set.")
    return v


def sftp(prefix):
    t = paramiko.Transport((env(prefix + "_HOST"), int(os.environ.get(prefix + "_PORT") or 22)))
    t.connect(username=env(prefix + "_USER"), password=env(prefix + "_PASS"))
    return t, paramiko.SFTPClient.from_transport(t)


def download():
    t, s = sftp("CITY")
    s.get("/plugins/ItemsAdder/output/generated.zip", build.SRC)
    t.close()


def publish(out, ver):
    repo = os.environ["GITHUB_REPOSITORY"]
    token = env("GITHUB_TOKEN")
    d = os.path.join(build.HERE, "publish")
    os.makedirs(d, exist_ok=True)

    def git(*a):
        r = subprocess.run(["git", "-C", d, *a], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("git gagal: " + " ".join(a) + "\n" + r.stderr[-500:])
        return r.stdout.strip()

    git("init", "-q")
    git("checkout", "-q", "--orphan", "pack")
    with open(out, "rb") as f, open(os.path.join(d, "RizzCity.zip"), "wb") as g:
        g.write(f.read())
    git("add", "RizzCity.zip")
    git("-c", "user.name=rizzcity-build", "-c", "user.email=build@rizzcity.local", "commit", "-q", "-m", f"RizzCity V{ver}")
    git("push", "-q", "-f", f"https://x-access-token:{token}@github.com/{repo}.git", "pack:pack")
    sha = git("rev-parse", "HEAD")
    return f"https://raw.githubusercontent.com/{repo}/{sha}/RizzCity.zip"


def edit_ia(prefix, url):
    t, s = sftp(prefix)
    with s.open("/plugins/ItemsAdder/config.yml", "r") as f:
        txt = f.read().decode("utf-8")
    import re
    txt = re.sub(r"(external-host:\s*\n\s*enabled: )\w+(\s*\n\s*url: ).*", lambda m: m.group(1) + "false" + m.group(2) + url, txt)
    txt = re.sub(r"(no-host:\s*\n\s*enabled: )\w+", r"\1true", txt)
    txt = re.sub(r"(self-host:\s*\n\s*enabled: )\w+", r"\1false", txt)
    txt = re.sub(r"skip_url_file_type_check: \w+", "skip_url_file_type_check: true", txt)
    with s.open("/plugins/ItemsAdder/config.yml", "w") as f:
        f.write(txt.encode("utf-8"))
    t.close()


def set_url(url):
    edit_ia("CITY", url)
    edit_ia("LOBBY", url)
    t, s = sftp("PROXY")
    with s.open("/plugins/rizzpack/pack.properties", "w") as f:
        f.write(f"url={url}\nuuid=d69238f2-b7ce-30b0-8262-17cd9490f29d\nforce=false\n".encode("utf-8"))
    t.close()
    print("URL pack di-set di proxy (RizzPack) + ItemsAdder RizzCity/Lobby.")


def walk(s, root):
    out = {}
    stack = [""]
    while stack:
        rel = stack.pop()
        for e in s.listdir_attr(posixpath.join(root, rel) if rel else root):
            p = posixpath.join(rel, e.filename) if rel else e.filename
            if stat.S_ISDIR(e.st_mode):
                stack.append(p)
            elif not e.filename.endswith(".tar.gz"):
                out[p] = e.st_size
    return out


def mkdirs(s, path):
    parts = path.strip("/").split("/")
    cur = ""
    for part in parts:
        cur += "/" + part
        try:
            s.stat(cur)
        except IOError:
            s.mkdir(cur)


def sync_lobby():
    dirs = ["assets", "backgrounds", "compasses", "fonts", "heads", "huds", "images", "layouts", "placeholders", "popups", "shaders", "texts"]
    tc, sc = sftp("CITY")
    tl, sl = sftp("LOBBY")
    for d in dirs:
        src = f"/plugins/BetterHud/{d}"
        dst = f"/plugins/BetterHud/{d}"
        try:
            a = walk(sc, src)
        except IOError:
            continue
        try:
            b = walk(sl, dst)
        except IOError:
            b = {}
            mkdirs(sl, dst)
        for rel in a:
            mkdirs(sl, posixpath.dirname(posixpath.join(dst, rel)))
            with sc.open(posixpath.join(src, rel), "rb") as f, sl.open(posixpath.join(dst, rel), "wb") as g:
                g.write(f.read())
        for rel in b:
            if rel not in a:
                sl.remove(posixpath.join(dst, rel))
    for name in ("font_images_unicode_cache.yml", "items_ids_cache.yml"):
        with sc.open(f"/plugins/ItemsAdder/storage/{name}", "rb") as f, sl.open(f"/plugins/ItemsAdder/storage/{name}", "wb") as g:
            g.write(f.read())
    tc.close()
    tl.close()
    print("Lobby BetterHud + ItemsAdder cache disamakan dengan RizzCity.")


def main():
    ver = (sys.argv[1] if len(sys.argv) > 1 else "") or time.strftime("ci-%Y%m%d-%H%M")
    build.PS = os.path.join(build.HERE, "tool", "packsquash")
    out = os.path.join(build.HERE, f"RizzCityV{ver}.zip")
    download()
    before = os.path.getsize(build.SRC)
    build.extract()
    build.fonts()
    build.shaders()
    build.extras()
    build.squash(out)
    after = os.path.getsize(out)
    url = publish(out, ver)
    print(f"Uploaded: {url}")
    set_url(url)
    sync_lobby()
    print(f"Selesai V{ver}: {before / 1e6:.2f} MB -> {after / 1e6:.2f} MB")
    print("Sekarang: /hud reload + /iareload di RizzCity DAN Lobby, lalu relog.")


if __name__ == "__main__":
    main()
