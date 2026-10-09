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

The image includes Pi 1.0.4, Build123d 0.13.0, Gmsh 4.15.2 (CLI and Python API), and Debian's CalculiX 2.20
(the local Mac installation uses CalculiX 2.23).

Gmsh is built from the official 4.15.2 source with OpenCASCADE support for
STEP geometry and without the graphical interface. This supports native Linux
ARM64 builds, for which the official pip package has no wheel.

Version-matched documentation is cached in the repository under `Docker contents/docs`
and extracted into the image, so reading it requires no network connection:

- CalculiX 2.20: `/opt/docs/calculix-2.20/CalculiX/ccx_2.20/doc/ccx/ccx.html`
- Build123d 0.13.0: `/opt/docs/build123d-0.13.0/index.xhtml`

The Build123d manual includes API references, tutorials, and examples. Its XHTML
pages and assets are extracted from the official EPUB and can be read as text or
opened in a browser. Search the manuals with `grep -ri 'search term' /opt/docs`.

Snapshots downloaded on 2026-10-09 from the official
[CalculiX HTML archive](https://www.dhondt.de/ccx_2.20.htm.tar.bz2) and
[Build123d 0.13.0 EPUB](https://build123d.readthedocs.io/_/downloads/en/v0.13.0/epub/).
The build verifies `docs/SHA256SUMS` before extraction. To refresh the cache,
replace the archives, regenerate the checksums, and rebuild the image; update
the documentation versions alongside any installed package version changes.

Inside a container, `pi`, `python`, `gmsh`, and `ccx` are available. Exit with `exit`
and resume a saved container with `docker start -ai mfg-1`.

Credentials are not included. To use DeepSeek, set `DEEPSEEK_API_KEY` in
your host shell and pass it at runtime:

```sh
docker run -it -e DEEPSEEK_API_KEY text-to-mfg:latest
```

Configure Pi's provider/model in that container as needed.

Pi exposes a `web_search` tool using the
[Brave Web Search API](https://api-dashboard.search.brave.com/documentation/services/web-search).
Set `BRAVE_SEARCH_API_KEY` in your host shell and pass it alongside your model key:

```sh
docker run -it -e DEEPSEEK_API_KEY -e BRAVE_SEARCH_API_KEY text-to-mfg:latest
```

Search returns up to five titles, URLs, and snippets into the conversation; it
never opens result URLs or saves remote files. Without the search key, searches
report a configuration error; local work still runs.

The `pi` launcher loads only the image's metering and search extensions. Both the
agent's `bash` tool and interactive `!` shell commands use an inherited Linux
seccomp filter that blocks network sockets, including Python/Node downloads and
package installs. Failure to install the filter stops the command. Local file
creation, CAD, FEA, and cached documentation remain available. Pi runs as the
unprivileged `pi` user, with its installed code and extensions owned by root.
Bind-mounted workspaces must be writable by UID 1001.

This policy applies to commands issued through the harness; the container's
ordinary terminal still has network access for operator administration. Do not
mount Docker sockets or other privileged services, or load additional trusted
extensions with network access. Existing containers need to be recreated from
the rebuilt image. Search text may be saved in Pi's normal session history.

The DfM checker, example `config.json`, README, and verification script are
included in `/opt/DfM`. The Docker environment README is at `/opt/README.md`.
Run the checker inside a container against a STEP file in your workspace:

```sh
python /opt/DfM/check_dfm.py /workspace/part.step --output-dir /workspace/results
python /opt/DfM/verify_dfm.py
```

The checker defaults to `/opt/DfM/config.json`. Use `--config` to supply your own
manufacturing limits. Read `/opt/DfM/README.md` for the checks and sampling
limitations; this is manufacturability screening, not CNC certification.
The image uses its existing Build123d installation, rather than the macOS
Python dependency lock described in the DfM README.

Pi automatically meters each prompt until the agent finishes, including tools,
retries, compaction, and queued continuations. It writes two files in the prompt's
working directory (normally `/workspace`):

- `agents-1-usage.txt`: total input, cached input, uncached input, and output tokens.
- `agents-1-time.txt`: total elapsed seconds from prompt submission to completion.

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
node --test metering.test.mjs web-search.test.mjs
```

Smoke check:

```sh
docker run --rm text-to-mfg:latest bash -ec 'pi --version; python -c "from build123d import Box; assert abs(Box(1, 2, 3).volume - 6) < 1e-9"; ccx -v || test "$?" -eq 201'
```

CalculiX 2.20 returns status 201 for its version command.

Check Gmsh's CLI and generate a tetrahedral mesh through its Python API:

```sh
docker run --rm text-to-mfg:latest gmsh --version
docker run --rm text-to-mfg:latest python -c 'import gmsh; gmsh.initialize(); gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1); gmsh.model.occ.synchronize(); gmsh.model.mesh.generate(3); assert len(gmsh.model.mesh.getElements(3)[1][0]) > 0; gmsh.finalize()'
```
