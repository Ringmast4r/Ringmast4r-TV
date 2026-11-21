#!/usr/bin/env python3
# CRT 480p HLS relay (v3, 2026-11-21): GPU-downscale ErsatzTV channels to 720x480 HLS for the Pi CRT.
# Public Ringmast4r TV stays full-res on ErsatzTV (8409); only the CRT uses this relay (8421).
# - 1 s segments + 1 s GOP: a cold channel has a playlist after ~1 s of output.
# - Warm neighbours: the relay reads the TV's current channel from FieldStation42 every second and keeps
#   the streamed channels just above and below it encoding, so channel up/down lands on a running stream.
# - Debounce: a cold channel only starts if the TV still wants it after 0.8 s (flipping past costs nothing).
# - Idle stop: everything stops 20 s after the TV is off/unreachable and no requests arrive; neighbours are
#   dropped after 30 minutes on one channel.
# - GET /status shows what the relay thinks the TV is on and which channels are warm.
import http.server, socketserver, subprocess, threading, time, os, json, urllib.request

PORT = 8421
HLSROOT = "/var/lib/docker/volumes/ersatztv-config/_data/crt"
CROOT = "/root/.local/share/ersatztv/crt"
MARK = "CRTHLS"
TV_STATUS = ["http://TV_HOST:4242/player/status"]
STREAMED = set(range(5, 56))   # dial numbers served here (1 = guide, 2-4 = files on the Pi)
DIAL_MAX = 55
DEBOUNCE = 0.8
SETTLE = 1.5                   # seconds on a channel before its neighbours are warmed
IDLE_STOP = 20
WARM_MAX_AGE = 1800

lock = threading.Lock()
procs = {}                     # channel -> Popen (docker exec client)
want = {"n": None}
tv = {"ch": None, "since": 0.0}
last_req = {"t": 0.0}


def kill_mark(n=None):
    # "[C]RTHLS" so pgrep never matches the sh -c command line that runs it
    pat = "[C]RTHLS_%d_" % n if n is not None else "[C]RTHLS"
    try:
        subprocess.run(["docker", "exec", "ersatztv", "sh", "-c",
                        "for p in $(pgrep -f '%s'); do kill -9 $p; done" % pat],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6)
    except Exception:
        pass


def ff_cmd(n):
    cd = "%s/%d" % (CROOT, n)
    inner = ("mkdir -p {cd} && exec ffmpeg -nostdin -hide_banner -loglevel error "
             "-hwaccel cuda -hwaccel_device 1 -hwaccel_output_format cuda "
             "-i 'http://localhost:8409/iptv/channel/{n}.m3u8?mode=segmenter' "
             "-vf scale_cuda=720:480 -c:v h264_nvenc -preset p4 -rc cbr -b:v 2800k -maxrate 2800k -bufsize 5600k "
             "-g 30 -keyint_min 30 -no-scenecut 1 -forced-idr 1 -bf 0 "
             "-c:a aac -b:a 128k -ac 2 -metadata comment={m}_{n}_ "
             "-f hls -hls_time 1 -hls_list_size 8 -hls_flags delete_segments+omit_endlist+independent_segments+temp_file "
             "-hls_segment_filename {cd}/seg%d.ts {cd}/index.m3u8").format(cd=cd, n=n, m=MARK)
    return ["docker", "exec", "ersatztv", "sh", "-c", inner]


def index_path(n):
    return "%s/%d/index.m3u8" % (HLSROOT, n)


def alive(n):
    p = procs.get(n)
    return p is not None and p.poll() is None


def start(n):  # call with lock held
    if alive(n):
        return
    kill_mark(n)
    try:
        os.remove(index_path(n))
    except Exception:
        pass
    procs[n] = subprocess.Popen(ff_cmd(n), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop(n):  # call with lock held
    p = procs.pop(n, None)
    if p is not None:
        try:
            p.terminate()
        except Exception:
            pass
    kill_mark(n)


def neighbours(c):
    out = []
    for d in (-1, 1):
        m = c + d
        if m < 1:
            m = DIAL_MAX
        elif m > DIAL_MAX:
            m = 1
        if m in STREAMED:
            out.append(m)
    return out


def ensure(n):
    want["n"] = n
    with lock:
        if alive(n) and os.path.exists(index_path(n)):
            return True          # warm: answer at once
        running = alive(n)
    if not running:
        time.sleep(DEBOUNCE)
        if want["n"] != n:
            return False         # viewer already flipped on
        with lock:
            start(n)
    for _ in range(100):
        if want["n"] != n:
            return False
        if os.path.exists(index_path(n)):
            return True
        time.sleep(0.2)
    return True


def poll_tv():
    for u in TV_STATUS:
        try:
            st = json.loads(urllib.request.urlopen(u, timeout=1.5).read())
            return st.get("channel_number")
        except Exception:
            continue
    return None


def manager():
    while True:
        time.sleep(1)
        ch = poll_tv()
        now = time.time()
        with lock:
            if ch is None or ch < 1:
                if now - last_req["t"] > IDLE_STOP:
                    for n in list(procs):
                        stop(n)
                continue
            if ch != tv["ch"]:
                tv["ch"], tv["since"] = ch, now
            keep = set()
            if ch in STREAMED:
                keep.add(ch)
            near = neighbours(ch)
            if now - tv["since"] < WARM_MAX_AGE:
                keep.update(n for n in near if alive(n))        # keep warm ones while flipping
                if now - tv["since"] >= SETTLE:
                    for n in near:
                        start(n)
                        keep.add(n)
            if want["n"] is not None and now - last_req["t"] < 5:
                keep.add(want["n"])                            # a cold start in progress
            for n in list(procs):
                if n not in keep:
                    stop(n)


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        last_req["t"] = time.time()
        path = self.path.split("?")[0]
        if path == "/status":
            with lock:
                body = json.dumps({"tv_channel": tv["ch"], "on_it_for_s": round(time.time() - tv["since"], 1),
                                   "warm": sorted(n for n in procs if alive(n)), "last_wanted": want["n"]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path.startswith("/iptv/channel/") and path.endswith(".m3u8"):
            try:
                n = int(path[len("/iptv/channel/"):-len(".m3u8")])
            except Exception:
                self.send_response(404); self.end_headers(); return
            if ensure(n) is False:
                self.send_response(503); self.end_headers(); return
            idx = index_path(n)
            if not os.path.exists(idx):
                self.send_response(503); self.end_headers(); return
            out = []
            for line in open(idx).read().splitlines():
                out.append("/crt/%d/%s" % (n, line) if (line and not line.startswith("#") and line.endswith(".ts")) else line)
            body = ("\n".join(out) + "\n").encode()
            self.send_response(200); self.send_header("Content-Type", "application/vnd.apple.mpegurl")
            self.send_header("Cache-Control", "no-cache"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if path.startswith("/crt/"):
            p = path.strip("/").split("/")
            if len(p) == 3 and p[1].isdigit() and p[2].endswith(".ts"):
                fp = "%s/%s/%s" % (HLSROOT, p[1], p[2])
                if os.path.exists(fp):
                    d = open(fp, "rb").read()
                    self.send_response(200); self.send_header("Content-Type", "video/mp2t")
                    self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d); return
            self.send_response(404); self.end_headers(); return
        self.send_response(404); self.end_headers()


class T(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    kill_mark(None)   # clear leftovers from a previous run
    threading.Thread(target=manager, daemon=True).start()
    print("CRT HLS relay v3 :%d" % PORT, flush=True)
    T(("0.0.0.0", PORT), H).serve_forever()
