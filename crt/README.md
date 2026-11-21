# RINGMAST4R // TV on a real CRT

The same 24/7 station, on a tube TV in the room. A Raspberry Pi 3B runs
[FieldStation42](https://github.com/shane-mason/FieldStation42) (mpv, IR-remote
channel flipping, a Prevue-style guide channel) and plays the engine's channels
out of its composite jack. The GPU box does the heavy lifting; the Pi only plays
a light 480p stream, so a 1 GB Pi 3B flips channels smoothly.

This folder is the working setup, copied off a running Pi and engine host, with
addresses and passwords replaced by placeholders.

<a id="how-it-fits"></a>
## `> how_it_fits`

```
media library ──> ErsatzTV engine (:8409, full-res, feeds the web player)
                        │
                        ├──> crt-hls relay (:8421)  GPU downscale to 720x480 H.264, 2.8 Mbit/s, 1 s HLS segments
                        │          │
                        └──> guide digest (:8420)   XMLTV -> small JSON (now..+6h)
                                   │
              Raspberry Pi 3B ─────┘   FieldStation42 + mpv under a tiny X session
                     │
               3.5 mm AV jack ──> composite ──> CRT "Video" input
```

- **The web player stays full-res.** The CRT gets its own 480p copy from the
  relay, so lowering the CRT never lowers the public stream.
- **The relay carries one channel at a time** and only encodes while the Pi is
  tuned to it (NVENC `scale_cuda` inside the ErsatzTV container). It waits 0.8 s
  before starting a channel, so channels you flip past never start an encode,
  and it stops the encode 20 s after the TV stops asking (guide, local channel, off).
  It also reads the TV's current channel from FieldStation42 (`TV_HOST:4242/player/status`)
  and keeps the streamed channels just above and below it encoding, so channel up/down
  lands on a running stream in about 1 s instead of 4-7 s.
- **One numbering:** each engine channel number is the CRT dial number, so the web
  player and the tube TV agree. A CRT stream URL is `/iptv/channel/<dial #>.m3u8`.
- **The guide digest exists because parsing the full XMLTV on the Pi took ~20 s**
  and froze the guide. The engine host parses it and serves ~60-180 KB of JSON.

<a id="hardware"></a>
## `> hardware`

| Part | Notes |
|------|-------|
| Raspberry Pi 3B | Raspberry Pi OS **Lite, Bookworm, 64-bit**. Lite leaves RAM and GPU for video. |
| 3.5 mm 4-pole (TRRS) to 3x RCA cable | **Wired backwards on most camcorder cables: video comes out the RED plug.** Red into the TV's yellow Video In; yellow + white are audio. |
| Tube TV with composite in | Select the **Video** input (not S-Video, not the tuner). |
| Flirc USB IR receiver | Lets any IR remote change channels (`remote_controller.py -d flirc`). The TV's own remote does not control the Pi. |
| USB Wi-Fi adapter (optional) | The built-in Wi-Fi works too. A 2.4 GHz MT7601U dongle was used here. |
| 5 V / 2.5 A supply | A 2 A brick throttles the Pi (check `vcgencmd get_throttled`; `0x0` is good). |

<a id="setup"></a>
## `> setup`

1. **Flash** Raspberry Pi OS Lite (Bookworm, 64-bit) with Raspberry Pi Imager.
   Set the user, SSH and Wi-Fi in Imager's settings.
2. **Packages:**
   `sudo apt install mpv ffmpeg git python3-venv python3-pip python3-dev python3-tk cifs-utils xserver-xorg xinit matchbox-window-manager`
   (`python3-tk` is required: the guide channel imports tkinter at load.)
3. **Composite out:** apply [`pi/config.txt.snippet`](pi/config.txt.snippet) to
   `/boot/firmware/config.txt` (`vc4-kms-v3d,composite=1`, `display_auto_detect=0`), reboot.
4. **Auto-start:** console auto-login (`sudo raspi-config nonint do_boot_behaviour B2`),
   then copy [`pi/bash_profile`](pi/bash_profile) to `~/.bash_profile` and
   [`pi/xinitrc`](pi/xinitrc) to `~/.xinitrc`. The profile forces the composite
   connector on and runs `startx`; the xinitrc turns off blanking, sets the CRT
   overscan margins, starts the remote listener and runs
   the player.
5. **mpv:** copy [`pi/mpv.conf`](pi/mpv.conf) to `~/.config/mpv/mpv.conf`
   (GPU output + V4L2 hardware H.264 decode, subtitles off, 15 s cache).
6. **FieldStation42:**
   ```bash
   git clone https://github.com/shane-mason/FieldStation42 ~/FieldStation42
   cd ~/FieldStation42
   git checkout $(cat /path/to/crt/fieldstation42/UPSTREAM_COMMIT)
   bash install.sh </dev/null
   git apply /path/to/crt/fieldstation42/fieldstation42-changes.patch
   cp -r /path/to/crt/fieldstation42/new-files/* .
   ```
   The patch is against the commit in `UPSTREAM_COMMIT`; on a newer
   FieldStation42 apply it by hand.
