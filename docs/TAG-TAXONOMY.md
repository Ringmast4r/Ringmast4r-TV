# Tag taxonomy (TMDB-aligned)

Controlled vocabulary for tagging every film. Both Plex and ErsatzTV read
these from each film's `.nfo` sidecar (`<genre>` + `<tag>`) and embedded tags. Channels are
queries against these fields.

## Rules
- Values lowercase, hyphenated, singular: `sci-fi`, `martial-arts`.
- A film gets its TMDB GENREs (1-3) + any number of TAGs.
- ERA is NOT a tag - derive from year. `90s Nostalgia` stays a source-based channel.
- QUALITY/RESOLUTION is NOT a tag - read from the probe.
- Vocabulary is a contract: no ad-hoc strings, add here first.

## GENRE (field: genre) - adopted 1:1 from TMDB so it auto-fills
| our genre | TMDB id | | our genre | TMDB id |
|-----------|--------|-|-----------|--------|
| action | 28 | | history | 36 |
| adventure | 12 | | horror | 27 |
| animation | 16 | | music | 10402 |
| comedy | 35 | | mystery | 9648 |
| crime | 80 | | romance | 10749 |
| documentary | 99 | | sci-fi | 878 (Science Fiction) |
| drama | 18 | | thriller | 53 |
| family | 10751 | | war | 10752 |
| fantasy | 14 | | western | 37 |
(TMDB "TV Movie" 10770 ignored for films.)

## TAG (field: tag) - LOCKED set, mostly auto from TMDB keywords
| tag | source | TMDB keyword id(s) |
|-----|--------|--------------------|
| gamer | auto | 41645 based-on-video-game, 282 video-game |
| hacker | auto | 2157 hacker, 303918 computer-hacker |
| heist | auto | 10051 heist, 191845 bank-heist, 250043 art-heist |
| martial-arts | auto | 779 martial-arts, 780 kung-fu |
| holiday | auto | 207317 christmas |
| dystopian | auto | 359337 post-apocalyptic, 4565 dystopia |
| superhero | auto | 9715 superhero, 9717 based-on-comic |
| monster | auto | 1299 monster |
| noir | auto | 9807 film-noir |
| cult | auto | 374649 cult-film |
| spy | auto | 470 spy, 5265 espionage |
| sports | auto | 333328 sport |
| biopic | auto | 9672 based-on-true-story |
| retro | MANUAL | none - curation call (pre-2000 candidate, human confirm) |
| kids | DERIVED | genre:family AND certification in (G, PG) |

## CANDIDATE tags (TMDB-ready) - each a possible niche channel
| tag | TMDB keyword id |
|-----|-----------------|
| zombie | 12377 |
| vampire | 3133 |
| time-travel | 4379 |
| anime | 210024 |
| slasher | 12339 |
| robot | 14544 |
| alien | 9951 |

## CHANNEL -> QUERY map (example lineup)
| Ch | Channel | Built from |
|----|---------|-----------|
| 02 | Movies | type:movie AND height<=1080 |
| 03 | Hack The Planet | folder/source + tag:hacker |
| 04 | Documentaries | genre:documentary |
| 05 | TV Series | folder/source |
| 06 | Horror | genre:horror |
| 07 | Cartoons | source: TV SERIES/Animated Series |
| 08 | Sci-Fi | genre:sci-fi |
| 09 | Crime | genre:crime |
| 10 | Westerns | genre:western |
| 11 | Extended Cut | edition/source |
| 12 | 90s Nostalgia | source-based (a dedicated folder or share) |
| 13 | Comedy | genre:comedy |
| 14 | Kids | genre:family OR tag:kids |
| 15 | Retro | tag:retro |
| 16 | Gamer | tag:gamer |
| 17 | Action | genre:action |
| 99 | Commercials | source: COMMERCIALS |

## Phase 2 enrichment pipeline (TMDB -> local db + NFO)
For each film (matched by title + year):
1. GET /3/search/movie?query=<title>&year=<year>  -> tmdb_id (verify year).
2. GET /3/movie/{id}?append_to_response=keywords,release_dates  -> genres[], keywords[],
   overview, runtime, vote_average, certification, poster_path.
3. Map genre_ids -> genres (table above); keyword_ids -> tags (tag-map.json).
4. Apply manual/derived tags (retro, kids).
5. Write to local db + a Kodi-style `.nfo` per film (read by Plex AND ErsatzTV).

Optional local metadata DB tables (if you keep one):
- tmdb_meta(title, year, tmdb_id, overview, runtime, rating, certification, release_date, poster_path, updated_at)
- film_tag(title, year, tag, source)        -- source: tmdb-keyword | tmdb-genre | manual | rule
Unmatched/low-confidence titles get queued for manual review (no silent guesses).
