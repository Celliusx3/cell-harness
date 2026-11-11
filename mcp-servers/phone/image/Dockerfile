FROM redroid/redroid:13.0.0_64only-latest AS android

FROM debian:bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends util-linux mount iproute2 procps \
    ca-certificates curl novnc websockify \
 && rm -rf /var/lib/apt/lists/*
ARG DROIDVNC_VERSION_CODE=67
ARG DROIDVNC_SHA256=5bc1de31b77df25f3444c1fff3e4a36a8a5ec6f2958f3fad70d9826babd013b4
RUN mkdir -p /opt/phone \
 && curl -fsSL --retry 5 -o /opt/phone/droidvnc-ng.apk \
    "https://f-droid.org/repo/net.christianbeier.droidvnc_ng_${DROIDVNC_VERSION_CODE}.apk" \
 && echo "$DROIDVNC_SHA256  /opt/phone/droidvnc-ng.apk" | sha256sum -c -
COPY --from=android / /android
COPY --chmod=755 start /usr/local/bin/phone-start
COPY --chmod=755 android /usr/local/bin/android
COPY --chmod=755 screen /usr/local/bin/phone-screen
COPY --chmod=644 embed.html /usr/share/novnc/embed.html
CMD ["/usr/local/bin/phone-start"]
