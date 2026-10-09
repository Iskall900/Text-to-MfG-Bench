FROM node:24-bookworm-slim AS offline-shell
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libseccomp-dev
COPY ["Docker contents/offline-shell.c", "/tmp/offline-shell.c"]
RUN gcc -Wall -Wextra -Werror -o /pi-offline-shell /tmp/offline-shell.c -lseccomp

FROM node:24-bookworm-slim AS gmsh-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl cmake g++ make libocct-data-exchange-dev
RUN curl -fsSL https://gmsh.info/src/gmsh-4.15.2-source.tgz | tar -xz -C /tmp \
    && cmake -S /tmp/gmsh-4.15.2-source -B /tmp/gmsh-build \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/gmsh \
        -DENABLE_BUILD_DYNAMIC=ON -DENABLE_FLTK=OFF \
    && cmake --build /tmp/gmsh-build --parallel 4 \
    && cmake --install /tmp/gmsh-build

FROM node:24-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv calculix-ccx git ca-certificates libgl1 libseccomp2 libocct-data-exchange-7.6 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir build123d==0.13.0
COPY --from=gmsh-build /opt/gmsh /opt/gmsh
ENV PYTHONPATH="/opt/gmsh/lib"

WORKDIR /opt/pi
COPY ["Docker contents/package.json", "Docker contents/package-lock.json", "./"]
RUN npm ci --omit=dev && npm cache clean --force
COPY ["Docker contents/metering.ts", "Docker contents/web-search.ts", "/opt/pi/extensions/"]
COPY --from=offline-shell /pi-offline-shell /usr/local/bin/pi-offline-shell
COPY ["Docker contents/pi-launcher.sh", "/usr/local/bin/pi"]
RUN chmod 755 /usr/local/bin/pi
COPY DfM/check_dfm.py DfM/config.json DfM/README.md DfM/verify_dfm.py /opt/DfM/
COPY ["Docker contents/README.md", "/opt/README.md"]

COPY ["Docker contents/docs/", "/tmp/docs/"]
RUN cd /tmp/docs && sha256sum -c SHA256SUMS \
    && mkdir -p /opt/docs/calculix-2.20 /opt/docs/build123d-0.13.0 \
    && python3 -m tarfile -e ccx_2.20.htm.tar.bz2 /opt/docs/calculix-2.20 \
    && python3 -m zipfile -e build123d-v0.13.0.epub /opt/docs/build123d-0.13.0 \
    && test -s /opt/docs/calculix-2.20/CalculiX/ccx_2.20/doc/ccx/ccx.html \
    && test -s /opt/docs/build123d-0.13.0/index.xhtml \
    && rm -rf /tmp/docs

ENV PATH="/usr/local/bin:/opt/gmsh/bin:/opt/venv/bin:/opt/pi/node_modules/.bin:${PATH}"
RUN useradd --create-home --uid 1001 pi \
    && mkdir -p /workspace && chown pi:pi /workspace
USER pi
WORKDIR /workspace
CMD ["bash"]
