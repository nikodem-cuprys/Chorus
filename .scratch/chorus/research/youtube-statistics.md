# YouTube statistics for the Publishing dashboard

Ticket: [23-youtube-statistics](../issues/23-youtube-statistics.md). Researched 2026-10-03 against Google/YouTube primary docs only (developers.google.com, support.google.com, and the Analytics API discovery document). Builds on [youtube-upload-api.md](youtube-upload-api.md); facts established there are not repeated. Pages were read through a fetch tool that summarises, so quotations are as that tool returned them; re-check wording against the linked page before relying on an exact phrase.

## TL;DR

- **Two sources of numbers.** The **Data API** gives lifetime counters per video (views, likes, dislikes for the owner, comments), near-live, at 1 quota unit per call. The **Analytics API** gives watch time, average view duration, retention, daily series, traffic sources and playlist metrics, but **48 to 72 hours late**.
- **Playlists have no counters in the Data API.** The playlist resource has only `itemCount`. Playlist views and watch time come from the Analytics API only.
- **Scopes.** The `youtube` scope, already needed for playlist writes, also covers every Data API read the dashboard needs. Analytics needs **one more scope: `yt-analytics.readonly`**. The monetary scope is not needed. Adding a scope means the user must reconnect once.
- **Quota is a non-issue.** Refreshing 200 videos hourly costs about **150 to 250 of the 10,000 daily units**. Analytics has its own quota, 1 unit per request; its default limit is not published. Analytics should be refreshed about once a day, since the data only moves once a day.
- **Token expiry: the earlier research is correct.** Testing status gives a refresh token that dies after 7 days for any YouTube scope. In production (unverified, personal use) does not have that expiry. Analytics scopes change none of this, nor the audit.
- **The private lock is the real limit on what the dashboard shows.** Nothing in the docs says the lock blocks reading statistics. But a private video can only be watched by the owner and people the owner invites, so its numbers will be close to zero, and YouTube shows **no geography or demographics for private or unlisted videos at all**. For an unaudited project, the statistics half of the dashboard will be nearly empty unless the user also tracks hand-uploaded public videos.
- **Policy allows storing statistics** longer than 30 days, provided Chorus checks every 30 days that it is still authorised. Do not invent derived metrics beyond simple arithmetic, and label the numbers as coming from YouTube.

## 1. Data API v3: what the owner can read

### Per video (`videos.list`, or the new `videos.batchGetStats`)

