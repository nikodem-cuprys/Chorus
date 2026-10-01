# YouTube upload API for a self-hosted single-user app

Type: research
Status: resolved
Blocked by: none

## Question

What does it take for a self-hosted, single-user app to upload videos to the user's own YouTube channel through the YouTube Data API v3? Cover: OAuth setup (the user's own Google Cloud project vs a shared one); whether unverified or unaudited API projects are forced to upload videos as private; the daily quota and cost per upload; one Work as several videos vs one long video (length limits); chapter timestamps in descriptions; thumbnails; playlists; and any rules on disclosing AI-generated or synthetic content. Also: the cheapest ffmpeg approach to render a still-image or waveform video from audio.

## Answer

- BYO Google Cloud project per user (shared or embedded credentials are forbidden by the Developer Policies). The consent screen must be "In production", because Testing mode refresh tokens expire after 7 days. The OAuth redirect must be localhost or HTTPS, so the first Connect happens from the Docker host.
- Unaudited projects created after 2020-07-28 get every upload **locked private**, with no appeal. Public uploads need a YouTube API compliance audit, so Chorus must also offer "Export for YouTube" (MP4, description, thumbnail) for manual upload.
- Quota: uploads have their own bucket of 100 per day at 1 unit each (changed 2025-12 and 2026-06). Thumbnails and playlist items cost 50 each out of 10,000 per day. Length: 15 min by default, up to 12 h or 256 GB once the account is verified.
- Recommended layout: one video per chapter plus a playlist per Work. Description chapters need 00:00 first, 3 or more timestamps, each at least 10 s, all within a 5,000-byte description. Set `containsSyntheticMedia=true` by default, and force it on when a cloned Voice is used.
- Render: a still frame at 1 fps with the AAC audio stream-copied and an explicit `-t`, which took about 1.4 s per 10 minutes of audio in a local test.

Full findings: [research/youtube-upload-api.md](../research/youtube-upload-api.md)
