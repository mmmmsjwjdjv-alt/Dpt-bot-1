FROM eclipse-temurin:21-jdk-jammy

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV DPT_BUILD_TOOLS=/opt/android-sdk/build-tools/35.0.0
ENV DEX2C_NDK=/opt/android-sdk/ndk/27.2.12479018
ENV PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/build-tools/35.0.0:/opt/android-sdk/ndk/27.2.12479018:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates curl unzip git wget build-essential \
    && rm -rf /var/lib/apt/lists/*

# Android SDK + build tools + NDK for DEX2C.
RUN mkdir -p /opt/android-sdk/cmdline-tools \
    && curl -fL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline-tools.zip \
    && unzip -q /tmp/cmdline-tools.zip -d /tmp/android-cmdline \
    && mv /tmp/android-cmdline/cmdline-tools /opt/android-sdk/cmdline-tools/latest \
    && yes | sdkmanager --sdk_root=/opt/android-sdk --licenses >/dev/null || true \
    && sdkmanager --sdk_root=/opt/android-sdk \
       "platform-tools" \
       "build-tools;35.0.0" \
       "ndk;27.2.12479018" \
    && rm -rf /tmp/cmdline-tools.zip /tmp/android-cmdline \
    && test -x /opt/android-sdk/build-tools/35.0.0/apksigner \
    && test -x /opt/android-sdk/build-tools/35.0.0/zipalign \
    && test -x /opt/android-sdk/ndk/27.2.12479018/ndk-build

# Official DPT Shell v2.21.0.
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

# Existing UNLOCK engine.
RUN git clone --depth 1 https://github.com/0xgf-18/unpacker-by-fahad.git /opt/fahad-unpacker \
    && cd /opt/fahad-unpacker \
    && chmod +x gradlew run.sh \
    && ./gradlew --no-daemon installDist

# DEX2C engine.
RUN git clone --depth 1 https://github.com/Kirlif/d2c.git /opt/dex2c \
    && cd /opt/dex2c \
    && python3 -m pip install --no-cache-dir -r requirements.txt \
    && python3 -m pip install --no-cache-dir "androguard>=3.4.0,<4"

# Configure DEX2C for the container NDK.
RUN python3 - <<'PY'
import json
p="/opt/dex2c/dcc.cfg"
cfg={
    "apkeditor":"tools/apkeditor.jar",
    "ndk_dir":"/opt/android-sdk/ndk/27.2.12479018",
    "signature":{
        "keystore_path":"keystore/debug.keystore",
        "alias":"androiddebugkey",
        "keystore_pass":"android",
        "store_pass":"android",
        "v1_enabled":True,
        "v2_enabled":True,
        "v3_enabled":True
    },
    "obfuscate":True,
    "dynamic_register":True
}
with open(p,"w",encoding="utf-8") as f:
    json.dump(cfg,f,indent=2)
PY

COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

COPY main.py /app/main.py
COPY patch_main.py /app/patch_main.py
RUN python3 /app/patch_main.py && rm -f /app/patch_main.py

RUN mkdir -p /tmp/maxo_jobs

CMD ["python3", "main.py"]
