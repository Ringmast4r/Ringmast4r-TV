# Gotchas: every trap, with fixes

Everything non-obvious that cost real time building a 38-channel station.
Rule 0 is first because it took the whole host down. Twice.

## 0. Never bulk-WRITE to slow storage while the station streams

Bulk downloads written to an ntfs-3g (FUSE) disk starved the transcoder:
ffmpeg could not read source files fast enough, produced empty HLS playlists,
every channel 404'd, and the engine got OOM-killed. The host's load spiked so
hard that even SSH started dropping.

Symptoms: logs spam `HlsSessionWorker.TrimPlaylist read empty playlist?` then
`Trim playlist failure; will return not found for channel N` for ALL channels;
the engine shows `Exited (137)`.

Fix and prevention:
- Kill the writer. A stuck writer in D-state (uninterruptible I/O) only clears
  once FUSE flushes; that is normal, wait it out.
- Throttle bulk writes hard: `ionice -c3 nice -n19 wget --limit-rate=3m ...`,
  or download while nobody is watching, or write to a different disk and move
  files during off-hours.

## 0.1 Never SCAN and STREAM at the same time (the read version of rule 0)

A full library scan ffprobes every file. Streaming transcodes with ffmpeg.
Both hammer the disk; on single-threaded ntfs-3g FUSE they starve each other.
Observed: load 157 on 72 cores, ffmpeg stuck in D-state (kill -9 does
nothing), docker stop hangs, the scan itself frozen.

Recovery: stop the whole container/VM/CT that runs the engine. That halts new
disk I/O so the stuck processes drain; load falls back in ~30 s. Bring it up
and let the scan finish untouched.

Procedure after any big library change:
1. Stop the player container so nobody can stream, then trigger the scan.
2. Leave it alone. Restarting the engine mid-scan cancels the scan.
   A 12k-file re-index over ntfs-3g takes 60-90 min; slow is normal.
3. Scan done, reset playouts, start the player.

Real fix: keep media on ext4/xfs/zfs. FUSE ntfs-3g simply cannot do both jobs
at once.

## 0.2 Channels empty while the DB clearly HAS the items? Rebuild the search index

SmartCollections (`tag:horror`) query the LUCENE SEARCH INDEX, not SQLite.
After a big tagging or rename pass the DB can be fully populated while
channels still come up nearly empty. Do NOT re-scan files to fix this (that is
the slow, dangerous ffprobe pass). Rebuild the index from the DB: stop the
engine, delete the `search-index` folder inside the config volume, start the
engine (it reindexes from the DB on startup, ~30 s, no file I/O), then reset
every playout. Channels went from 0-1 items to fully populated in ~2 min.

## 0.3 "No discriminators matched the discriminator value ''"

Schedule items are table-per-type; you inserted a base `ProgramScheduleItem`
row without its subtype row. See CHANNELS.md. Repair:

```sql
INSERT INTO ProgramScheduleFloodItem (Id)
  SELECT psi.Id FROM ProgramScheduleItem psi
  WHERE psi.Id NOT IN (SELECT Id FROM ProgramScheduleFloodItem)
    AND psi.Id NOT IN (SELECT Id FROM ProgramScheduleOneItem)
    AND psi.Id NOT IN (SELECT Id FROM ProgramScheduleDurationItem)
    AND psi.Id NOT IN (SELECT Id FROM ProgramScheduleMultipleItem);
```

## 1. Stop the engine before editing its SQLite DB

The scanner holds the write lock; live writes fail silently (SQLITE_BUSY).
`docker stop ersatztv`, edit, `docker start ersatztv`. Push SQL via a file and
`.read /tmp/x.sql` instead of fighting nested quote escaping over ssh.

The REST API is tiny and the useful bits are:
`POST /api/libraries/{id}/scan` and `POST /api/channels/{num}/playout/reset`.
Everything else you configure in the UI or the DB.

## 2. No GPU means 480p, and 4K jams everything

Software x264 transcodes 4K at under 0.4x real time and throws libx264 errors
that jam the channel. On CPU-only hosts: profile at 480p veryfast, and scope
every collection to `Height BETWEEN 1 AND 1080` (also drops Height=0
corrupt/unprobed files). A resolution change needs a playout reset per channel
to take effect.

## 3. The scanner only descends into SUBFOLDERS

Files sitting loose in a library path's root are silently skipped: 0 added,
LastScan still updates, no error anywhere. Put media at least one folder deep.

## 4. Never point a library path at a Windows drive root over SMB

Drive roots contain `System Volume Information`, ACL-locked even to the share
user; the scanner throws an unhandled UnauthorizedAccessException and aborts
the ENTIRE scan. Share and mount subfolders only.

## 5. Everything scans as a "movie" in a movie library

TV episodes and commercials in a movie library become Movie rows (no Episode
rows, no Show structure). Collections filter on `mv.MovieId`. If you want real
Show/Season/Episode handling, use a separate Shows library.

## 6. The absolute-URL rewrite (why the player's nginx conf looks like that)

ErsatzTV embeds one absolute URL per channel master playlist, built from the
request's Host header. Two traps:

- Hard-coding `X-Forwarded-Proto https` makes a tunnel work but breaks LAN
  (https URL on an http-only port = ERR_SSL_PROTOCOL_ERROR).
- `proxy_set_header Host $host` strips the port (`$host` has no port), the
  engine emits a portless URL, and the browser dials port 80:
  ERR_CONNECTION_REFUSED. Use `$http_host`.

Fix (in player/default.conf): pass `$http_host` and `$scheme` through, and
sub_filter every absolute scheme+host you serve down to relative `/iptv/`.
Requires `proxy_set_header Accept-Encoding ""` plus m3u8 MIME types in
`sub_filter_types`, or sub_filter never sees the playlist bodies.

## 7. Network-mounted media vs reboots (docker bind gotcha)

A docker bind mount does NOT see a filesystem mounted after the container
started; the engine just sees an empty directory and every channel dies with
`PlayoutItemDoesNotExistOnDisk`. After remounting on the host you must restart
the engine container. Prevention: fstab the mounts with
`nofail,_netdev,x-systemd.automount` so first access mounts them on demand.

## 8. Playout resets can race engine startup

A reset fired immediately after `docker start` can build 0 items. Wait ~10 s
after startup, then reset again. Corrupt source files (no moov atom) get
logged as WRN and skipped; harmless, and the height scope excludes them.

## 9. Player behavior notes

- Autoplay tries sound-on; when the browser blocks it, it falls back to muted
  and shows a TAP TO UNMUTE pill.
- Number keys buffer one second so multi-digit channels (10, 12, 99) work.
- An empty/dead channel shows an on-screen status (with the reason) instead of
  a black screen, and every tune + HLS error is logged to the console with a
  plain-English explanation. Open devtools before asking why a channel is
  dark; the answer is usually printed there.
