FROM redroid/redroid:13.0.0_64only-latest AS android

FROM debian:bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends util-linux mount iproute2 procps \
 && rm -rf /var/lib/apt/lists/*
COPY --from=android / /android
COPY --chmod=755 start /usr/local/bin/phone-start
COPY --chmod=755 android /usr/local/bin/android
CMD ["/usr/local/bin/phone-start"]