| Field | What it is | Notes |
|---|---|---|
| `statistics.viewCount` | "The number of times the video has been viewed." | Since 2026-08-24 a view is counted "the moment a video begins to play (includes autoplay, hold the pointer over, and click/tap to play)" for all formats. [videos resource](https://developers.google.com/youtube/v3/docs/videos), [revision history, 2026-08-27](https://developers.google.com/youtube/v3/revision_history) |
| `statistics.likeCount` | Number of likes. | [videos resource](https://developers.google.com/youtube/v3/docs/videos) |
| `statistics.dislikeCount` | Number of dislikes. | Private since 2021-12-13: "included in an API response only if the API request was authenticated by the video owner." Chorus is always the owner, so it gets it. [videos resource](https://developers.google.com/youtube/v3/docs/videos) |
| `statistics.commentCount` | Number of comments. | Help says comments are not allowed on private videos, so this stays 0 for locked uploads. [Privacy settings (YouTube Help)](https://support.google.com/youtube/answer/157177?hl=en) |
| `statistics.favoriteCount` | Deprecated 2015-08-28. | "The property's value is now always set to `0`." Do not show it. |
| `contentDetails.duration` | ISO 8601 length. | May differ by about 1 second from the real length. |

`videos.batchGetStats` was added on 2026-06-03. It returns only `viewCount`, `likeCount`, `commentCount`, duration and publish time (no dislikes, no status), costs 1 unit, and has **its own quota bucket of 10,000 units per day**. "Authentication is required to use this method against non-public videos, but is not required for public videos." [videos.batchGetStats](https://developers.google.com/youtube/v3/docs/videos/batchGetStats), [revision history, 2026-06-03](https://developers.google.com/youtube/v3/revision_history) Since `videos.list` returns statistics and status together in one call, Chorus does not need it.

### Upload and processing status (for the status half of the dashboard)

All from `videos.list`. `fileDetails`, `processingDetails` and `suggestions` "are only available to that video's owner"; asking for them without owner authorisation returns 403. [videos.list](https://developers.google.com/youtube/v3/docs/videos/list)

| Field | Values | Dashboard use |
|---|---|---|
| `status.uploadStatus` | `uploaded`, `processed`, `failed`, `rejected`, `deleted` | The main state badge |
| `status.failureReason` | `codec`, `conversion`, `emptyFile`, `invalidFile`, `tooSmall`, `uploadAborted` | Why the upload failed |
| `status.rejectionReason` | `claim`, `copyright`, `duplicate`, `inappropriate`, `legal`, `length`, `termsOfUse`, `trademark`, `uploaderAccountClosed`, `uploaderAccountSuspended` | Why YouTube rejected it. `length` is the unverified-account 15 minute limit |
| `status.privacyStatus` | `private`, `public`, `unlisted` | Shows the effect of the private lock |
| `status.publishAt` | Scheduled publish time; only settable while private | Optional |
| `status.madeForKids`, `status.containsSyntheticMedia` | Booleans | Confirm what Chorus set |
| `processingDetails.processingStatus` | `processing`, `succeeded`, `failed`, `terminated` | Progress badge |
| `processingDetails.processingProgress.partsTotal`, `.partsProcessed`, `.timeLeftMs` | Estimates | A progress bar |
| `processingDetails.processingFailureReason` | `uploadFailed`, `transcodeFailed`, `streamingFailed`, `other` | Why processing failed |
| `processingDetails.thumbnailsAvailability` and the other `*Availability` fields | Availability flags | Rarely useful |

Source for all rows: [videos resource](https://developers.google.com/youtube/v3/docs/videos).

**No field says "locked private because the project is unaudited".** The only visible symptom is `privacyStatus: private`. Chorus must infer the lock from its own "project audited" setting.

### Per playlist

The playlist resource has `snippet`, `status` (`privacyStatus`, `podcastStatus`), `contentDetails.itemCount` ("The number of videos in the playlist"), `player` and `localizations`. **There is no `statistics` part and no view count.** [playlists resource](https://developers.google.com/youtube/v3/docs/playlists) The dashboard can show the item count and privacy from here; playlist views need the Analytics API (section 2).

`playlistItems.list` returns `contentDetails`, `id`, `snippet`, `status` for up to 50 items per page. [playlistItems.list](https://developers.google.com/youtube/v3/docs/playlistItems/list) Chorus already stores the video IDs it uploaded, so this call is only needed to detect that the user changed the playlist by hand.

### Per channel (`channels.list?mine=true&part=statistics`)

| Field | Notes |
|---|---|
| `statistics.viewCount` | "The sum of the number of times all the videos in all formats have been viewed for a channel." |
| `statistics.subscriberCount` | "This value is rounded down to three significant figures." The fetch summary added that the owner gets the exact count; I could not confirm that sentence verbatim (see the last section). |
| `statistics.hiddenSubscriberCount` | Whether the count is public. |
| `statistics.videoCount` | "The number of public videos uploaded to the channel. Note that the value reflects the count of the channel's public videos only, even to owners." **A channel holding only locked private uploads reports 0 here.** Count videos from Chorus's own records instead. |
| `statistics.commentCount` | Deprecated. |

Source: [channels resource](https://developers.google.com/youtube/v3/docs/channels).

### Private and unlisted videos

- The owner can read status and statistics of their own private and unlisted videos when the request carries their OAuth token. The docs say this directly for `batchGetStats` (quoted above). For `videos.list` the page only says the three owner-only parts need the owner; it does not spell out private videos. Treated as confirmed in practice, flagged in the last section.
- The numbers will be small. "Private videos and playlists can only be seen by you and whomever you choose", they are not in search or on the channel, and comments are off. [Privacy settings (YouTube Help)](https://support.google.com/youtube/answer/157177?hl=en)
- Whether the owner's own playbacks of a private video add to `viewCount` is not documented.

## 2. YouTube Analytics API (`reports.query`)

Every request uses `ids=channel==MINE`, `startDate`, `endDate`, `metrics`, and optionally `dimensions`, `filters`, `sort`, `maxResults`. A `video` or `playlist` filter "can specify up to 500 IDs". [reports.query](https://developers.google.com/youtube/analytics/reference/reports/query) Everything below is a channel report, available to a normal channel owner. Content owner reports are a separate set and do not apply.

### Metrics a channel owner gets

| Metric | Meaning | Source |
|---|---|---|
| `views` | Views. Counted from the start of playback since 2026-08-27. | [metrics](https://developers.google.com/youtube/analytics/metrics), [revision history](https://developers.google.com/youtube/analytics/revision_history) |
| `engagedViews` | "viewed past the first frame, or the user clicks/taps to play". The older, stricter count. | [metrics](https://developers.google.com/youtube/analytics/metrics) |
| `estimatedMinutesWatched` | Watch time in minutes. | same |
| `averageViewDuration` | "The average length, in seconds, of video playbacks." | same |
| `averageViewPercentage` | "The average percentage of a video watched during a video playback." Cannot be combined with `liveOrOnDemand`. | same, [channel reports](https://developers.google.com/youtube/analytics/channel_reports) |
| `likes`, `dislikes`, `comments`, `shares` | Counts of each action in the date range. | [metrics](https://developers.google.com/youtube/analytics/metrics) |
| `subscribersGained`, `subscribersLost` | Subscriptions and unsubscriptions. | same |
| `videosAddedToPlaylists`, `videosRemovedFromPlaylists` | Times the video was added to or removed from any playlist. | same |
| `audienceWatchRatio` | "The absolute ratio of viewers watching the video at the given point in the video." Can exceed 1 when viewers rewatch. | same |
| `relativeRetentionPerformance` | Retention "in comparison to all YouTube videos of similar length", 0 to 1. | same |
| `startedWatching`, `stoppedWatching`, `totalSegmentImpressions` | Per-segment retention counts. | same |
| `viewerPercentage` | Share of logged-in viewers in an age or gender bucket. Demographics report only. | same |
| Revenue and ad metrics (`estimatedRevenue` and so on) | Need the monetary scope and Partner Program membership; otherwise 403. Not relevant to Chorus. | [channel reports](https://developers.google.com/youtube/analytics/channel_reports) |

Thumbnail impressions and click-through rate, which YouTube Studio shows, are **not** on the metrics page. Treat them as unavailable through the API.

### Reports that matter for the dashboard

| Report | Dimensions | Filters and limits | Requests for 200 videos |
|---|---|---|---|
| Channel totals | none | optional `video==` list | 1 |
| Daily or monthly series | `day` or `month` | optional `video==` (0 or 1 filter, multiple IDs allowed) | 1 for the channel, or 1 per Work with that Work's video IDs |
| Per-video totals | `video` | Either the Top videos report (`sort` required, `maxResults` 200 or less), or `filters=video==id1,id2,...` with `dimensions=video`: "If you do specify multiple values for one of these filters, you can also add that filter to the list of dimensions". Up to 500 IDs. | 1 |
| Audience retention | `elapsedVideoTimeRatio` (required) | **One video per request**: "the value must specify a single video ID". Optional `audienceType`, `subscribedStatus`. | 200, so fetch on demand when the user opens a chapter |
| Traffic sources | `insightTrafficSourceType` (+ optional `day`) | Errors "if the product of # of queried videos X # of days in date range exceeds 50,000". | 1 |
| Traffic source detail | `insightTrafficSourceDetail` | Needs a traffic source type filter, `sort`, `maxResults` 25 or less. | 1 per source type |
| Geography | `country`; `province` needs `country==US`; `city` needs `sort` and `maxResults` 250 or less | Subject to thresholds below. | 1 |
| Devices | `deviceType`, `operatingSystem` | | 1 |
| Demographics | `ageGroup`, `gender` | `viewerPercentage` only. Subject to thresholds. | 1 |
| Playlist basic and daily | none, or `day` or `month` | `playlist==` filter is required ("exactly 1" filter; multiple IDs allowed). | 1 per Work, or 1 for all with `dimensions=playlist` |

Sources: [channel reports](https://developers.google.com/youtube/analytics/channel_reports), [sample requests](https://developers.google.com/youtube/analytics/sample-requests), [dimensions](https://developers.google.com/youtube/analytics/dimensions).

### Playlist metrics and their recent changes

Playlist reports return two families of metrics. [channel reports](https://developers.google.com/youtube/analytics/channel_reports), [metrics](https://developers.google.com/youtube/analytics/metrics)

- **Aggregated video metrics** (`views`, `engagedViews`, `estimatedMinutesWatched`, `averageViewDuration`): all activity on the playlist's videos that the channel owns, wherever it happened.
- **In-playlist metrics**: activity that happened in the context of the playlist.
  - `playlistViews`, `playlistEstimatedMinutesWatched`, `playlistAverageViewDuration`, `playlistSaves`
  - `playlistStarts`, `viewsPerPlaylistStart`, `averageTimeInPlaylist`: these three count "only playlist views that occurred on the web".

Changes [Analytics revision history](https://developers.google.com/youtube/analytics/revision_history):
- 2024-01-19: `playlistViews`, `playlistEstimatedMinutesWatched`, `playlistAverageViewDuration` and `playlistSaves` added for channel playlist reports.
- 2024-04-22 and 2025-04-22: the `isCurated` dimension was deprecated and is "no longer supported" as of 2024-12-31. Older sample code that sends `isCurated==1` now fails. Use `playlistViews` rather than `views` for in-playlist counts.
- The channel reports page still carried a sentence saying `isCurated` "will be deprecated soon" on the day I read it; the revision history is the authority.

For Chorus, "how much of this Work was listened to" is best shown as `estimatedMinutesWatched` summed over the Work's videos (aggregated family). The in-playlist family only counts listening started from the playlist page.

### Freshness

- "Data processing typically introduces a latency of 48 to 72 hours. Therefore, API responses do not contain data for the most recent days". [Data model](https://developers.google.com/youtube/analytics/data_model) (section added 2026-09-09, per the revision history).
- So the dashboard has two clocks: Data API counters that are current, and Analytics numbers that end two to three days ago. Show the end date of the Analytics data next to it.

### Thresholds that can leave a small channel's reports empty

- "Some YouTube Analytics data is limited when metrics do not meet a certain threshold." The affected data: demographics (age, gender), geography, and "specific traffic sources, such as search terms or external URLs". "The actual thresholds at which data is limited are not published and subject to change at YouTube's discretion." [Data model](https://developers.google.com/youtube/analytics/data_model)
- YouTube Help adds a rule that hits Chorus directly: "You won't see demographics data for private or unlisted videos, regardless of the amount of traffic on your channel", and the same for geography. [Understand limited data in YouTube Analytics](https://support.google.com/youtube/answer/9101241?hl=en)
- The docs do not say that `views`, `estimatedMinutesWatched`, `averageViewDuration` or retention are thresholded. In practice retention for a video with a handful of views may come back empty; that is not documented either way.
- Deleted videos drop out of per-video breakdowns but stay in channel totals, so totals and the sum of rows can disagree. [Data model](https://developers.google.com/youtube/analytics/data_model) This matters for the "old video stays on the channel" regeneration rule only if the user deletes the old video.

### Reporting API (bulk reports)

Chorus would schedule jobs; YouTube then writes one CSV per report type per day, kept for 60 days (30 for backfilled history). [Reporting API reports](https://developers.google.com/youtube/reporting/v1/reports) Google positions it for "high-volume applications that require bulk datasets". [Analytics and Reporting overview](https://developers.google.com/youtube/reporting) **Not worth it for one user**: same scopes, same delay, more moving parts (job management, CSV ingest, backfill replacement), and the targeted queries above already answer every dashboard question in a handful of requests.

## 3. OAuth scopes

| Scope | Console description | Covers |
|---|---|---|
| `youtube.upload` | "Manage your YouTube videos" | `videos.insert` only, as far as the docs confirm. Not accepted by `playlists.insert`, `playlistItems.insert`, `playlistItems.list` or `channels.list`. |
| `youtube` | "Manage your YouTube account" | Uploads, playlist writes, and all Data API reads below. |
| `youtube.force-ssl` | "See, edit, and permanently delete your YouTube videos, ratings, comments and captions" | Accepted wherever `youtube` is. Not needed. |
| `youtube.readonly` | "View your YouTube account" | All Data API reads. Not needed if `youtube` is already granted. |
| `yt-analytics.readonly` | "View YouTube Analytics reports for your YouTube content. This scope provides access to user activity metrics, like view counts and rating counts." | `reports.query` for every non-revenue metric. **This is the one to add.** |
| `yt-analytics-monetary.readonly` | Adds "estimated revenue and ad performance metrics". | Not needed. Revenue also needs Partner Program membership. |

Sources: [Data API OAuth guide](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps), [reports.query](https://developers.google.com/youtube/analytics/reference/reports/query).

Which scopes each call accepts:

| Call | Accepted scopes | Source |
|---|---|---|
| `videos.insert` | `youtube.upload`, `youtube`, `youtube.force-ssl`, `youtubepartner` | [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert) |
| `playlists.insert`, `playlistItems.insert` | `youtube`, `youtube.force-ssl`, `youtubepartner` | [playlists.insert](https://developers.google.com/youtube/v3/docs/playlists/insert), [playlistItems.insert](https://developers.google.com/youtube/v3/docs/playlistItems/insert) |
| `playlistItems.list`, `channels.list` | `youtube`, `youtube.force-ssl`, `youtube.readonly`, `youtubepartner` | Data API discovery document, read 2026-10-03 |
| `videos.batchGetStats` | `youtube`, `youtube.force-ssl`, `youtube.readonly`, `youtubepartner` | [videos.batchGetStats](https://developers.google.com/youtube/v3/docs/videos/batchGetStats) |
| `videos.list`, `playlists.list` | Not listed on the method pages. Assumed the same as the other list calls. | see last section |
| `reports.query` | Reference page: `yt-analytics.readonly`, `yt-analytics-monetary.readonly`, plus `youtube` described as being for managing Analytics groups. | [reports.query](https://developers.google.com/youtube/analytics/reference/reports/query) |

**This settles the open point in the earlier research:** `playlistItems.insert` does not accept `youtube.upload`. Publishing with playlists needs `youtube`.

**Answer for Chorus:** request `youtube` + `yt-analytics.readonly`. `youtube.upload` becomes redundant once `youtube` is requested, and the policy says to "only request access to authorization scopes that they currently use" ([Developer Policies](https://developers.google.com/youtube/terms/developer-policies)), so drop it. If the statistics dashboard is optional, request `yt-analytics.readonly` only when the user turns it on (incremental authorisation is the documented best practice), and degrade to Data API counters when it is missing.

The Analytics discovery document (revision 20260930) lists `youtube` and `youtube.readonly` among the scopes `reports.query` accepts, which would mean no extra scope is needed. The reference page describes `youtube` only as the scope for managing groups. The two disagree; build on `yt-analytics.readonly`, which both agree on.

**Sensitive or restricted?**
- **Not restricted.** Google's list of restricted scopes covers Gmail, Drive, Fit, Chat, Data Portability, Photos Ambient and Health. No YouTube Data or Analytics scope is on it. [Restricted scope verification](https://support.google.com/cloud/answer/13464325) So no security assessment applies.
- **Sensitive: not confirmed from a docs page.** Google does not publish a per-scope list; "scope categories (non-sensitive, sensitive, or restricted) are indicated automatically in the Google Cloud Console" when the scope is added. [Sensitive scope verification](https://support.google.com/cloud/answer/13463073) The earlier research treats the YouTube scopes as gated, and the Analytics scopes expose private account data, so assume all six are sensitive. For Chorus the category has no practical effect (section 5).

## 4. Quota

### Data API

Default allocation: "100 `search.list` calls, 100 `videos.insert` calls, and 10,000 units per day combined for all other endpoints." [Getting started](https://developers.google.com/youtube/v3/getting-started)

| Call | Cost | Source |
|---|---|---|
| `videos.list` | 1 | [Quota calculator](https://developers.google.com/youtube/v3/determine_quota_cost) |
| `playlistItems.list` | 1 per page of up to 50 | same |
| `playlists.list` | 1 | same |
| `channels.list` | 1 | same |
| `videos.batchGetStats` | 1, in its own bucket of 10,000 per day | [revision history, 2026-06-03](https://developers.google.com/youtube/v3/revision_history) |

- The cost is per request, not per ID or per `part`. The docs no longer say that `part` changes the cost.
- "Every API request, even if invalid, will cost at least one quota point", and each extra page costs again. [Quota calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- Batching: a `videos.list` request takes a comma-separated list of IDs. The 50-ID ceiling is long-standing behaviour but **is not stated on the method page, the implementation guide or the revision history** as read today. Batch by 50 and treat a 400 as a signal to shrink the batch.

**Arithmetic: 200 videos, refreshed every hour**

| Per refresh | Calls | Units |
|---|---|---|
| `videos.list?part=status,statistics,processingDetails,contentDetails` in batches of 50 | 4 | 4 |
| `playlists.list` for the Work playlists (up to 50 IDs per call) | 1 | 1 |
| `channels.list?mine=true&part=statistics` | 1 | 1 |
| Optional: `playlistItems.list` to detect hand edits, about 5 Works | 5 | 5 |
| **Total** | 6 to 11 | **6 to 11** |

Per day: 24 x 6 = **144 units**, or 24 x 11 = **264 units** with the playlist check. That is 1.4% to 2.6% of the 10,000 units, and it does not touch the upload bucket. Unbatched (one `videos.list` per video) it would be 200 x 24 = 4,800 units, which would crowd out a day of Publishing (about 4,050 units for a 40-chapter Work, per the earlier research). **Batching is required, not optional.** Even a refresh every 5 minutes, batched, is about 1,730 units a day.

### Analytics API

- Separate quota from the Data API. "Each API request that you make counts as one unit of your API usage quota. Quota limits are visible on the Quotas panel in the Google Cloud console." [Data model](https://developers.google.com/youtube/analytics/data_model) The overview page words it differently ("The API server evaluates each query to determine its quota cost") but points to the same section. [Overview](https://developers.google.com/youtube/reporting)
- **The default daily and per-minute limits are not published in the docs.** The user sees them in their own console.
- Because the data lags 48 to 72 hours and moves once a day, refresh Analytics **once or twice a day**, not hourly. A daily refresh for 200 videos in 5 Works:

| Query | Requests |
|---|---|
| Per-video totals (`dimensions=video`, 200 IDs in one filter) | 1 |
| Channel daily series | 1 |
| Per-Work daily series | 5 |
| Playlist metrics (`dimensions=playlist`) | 1 |
| Traffic sources, geography | 2 |
| **Total** | **about 10 per day** |

Retention costs 1 request per video. Fetch it when the user opens a chapter and cache it for a day; fetching all 200 daily would be 200 requests, which is still small but wasteful.

## 5. Verification, the private lock and token expiry

### Token expiry: the earlier research is confirmed

- Testing status: refresh tokens expire in 7 days unless the only scopes are name, email and profile (`userinfo.email`, `userinfo.profile`, `openid`). Any YouTube scope, read-only or not, falls under the 7-day rule. [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2) The console help says the same: "Authorizations by a test user will expire seven days from the time of consent." [Manage app audience](https://support.google.com/cloud/answer/15549945)
- In production: the 7-day rule does not apply. The remaining ways a token dies are unchanged: revoked by the user, unused for six months, the 100-token cap per account per client, or the user granted time-limited access that ran out. [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2)
- **A dashboard makes the token healthier, not weaker**: an hourly refresh keeps the token in use, so the six-month idle expiry cannot trigger.
- So the wizard instruction stands: publish the consent screen to **In production**.

### Does adding Analytics scopes change anything?

| Item | Effect of adding `yt-analytics.readonly` | Source |
|---|---|---|
| OAuth verification | None for personal use. "If the app is for your personal use (fewer than 100 users), you and your limited number of users can continue using the app without going through verification." The exemption is not tied to which scopes are requested. | [When verification is not needed](https://support.google.com/cloud/answer/13464323) |
| Unverified-app screen | Still shown once at consent. | same |
| 100-user limits | Unchanged: 100 listed test users in Testing; 100 new users in total for an unverified app in production. Chorus uses 1. | [Manage app audience](https://support.google.com/cloud/answer/15549945) |
| 7-day expiry in Testing | Unchanged (already applies because of the `youtube` scope). | [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2) |
| Security assessment | None. No YouTube scope is restricted. | [Restricted scopes](https://support.google.com/cloud/answer/13464325) |
| Existing connection | The user must go through consent again to grant the new scope. Use `include_granted_scopes=true` so the old grants carry over. | [Data API OAuth guide](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps) |
| YouTube API compliance audit | Not required for reading statistics. The audit is required to request quota "beyond the default allocation" and to lift the private lock. If the user does apply, the audit form will now cover an analytics use case too (see section 6). | [Quota and compliance audits](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits), [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert) |

The Analytics API is a separate API in the Cloud project. The wizard must tell the user to enable **YouTube Analytics API** next to **YouTube Data API v3**.

### The private lock and statistics

- The lock is described only as a restriction on `videos.insert` output: videos are "restricted to private viewing mode". No page says it limits reading. The owner can read status and statistics of their own private videos (section 1). **Not explicitly confirmed, not contradicted.**
- A locked video "won't appear on your channel or in search results, and will be invisible to other users." [Videos locked as private](https://support.google.com/youtube/answer/7300965?hl=en) So there is nobody to generate views except the owner and anyone the owner invites by email.
- Do private videos produce Analytics data? The Help page on limited data says demographics and geography are never shown "for private or unlisted videos, regardless of the amount of traffic". [Limited data](https://support.google.com/youtube/answer/9101241?hl=en) That wording implies other reports (views, watch time) do exist for private videos, but no primary page says so outright.

**Consequence for the dashboard:**
1. For an unaudited project, show upload and processing status as the main content, with Data API counters as a small secondary line. Do not build charts that will sit empty.
2. The statistics become meaningful in two cases: the project is audited, or the user uploaded by hand (YouTube export) and pasted the video links. For hand-uploaded videos on the user's own channel, the same token reads the same statistics, because ownership is by channel, not by which client uploaded. That makes the dashboard useful on the main path, not only on the Publishing path.
3. Always show `privacyStatus` per video, so the lock is visible rather than explained away.

## 6. Developer Policies on storing and showing statistics

From [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies), section III.E.4, and the [policy guide](https://developers.google.com/youtube/terms/developer-policies-guide). Both pages last updated 2026-09-14.

| Rule | Text | What Chorus does |
|---|---|---|
| Statistics and Analytics data may be kept | III.E.4.b: API Clients may store "for as long as is necessary" (1) "data retrieved through the YouTube Analytics API service", (2) Reporting API data, "or (3) statistics provided through other YouTube API services, such as the number of views for a video". | A local history of counters is allowed. |
| But re-check authorisation every 30 days | "even though an API Client may store this data for more than 30 days, the Client must still ensure every 30 days that it is still authorized by the user to access that data." | The hourly refresh does this for free. If the refresh token is dead for 30 days, delete stored statistics. |
| Everything else: 30 days | III.E.4.c: other Authorized Data "for no longer than 30 calendar days". | Titles, descriptions, thumbnails fetched back from YouTube must be refreshed or dropped within 30 days. Chorus's own copies of what it sent are its own data. |
| Keep stored data consistent | III.E.4.e: "use reasonable efforts to ensure that their stored API Data is consistent with the current data available". | Refresh; drop videos that return not found. |
| Show the latest | III.E.4.f: "must display the most updated API Data available", though historical data may be shown "provided that it is presented accurately in context of time." | Show "as of" times. Label Analytics figures with their end date. |
| No derived metrics | III.E.4.h: "must not (i) replace API Data with similar, independently calculated data, or (ii) access or use API Data to create new or derived data or metrics." | See below. |
| Deletion on disconnect | Delete Authorized Data within 7 calendar days when the user revokes through the app; within 30 days when they revoke in Google security settings. | "Disconnect YouTube" wipes stored statistics. |
| Aggregation | Guide: do not "Compile or aggregate authorized API data unless you are making the compiled API data viewable ONLY to the content or channel owner". | Fine: single user, own channel. Do not add any sharing of the dashboard. |
| Attribution | III.F.2: a page that "displays YouTube content must make clear to the viewer that YouTube is the source of the relevant content by displaying YouTube Brand Features", and other content must not look as if it came from YouTube. | Put a YouTube mark or a "Data from YouTube" label on the statistics panel, following the Branding Guidelines. Keep Chorus's own numbers (render time, local listening) visually separate. |
| Inactivity | YouTube may "disable or curtail" access "if your API Project has been inactive for 90 consecutive days." | An hourly refresh keeps the project active. |

**Derived metrics.** The guide draws the line: acceptable metrics "use only YouTube API data and combine them via simple mathematical calculations (combine them via addition, subtraction, averages, multiplication, division)", with examples "Average daily views in a month", "Total views in a group of videos/channels" and "Graphs visualizing raw metrics". So per-Work totals, sums over chapters, and line charts are fine. A Chorus-invented score ("engagement index", "predicted completion") is not. Do not blend YouTube numbers with local listening numbers into one figure.

The guide also carries the sentence: "These policies are only applicable to audited developers with analytics use cases that have explicitly applied for permission to create additional metrics and/or store statistical data through the standard quota extension request (starting June 01, 2026)." I could not tell from the fetched text which bullets that sentence governs. Read strictly, it could mean that storing statistical data needs an approved use case. III.E.4.b in the policy itself allows storing statistics without such a condition. See the last section.

## What the dashboard can show

| Item | Source | Fresh | Works when locked private |
|---|---|---|---|
| Upload state, processing progress, failure and rejection reason, privacy | Data API `videos.list` | Live | Yes |
| Views, likes, dislikes, comments per chapter | Data API `videos.list` | Live | Yes, but near zero |
| Playlist item count and privacy | Data API `playlists.list` | Live | Yes |
| Channel subscribers and total views | Data API `channels.list` | Live | Yes (`videoCount` ignores private videos) |
| Watch time, average view duration and percentage, per chapter and per Work | Analytics | 2 to 3 days late | Probably, near zero |
| Daily series | Analytics | 2 to 3 days late | Probably, near zero |
| Retention curve per chapter | Analytics, 1 request per video | 2 to 3 days late | Unknown at very low views |
| Playlist starts, saves, in-playlist watch time | Analytics | 2 to 3 days late | Near zero |
| Traffic sources | Analytics | 2 to 3 days late | Detail may be thresholded |
| Geography, demographics | Analytics | 2 to 3 days late | **No. Never shown for private or unlisted videos** |
| Thumbnail impressions, click-through rate | Not in the API | n/a | n/a |
| Revenue | Needs monetary scope and Partner Program | n/a | n/a |

## Open or unverified points

- **50 IDs per `videos.list` request.** Not stated on the method page, the implementation guide or the revision history as fetched on 2026-10-03. `batchGetStats` states no maximum either. Verify during build.
- **Scopes accepted by `videos.list` and `playlists.list`.** The method pages have no authorisation section and the Data API discovery document was truncated by the fetch tool before those methods. Inferred from `channels.list`, `playlistItems.list` and `batchGetStats`, which all accept `youtube` and `youtube.readonly`.
- **Whether `youtube.upload` alone can read the uploader's videos.** No page lists it for any list call. Moot if Chorus requests `youtube`.
- **Whether `youtube` alone authorises `reports.query`.** The discovery document (revision 20260930) lists it; the reference page describes it as for groups only. Not tested.
- **Sensitive classification of the YouTube and Analytics scopes.** No docs page lists it; only the Cloud Console shows it. All that is confirmed is that none is restricted.
- **Analytics API default quota numbers** (per day, per minute). Not published in the docs.
- **Private videos and Analytics.** Confirmed: no geography or demographics. Not confirmed from a primary source: that views and watch time reports are returned for private videos, whether the owner's own playbacks count as views, and whether retention reports return rows at very low view counts.
- **Private lock and reads.** No page says the lock affects `videos.list` or Analytics; none says it does not. No API field marks a video as locked.
- **Exact subscriber count for the owner.** The resource page says the value is rounded to three significant figures; the summary I received added that owners get the exact number, which I could not see quoted.
- **Scope of the "audited developers with analytics use cases ... (starting June 01, 2026)" sentence** in the policy guide. It may only govern creating extra derived metrics, or it may also touch long-term storage of statistics. Read the guide page in a browser before the dashboard stores more than 30 days of history.
- **Channel reports page still mentions `isCurated` as "deprecated soon".** The revision history says it has been unsupported since 2024-12-31.
- **Verbatim wording.** Pages were read through a summarising fetch tool (direct download failed TLS verification in this environment), so short quotations are reliable in substance but should be re-checked before being copied into user-facing help text.
