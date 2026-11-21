#!/usr/bin/env python3
# Guide digest: parse ErsatzTV XMLTV (on the engine host), serve a compact JSON the Pi can use cheaply.
import http.server, socketserver, json, time, urllib.request, datetime
import xml.etree.ElementTree as ET
PORT=8420
_cache={"t":0.0,"data":None}
def build():
    now=time.time()
    if _cache["data"] is not None and now-_cache["t"]<60: return _cache["data"]
    raw=urllib.request.urlopen("http://localhost:8409/iptv/xmltv.xml",timeout=20).read()
    root=ET.fromstring(raw)
    id2num={}
    for ch in root.findall("channel"):
        for dn in ch.findall("display-name"):
            t=(dn.text or "").strip()
            if t.isdigit(): id2num[ch.get("id")]=t; break
    nowu=datetime.datetime.now(datetime.timezone.utc)
    lo=nowu-datetime.timedelta(hours=1); hi=nowu+datetime.timedelta(hours=6)
    out={}
    for pr in root.findall("programme"):
        num=id2num.get(pr.get("channel"))
        if not num: continue
        try:
            st=datetime.datetime.strptime(pr.get("start"),"%Y%m%d%H%M%S %z")
            sp=datetime.datetime.strptime(pr.get("stop"),"%Y%m%d%H%M%S %z")
        except Exception: continue
        if sp<lo or st>hi: continue
        out.setdefault(num,[]).append([pr.findtext("title") or "Program", st.timestamp(), sp.timestamp()])
    _cache["data"]=out; _cache["t"]=now
    return out
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        try: body=json.dumps(build()).encode()
        except Exception:
            self.send_response(500); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-cache"); self.end_headers()
        try: self.wfile.write(body)
        except Exception: pass
class T(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads=True; allow_reuse_address=True
if __name__=="__main__":
    print("CRT guide digest :%d"%PORT,flush=True)
    T(("0.0.0.0",PORT),H).serve_forever()
