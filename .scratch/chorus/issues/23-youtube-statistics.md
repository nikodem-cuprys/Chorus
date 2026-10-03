# YouTube statistics available to the Publishing dashboard

Type: research
Status: resolved
Blocked by: none

## Question

The final milestone adds a dashboard with upload status and statistics (ticket 12). Which statistics can a single user read for their own videos through the YouTube Data API and the YouTube Analytics API (views, watch time, likes, comments, retention, per playlist), which OAuth scopes each needs beyond the upload scope from ticket 04, what they cost in quota, and whether the extra scopes change Google's verification or the private lock for unaudited projects. Resolves with those facts, so the dashboard's contents can be chosen.

## Answer

Researched on 2026-10-03 against Google's own documentation. The pages were read through a tool that summarises, so exact wording should be re-checked on the linked pages before it is quoted.

- **Two sources.** The Data API gives lifetime counters per video, nearly live: views, likes, dislikes (owner only), comments. The Analytics API gives watch time, average view duration and percentage, daily series, traffic sources, geography, subscribers gained and audience retention, but 48 to 72 hours late. Retention is one video per request. Thumbnail impressions and click-through rate are not in either API.
- **Upload status.** `videos.list` returns upload status, failure and rejection reasons, privacy status and processing progress (parts done, time left) to the owner. No field says a video is locked private by an unaudited project; Chorus has to infer that from its own setting.
- **Playlists.** The Data API has only the item count. Playlist views, watch time, average view duration and saves come from Analytics.
- **Scopes.** The `youtube` scope covers every Data API read. Analytics needs one more, `yt-analytics.readonly`; the monetary scope is not needed. The user enables the YouTube Analytics API in their Cloud project and reconnects once. Correction to ticket 04: adding to a playlist does not accept `youtube.upload`, so Publishing needs `youtube`, which makes `youtube.upload` redundant.
- **Quota.** Each list call costs 1 unit whatever the number of ids, so refreshing 200 videos every hour, in batches of 50, costs about 150 to 250 of the 10,000 daily units. Unbatched it would be 4,800, so batching is required. Analytics has a separate quota at 1 unit per request; its default limit is not published. Once a day is enough, since the data moves once a day.
- **Verification, audit and tokens.** The Analytics scope changes nothing: no YouTube scope is on Google's restricted list, personal use stays exempt from verification, and the compliance audit is still needed only to lift the private lock. Ticket 04 is confirmed: in Testing status the refresh token expires after 7 days, so the consent screen must be "In production".
- **The private lock is the real limit.** Nothing in the documentation says the lock blocks reading statistics, but a locked video can be watched only by the owner and invited people, so its numbers stay near zero, and YouTube never shows geography or demographics for private or unlisted videos. For an unaudited project the statistics are meaningful only for hand-uploaded public videos, which the same token can read.
- **Policy.** Statistics may be stored longer than 30 days if authorisation is re-checked every 30 days. Show the latest data and date older data, no derived metrics beyond simple arithmetic, YouTube attribution on the panel, and delete the data within 7 days of disconnecting.

Not confirmed from a primary source: the 50-id limit per `videos.list` request; whether Analytics returns views and watch time for private videos and counts the owner's own playbacks; that the private lock has no effect on reads; the Analytics default quota; whether these scopes are classed "sensitive"; and one policy sentence about "audited developers with analytics use cases (starting June 01, 2026)" that may bear on keeping long history.

Full findings: [research/youtube-statistics.md](../research/youtube-statistics.md)
