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
    hsetroot \
    novnc \
    procps \
    python3 \
    scrot \
    util-linux \
    websockify \
    x11-utils \
    x11vnc \
    xdotool \
    xvfb \
  && rm -rf /var/lib/apt/lists/* \
  && install -d -m 1777 /tmp/.X11-unix \
  && useradd --uid 1000 --create-home --home-dir /home/pc --shell /bin/bash pc

ARG TARGETARCH
ARG AGENT_BROWSER_VERSION=0.41.2
RUN case "$TARGETARCH" in \
    amd64) arch=x64 sha256=c4351f3802ffa5254d8c69f20a52e2fcf56925c6016fcf4203db25a07d811379 ;; \
    arm64) arch=arm64 sha256=00d291f45e1c4d527b3aa08c70c54c7c3030fde0794f8d4575aaa3ca1680f728 ;; \
    *) echo "no agent-browser for $TARGETARCH" >&2; exit 1 ;; \
  esac \
  && curl -fsSL --retry 5 -o /usr/local/bin/agent-browser \
    "https://github.com/vercel-labs/agent-browser/releases/download/v${AGENT_BROWSER_VERSION}/agent-browser-linux-${arch}" \
  && echo "$sha256  /usr/local/bin/agent-browser" | sha256sum -c - \
  && chmod 755 /usr/local/bin/agent-browser

COPY --chmod=755 start /usr/local/bin/pc-start
COPY --chmod=755 pc-browser /usr/local/bin/pc-browser
COPY --chmod=755 pc_page.py /usr/local/bin/pc-page
COPY --chmod=644 embed.html /usr/share/novnc/embed.html

USER pc
WORKDIR /home/pc
ENV HOME=/home/pc DISPLAY=:1
CMD ["/usr/local/bin/pc-start"]
