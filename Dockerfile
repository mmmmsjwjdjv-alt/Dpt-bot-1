FROM eclipse-temurin:21-jdk-jammy

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV DPT_BUILD_TOOLS=/opt/android-sdk/build-tools/35.0.0
ENV PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/build-tools/35.0.0:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates curl unzip git wget \
    && rm -rf /var/lib/apt/lists/*

# Android build-tools: required by the Unlock engine for zipalign/apksigner.
RUN mkdir -p /opt/android-sdk/cmdline-tools \
    && curl -fL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline-tools.zip \
    && unzip -q /tmp/cmdline-tools.zip -d /tmp/android-cmdline \
    && mv /tmp/android-cmdline/cmdline-tools /opt/android-sdk/cmdline-tools/latest \
    && yes | sdkmanager --sdk_root=/opt/android-sdk --licenses >/dev/null || true \
    && sdkmanager --sdk_root=/opt/android-sdk "platform-tools" "build-tools;35.0.0" \
    && rm -rf /tmp/cmdline-tools.zip /tmp/android-cmdline \
    && test -x /opt/android-sdk/build-tools/35.0.0/apksigner \
    && test -x /opt/android-sdk/build-tools/35.0.0/zipalign

# Official DPT Shell v2.21.0. Keep both dpt.jar and shell-files.
RUN mkdir -p /opt/dpt-package \
    && curl -fL "https://github.com/luoyesiqiu/dpt-shell/releases/download/v2.21.0/dpt-shell-v2.21.0.zip" -o /tmp/dpt.zip \
    && unzip -q /tmp/dpt.zip -d /opt/dpt-package \
    && DPT_JAR="$(find /opt/dpt-package -type f -name 'dpt.jar' | head -n 1)" \
    && test -n "$DPT_JAR" \
    && cp "$DPT_JAR" /opt/dpt.jar \
    && SHELL_DIR="$(find /opt/dpt-package -type d -name 'shell-files' | head -n 1)" \
    && test -n "$SHELL_DIR" \
    && cp -a "$SHELL_DIR" /opt/shell-files \
    && test -f /opt/dpt.jar \
    && test -d /opt/shell-files \
    && rm -rf /opt/dpt-package /tmp/dpt.zip

# Clone the DPT-only branch/tool at build time; source is not bundled in this bot archive.
RUN git clone --depth 1 https://github.com/0xgf-18/unpacker-by-fahad.git /opt/fahad-unpacker \
    && cd /opt/fahad-unpacker \
    && chmod +x gradlew run.sh \
    && ./gradlew --no-daemon installDist

COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt
COPY main.py /app/main.py
RUN mkdir -p /tmp/maxo_jobs

CMD ["python3", "main.py"]
