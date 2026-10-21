# Chorus

Chorus turns a written work into a multi-voice audio drama. You import a Source (an EPUB, MOBI, AZW3, PDF with a text layer, TXT, or another format Calibre can convert). Chorus finds the Characters and who says each line, gives each Speaker a Voice and each line an Emotion, and voices the whole Work on your own NVIDIA card. You can listen in the browser or export the Audio drama as MP3 or M4B.

It is self-hosted and single-user: it runs in Docker on your machine and is used through a browser at `http://localhost:8000`. Nothing leaves the machine except the one-time model download. The minimum card is a **GTX 1050 Ti** (4 GB, Pascal).

## What to expect

On a GTX 1050 Ti, for a novel of about 100,000 words:

- **Analysis takes about 3.5 hours.** This is finding the Characters and who says each line.
- **Voicing takes about a day.** It runs at about twice real time, and a novel is 10 to 11 hours of audio.
- **Listening starts early.** Each chapter can be played as soon as it is voiced, while the rest of the Work is still being voiced.

Long jobs can be paused, resumed and cancelled from the Work page without losing finished lines. A job cut off by a crash or reboot carries on by itself when Chorus is back up.

**The card is tight.** Analysis adds about 3.3 GB on the card at its peak and voicing about 3.1 GB, out of 4 GB, which leaves little room for a desktop on the same card. Close games, video players and other programs that use the GPU while Chorus works. On Windows, a busy desktop makes Chorus slow down by spilling into system memory. On Linux, it makes the job fail.

## Host setup

You need:

- an NVIDIA card with at least 4 GB (GTX 1050 Ti or newer);
- at least 35 GB of free disk space (the image is about 14 GB, the models 6 GB, plus the build cache and your audio);
- the setup below for Windows or Linux.

### The NVIDIA driver: branch R580

Install a driver from the **R580 branch**: 580.x on Linux, 58x.xx on Windows (Chorus was measured with 582.28). R580 is the last driver branch that supports Pascal cards such as the 1050 Ti, with security updates until October 2028. **Do not move to R590 or later:** those drivers drop Pascal. If you use the NVIDIA app or GeForce Experience, turn off automatic driver updates.

Chorus's whole GPU stack (CUDA 12.6, PyTorch 2.14, llama.cpp built for Pascal) is frozen at the last versions that still run on these cards.

### Windows

Windows 11 is the safer host. Docker Desktop's support for Windows 10 (22H2) ends with Microsoft's servicing of it.

1. **Turn on virtualization** in the BIOS/UEFI (Intel VT-x or AMD SVM). Task Manager → Performance → CPU should say "Virtualization: Enabled".
2. **Install the R580 driver** on Windows itself (see above).
3. **Install WSL2.** In PowerShell as administrator, run `wsl --install`, restart, then run `wsl --update`. **Do not install a Linux NVIDIA driver inside WSL:** the Windows driver provides the GPU to WSL.
4. **Install Docker Desktop** and make sure Settings → General → "Use the WSL 2 based engine" is on.
5. **Check that Docker sees the card:**

   ```sh
   docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
   ```

   This should print a table naming your card and the driver version. If it fails, fix this step before going on.

### Linux

1. **Install the R580 driver** (on Ubuntu, `nvidia-driver-580`) and restart.
2. **Install Docker Engine** with the Compose plugin, from Docker's own repository.
3. **Install the NVIDIA Container Toolkit**, then connect it to Docker:

   ```sh
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

4. **Check that Docker sees the card** with the same command as on Windows:

   ```sh
   docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
   ```

## Install and first run

```sh
git clone https://github.com/nikodem-cuprys/Chorus.git
cd Chorus
docker compose up -d --build
```

The first build takes a long time: it compiles llama.cpp for Pascal cards and downloads about 7 GB of PyTorch and CUDA libraries. Later builds reuse that work.

Open **http://localhost:8000**. The first time, the **First run** screen downloads the two models, about 6 GB in total: the analysis model and the voice model. Each has a progress bar, and an interrupted download carries on where it stopped. When both are in place, you reach the **Library**. From there, **Import** a Source. Analysis starts by itself, then voicing; the Work page shows each job's progress, the time left, and pause, resume and cancel.

If the build fails with "certificate verify failed" or "invalid peer certificate", antivirus software or a proxy is re-signing your HTTPS traffic. See [`certs/README.md`](certs/README.md).

Chorus checks its GPU stack every time it starts. If something is wrong, for example a driver from the wrong branch, the interface says what failed.

### Where things are

- **Exports:** MP3 and M4B exports are written to the `exports` folder next to `compose.yaml`, one sub-folder per Work, as ordinary files you can open, copy or move. They stay when you delete a Work. To put them somewhere else, set `CHORUS_EXPORTS_DIR` before starting, e.g. `CHORUS_EXPORTS_DIR=D:/Audiobooks docker compose up -d`.
- **Everything else** is kept in Docker volumes and survives `docker compose down`: your Works, audio, the models and the database. `docker compose down -v` deletes them.
- **Port:** Chorus listens on `127.0.0.1:8000`, so it is reachable only from this machine. It has no login. Set `CHORUS_PORT` to use another port.

### Stopping and updating

```sh
docker compose down                         # stop; everything is kept
git pull && docker compose up -d --build    # update
```

## Responsible use

- **Other people's writing:** voicing a work you did not write, and above all sharing the result, needs the author's permission. For fanworks, that includes podfic permission.
- **Other people's voices:** clone only a voice whose speaker has agreed to it.
- **AO3:** AO3's terms forbid commercial use of works taken from it. Do not monetise an audio drama made from an AO3 work.

Chorus informs and never blocks: these are your responsibility.

## Credits and licences

Chorus is released under the [MIT licence](LICENSE).

| Component | Used for | Licence |
|---|---|---|
| [Chatterbox](https://github.com/resemble-ai/chatterbox) 500M (Resemble AI) | the voice model | MIT |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | the built-in Voices' reference clips, generated once and bundled | Apache-2.0 |
| [Qwen3.5-4B](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) (GGUF by Unsloth) | the analysis model | Apache-2.0 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | runs the analysis model | MIT |
| [Calibre](https://calibre-ebook.com) `ebook-convert` | converting MOBI, AZW3 and other formats | GPL-3.0, run as a separate program |
| [ffmpeg](https://ffmpeg.org) | putting chapters together and writing MP3 and M4B | GPL, run as a separate program |
| lxml, pypdf | reading EPUB and PDF | BSD-3-Clause |
| pdfplumber (on pdfminer.six), charset-normalizer | reading PDF and TXT | MIT |
| lingua-py | detecting a Work's language | Apache-2.0 |

Calibre and ffmpeg run as separate programs inside the image and are not linked into Chorus, so the image is an aggregate of separately licensed programs. The model weights are not part of the image: they are downloaded from Hugging Face on first run, in pinned versions.

For development (running the tests, conventions), see [`docs/development.md`](docs/development.md). The design is in [`docs/spec/`](docs/spec/README.md).
