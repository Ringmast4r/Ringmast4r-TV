r"""Commercials and bumpers downloader for Ringmast4r TV.

Pulls archive.org 'original' video files into <COMMERCIALS_DIR>/<theme>/, one
pack at a time, sequentially (no parallel writes), idempotent (skips files
already on disk > 0 bytes), and writes a Kodi/ErsatzTV .nfo sidecar next to
every clip so it gets tagged on the next library scan.

WARNING: if your destination sits on a slow FUSE mount (e.g. ntfs-3g), bulk
writes can starve a streaming ErsatzTV on the same disk. Throttle or download
while nobody is watching. See docs/GOTCHAS.md rule 0.

Usage:  python dl_commercials.py <theme> [max_identifiers] [max_file_mb] [pack_cap_gb]
Themes: see the PACKS dict below.
Destination: set the COMMERCIALS_DIR env var (default ./commercials).
"""
import os, sys, json, time, html, urllib.request, urllib.parse

BASE = os.environ.get("COMMERCIALS_DIR", os.path.join(".", "commercials"))
VIDEXT = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.mpg', '.mpeg', '.webm', '.flv', '.ts'}

# theme -> (archive.org query, nfo tags, destination folder under BASE)
PACKS = {
    'adult-swim':           ('identifier:AdultswimBumps',
                             ['commercial', 'bumper', 'retro', 'adult-swim'], 'Adult Swim Bumpers'),
    'bumpers':              ('(identifier:yt-CNArchive OR identifier:yt-sticksticklyvideo)',
                             ['commercial', 'bumper', 'retro'], 'bumpers'),
    'general-80s':          ('title:(commercials) AND (1980s OR "80s") AND mediatype:movies',
                             ['commercial', 'retro'], 'general-80s'),
    'general-mixed':        ('title:(commercials) AND mediatype:movies',
                             ['commercial', 'retro'], 'general-mixed'),
    'kids-cartoon-ads':     ('title:(commercials) AND (cartoon OR toy OR cereal) AND mediatype:movies',
                             ['commercial', 'kids', 'retro'], 'kids-cartoon-ads'),
    'trailers-horror-scifi':('title:(trailers) AND (horror OR "science fiction" OR scifi) AND mediatype:movies',
                             ['trailer', 'retro'], 'trailers-horror-scifi'),
    'christmas':            ('title:(commercials) AND (christmas OR holiday) AND mediatype:movies',
                             ['commercial', 'holiday', 'retro'], 'christmas'),
    # --- broadcast glue (added 2026-06-15) ---
    'station-ids':          ('title:("station ID" OR idents OR "network promos" OR "station identification") AND mediatype:movies',
                             ['station-id', 'bumper', 'retro'], 'station-ids'),
    'interstitials':        ('title:("test pattern" OR "sign off" OR "sign-off" OR "color bars" OR "please stand by") AND mediatype:movies',
                             ['interstitial', 'retro'], 'interstitials'),
    'psa':                  ('title:(PSA OR "public service announcement") AND mediatype:movies',
                             ['psa', 'retro'], 'psa'),
    'ebs':                  ('title:("emergency broadcast") AND mediatype:movies',
                             ['ebs', 'retro'], 'ebs'),
    'infomercials':         ('title:(infomercial OR infomercials) AND mediatype:movies',
                             ['infomercial', 'retro'], 'infomercials'),
    'yule-log':             ('title:("yule log") AND mediatype:movies',
                             ['yule-log', 'holiday', 'retro'], 'yule-log'),
    'trailers-western':     ('title:(trailers) AND (western) AND mediatype:movies',
                             ['trailer', 'western', 'retro'], 'trailers-western'),
    'trailers-action':      ('title:(trailers) AND (action) AND mediatype:movies',
                             ['trailer', 'action', 'retro'], 'trailers-action'),
    'trailers-comedy':      ('title:(trailers) AND (comedy) AND mediatype:movies',
                             ['trailer', 'comedy', 'retro'], 'trailers-comedy'),
    'trailers-kids':        ('title:(trailers) AND (cartoon OR kids OR family) AND mediatype:movies',
                             ['trailer', 'kids', 'retro'], 'trailers-kids'),
    'halloween':            ('title:(halloween) AND (commercials OR bumpers OR specials) AND mediatype:movies',
                             ['commercial', 'holiday', 'halloween', 'retro'], 'halloween'),
}

def search(q, rows):
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {'q': q, 'fl[]': 'identifier', 'rows': rows, 'output': 'json', 'sort[]': 'downloads desc'}, doseq=True)
    with urllib.request.urlopen(url, timeout=40) as r:
        return [d['identifier'] for d in json.load(r)['response']['docs']]

def meta(ident):
    with urllib.request.urlopen(f"https://archive.org/metadata/{ident}", timeout=40) as r:
        return json.load(r)

def write_nfo(path, title, tags):
    x = ['<?xml version="1.0" encoding="UTF-8"?>', '<movie>',
         f'  <title>{html.escape(title)}</title>']
    for t in sorted(set(tags)):
        x.append(f'  <tag>{html.escape(t)}</tag>')
    x.append('</movie>')
    open(path, 'w', encoding='utf-8').write("\n".join(x))

def fetch(url, dest):
    tmp = dest + '.part'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)
    return os.path.getsize(dest)

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PACKS:
        print("themes:", ", ".join(PACKS)); return
    theme = sys.argv[1]
    max_ids   = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    max_mb    = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    cap_gb    = float(sys.argv[4]) if len(sys.argv) > 4 else 25.0
    q, tags, folder = PACKS[theme]
    out = os.path.join(BASE, folder)
    os.makedirs(out, exist_ok=True)

    print(f"== pack '{theme}' -> {out}")
    ids = search(q, max_ids)
    print(f"   {len(ids)} archive.org identifiers (top by downloads)")
    got = 0; skipped = 0; total = 0
    for n, ident in enumerate(ids, 1):
        if total / 1e9 >= cap_gb:
            print(f"   pack cap {cap_gb} GB reached - stopping"); break
        try:
            m = meta(ident)
        except Exception as e:
            print(f"   [{n}/{len(ids)}] {ident}: meta err {e}"); continue
        d = m.get('dir'); server = m.get('server')
        files = [f for f in m.get('files', [])
                 if f.get('source') == 'original'
                 and os.path.splitext(f['name'])[1].lower() in VIDEXT]
        for f in files:
            if total / 1e9 >= cap_gb:
                break
            sz = int(f.get('size', 0) or 0)
            if sz and sz > max_mb * 1e6:
                continue  # too big for a short-clip pack
            safe = f['name'].replace('/', '_').replace('\\', '_')
            base_noext = os.path.splitext(safe)[0]
            dest = os.path.join(out, safe)
            nfo = os.path.join(out, base_noext + '.nfo')
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                skipped += 1
                if not os.path.exists(nfo):
                    write_nfo(nfo, base_noext, tags)
                continue
            url = f"https://{server}{d}/{urllib.parse.quote(f['name'])}"
            try:
                wrote = fetch(url, dest)
                write_nfo(nfo, base_noext, tags)
                total += wrote; got += 1
                print(f"   [{n}/{len(ids)}] +{wrote/1e6:6.1f}MB  {safe}")
            except Exception as e:
                print(f"   [{n}/{len(ids)}] FAIL {safe}: {e}")
                if os.path.exists(dest + '.part'):
                    try: os.remove(dest + '.part')
                    except OSError: pass
            time.sleep(0.5)  # gentle throttle
    print(f"\n== '{theme}' done: {got} new, {skipped} already had, {total/1e9:.2f} GB this run")

if __name__ == '__main__':
    main()
