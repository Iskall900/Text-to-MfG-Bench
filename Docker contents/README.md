# Docker environment

Build the reusable image from the repository root:

```sh
docker build -f "Docker contents/Dockerfile" -t text-to-mfg:latest .
```

Create separate containers (each has its own writable workspace):

```sh
docker run -it --name mfg-1 text-to-mfg:latest
docker run -it --name mfg-2 text-to-mfg:latest
```

The image (Debian 13, Node 24 LTS, Python 3.13) includes Pi 1.4.0, Build123d 0.13.0, Gmsh 4.15.2
(CLI and Python API), and CalculiX 2.23 (same as the local Mac installation). Debian 13 no longer
packages CalculiX, so `ccx` is built from the official source with multithreaded SPOOLES and ARPACK.
Set `OMP_NUM_THREADS` to limit its solver threads.

Also installed:

- CalculiX GraphiX 2.23 (`cgx`), the CalculiX pre/post-processor, built from source. There is no
  display, so run it under the virtual X server: `xvfb-run -a cgx -b view.fbd` (Mesa software
  rendering; `hcpy png` screenshots use ImageMagick). cgx stops to ask before each `sys` command
  in an `.fbd` file, so avoid `sys` in batch scripts or they wait for input.
- Python: matplotlib (headless `Agg` backend), meshio, trimesh, pypdf.
- PDFs: `pdftotext`, `pdftoppm` (render pages to PNG), and `pypdf`.
- ripgrep 15.2.0 and fd 10.5.0 from their official GitHub releases (Pi's `grep`/`find` tools
  use these instead of downloading their own copies in each new container).
- `ps`, `pkill`, `less`, `file`, `zip`/`unzip`, `jq`, `bc`, `tree`, `patch`, `nano`, `vi`.

Gmsh is built from the official 4.15.2 source with OpenCASCADE support for
STEP geometry and without the graphical interface. This supports native Linux
ARM64 builds, for which the official pip package has no wheel.

Version-matched documentation is cached in the repository under `Docker contents/docs`
and extracted into the image, so reading it requires no network connection:

- CalculiX 2.23: `/opt/docs/calculix-2.23/CalculiX/ccx_2.23/doc/ccx/ccx.html`
- CalculiX GraphiX 2.23: `/opt/docs/calculix-2.23/CalculiX/cgx_2.23/doc/cgx/cgx.html`
- NAS1352 / NAS620 fastener specifications: `/opt/docs/nas/*.pdf`, with `.txt` extracts
- Build123d 0.13.0: `/opt/docs/build123d-0.13.0/index.xhtml`

The Build123d manual includes API references, tutorials, and examples. Its XHTML
pages and assets are extracted from the official EPUB and can be read as text or
opened in a browser. Search the manuals with `grep -ri 'search term' /opt/docs`.

