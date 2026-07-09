# Channels: recipes

How to build channels fast and reproducibly, straight against ErsatzTV's
SQLite DB. Everything here was learned on a 38-channel station.

DB path inside the engine container:
`/root/.local/share/ersatztv/ersatztv.sqlite3`
(with the compose file here, that lives in the `ersatztv-config` volume:
`docker volume inspect ersatztv-config`).

**STOP the engine before writing to the DB** (the scanner holds the write
lock; live writes fail silently with SQLITE_BUSY):

```
docker stop ersatztv
sqlite3 <db> '.read /tmp/build.sql'
docker start ersatztv
```

## Two kinds of channel

1. **Folder collection**: hand-curated `CollectionItem` rows selected by file
   path. Survives anything except renames.
2. **Tag-driven SmartCollection** (better): the channel is a query like
   `tag:horror`. Give every file a Kodi `.nfo` sidecar with `<genre>` and
   `<tag>` values (vocabulary: TAG-TAXONOMY.md), and the channel fills itself
   as the library grows. A rename never breaks it.

Hyphenated tags must be quoted in queries: `tag:"martial-arts"`,
`tag:"music-video"`.

## The ID convention

Use ONE internal id `I` shared across Channel / Collection (or
SmartCollection) / ProgramSchedule / ProgramScheduleItem / Playout per
channel. The on-screen number is separate. Track your next free `I`.

## Recipe: one channel, raw SQL

```sql
PRAGMA foreign_keys=OFF;
BEGIN;

-- A) folder collection variant: curate by path, transcode-safe height scope
INSERT INTO Collection VALUES(I,'CH MyChannel',0);
INSERT INTO CollectionItem (CollectionId, MediaItemId)
SELECT I, mv.MovieId FROM MediaFile mf JOIN MediaVersion mv ON mv.Id=mf.MediaVersionId
WHERE mv.MovieId IS NOT NULL AND mv.Height BETWEEN 1 AND 1080 AND (
  mf.Path LIKE '%/Some Title (1999)%' OR mf.Path LIKE '%/MY FOLDER/%'
) GROUP BY mv.MovieId;

-- A') SmartCollection variant (instead of A): one row, the query IS the channel
-- INSERT INTO SmartCollection (Id,Name,Query) VALUES(I,'CH MyChannel','tag:horror');

-- B) schedule (columns: FixedStartTimeBehavior,KeepMultiPart,Name,RandomStart,Shuffle,TreatAsShows)
INSERT INTO ProgramSchedule VALUES(I,0,0,'SCHED MyChannel',0,0,0);

-- C) schedule item: base row + the FLOOD subtype row with the SAME Id (required, see below)
--    CollectionType: 0 = Collection, 5 = SmartCollection (set CollectionId or SmartCollectionId to I accordingly)
INSERT INTO ProgramScheduleItem VALUES(I,I,0,NULL,NULL,NULL,0,NULL,0,0,NULL,0,0,0,NULL,NULL,NULL,3,NULL,NULL,NULL,NULL,NULL,NULL,I,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT INTO ProgramScheduleFloodItem VALUES(I);

-- D) channel: clone your first UI-made channel's row, change Id/Name/Number/SortNumber/UniqueId
--    keep StreamingMode=4 (HLS Segmenter). Generate a fresh GUID for UniqueId.

-- E) playout (ChannelId, ..., ProgramScheduleId, ScheduleKind=1 Classic, Seed)
INSERT INTO Playout VALUES(I,I,NULL,NULL,NULL,I,NULL,1,12345);
COMMIT;
```

Then start the engine, wait ~10 s for it to come up, and build the timeline:

```
curl -s -X POST http://localhost:8409/api/channels/<NUM>/playout/reset
```

The watch page discovers new channels from `channels.m3u` automatically.

Column layouts shift between ErsatzTV versions. Before bulk-inserting, make
one channel in the UI and copy its rows (`SELECT * FROM Channel WHERE Id=1;`)
rather than trusting anyone's column list, including this one.

## The table-per-type trap (the classic 0-items failure)

`ProgramScheduleItem` subclasses live in SEPARATE tables:
`ProgramScheduleFloodItem`, `...OneItem`, `...DurationItem`, `...MultipleItem`.
Every schedule item needs its base row AND a subtype row with the same Id.
Miss it and the playout build fails with:

```
No discriminators matched the discriminator value ''
```

and the channel silently builds 0 items. Flood is the normal 24/7 shuffle.

## Useful enums

`PlaybackOrder.Shuffle=3` (in ProgramScheduleItem),
`StreamingMode.HttpLiveStreamingSegmenter=4` (in Channel),
`CollectionType.Collection=0 / SmartCollection=5`,
`PlayoutScheduleKind.Classic=1`.

## Edit, widen, trim

- Widen a folder channel: INSERT more CollectionItem rows, reset the playout.
- Trim: DELETE the CollectionItem rows (engine stopped), reset the playout.
- SmartCollection channels: just fix the Query (or the tags on disk + rescan),
  then reset the playout.
- A live viewer keeps the old stream until they re-tune (flip away and back).

## After every scan

A playout captures its collection at BUILD time. New files do not appear on a
channel until you `playout/reset` it. Scan, then reset, then watch.

## Seasonal channels

Build them like any channel and flip visibility with `Channel.IsEnabled`
(0/1), for example a Holiday channel enabled in December.
