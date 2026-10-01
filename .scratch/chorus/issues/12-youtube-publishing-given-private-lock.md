# How YouTube Publishing works given that unaudited uploads are locked private

Type: grilling
Status: resolved
Blocked by: none

## Question

YouTube locks every API upload from an unaudited Google Cloud project to private, and whether a personal project can pass the compliance audit is undocumented (see `../research/youtube-upload-api.md`). What should Publishing to YouTube be in Chorus? Options: (a) direct upload stays, as private uploads the user then makes public by hand in YouTube Studio; (b) direct upload plus a guided path for the user to apply for the audit; (c) drop direct upload and offer only "Export for YouTube" (MP4 per chapter, description with chapter timestamps, thumbnail); (d) both (a) and (c). Also settle the video layout (one video per chapter plus a playlist per Work, or one long video) and what happens to already-published videos when a chapter is regenerated.

## Answer

Correction to the question: option (a) is not possible. A video locked private by an unaudited project cannot be made public in YouTube Studio and cannot be appealed; it has to be uploaded again by hand or through an audited project.

- **Main path: YouTube export.** An Export that writes, per chapter, an upload-ready MP4, a description, a thumbnail and an upload checklist. The user uploads by hand in YouTube Studio. Publishing (upload from the app) is not part of the first build.
- **Layout:** one video per chapter, grouped in one playlist per Work. No single long video.
- **Image:** a still. The Work's cover if the Source has one, otherwise a generated title card; the Work title and chapter title are drawn on it.
- **Disclosure:** the checklist reminds the user to tick YouTube's "altered or synthetic content" box, and the generated description ends with a line saying the voices are AI-generated. The user can edit the description before uploading.
- **Video links:** the user can paste each chapter's YouTube link into Chorus; the Library shows it.
- **Regeneration (manual path):** Chorus records when each chapter was last exported for YouTube and flags chapters whose audio changed since. A pasted link is kept and shown as "video outdated" until the user re-exports and either pastes a new link or confirms the video was replaced.
- **Final milestone: one-click Publishing with a YouTube dashboard.** Built very late. One click on a Work renders the videos, uploads them, builds the playlist, sets thumbnails and the synthetic-media flag; nothing is uploaded without that click. Uses the user's own Google Cloud project, and uploads are private unless the project is audited (see `../research/youtube-upload-api.md`). The dashboard shows upload status per Work and chapter plus YouTube statistics (views, watch time). Its details are left as not yet specified on the map.
- **Regeneration (Publishing path):** Chorus uploads the new video and puts it in the playlist in the old one's place. The old video stays on the channel, outside the playlist, and Chorus tells the user; it never deletes a video automatically.
- **Glossary:** added "YouTube export". Publishing keeps its strict meaning (upload from the app); a hand-uploaded chapter is "exported, with a video link", not Published.
