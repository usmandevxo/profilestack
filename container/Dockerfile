FROM alpine:3.19

ARG USER_ID=1001
ARG GROUP_ID=1001

RUN apk add --no-cache \
        chromium \
        xvfb \
        x11vnc \
        openbox \
        novnc \
        websockify \
        xset \
        font-noto \
        bash \
        python3 \
        coreutils \
        util-linux \
        tzdata \
        mesa-gl \
        mesa-dri-gallium \
    && addgroup -g ${GROUP_ID} chrome \
    && adduser -u ${USER_ID} -G chrome -D -s /bin/bash chrome \
    && mkdir -p /home/chrome/.config/chromium /home/chrome/Downloads /home/chrome/scripts /var/lib/dbus /etc/chromium/policies/managed \
    && touch /etc/machine-id /var/lib/dbus/machine-id /etc/timezone \
    && echo '{"SigninAllowed":false,"BrowserSignin":0,"SyncDisabled":true,"PasswordManagerEnabled":true,"MetricsReportingEnabled":false}' > /etc/chromium/policies/managed/default.json \
    && chown chrome:chrome /etc/machine-id /var/lib/dbus/machine-id /etc/timezone \
    && chown -R chrome:chrome /home/chrome /var/lib/dbus /etc/chromium \
    && ln -sf /usr/share/novnc/vnc_lite.html /usr/share/novnc/index.html \
    && rm -rf /var/cache/apk/* /tmp/* /var/tmp/*

COPY vnc_lite.html /usr/share/novnc/vnc_lite.html
RUN ln -sf /usr/share/novnc/vnc_lite.html /usr/share/novnc/index.html

COPY --chown=chrome:chrome hardware-spoof.sh   /home/chrome/scripts/
COPY --chown=chrome:chrome user-agent-spoof.sh /home/chrome/scripts/
COPY --chown=chrome:chrome proxy-wrapper.py    /home/chrome/scripts/
COPY --chown=chrome:chrome cdp-forwarder.py    /home/chrome/scripts/
COPY --chown=chrome:chrome openbox-rc.xml      /home/chrome/scripts/
COPY --chown=chrome:chrome entrypoint.sh       /home/chrome/scripts/

RUN chmod +x /home/chrome/scripts/*.sh /home/chrome/scripts/*.py

ENV CHROME_PROFILE=default
ENV DISPLAY=:99

USER chrome
WORKDIR /home/chrome

EXPOSE 6080 9222

ENTRYPOINT ["/home/chrome/scripts/entrypoint.sh"]
CMD []
