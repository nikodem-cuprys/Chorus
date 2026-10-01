# YouTube upload API for a self-hosted, single-user Chorus

Ticket: [04-youtube-upload-api](../issues/04-youtube-upload-api.md). Researched 2026-09-29 against Google/YouTube primary docs; a local ffmpeg 8.1.1 benchmark backs the rendering section.

## TL;DR

- **Bring your own Google Cloud project (BYO).** Each user creates their own project and OAuth client, and pastes the client ID and secret into Chorus. Chorus must never ship shared credentials: the YouTube Developer Policies forbid embedding API credentials in open-source projects or sharing them.
- **Hard blocker:** videos uploaded through `videos.insert` from an **unaudited project created after 28 July 2020 are locked private**. Setting `privacyStatus` has no effect, and the user **cannot appeal**. They must re-upload through an audited API client or through YouTube's own site/app. Lifting the lock takes a YouTube API compliance audit of *that* project. So Publishing without an audit only ever gives **private** videos.
- **Quota is no longer the constraint:** since 2025-12-04 an upload costs about 1 unit instead of about 1600. Since 2026-06-01 uploads have their **own bucket of 100 `videos.insert` calls per day**, next to 10,000 units per day for everything else (thumbnail, playlist and update calls cost 50 each).
- **Length:** 15 minutes by default. A phone-verified account can upload up to **12 hours or 256 GB**, whichever is smaller.
- **Recommendation:** one video per chapter, grouped in a playlist per Work. Also offer "one long video with chapter timestamps" when the Work fits in 12 hours.
- **Disclosure:** set `status.containsSyntheticMedia = true` by default. The API has supported this since 2024-10-30.
- **Rendering:** a still image plus stream-copied AAC audio renders **10 minutes of audio in about 1.4 s** with about 44 KB of video overhead. A waveform video is about 15x slower. Default to the still image.

## 1. OAuth setup: the user's own Cloud project vs a shared one

