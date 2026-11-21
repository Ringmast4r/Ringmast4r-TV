#!/usr/bin/env python3
"""Channel + volume banner for FieldStation42 on the CRT.
Flashes 'CH N  STATION / title' on channel change and 'VOLUME NN%' on volume
change, via mpv's native OSD (show-text) - drawn over the video, no window."""
import json, re, socket, subprocess, time, urllib.request

STATUS_URL = "http://127.0.0.1:4242/player/status"
MPV_SOCK = "/tmp/mpvsocket"
CH_MS = 5000
VOL_MS = 2000

def mpv_show(text, ms):
    try:
        s = socket.socket(socket.AF_UNIX); s.settimeout(2); s.connect(MPV_SOCK)
        s.send(json.dumps({"command": ["show-text", text, ms]}).encode() + b"\n")
        s.recv(1024); s.close()
    except Exception:
        pass

def get_status():
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=2) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def get_volume():
    try:
        out = subprocess.run(["amixer", "-M", "sget", "PCM"],
                             capture_output=True, text=True, timeout=2).stdout
        m = re.search(r"\[(\d+)%\]", out)
        muted = "[off]" in out
        return (int(m.group(1)) if m else None), muted
    except Exception:
        return None, False

def vol_bar(pct):
    filled = round(pct / 10)
    return "#" * filled + "-" * (10 - filled)

def main():
    last_ch = object()
    last_vol = None
    last_mute = False
    first_vol = True
    while True:
        st = get_status()
        if st and st.get("channel_number") is not None:
            ch = st.get("channel_number")
            net = (st.get("network_name") or "").strip()
            title = (st.get("title") or "").strip()
            if ch != last_ch:
                line = f"CH {ch}   {net}".rstrip()
                if title and title.lower() not in ("unknown", "guide"):
                    line += f"\n{title}"
                mpv_show(line, CH_MS)
                last_ch = ch
        vol, muted = get_volume()
        if vol is not None:
            if not first_vol and (vol != last_vol or muted != last_mute):
                if muted:
                    mpv_show("MUTE", VOL_MS)
                else:
                    mpv_show(f"VOLUME {vol_bar(vol)} {vol}%", VOL_MS)
            last_vol, last_mute, first_vol = vol, muted, False
        time.sleep(0.4)

if __name__ == "__main__":
    main()
