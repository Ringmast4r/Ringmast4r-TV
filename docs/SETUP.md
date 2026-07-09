# Setup: from a folder of media to a running station

This is the full path from zero to flipping channels. Example host IP used
throughout: `192.168.1.50`. Substitute yours.

## 1. The architecture

```
MEDIA SOURCES                      ENGINE HOST                          VIEWER
-------------                      -----------                          ------
local disk  ---------------+
  /path/to/movies          |  mounted read-only
                           +->  /media/movies -------+
SMB share from another PC -+                         |
  (optional, see scripts/)                           v
                              +--------------------------------------+
                              | docker: ersatztv  (port 8409)        |
                              |   scans media -> builds 24/7 playouts|
                              |   transcodes on tune-in -> HLS+XMLTV |
                              +----------------+---------------------+
                                               | /iptv/*
                              +----------------v---------------------+
                              | docker: etv-player (nginx, port 8410)|
                              |   serves index.html                  |    LAN:    http://192.168.1.50:8410
                              |   proxies /iptv/* to the engine      | -> public: optional tunnel
                              |   rewrites absolute URLs -> relative |
                              +--------------------------------------+
```

Key mental model: a channel's schedule "runs" 24/7 on paper. ErsatzTV
pre-computes a timeline pinned to the wall clock (just database rows, free).
Video only transcodes when someone tunes in, and you join mid-program.

## 2. Media layout

- Mount media into the engine container read-only.
- Point library paths at folders whose CONTENT sits in subfolders:
  `/media/movies/MOVIES/Alien (1979).mkv` scans;
  `/media/movies/Alien (1979).mkv` (loose in the path root) is silently skipped.
- Never point a library path at a Windows drive root over SMB: the
  `System Volume Information` folder is ACL-locked and aborts the whole scan.
- Name files `Title (Year).ext`. Add Kodi-style `.nfo` sidecars if you want
  genre/tag channels (see docs/TAG-TAXONOMY.md); ErsatzTV reads them on scan.

## 3. Bring it up

```
docker compose up -d
```

Open `http://192.168.1.50:8409`, add a Local library pointing at
`/media/movies`, and let the scan finish. Scanning ffprobes every file:
on a fast disk it is quick; over FUSE/ntfs-3g budget 60-90 min per 10k files
and do not stream while it runs (see GOTCHAS rule 0.1).

## 4. The transcode profile

Settings > FFmpeg Profiles. One profile is shared by every channel here.

- CPU only: 480p, preset veryfast. Do not be a hero; live 1080p x264 on many
  channels will fall behind real time.
- NVENC: 720p at 4000 kbps is a sweet spot if your library is mostly SD/720p
  sources. 1080p at 8000 kbps if your sources deserve it.
- Scope every channel's content to `Height BETWEEN 1 AND 1080` (SQL recipes do
  this): it excludes 4K (which jams software transcode) and Height=0
  corrupt/unprobed files.

Changing resolution later requires a playout reset per channel to take effect.

## 5. Channels

Two ways:

1. The UI: Collections or Smart Collections, then a Schedule (shuffle flood),
   then a Playout. Fine for a few channels.
2. Raw SQL against the engine's SQLite DB. Faster for 30 channels and fully
   reproducible. Complete recipes, column maps and the table-per-type trap:
   [CHANNELS.md](CHANNELS.md).

Channel numbering tip: leave channel 1 unused by the engine. The web player
injects its TV Guide as channel 1.

Streaming mode for every channel: `HLS Segmenter` (`StreamingMode=4`).
Browsers cannot play the default MPEG-TS.

## 6. The player and the URL rewrite (read this one)

The watch page fetches `/iptv/channels.m3u`, builds the sidebar, and plays
`/iptv/channel/N.m3u8` via hls.js. nginx proxies `/iptv/` to the engine.

The trap: ErsatzTV embeds ONE absolute URL in each channel's master playlist,
built from the Host header it receives. If that absolute URL survives to the
browser, LAN http and tunnel https each break in a different way. The fix
lives in `player/default.conf`:

- `proxy_set_header Host $http_host;` (NOT `$host`, which strips the port and
  produces a portless URL that dials port 80 and gets connection-refused).
- `sub_filter` every scheme+host you serve down to the relative `/iptv/` path,
  so the browser resolves scheme and host itself.

Edit the sub_filter list to your real LAN IP and hostname before first run.

## 7. Operating it

```
# rescan the library (player off if your disk is slow):
curl -s -X POST http://192.168.1.50:8409/api/libraries/1/scan

# rebuild one channel's timeline (after collection/profile changes):
curl -s -X POST http://192.168.1.50:8409/api/channels/6/playout/reset
```

A SmartCollection captures items at playout-BUILD time: after a scan grows the
library you must reset playouts or channels keep the old snapshot.

If media lives on a network mount, add `nofail,_netdev,x-systemd.automount` to
its fstab entry on the host. A reboot that comes up before the NAS otherwise
leaves the engine staring at an empty directory and every channel dark
(docker bind mounts do not see filesystems mounted after container start;
restart the container after remounting).

## 8. Going public (optional)

Point a Cloudflare Tunnel (or any reverse proxy) at the PLAYER port (8410),
not the engine. Add your public hostname to the sub_filter list. Remember:
no built-in auth, and only serve content you have the rights to distribute.

## 9. Extras

- Commercials channel: [COMMERCIALS.md](COMMERCIALS.md).
- Feeding channels from another PC's drives over SMB:
  `scripts/setup-windows-shares.ps1`, plus an fstab CIFS mount on the engine
  host.
- The same engine can feed a real CRT: run a small HLS relay and a Raspberry
  Pi player (FieldStation42) for hardware channel flipping with an IR remote.
  Out of scope here, but the engine side is identical.