### Why it must be the user's own project
- The Developer Policies say you must not "share or disclose your API Credentials to any other third party" or "embed your API Credentials in open source projects", and must not use one API project for multiple API clients. [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
- A shared Chorus project would also need Google OAuth verification (the YouTube scopes are gated scopes) plus a YouTube audit, run by whoever maintains Chorus. That is at odds with self-hosting.
- *Inference:* nothing in the policies forbids each user registering their own project for their own copy of the app. In that setup the user is the "developer" of an API client used only by themselves.

### What the user does (a one-time setup wizard in Chorus)
1. Create a Google Cloud project and enable the **YouTube Data API v3**.
2. Configure the OAuth consent screen: External user type, add themselves as a test user, then **publish to "In production"** (explained below).
3. Create an OAuth client ID of type **Web application**, with the redirect URI `http://localhost:<port>/oauth/youtube/callback`.
4. Paste the client ID and secret into Chorus, click Connect, and grant the scope `https://www.googleapis.com/auth/youtube.upload`. Add `.../auth/youtube` only if Chorus also manages playlists, since playlist writes need it. [videos.insert scopes](https://developers.google.com/youtube/v3/docs/videos/insert), [OAuth scopes list](https://developers.google.com/identity/protocols/oauth2/scopes)

### Gotchas
- **Testing mode kills tokens weekly.** "A Google Cloud Platform project with an OAuth consent screen configured for an external user type and a publishing status of 'Testing' is issued a refresh token expiring in 7 days." [Google OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2) So the wizard must tell the user to switch the app to **In production**.
- **Verification is not needed for personal use.** "If the app is for your personal use (fewer than 100 users), you and your limited number of users can continue using the app without going through verification." The unverified-app warning screen remains; the user clicks through it once. [When is verification not needed](https://support.google.com/cloud/answer/13464323)
- **Redirect URIs must be HTTPS or localhost; raw IPs are not allowed except localhost.** [Web server OAuth flow](https://developers.google.com/identity/protocols/oauth2/web-server) Because Chorus runs in Docker, a user who opens it at `http://192.168.x.x:port` or `http://nas:port` **cannot complete the OAuth callback there**. Two options:
  - (a) Do the one-time Connect from a browser on the Docker host, via `http://localhost:port`.
  - (b) Use the user's own HTTPS domain or reverse proxy.
  After that, the stored refresh token works from anywhere. The spec should document this.
- Request `access_type=offline` (and `prompt=consent` on reconnect) to get a refresh token. [Web server OAuth flow](https://developers.google.com/identity/protocols/oauth2/web-server)
- **Refresh tokens can still die:** the user revokes access, the token goes unused for 6 months, and so on. There is also a cap of 100 refresh tokens per account per client. [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2) Chorus needs a "reconnect YouTube" state, and must not treat a failed refresh as a failed job.
- **Policy obligations for any API client:**
  - Require users to agree to a privacy policy.
  - Never handle Google passwords.
  - Request only the scopes currently needed.
  - Let the user set the title and keep final control over what is published.
  - Delete or refresh stored API data within 30 days.
  [Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
  For a single-user self-hosted app most of these are trivial. The privacy-policy requirement matters mainly for the audit.

## 2. Unverified or unaudited projects: private-only lock

- "All videos uploaded via the `videos.insert` endpoint from unverified API projects created after 28 July 2020 will be restricted to private viewing mode. To lift this restriction, each API project must undergo an audit to verify compliance with the Terms of Service." [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- "For videos that have been locked as private due to upload via an unverified API service, you will not be able to appeal. You'll need to re-upload the video via a verified API service or via the YouTube app/site. The unverified API service can also apply for an API audit." [Videos locked as private (YouTube Help)](https://support.google.com/youtube/answer/7300965?hl=en)
- The audit goes through the "YouTube API Services – Audit and Quota Extension Form". [Quota and compliance audits](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits), [form](https://support.google.com/youtube/contact/yt_api_form) The docs do not say whether a personal, single-user project will be approved, what it must submit, or how long review takes. YouTube reserves the right to request "account(s) necessary to access all features" of the client. [Developer Policies](https://developers.google.com/youtube/terms/developer-policies)

**Consequences for Chorus:**
1. Publishing must present the audit as an **optional, user-driven step** that happens outside Chorus. Chorus should ship a help page with what the user needs: a privacy policy URL, a description of the app, and a screencast.
2. The UI must **show honestly that uploads will be private** until the user marks their project as audited. Do not offer a "Public" choice that silently becomes private. Instead, record "project audited: yes/no" in Settings.
3. **Fallback path, needing no audit:** "Export for YouTube" writes the rendered MP4, `description.txt` (with chapters), and the thumbnail. The user uploads them by hand in YouTube Studio. Chorus already has an Export path, so this is cheap to add and it is the realistic default for most users.
4. Private uploads are still useful as a "private cloud listening" copy. Treat that as a secondary benefit.

## 3. Quota and cost per upload

| Call | Cost | Source |
|---|---|---|
| `videos.insert` | 1 unit, in its own **Video Uploads** bucket: **100 calls per day** by default | [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert), [Getting started](https://developers.google.com/youtube/v3/getting-started) |
| `thumbnails.set` | about 50 | [thumbnails.set](https://developers.google.com/youtube/v3/docs/thumbnails/set) |
| `playlists.insert`, `playlistItems.insert`, `videos.update` | 50 each | [Quota calculator](https://developers.google.com/youtube/v3/determine_quota_cost) |
| Other endpoints combined | 10,000 units per day | [Getting started](https://developers.google.com/youtube/v3/getting-started) |

History [revision history](https://developers.google.com/youtube/v3/revision_history):
- 2025-12-04: an upload went "from approximately 1600 units to approximately 100 units".
- 2026-06-01: `videos.insert` and `search.list` moved into their own buckets.

Older blog posts saying "6 uploads per day" are obsolete.

**Budget:** a Work of 40 chapters published as 40 videos with thumbnails and one playlist costs:
- 40 upload calls,
- 40 x 50 thumbnail units,
- 50 for the playlist,
- 40 x 50 playlist-item units,
- for about 4,050 of the 10,000 general units in total.

So about 2 such Works fit per day, and the playlist items plus thumbnails are the binding cost, not the uploads. The upload queue must be quota-aware:
- Persist per-video state.
- On `quotaExceeded`, pause and resume after the quota reset (midnight Pacific).

**Uploads themselves:** use the **resumable upload protocol**:
- POST with `uploadType=resumable` to get a session URI, then PUT the bytes, in chunks whose size is a multiple of 256 KB.
- After an interruption, query progress with `Content-Range: bytes */TOTAL`, which answers 308 with a `Range` header.
- Session URIs expire; a 404 means start over.
[Resumable uploads](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol)

This fits the "Long jobs: resume after crash" open question on the map. The maximum file is 256 GB, with MIME type `video/*` or `application/octet-stream`. [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)

## 4. One Work as several videos vs one long video

- Length limits: "By default, you can upload videos that are up to 15 minutes long." Verifying the account (by phone) raises this; the absolute cap is "256 GB or 12 hours, whichever is less." [Upload videos longer than 15 minutes](https://support.google.com/youtube/answer/71673)
- Chorus cannot verify the account through the API. The wizard should tell the user to verify first. Chorus should also warn before rendering when any planned video is over 15 minutes and the user has not confirmed verification.

**Recommendation: a per-Work publishing mode, defaulting to "one video per chapter + playlist".**
- Chapters map naturally to the Work's own structure. Most chapters are under 12 hours, and failures and regeneration touch only one video.
- If a single chapter is over 12 hours (rare), split it at a Scene boundary.
- The optional mode "one video per Work" is allowed only if the total is 12 hours or less. It uses description chapter timestamps (section 5).
- *Monetization note, for later:* the YouTube Partner Program forbids "mass-produced, generic, repetitive" content with minimal variation. [YouTube channel monetization policies](https://support.google.com/youtube/answer/1311392) Dozens of identical still-image chapter videos could draw that label. Per-chapter titles and thumbnails reduce the risk; they do not remove it.

## 5. Chapter timestamps in descriptions

- Requirements [Video Chapters (YouTube Help)](https://support.google.com/youtube/answer/9884579?hl=en):
  - The first timestamp is `00:00`.
  - There must be at least **3** timestamps, in ascending order.
  - Each chapter must be at least **10 seconds**.
- Chapters are unavailable if the channel has active strikes or the content "may be inappropriate to some viewers". [same page](https://support.google.com/youtube/answer/9884579?hl=en)
- Description limit: **5,000 bytes**, and no `<` or `>` characters. Title limit: **100 characters**, same character restriction. Tags: 500 characters in total. [videos resource](https://developers.google.com/youtube/v3/docs/videos)

**What this means for Chorus:**
- The chapter list must be byte-counted. A Work with 150 chapters of about 30 characters each is about 4.5 KB, which is borderline.
- Strip `<` and `>` from chapter titles, and truncate or abbreviate when needed.
- Use `H:MM:SS` for videos over 1 hour.
- The same chapter timing should drive M4B chapter markers, so there is one source of truth.
- In per-chapter mode, the description can carry Scene timestamps instead, when there are 3 or more Scenes and each is at least 10 seconds.

## 6. Thumbnails

- `thumbnails.set`: JPEG or PNG, up to 50 MB through the API, about 50 units per call. It returns 403 if "the authenticated user doesn't have permissions to upload and set custom video thumbnails". [thumbnails.set](https://developers.google.com/youtube/v3/docs/thumbnails/set)
- Help Center: the account must be verified; recommended size is 1280x720, 16:9, minimum width 640 px. Some clients keep the older 2 MB limit. [Add video thumbnails](https://support.google.com/youtube/answer/72431?hl=en&co=GENIE.Platform%3DDesktop)

**What Chorus should do:**
- Generate a 1280x720 JPEG under 2 MB: cover art plus the Work and chapter title.
- Use the same image as the video's still frame.
- Treat a 403 on `thumbnails.set` as a non-fatal warning.

## 7. Playlists

- `playlists.insert` (50 units) creates one playlist per Work. `playlistItems.insert` (50 units per video) adds each video with an explicit `position` in chapter order. [Quota calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- The playlist privacy should match the videos, which means private for unaudited projects.
- Playlist writes need the broader `youtube` scope, not just `youtube.upload` (inferred from the scope descriptions: `youtube.upload` is "Upload YouTube videos and manage your YouTube videos"). Request it at Connect time only if playlists are enabled. [OAuth scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
- Store the YouTube `videoId` and `playlistId` per Work and chapter in the data model, so that regenerating a chapter can re-upload and replace the item in the playlist. YouTube has no "replace video file" operation.

## 8. Disclosure of AI-generated or synthetic content

- API field: `status.containsSyntheticMedia` "allows the channel owner to disclose that a video contains realistic Altered or Synthetic (A/S) content". It can be set on insert or update. [videos resource](https://developers.google.com/youtube/v3/docs/videos), added 2024-10-30 [revision history](https://developers.google.com/youtube/v3/revision_history)
- What must be disclosed: content that "Makes a real person appear to say or do something they didn't do" or "Generates a realistic scene that didn't actually occur". Among the examples that do *not* need disclosure is "Cloning one's own voice to create voice overs or dubs". Creators who "consistently choose not to disclose" may get a label applied, content removed, or their channel suspended. [Disclosing use of GenAI content](https://support.google.com/youtube/answer/14328491)
- The policy does not explicitly cover AI narration of fiction with synthetic voices.

**Risk reading:**
- Built-in voices for fictional Characters: probably exempt as not depicting a real person, but ambiguous.
- **Zero-shot clones of a real person's voice other than the user's own: disclosure is clearly required.** They also raise consent and likeness issues beyond YouTube.

**Recommendation:**
- Set `containsSyntheticMedia = true` by default, and let the user switch it off per Work.
- If any Voice in the Work is a clone, force it on (the user cannot switch it off).
- Also add a plain-text line to the description, for example: "Narrated with AI-generated voices (Chorus)."
- Always set `status.selfDeclaredMadeForKids` explicitly; it is part of the insert body. [videos resource](https://developers.google.com/youtube/v3/docs/videos)

**Adjacent risk:** Chorus cannot enforce copyright of the Source text on YouTube (AO3 fanfic, commercial books). That is outside this ticket, but the Publishing UI should put the responsibility on the user.

## 9. Cheapest ffmpeg video from audio

YouTube recommends the following. [Recommended upload encoding settings](https://support.google.com/youtube/answer/1722171) It does not address still-image or audio-only uploads, so no minimum frame rate is documented.
- MP4 with the moov atom at the front (fast start).
- H.264 video, 4:2:0.
- AAC-LC or Opus audio at 48 kHz.
- Common frame rates 24 to 60 fps.

Relevant ffmpeg primitives:
- The image2 demuxer's `loop` ("If set to 1, loop over the input") and `framerate` options. [ffmpeg-formats](https://ffmpeg.org/ffmpeg-formats.html)
- `-shortest`, `-r`. [ffmpeg](https://ffmpeg.org/ffmpeg.html)
- libx264's `-tune` and `-preset` (values per `x264 --fullhelp`; `stillimage` is one, confirmed via `ffmpeg -h encoder=libx264` on ffmpeg 8.1.1).
- `showwaves` for an animated waveform. [ffmpeg-filters](https://ffmpeg.org/ffmpeg-filters.html)

**Recommended: still frame at 1 fps, audio stream-copied from the already-encoded AAC Export.** Pass `-t` explicitly, set to the audio duration taken from `ffprobe`.

```sh
ffmpeg -loop 1 -framerate 1 -i cover.png -i chapter.m4a \
  -map 0:v -map 1:a -c:v libx264 -preset veryfast -tune stillimage \
  -pix_fmt yuv420p -g 60 -c:a copy -t <audio_duration> -movflags +faststart out.mp4
```

Measured locally on 10 minutes of 48 kHz stereo audio, 12 threads, ffmpeg 8.1.1:

| Variant | Wall time | Output | Notes |
|---|---|---|---|
| Still, 1 fps, `-c:a copy`, `-t` | **1.4 s** | 14.56 MB, where the audio alone is 14.51 MB | Video overhead about 44 KB. Duration exact at 600.0 s |
| Still, 1 fps, AAC re-encode, `-shortest` | 13.5 s | 14.56 MB | **Overshot to 638 s**: `-shortest` with a looped image is unreliable, so use `-t` |
| `showwaves` overlay at 10 fps | 23.6 s | 15.1 MB | About 15x slower than the still frame. Only as an opt-in style |

This is CPU-only and trivial on any machine, so the GTX 1050 Ti is not involved. At about 1.4 s per 10 minutes, a 12-hour Work renders in under 2 minutes. Keeping the audio as a stream copy also means the YouTube audio is bit-identical to the local M4B/MP3 Export's AAC source, if that Export is AAC.

## Recommended integration approach

1. **Settings, then "Connect YouTube" wizard** using the BYO Google Cloud project flow: enable the API, set the consent screen to In production, create a Web client with a localhost redirect, paste the credentials, and do OAuth with `access_type=offline`. Store the refresh token encrypted at rest. Include a toggle "My project has passed the YouTube API audit", off by default.
2. **Publish dialog per Work:**
   - mode: per-chapter plus playlist (default), or a single video if 12 hours or less;
   - titles, editable, prefilled from the Work and chapter;
   - description template with chapter or Scene timestamps, byte-checked;
   - thumbnail;
   - `containsSyntheticMedia` (default on, forced on when a cloned Voice is used);
   - made-for-kids;
   - privacy, where the only choice is **Private** unless the audit toggle is on.
3. **Render step:** a still-frame MP4 from the Export's AAC audio, as above.
4. **Upload queue:** a persistent job per video, resumable upload, quota-aware backoff on `quotaExceeded` until the Pacific-midnight reset, then thumbnail, then playlist item. Record the `videoId` and `playlistId` against the Work and chapter.
5. **Always also offer "Export for YouTube"** (MP4, description.txt, thumbnail) as the no-audit path for public videos, uploaded by hand in Studio.

## Open or unverified points

- Whether YouTube approves compliance audits for personal, single-user projects, and how long review takes. Not documented.
- Whether AI narration of fiction by non-cloned synthetic voices strictly requires the A/S disclosure. The policy is silent; this document defaults to disclosing.
- Exactly which scope `playlistItems.insert` accepts (`youtube` vs `youtube.upload`). Confirm against the method page during build.
