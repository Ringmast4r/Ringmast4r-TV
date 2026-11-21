#!/usr/bin/env python3
# CRT 480p HLS relay: GPU-downscale ErsatzTV channels to 480p HLS for the weak Pi CRT.
# Public ringmast4r TV stays full-res on ErsatzTV (8409); only the CRT uses this (8421).
import http.server, socketserver, subprocess, threading, time, os
PORT=8421
HLSROOT="/var/lib/docker/volumes/ersatztv-config/_data/crt"
CROOT="/root/.local/share/ersatztv/crt"
MARK="CRTHLS"
_lock=threading.Lock(); _state={"n":None,"proc":None}
def kill_all():
    try: subprocess.run(["docker","exec","ersatztv","sh","-c","for p in $(pgrep -f %s); do kill -9 $p; done"%MARK],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=6)
    except Exception: pass
def ff_cmd(n):
    cd="%s/%d"%(CROOT,n)
    inner=("mkdir -p {cd} && exec ffmpeg -nostdin -hide_banner -loglevel error "
           "-hwaccel cuda -hwaccel_output_format cuda "
           "-i 'http://localhost:8409/iptv/channel/{n}.m3u8?mode=segmenter' "
           "-vf scale_cuda=720:480 -c:v h264_nvenc -preset p4 -rc cbr -b:v 2800k -maxrate 2800k -bufsize 5600k -g 48 -bf 0 "
           "-c:a aac -b:a 128k -ac 2 -metadata comment={m} "
           "-f hls -hls_time 4 -hls_list_size 10 -hls_flags delete_segments+omit_endlist "
           "-hls_segment_filename {cd}/seg%d.ts {cd}/index.m3u8").format(cd=cd,n=n,m=MARK)
    return ["docker","exec","ersatztv","sh","-c",inner]
def ensure(n):
    with _lock:
        if _state["n"]==n and _state["proc"] and _state["proc"].poll() is None: return
        if _state["proc"]:
            try: _state["proc"].terminate()
            except Exception: pass
        kill_all()
        try: os.remove("%s/%d/index.m3u8"%(HLSROOT,n))
        except Exception: pass
        _state["proc"]=subprocess.Popen(ff_cmd(n),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); _state["n"]=n
    for _ in range(60):
        if os.path.exists("%s/%d/index.m3u8"%(HLSROOT,n)): return
        time.sleep(0.4)
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        path=self.path.split("?")[0]
        if path.startswith("/iptv/channel/") and path.endswith(".m3u8"):
            try: n=int(path[len("/iptv/channel/"):-len(".m3u8")])
            except Exception: self.send_response(404); self.end_headers(); return
            ensure(n); idx="%s/%d/index.m3u8"%(HLSROOT,n)
            if not os.path.exists(idx): self.send_response(503); self.end_headers(); return
            out=[]
            for line in open(idx).read().splitlines():
                out.append("/crt/%d/%s"%(n,line) if (line and not line.startswith("#") and line.endswith(".ts")) else line)
            body=("\n".join(out)+"\n").encode()
            self.send_response(200); self.send_header("Content-Type","application/vnd.apple.mpegurl")
            self.send_header("Cache-Control","no-cache"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path.startswith("/crt/"):
            p=path.strip("/").split("/")
            if len(p)==3 and p[1].isdigit() and p[2].endswith(".ts"):
                fp="%s/%s/%s"%(HLSROOT,p[1],p[2])
                if os.path.exists(fp):
                    d=open(fp,"rb").read(); self.send_response(200); self.send_header("Content-Type","video/mp2t")
                    self.send_header("Content-Length",str(len(d))); self.end_headers(); self.wfile.write(d); return
            self.send_response(404); self.end_headers(); return
        self.send_response(404); self.end_headers()
class T(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads=True; allow_reuse_address=True
if __name__=="__main__":
    print("CRT HLS relay :%d"%PORT,flush=True); T(("0.0.0.0",PORT),H).serve_forever()