7. **Channels:** copy [`fieldstation42/confs/`](fieldstation42/confs) into
   `~/FieldStation42/confs/` and replace `ENGINE_HOST` with your engine host.
   Each streamed channel points at `http://ENGINE_HOST:8421/iptv/channel/<dial #>.m3u8`.
   `confs/main_config.json` boots to the guide (`"start_channel": 1`), uses a
   12-hour clock and gives streams 60 s to start (`"video_seek_timeout": 60`).
   Then build the local channels: `env/bin/python station_42.py -r` and `env/bin/python station_42.py -w`.
8. **Relays on the engine host:** copy [`relay/crt-hls/`](relay/crt-hls) to
   `/opt/crt-hls/` and [`relay/guide-digest/`](relay/guide-digest) to
   `/opt/crt-relay/`, install the two `.service` files in `/etc/systemd/system/`,
   then `sudo systemctl enable --now crt-hls crt-relay`. They expect the
   ErsatzTV container to be named `ersatztv` with NVENC available. The relay
   encodes on GPU 1 (`-hwaccel_device 1`); use `0` on a one-GPU box.
   In ErsatzTV's settings set the HLS segmenter idle timeout to 15 s
   (`ffmpeg.segmenter.timeout_seconds`) and the initial segment count to 1, so
   channels the TV leaves stop encoding quickly.
9. **Schedules:** [`pi/crontab.txt`](pi/crontab.txt) re-extends schedules every
   3 days (`station_42.py -w`) and restarts the player. Without it, the local
   channels run dry when their week runs out.
10. **Wi-Fi (if not set in Imager):** set the country first
    (`sudo raspi-config nonint do_wifi_country US`); until then both radios stay
    rfkill-blocked. Then use [`pi/wifi.nmconnection.example`](pi/wifi.nmconnection.example).

Optional: [`pi/fstab.example`](pi/fstab.example) mounts a movie share for
`loop` channels that play files directly. Streamed channels do not need it.

<a id="what-the-patch-changes"></a>
## `> what_the_patch_changes`

| File | Change |
|------|--------|
| `fs42/liquid_blocks.py` | **Guide lag fix.** `playback_duration()` used `timedelta.seconds`, which is 0 for a block of exactly one day (every `loop` channel). The guide then stepped one second at a time: one rebuild took 110 s on a Pi 3B, and leaving the guide waited for it. With `total_seconds()` a rebuild takes under 0.5 s and guide-to-channel takes 0.3 s. |
| `fs42/station_player.py` | Leaving the guide waits at most 1 s for its window to close, then terminates it, instead of `join()` with no timeout. |
| `field_player.py` | `start_channel: 1` works: the guide sits at index 0, which the start-channel check treated as "not found". |
| `fs42/guide_builder.py` + new `fs42/ersatz_guide.py` | The on-screen guide shows real titles and times for streamed channels, from the guide digest. |
| `fs42/fs42_server/api/schedules.py`, `summary.py` | Same listings in the web guide. Streamed channels report a non-zero schedule window, or the web guide skips them. |
| `fs42/fs42_server/static/guide.html`, `guide_frame.html` | AM/PM times, click a row to tune the TV, mouse-wheel scroll, cache-busted iframe. |
| `fs42/fs42_server/api/player.py` | Volume steps of 10% (upstream default is 2%). |
| new `fs42/pi/channel_banner.py` | Experimental on-screen channel and volume banner. Not started by `xinitrc`. |

The clock format, stream timeout and start channel are settings in
`confs/main_config.json`, not code changes. Upstream already grabs the IR device
exclusively and uses the perceptual `amixer -M` volume scale.

<a id="the-dial"></a>
## `> the_dial`

Dial number = engine number = web player number for every streamed channel.

| # | Channel | # | Channel | # | Channel | # | Channel |
|--:|---------|--:|---------|--:|---------|--:|---------|
| 1 | Guide (local) | 15 | Movies | 29 | Spy | 43 | Disney |
| 2 | The Matrix | 16 | Action | 30 | Martial Arts | 44 | Pixar |
| 3 | The Matrix Reloaded | 17 | Comedy | 31 | Adult Swim | 45 | James Bond 007 |
| 4 | The Matrix Revolutions | 18 | Kids | 32 | Holiday | 46 | Star Trek |
| 5 | TV Series | 19 | Adventure | 33 | Drama | 47 | Saturday Morning |
| 6 | Documentaries | 20 | Thriller | 34 | History | 48 | The X-Files |
| 7 | Hack The Planet | 21 | 90s Nostalgia | 35 | Family | 49 | Stephen King |
| 8 | Horror | 22 | Fantasy | 36 | Biopic | 50 | Slashers |
| 9 | Cartoons | 23 | Mystery | 37 | Romance | 51 | Tarantino |
| 10 | Sci-Fi | 24 | War | 38 | Zombie | 52 | Movie Sagas |
| 11 | Crime | 25 | Vampire | 39 | Monster | 53 | Sci-Fi TV |
| 12 | Westerns | 26 | Superhero | 40 | Time Travel | 54 | Prime Time |
| 13 | Music Video | 27 | Dystopian | 41 | Infomercials | 55 | Science |
| 14 | Extended Cut | 28 | Alien | 42 | Commercials | | |

