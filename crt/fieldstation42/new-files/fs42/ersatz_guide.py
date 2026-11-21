# Bridge: fetch a compact guide digest from the engine host (port 8420) for streaming channels.
import json, time, urllib.request, datetime
_cache = {"t": 0.0, "data": None}
TTL = 45.0
def _num(station):
    try: return station["streams"][0]["url"].split("/channel/")[1].split(".m3u8")[0]
    except Exception: return None
def _digest(station):
    try: base = station["streams"][0]["url"].split("/iptv/")[0]
    except Exception: return None
    dbase = base.rsplit(":", 1)[0] + ":8420"
    now = time.time()
    if _cache["data"] is not None and now - _cache["t"] < TTL: return _cache["data"]
    try:
        raw = urllib.request.urlopen(dbase + "/guide.json", timeout=6).read()
        _cache["data"] = json.loads(raw); _cache["t"] = now
    except Exception:
        return _cache["data"]
    return _cache["data"]
def slots(station, start_time, window=5400):
    num = _num(station)
    if not num: return None
    data = _digest(station)
    progs = data.get(num) if data else None
    if not progs: return None
    sa = start_time.timestamp(); ea = sa + window
    out = []
    for item in sorted(progs, key=lambda x: x[1]):
        title, st, sp = item[0], item[1], item[2]
        if sp <= sa or st >= ea: continue
        seg_s = st if st > sa else sa; seg_e = sp if sp < ea else ea
        out.append((title, seg_e - seg_s, st < sa, sp > ea))
    return out or None
def schedule_blocks(station, sdt=None, edt=None):
    num = _num(station)
    if not num: return None
    data = _digest(station)
    if data is None: return None
    progs = data.get(num)
    if not progs: return []
    if sdt is None: sdt = datetime.datetime.now()
    if edt is None: edt = sdt + datetime.timedelta(hours=6)
    sa = sdt.timestamp(); ea = edt.timestamp()
    out = []
    for item in sorted(progs, key=lambda x: x[1]):
        title, st, sp = item[0], item[1], item[2]
        if sp <= sa or st >= ea: continue
        dur = sp - st
        out.append({
            "content": [{"title": title, "duration": dur, "tag": "content", "content_type": "feature", "media_type": "video"}],
            "start_time": datetime.datetime.fromtimestamp(st).isoformat(),
            "end_time": datetime.datetime.fromtimestamp(sp).isoformat(),
            "title": title, "reel_blocks": None,
            "plan": [{"path": "", "skip": 0, "duration": dur, "is_stream": True, "content_type": "feature", "media_type": "video"}],
        })
    return out
