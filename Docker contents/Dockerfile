FROM node:24-trixie-slim AS offline-shell
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libseccomp-dev
COPY ["Docker contents/offline-shell.c", "/tmp/offline-shell.c"]
RUN gcc -Wall -Wextra -Werror -o /pi-offline-shell /tmp/offline-shell.c -lseccomp

FROM node:24-trixie-slim AS gmsh-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl cmake g++ make libocct-data-exchange-dev
RUN curl -fsSLO https://gmsh.info/src/gmsh-4.15.2-source.tgz \
    && echo "be3f66f225d27ba9fa014f07e83169285da8a051b0e8ab7103d88066b39bdd3e  gmsh-4.15.2-source.tgz" | sha256sum -c \
    && tar -xzf gmsh-4.15.2-source.tgz -C /tmp \
    && cmake -S /tmp/gmsh-4.15.2-source -B /tmp/gmsh-build \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/gmsh \
        -DENABLE_BUILD_DYNAMIC=ON -DENABLE_FLTK=OFF \
    && cmake --build /tmp/gmsh-build --parallel 4 \
    && cmake --install /tmp/gmsh-build

# Debian 13 dropped calculix-ccx, so build upstream 2.23 (matches the Mac install).
FROM node:24-trixie-slim AS ccx-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl bzip2 gcc gfortran make perl libarpack2-dev libopenblas-dev
WORKDIR /build
RUN curl -fsSLO https://www.dhondt.de/ccx_2.23.src.tar.bz2 \
    && curl -fsSLO https://www.netlib.org/linalg/spooles/spooles.2.2.tgz \
    && printf '%s\n' \
        "9c88385c10fb04f5dc6c4e98027a51bebdd8aee3920e05190d6c1dd08357d6e7  ccx_2.23.src.tar.bz2" \
        "a84559a0e987a1e423055ef4fdf3035d55b65bbe4bf915efaa1a35bef7f8c5dd  spooles.2.2.tgz" | sha256sum -c \
    && tar -xjf ccx_2.23.src.tar.bz2 \
    && mkdir CalculiX/ccx_2.23/SPOOLES.2.2 && tar -xzf spooles.2.2.tgz -C CalculiX/ccx_2.23/SPOOLES.2.2
# ponytail: SPOOLES and ccx predate gcc 14's stricter C; -fpermissive keeps them compiling.
RUN cd CalculiX/ccx_2.23/SPOOLES.2.2 \
    && make lib CC=gcc OPTLEVEL="-O2 -fpermissive -w" \
    && cd MT/src && make -f makeGlobalLib CC=gcc OPTLEVEL="-O2 -fpermissive -w"
RUN cd CalculiX/ccx_2.23/src \
    && make -f Makefile_MT -j"$(nproc)" CC=gcc ccx_2.23_MT.a \
        CFLAGS='-O2 -w -fpermissive -fopenmp -I ../SPOOLES.2.2 -DARCH=Linux -DSPOOLES -DARPACK -DMATRIXSTORAGE -DUSE_MT=1' \
        FFLAGS='-O2 -w -fopenmp -cpp -fallow-argument-mismatch' \
    && ./date.pl \
    && gcc -O2 -w -fpermissive -fopenmp -I ../SPOOLES.2.2 -DARCH=Linux -DSPOOLES -DARPACK -DMATRIXSTORAGE -DUSE_MT=1 -c ccx_2.23.c \
    && gfortran -fopenmp -O2 -o /usr/local/bin/ccx_2.23 ccx_2.23.o ccx_2.23_MT.a \
        ../SPOOLES.2.2/spooles.a -larpack -lopenblas -lpthread -lm

FROM node:24-trixie-slim AS cgx-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl bzip2 g++ make libgl-dev libglu1-mesa-dev \
    libx11-dev libxi-dev libxmu-dev libxext-dev libxt-dev libsm-dev libice-dev
WORKDIR /build
RUN curl -fsSLO https://www.dhondt.de/cgx_2.23.all.tar.bz2 \
    && echo "04abbe0d2bac6a7bff018238b409568c189ede25589880e8cdd947f56ebd67c7  cgx_2.23.all.tar.bz2" | sha256sum -c \
    && tar -xjf cgx_2.23.all.tar.bz2 \
    && cd CalculiX/cgx_2.23/src && make -j"$(nproc)" \
    && install -m 755 cgx /usr/local/bin/cgx

