# Architecture and tech stack, including GPU sharing between the language and voice models

Type: grilling
Status: claimed
Blocked by: 04, 07, 08, 12, 14

## Question

What is Chorus's architecture and tech stack? Decide: the backend and frontend stack; how the pipeline stages run as resumable background jobs; how the analysis model and the voice model take turns on a single 4 GB GPU (the load and unload strategy); how the Work, Script, Voices and generated audio are stored; how the YouTube integration fits in; and the Docker packaging. Also decide Chorus's own license, which determines whether AGPL/GPL libraries can be imported in-process or must run as separate processes (see `../research/source-import-libraries.md`). All of it must stay within the constraints in the map's Notes.
