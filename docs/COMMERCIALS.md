# The commercials channel

Retro commercials and bumpers are what make a homemade station feel like real
broadcast. Two uses:

1. A dedicated channel (we run it as channel 99) that shuffles the whole pool 24/7.
2. Filler between programs on the real channels, theme-matched (ErsatzTV
   Filler Presets: toy ads on the kids channel, trailers on horror, and so on).

## Sourcing clips

The Internet Archive (archive.org) is the primary source: free and
downloadable. Search terms that work well:

- `1990s commercials`, `1980s commercials`
- `Saturday morning cartoon commercials`
- `Cartoon Network bumpers`, `Nickelodeon bumpers`, `MTV idents`
- `vintage movie trailers horror sci-fi`
- `station ID`, `sign off`, `test pattern`, `emergency broadcast test`
- `80s Christmas commercials`

`scripts/dl_commercials.py` automates it: per-theme archive.org queries, pulls
the original video files one pack at a time, skips anything already on disk,
and writes a Kodi/ErsatzTV `.nfo` sidecar next to every clip (tags like
`commercial`, `bumper`, `trailer`, `kids`, `holiday`) so the next library scan
makes them queryable.

```
set COMMERCIALS_DIR=/path/inside/your/media/library/COMMERCIALS
python dl_commercials.py bumpers 25 200 10
python dl_commercials.py general-80s 25 200 10
python dl_commercials.py trailers-horror-scifi 25 200 10
```

Args: `<theme> <max_identifiers> <max_file_MB> <pack_cap_GB>`. Themes and
queries are in the PACKS dict at the top of the script. Aim the destination
INSIDE your media library (one folder deep) so the normal scan picks clips up.

WARNING: if the destination is on the same slow disk the station streams from,
throttle. The full-speed version of this download once took our whole server
down (GOTCHAS.md rule 0).

## Building channel 99

With `.nfo` tags: a SmartCollection with query `tag:commercial` and a shuffle
flood schedule, exactly like any other channel (CHANNELS.md). Path variant if
you skip tagging:

```sql
INSERT INTO CollectionItem (CollectionId, MediaItemId)
SELECT <id>, mv.MovieId FROM MediaFile mf JOIN MediaVersion mv ON mv.Id=mf.MediaVersionId
WHERE mv.MovieId IS NOT NULL AND mv.Height BETWEEN 1 AND 1080
  AND mf.Path LIKE '/media/movies/COMMERCIALS/%'
GROUP BY mv.MovieId;
```

Commercials are short, so a 24/7 playout packs in thousands of items. That is
expected and fine.

After each new download pass: rescan the library, re-widen the collection (or
let the SmartCollection catch them), and reset playout 99.

## Theme folders that worked for us

bumpers, general-80s, general-mixed, kids-cartoon-ads, trailers-horror-scifi,
trailers-action, trailers-comedy, trailers-kids, trailers-western, christmas,
halloween, station-ids, interstitials (test patterns, sign-offs, color bars),
psa, ebs (emergency broadcast tests), infomercials, yule-log, adult-swim
(bumpers).

Filler wiring (pre/mid/post-roll per channel) is ErsatzTV Filler Presets;
build the themed pools first, the wiring is the easy part.