# Official static release builds; Pi's grep/find tools use these from PATH instead of downloading.
FROM node:24-trixie-slim AS search-tools
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl
RUN case "$TARGETARCH" in \
        arm64) a=aarch64 rg=800b1e7206afe799dfb5a6901f23147cfaabe0e52210538100f61e86e1740915 fd=d76c4317f7d5dba69f8a2a15856c90c777e7f0dd4e85f0de8c76de6992c374d4 ;; \
        amd64) a=x86_64 rg=33e15bcf1624b25cdd2a55813a47a2f95dbe126268203e76aa6a585d1e7b149c fd=761c72dc8e120d85b22292063be8a796e2eeb20eb3e4f38b8fa2343ccf3514a7 ;; \
        *) echo "unsupported arch $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && curl -fsSLo rg.tgz "https://github.com/BurntSushi/ripgrep/releases/download/15.2.0/ripgrep-15.2.0-$a-unknown-linux-musl.tar.gz" \
    && curl -fsSLo fd.tgz "https://github.com/sharkdp/fd/releases/download/v10.5.0/fd-v10.5.0-$a-unknown-linux-musl.tar.gz" \
    && printf '%s  rg.tgz\n%s  fd.tgz\n' "$rg" "$fd" | sha256sum -c \
    && tar -xzf rg.tgz --strip-components=1 -C /usr/local/bin --wildcards '*/rg' \
    && tar -xzf fd.tgz --strip-components=1 -C /usr/local/bin --wildcards '*/fd'

FROM node:24-trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv git ca-certificates libgl1 libseccomp2 libocct-data-exchange-7.8 \
    libarpack2t64 libopenblas0-pthread libgfortran5 libgomp1 \
    libglu1-mesa libxi6 libxmu6 libxt6t64 libgl1-mesa-dri xvfb xauth imagemagick \
    procps psmisc less file unzip zip bzip2 xz-utils jq bc tree patch diffutils nano vim-tiny \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir build123d==0.13.0 \
        matplotlib==3.11.2 meshio==5.3.5 trimesh==5.2.0 pypdf==6.21.3
COPY --from=gmsh-build /opt/gmsh /opt/gmsh
COPY --from=ccx-build /usr/local/bin/ccx_2.23 /usr/bin/ccx
COPY --from=cgx-build /usr/local/bin/cgx /usr/local/bin/cgx
COPY --from=search-tools /usr/local/bin/rg /usr/local/bin/fd /usr/local/bin/
ENV PYTHONPATH="/opt/gmsh/lib"

WORKDIR /opt/pi
COPY ["Docker contents/package.json", "Docker contents/package-lock.json", "./"]
RUN npm ci --omit=dev && npm cache clean --force
COPY ["Docker contents/metering.ts", "Docker contents/web-search.ts", "Docker contents/redact.ts", "/opt/pi/extensions/"]
COPY --from=offline-shell /pi-offline-shell /usr/local/bin/pi-offline-shell
COPY ["Docker contents/pi-launcher.sh", "/usr/local/bin/pi"]
COPY ["Docker contents/ccx-limited.py", "/usr/local/bin/ccx"]
RUN chmod 755 /usr/local/bin/pi /usr/local/bin/ccx
COPY ["Docker contents/README.md", "/opt/README.md"]

COPY ["Docker contents/docs/", "/tmp/docs/"]
RUN cd /tmp/docs && sha256sum -c SHA256SUMS \
    && mkdir -p /opt/docs/calculix-2.23 /opt/docs/build123d-0.13.0 /opt/docs/nas \
    && python3 -m tarfile -e ccx_2.23.htm.tar.bz2 /opt/docs/calculix-2.23 \
    && python3 -m tarfile -e cgx_2.23.htm.tar.bz2 /opt/docs/calculix-2.23 \
    && test -s /opt/docs/calculix-2.23/CalculiX/cgx_2.23/doc/cgx/cgx.html \
    && python3 -m zipfile -e build123d-v0.13.0.epub /opt/docs/build123d-0.13.0 \
    && cp NAS*.pdf /opt/docs/nas/ \
    && for f in /opt/docs/nas/*.pdf; do pdftotext -layout "$f"; done \
    && test -s /opt/docs/calculix-2.23/CalculiX/ccx_2.23/doc/ccx/ccx.html \
    && test -s /opt/docs/build123d-0.13.0/index.xhtml \
    && rm -rf /tmp/docs

ENV PATH="/usr/local/bin:/opt/gmsh/bin:/opt/venv/bin:/opt/pi/node_modules/.bin:${PATH}" \
    MPLBACKEND=Agg \
    CCXDOCS=/opt/docs/calculix-2.23/CalculiX/ccx_2.23/doc/ccx \
    CGXDOCS=/opt/docs/calculix-2.23/CalculiX/cgx_2.23/doc/cgx
RUN useradd --create-home --uid 1001 pi \
    && mkdir -p /workspace && chown pi:pi /workspace
USER pi
WORKDIR /workspace
CMD ["bash"]
