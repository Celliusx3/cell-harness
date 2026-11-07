FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    chromium \
    curl \
    fluxbox \
    fonts-liberation \
    fonts-noto-color-emoji \
    novnc \
    procps \
    python3 \
    util-linux \
    websockify \
    x11-utils \
    x11vnc \
    xdotool \
    xvfb \
  && rm -rf /var/lib/apt/lists/* \
  && useradd --uid 1000 --create-home --home-dir /home/pc --shell /bin/bash pc

COPY --chmod=755 start /usr/local/bin/pc-start

USER pc
WORKDIR /home/pc
ENV HOME=/home/pc DISPLAY=:1
CMD ["/usr/local/bin/pc-start"]
