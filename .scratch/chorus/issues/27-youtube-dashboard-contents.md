# What the YouTube dashboard shows

Type: grilling
Status: resolved
Blocked by: none

## Question

The final milestone adds one-click Publishing with a dashboard of upload status and YouTube statistics (ticket 12). Ticket 23 found what can be read: live counters and upload and processing status per video; watch time, retention, daily series and playlist figures 48 to 72 hours late; one extra permission; and that videos locked private by an unaudited project show almost nothing. Decide: which figures the dashboard shows per chapter, per Work and for the channel; whether it also tracks hand-uploaded videos through their pasted links (the only ones with real numbers for an unaudited project), and so whether part of it arrives before the final milestone; how the private lock is explained on it; how often it refreshes and how much history Chorus keeps, within the policy limits in `../research/youtube-statistics.md`; and whether the statistics permission is asked for at Connect or only when the user opens the statistics.

## Answer

Decided by the user on 2026-10-03 in a grilling session.

- **Which videos:** every chapter that has a video, whether Chorus uploaded it or the user pasted its link, marked as one or the other. The dashboard stays in the final milestone, because it needs the Connect wizard; until then a pasted link is just a link.
- **Figures per chapter:** status, views, likes and comments (live); watch time and average percentage listened (2 to 3 days late). No dislikes.
- **Figures per Work:** the sums, a chart of views per day, the playlist link and the number of videos in it. No playlist figures.
- **Figures for the channel:** subscribers and total views.
- **Left out:** retention curves, traffic sources, geography and demographics.
- **Placement:** one YouTube page for the whole Library (connection state, channel totals, a table of Works with upload status and totals), and the YouTube section of each Work page for that Work's chapters.
- **Permission:** the Connect wizard asks once for both `youtube` and `yt-analytics.readonly`. If the user unticks statistics on Google's screen, Publishing still works and the dashboard shows only the live counters, with a "grant statistics access" button.
- **Refresh:** live counters hourly while the dashboard is in use and on a Refresh button; delayed figures once a day.
- **History:** none. Chorus stores only the most recent figures with the time they were fetched; a chart asks YouTube for its date range when opened. So the unclear policy sentence about long storage (ticket 23) does not matter.
- **Private lock:** Connect has a setting "my Google Cloud project has passed the YouTube audit", off by default. While it is off, the YouTube page and each uploaded chapter carry a plain notice: videos uploaded by Chorus are private and cannot be made public, their numbers stay near zero, and for public videos use YouTube export and paste the link. Uploaded videos are labelled "private (locked)".
- **Edge cases:** a pasted link to a video not on the connected channel shows as "not on your channel", with no figures. A video deleted on YouTube shows as "removed on YouTube" and the link is kept until the user clears it. A video replaced after regeneration (ticket 12) is listed as "replaced", with its link and no figures. The "video outdated" flag from ticket 12 appears beside the figures.
- **YouTube's rules (ticket 23):** delayed figures carry the date they run up to; every panel says the numbers come from YouTube; only sums and averages of YouTube's own numbers are shown; "Disconnect YouTube" deletes all stored figures at once and keeps the pasted links.
