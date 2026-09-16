<div align="center">

<img width="100%" alt="RINGMAST4R TV" src="https://capsule-render.vercel.app/api?type=waving&color=0:000000,100:7F1D7B&height=220&section=header&text=RINGMAST4R%20TV&fontSize=60&fontColor=ffffff&animation=twinkling&fontAlignY=35&desc=Web%20%7C%20Docker%20%7C%20ErsatzTV%20%7C%20IPTV&descSize=16&descAlignY=58"/>

`Web` [`Docker`](https://www.docker.com/) [`ErsatzTV`](https://ersatztv.org/) `IPTV` - Run your own 24/7 cable TV station from your media library: themed channels, a Prevue-style guide, and a CRT-green web player. Built on ErsatzTV.

[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=600&size=20&pause=1000&color=7F1D7B&center=true&vCenter=true&multiline=true&repeat=true&width=950&height=90&lines=Run+your+own+24%2F7+cable+TV+station+from+your+media+library%3A+themed...%3BWeb+%2F+Docker+%2F+ErsatzTV+%2F+IPTV)](https://git.io/typing-svg)

<br>

[![Project](https://img.shields.io/badge/Project-Ringmast4r--TV-7F1D7B?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Ringmast4r/Ringmast4r-TV)
[![Format](https://img.shields.io/badge/Format-Docker-000000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Ringmast4r/Ringmast4r-TV/tree/main)

[![Stars](https://img.shields.io/github/stars/Ringmast4r/Ringmast4r-TV?style=flat-square&color=7F1D7B)](https://github.com/Ringmast4r/Ringmast4r-TV/stargazers)
[![Forks](https://img.shields.io/github/forks/Ringmast4r/Ringmast4r-TV?style=flat-square&color=7F1D7B)](https://github.com/Ringmast4r/Ringmast4r-TV/network/members)
[![Repo Size](https://img.shields.io/github/repo-size/Ringmast4r/Ringmast4r-TV?style=flat-square&color=7F1D7B)](https://github.com/Ringmast4r/Ringmast4r-TV)
[![Last Commit](https://img.shields.io/github/last-commit/Ringmast4r/Ringmast4r-TV?style=flat-square&color=7F1D7B)](https://github.com/Ringmast4r/Ringmast4r-TV/commits/main)

</div>

---

# RINGMAST4R // TV

Turn your own media library into a 24/7 cable TV station: themed channels that run
around the clock, a Prevue-style scrolling guide on channel 1, and a CRT-green web
player you can open on anything with a browser. You join every show mid-program,
like real cable. There is no on-demand, no pause, no library browsing. It is TV.

![Ringmast4r TV](player/og-image.png)

Built on [ErsatzTV](https://ersatztv.org/) (the fake-live-TV engine), [hls.js]
(browser playback), nginx, and Docker. This repo is the full recipe: the player,
the proxy config that makes browser playback actually work, channel-building
SQL, a tag taxonomy, a commercials downloader, and every gotcha that cost us a
weekend so it does not cost you one.

<a id="what-you-get"></a>
## `> what_you_get`

- 24/7 channels built from folders or tag queries (Movies, Horror, Cartoons,
  Sci-Fi, Westerns, Commercials, whatever your library supports).
- Channel 1 is a client-side TV guide: NOW/NEXT per channel, live clock,
  auto-scroll, built from the engine's XMLTV feed, zero transcode cost.
- A watch page with channel flipping (arrows, number keys with a digit buffer so
  99 works), mobile drawer, tap-to-unmute, an on-screen status overlay that says
  WHY a channel is dark, and console logging for every tune.
- Schedules are pinned to the wall clock and cost nothing until someone tunes
  in; video only transcodes while somebody is watching.
- Optional: a retro commercials channel fed from archive.org (script included).

<a id="quickstart"></a>
## `> quickstart`

1. Install Docker (with the NVIDIA container toolkit if you have a GPU).
2. Clone this repo and edit `docker-compose.yml`: point the media volume at your
   library (read-only, and point at subfolders, never a drive root).
3. Edit `player/default.conf`: put your LAN IP (and public hostname if you have
   one) into the `sub_filter` list. This step is what makes HLS work in a
   browser; the comments in the file explain the trap.
4. `docker compose up -d`
5. Open the engine UI at `http://<host>:8409`, add your media as a library,
   let it scan, then build channels (UI, or SQL recipes in
   [docs/CHANNELS.md](docs/CHANNELS.md)).
6. Watch at `http://<host>:8410`.

Full walkthrough with channel SQL, schedules and troubleshooting:
[docs/SETUP.md](docs/SETUP.md).

<a id="the-one-rule"></a>
## `> the_one_rule`

**Never scan the library and stream at the same time if your media sits on a
slow filesystem** (ntfs-3g FUSE, some network mounts). Both are heavy I/O; on a
single-threaded FUSE driver they starve each other and can take the whole host
down. Scan with the player off, then stream. War story and recovery steps in
[docs/GOTCHAS.md](docs/GOTCHAS.md).

<a id="hardware-reality-check"></a>
## `> hardware_reality_check`

| Setup | Experience |
|-------|-----------|
| Any x86 box, CPU only | Works. Cap the transcode profile at 480p veryfast and exclude 4K sources; software x264 cannot do 4K live. 480p is period-correct for the CRT aesthetic anyway. |
| NVIDIA GPU (NVENC) | 720p/1080p live transcode is effortless. Use the `-nvidia` image. One mid-range card handles many concurrent channels. |
| Media on ext4/xfs/zfs | No special care needed. |
| Media on ntfs-3g / FUSE | Read the one rule above. Seriously. |

Match the transcode resolution to your sources: if most of your library is SD,
a 1080p profile just upscales noise and wastes bandwidth.

<a id="repo-layout"></a>
## `> repo_layout`

| Path | What |
|------|------|
| `docker-compose.yml` | Engine + player, one command up |
| `player/index.html` | The watch page (single file, no build step) |
| `player/default.conf` | nginx: static page + `/iptv/` proxy + the URL rewrite that makes HLS work on LAN and tunnel |
| `docs/SETUP.md` | Full build walkthrough |
| `docs/CHANNELS.md` | Channel recipes: folder collections and tag-driven SmartCollections, raw SQL included |
| `docs/GOTCHAS.md` | Every trap we hit, with fixes |
| `docs/TAG-TAXONOMY.md` | A locked tag vocabulary (TMDB-aligned) so channels stay queryable |
| `docs/COMMERCIALS.md` | The retro commercials channel |
| `scripts/dl_commercials.py` | archive.org commercials/bumpers downloader with .nfo sidecars |
| `scripts/setup-windows-shares.ps1` | Optional: feed channels from a Windows PC over SMB |

<a id="going-public-optional"></a>
## `> going_public_optional`

The player works great LAN-only. If you expose it (for example through a
Cloudflare Tunnel to the player port), remember there is no auth built in:
anyone with the URL can watch. Gate it with your tunnel provider's access
rules, and only serve content you have the rights to distribute.

<a id="credits"></a>
## `> credits`

[ErsatzTV](https://github.com/ErsatzTV/ErsatzTV) does the heavy lifting.
[hls.js](https://github.com/video-dev/hls.js) plays it.
[The Internet Archive](https://archive.org) supplies the retro commercials.
Aesthetic: every cable box and Prevue Guide channel of the 1990s.

MIT licensed. Build your own station.

---

<div align="center">

<img width="100%" alt="RINGMAST4R TV footer" src="https://capsule-render.vercel.app/api?type=waving&color=0:7F1D7B,100:000000&height=120&section=footer&text=RINGMAST4R%20%2F%2F%20IPTV&fontSize=18&fontColor=ffffff&fontAlignY=65"/>

</div>
