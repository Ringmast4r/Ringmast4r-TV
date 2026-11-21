import socket, json, time, urllib.request
BASE="http://127.0.0.1:4242"; CH=2
def mpv(prop):
    try:
        s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(2);s.connect('/tmp/mpvsocket')
        s.sendall((json.dumps({"command":["get_property",prop],"request_id":1})+"\n").encode());time.sleep(0.15)
        d=s.recv(2000).decode();s.close()
        for ln in d.split("\n"):
            try:
                o=json.loads(ln)
                if o.get("request_id")==1: return o.get("data")
            except: pass
    except Exception: return None
def server_up():
    try: return urllib.request.urlopen(BASE+"/",timeout=3).getcode()==200
    except Exception: return False
def tune(ch):
    try: urllib.request.urlopen("%s/player/channels/%d"%(BASE,ch),timeout=8)
    except Exception: pass
def playing():
    a=mpv("time-pos"); time.sleep(2); b=mpv("time-pos")
    return isinstance(a,(int,float)) and isinstance(b,(int,float)) and b>a
for _ in range(120):
    if server_up(): break
    time.sleep(2)
print("server up; tuning ch%d"%CH, flush=True)
for attempt in range(40):
    tune(CH); time.sleep(6)
    if playing(): print("ch%d PLAYING (try %d)"%(CH,attempt+1), flush=True); break
    print("not playing, retry %d"%(attempt+1), flush=True); time.sleep(4)
else:
    print("gave up", flush=True)