On the CRT, channels 2-4 are `loop` channels playing 480p files stored on the Pi,
so they tune instantly; the engine has its own 2-4 (one film each) for the web
player. Everything from 5 up streams from the engine. The new channels are
tag-driven smart collections (`tag:disney`, `tag:"star-trek"`, `tag:science`, ...):
the engine's search splits tags on hyphens, so pick tag words that no other
channel's query uses.

<a id="gotchas"></a>
## `> gotchas`

- **Blank CRT, Pi playing fine:** the RCA plugs are swapped. Video is the red plug.
- **mpv refuses the composite output** ("Chosen connector is disconnected" /
  "Failed to create KMS"): composite has no hotplug, so the kernel reports it
  disconnected. Force it on before X starts:
  `echo on | sudo tee /sys/class/drm/card0-Composite-1/status` (done in `bash_profile`).
- **An old DSI touchscreen steals the display:** set `display_auto_detect=0` and unplug it.
- **Picture cut off at the edges:** tune the four `xrandr` margins in `xinitrc` by eye.
- **Wi-Fi shows "unavailable":** no Wi-Fi country set, so both radios are rfkill
  soft-blocked. `raspi-config nonint do_wifi_country US`, then `rfkill unblock wifi`.
  (`iw` and `rfkill` live in `/usr/sbin`, which a plain SSH session may not have on its PATH.)
- **mpv will not start on raw MPEG-TS over HTTP** under `vo=gpu`; serve HLS.
- **1080p on a Pi 3B stutters**, even with hardware decode, and it has no real HEVC
  decode. That is why the relay sends 480p.
- **Do not put `profile=fast` in `mpv.conf`**: it errors on this mpv build and risks a black screen.
- **Local `loop` channels need a built schedule** (`station_42.py -w`) or the guide is
  empty and the player sticks on the guide.
- **Changing to a streamed channel takes about 7 s**: the engine and the relay both
  start an encode on demand. Local files tune in well under a second.
- **Flipping fast through streamed channels jams the GPU** if every channel you pass
  starts an encode: GeForce cards allow about 8 NVENC sessions, and leftovers fail
  with `OpenEncodeSessionEx failed: incompatible client key (21)`. The relay's 0.8 s
  debounce, its 20 s idle stop and the engine's 15 s segmenter timeout prevent it.
- **The guide freezes for up to two minutes** on a stock FieldStation42 with `loop`
  channels: see `fs42/liquid_blocks.py` in the patch table.
- **mpv's control socket moved** in newer FieldStation42 to `~/FieldStation42/runtime/mpv.socket`.
- **Fixed address:** give the Pi a static address in NetworkManager
  (`nmcli con mod <connection> ipv4.method manual ipv4.addresses <ip>/24 ipv4.gateway <router> ipv4.dns <dns>`)
  so the web remote stays put across power cycles.
- **Wrong guide times:** Raspberry Pi OS defaults to Europe/London. Set the Pi's timezone
  to match the engine (`sudo timedatectl set-timezone America/New_York`).

<a id="blank-tv-checklist"></a>
## `> blank_tv_checklist`

1. Is the Pi playing? `curl localhost:4242/player/status` on the Pi.
2. Is X on the composite output? `xrandr` should show `Composite-1 connected 720x480i`.
3. Is the picture there? `ffmpeg -f x11grab -video_size 720x480 -i :0 -frames:v 1 /tmp/shot.png`
4. Cable: red plug in the yellow jack, AV plug pushed fully into the Pi, TV on Video.

<a id="layout"></a>
## `> layout`

| Path | What |
|------|------|
| `pi/` | Boot and display files: `bash_profile`, `xinitrc`, `mpv.conf`, `config.txt.snippet`, `crontab.txt`, Wi-Fi and fstab examples |
| `fieldstation42/UPSTREAM_COMMIT` | The FieldStation42 commit the patch applies to |
| `fieldstation42/fieldstation42-changes.patch` | All changes to upstream files |
| `fieldstation42/new-files/` | Files added to the FieldStation42 tree |
| `fieldstation42/confs/` | The 55 channel configs (`ENGINE_HOST` placeholder) and `main_config.json` |
| `relay/crt-hls/` | The 480p relay and its systemd unit |
| `relay/guide-digest/` | The guide digest and its systemd unit (`crt-relay.service`) |