Snapshots downloaded from the official
CalculiX [ccx](https://www.dhondt.de/ccx_2.23.htm.tar.bz2) and
[cgx](https://www.dhondt.de/cgx_2.23.htm.tar.bz2) HTML archives (2026-10-27) and
[Build123d 0.13.0 EPUB](https://build123d.readthedocs.io/_/downloads/en/v0.13.0/epub/) (2026-10-09).
The build verifies `docs/SHA256SUMS` before extraction. To refresh the cache,
replace the archives, regenerate the checksums, and rebuild the image; update
the documentation versions alongside any installed package version changes.

Inside a container, `pi`, `python`, `gmsh`, and `ccx` are available. Exit with `exit`
and resume a saved container with `docker start -ai mfg-1`.

Credentials are not included. Keep keys in a private file outside the repository,
one `NAME=value` per line (for example `DEEPSEEK_API_KEY`, `BRAVE_SEARCH_API_KEY`):

```sh
mkdir -p ~/.config/text-to-mfg
touch ~/.config/text-to-mfg/keys.env
chmod 600 ~/.config/text-to-mfg/keys.env
```

Open that file in an editor and add the keys, then pass it at runtime:

```sh
docker run -it --env-file ~/.config/text-to-mfg/keys.env text-to-mfg:latest
```

Do not use `-e NAME=value` (it lands in shell history), Pi's `/login` (it saves keys
to `~/.pi/agent/auth.json` in the container), or `docker commit`/`docker push` on a
container started with keys (the image config keeps them). `docker inspect` shows
them to anyone with Docker access on the same machine.

Pi keeps keys for model and search requests. Any variable whose name contains
`KEY`, `TOKEN`, or `SECRET` is removed before agent `bash` and interactive `!`
commands start. Every tool result, interactive `!` output, user prompt, and model
reply passes through `redact.ts`, which replaces those variables' values (8+
characters) with `[REDACTED]` before Pi shows or saves them. This also catches
keys read from `/proc/*/environ`. It matches exact text only: deliberately
encoding a key gets through, and preventing that requires running the shell as a
separate user.

Configure Pi's provider/model in that container as needed.

Each `pi` launch allows at most 15 modal CalculiX invocations through `ccx`.
The wrapper detects `*FREQUENCY`, including included input files, and shares a
locked counter across child processes. Failed modal attempts count; static solves
and version checks do not. A new Pi launch resets the budget. Direct execution of
`/usr/bin/ccx` bypasses this operational limit; it is not a security boundary.
Rebuild the image and recreate containers to apply it.

Pi exposes a `web_search` tool using the
[Brave Web Search API](https://api-dashboard.search.brave.com/documentation/services/web-search).
Add `BRAVE_SEARCH_API_KEY` to the same key file.

Search returns up to five titles, URLs, and snippets into the conversation; it
never opens result URLs or saves remote files. Without the search key, searches
report a configuration error; local work still runs.

The `pi` launcher loads only the image's metering and search extensions. Both the
agent's `bash` tool and interactive `!` shell commands use an inherited Linux
seccomp filter that refuses every socket family except local Unix sockets, which
blocks Python/Node downloads and package installs while letting `cgx` reach the
virtual X server. Failure to install the filter stops the command. Local file
creation, CAD, FEA, and cached documentation remain available. Pi runs as the
unprivileged `pi` user, with its installed code and extensions owned by root.
Bind-mounted workspaces must be writable by UID 1001.

This policy applies to commands issued through the harness; the container's
ordinary terminal still has network access for operator administration. Do not
mount Docker sockets or other privileged services, or load additional trusted
extensions with network access. Existing containers need to be recreated from
the rebuilt image. Search text may be saved in Pi's normal session history.

Pi automatically meters each prompt until the agent finishes, including tools,
retries, compaction, and queued continuations. It writes all metering `.txt` reports in `data-Pi` inside the prompt's
working directory (normally `/workspace/data-Pi`), creating the folder as needed:

- `agents-1-usage.txt`: total input, cached input, uncached input, and output tokens.
- `agents-1-time.txt`: total elapsed seconds from prompt submission to completion.
- `compute.txt`: `modal_fea_runs` for the latest prompt. Counts allowed modal
  `ccx` attempts (including failed solves). Help, static solves, and attempts
  rejected by the modal limit do not count. Direct `/usr/bin/ccx` calls bypass
  the counter. Each prompt replaces `compute.txt`; concurrent prompts in one
  directory leave the last completed report.

Both reports include the outcome (`completed`, `aborted`, or `error`). Cache writes
count as uncached input. Tokens are provider-reported; missing usage cannot be
recovered or estimated. Preflight failures before a model run starts do not produce
reports, and forcibly killing the process prevents it from writing reports.
Each new prompt uses the next available number, even after restarting Pi, without
overwriting earlier files. Concurrent processes reserve separate file pairs.
Reports contain no prompts or credentials. Use a bind mount or `docker cp` to
retain reports when removing a container.

Run the local metering checks after `npm ci`:

```sh
node --test metering.test.mjs web-search.test.mjs redact.test.mjs
```

Check, with fake keys, that neither shell sees credentials and the saved session
file never contains them (run from the repository root after building):

```sh
docker run --rm -e PI_NETWORK_IMAGE_TEST=1 -e DEEPSEEK_API_KEY=canary-deepseek-0123456789 -e BRAVE_SEARCH_API_KEY=canary-brave-0123456789 -e NASA_API_KEY=canary-nasa-0123456789 -v "$PWD/Docker contents/redact.test.mjs:/opt/pi/redact.test.mjs:ro" -w /opt/pi text-to-mfg:latest node --test redact.test.mjs
```

Smoke check:

```sh
docker run --rm text-to-mfg:latest bash -ec 'pi --version; python -c "from build123d import Box; assert abs(Box(1, 2, 3).volume - 6) < 1e-9"; ccx -v || test "$?" -eq 201'
```

CalculiX returns status 201 for its version command.

Check Gmsh's CLI and generate a tetrahedral mesh through its Python API:

```sh
docker run --rm text-to-mfg:latest gmsh --version
docker run --rm text-to-mfg:latest python -c 'import gmsh; gmsh.initialize(); gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1); gmsh.model.occ.synchronize(); gmsh.model.mesh.generate(3); assert len(gmsh.model.mesh.getElements(3)[1][0]) > 0; gmsh.finalize()'
```
