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
                        ├──> crt-hls relay (:8421)  GPU downscale to 720x480 H.264, 2.8 Mbit/s HLS
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
  tuned to it (NVENC `scale_cuda` inside the ErsatzTV container).
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
   overscan margins, starts the remote listener, tunes a start channel and runs
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
   Each streamed channel points at `http://ENGINE_HOST:8421/iptv/channel/<engine #>.m3u8`.
   Then build: `env/bin/python station_42.py -r` and `env/bin/python station_42.py -w`.
8. **Relays on the engine host:** copy [`relay/crt-hls/`](relay/crt-hls) to
   `/opt/crt-hls/` and [`relay/guide-digest/`](relay/guide-digest) to
   `/opt/crt-relay/`, install the two `.service` files in `/etc/systemd/system/`,
   then `sudo systemctl enable --now crt-hls crt-relay`. They expect the
   ErsatzTV container to be named `ersatztv` with NVENC available.
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
| `fs42/station_manager.py` | `video_seek_timeout` 10 -> 60 s (an HLS channel takes 10-15 s to warm up; 10 s gave "technical difficulties"). 12-hour clock. |
| `fs42/guide_builder.py` + new `fs42/ersatz_guide.py` | The on-screen guide shows real titles and times for streamed channels, from the guide digest. |
| `fs42/fs42_server/api/schedules.py`, `summary.py` | Same listings in the web guide. Streamed channels report a non-zero schedule window, or the web guide skips them. |
| `fs42/fs42_server/static/guide.html`, `guide_frame.html` | AM/PM times, click a row to tune the TV, mouse-wheel scroll, cache-busted iframe. |
| `fs42/fs42_server/api/player.py` | Volume steps of 10% on the perceptual (`amixer -M`) scale. |
| `fs42/pi/remote_controller.py` | Grabs the IR device exclusively so key presses do not leak to the console. |
| `fs42/reception.py`, `field_player.py` | A short static "flick" effect for channel changes. |
| new `pi_boot_tune.py` | Waits for the player at boot, tunes the start channel and retries until it actually plays. |
| new `fs42/pi/channel_banner.py` | Experimental on-screen channel and volume banner. Not started by `xinitrc`. |

<a id="the-dial"></a>
## `> the_dial`

| CRT # | Channel | Source |
|------:|---------|--------|
| 1 | Guide | Prevue-style guide (local) |
| 2-4 | The Matrix trilogy | `loop` channels from local 480p files |
| 5 | TV Series | engine 5 |
| 6 | Documentaries | engine 4 |
| 7 | Hack The Planet | engine 3 |
| 8 | Horror | engine 6 |
| 9 | Cartoons | engine 7 |
| 10 | Sci-Fi | engine 8 |
| 11 | Crime | engine 9 |
| 12 | Westerns | engine 10 |
| 13 | Music Videos | engine 27 |
| 14 | Extended Cuts | engine 11 |
| 15 | Movies | engine 2 |
| 16 | Action | engine 15 |
| 17 | Comedy | engine 13 |
| 18 | Kids | engine 14 |
| 19 | Adventure | engine 18 |
| 20 | Thriller | engine 16 |
| 23 | Mystery | engine 26 |
| 24 | War | engine 25 |
| 33-40 | Drama, History, Family, Biopic, Romance, Zombie, Monster, Time Travel | engine 31-38 |

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
- **Changing to a streamed channel takes 10-15 s**: the relay starts an encode on demand.
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
| `fieldstation42/confs/` | The 30 channel configs (`ENGINE_HOST` placeholder) |
| `relay/crt-hls/` | The 480p relay and its systemd unit |
| `relay/guide-digest/` | The guide digest and its systemd unit (`crt-relay.service`) |
