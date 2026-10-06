FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y \
    git \
    wget \
    unzip \
    zip \
    openjdk-17-jdk \
    build-essential \
    cmake \
    ninja-build \
    clang \
    libc6-dev \
    libstdc++6 \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Android command-line tools
RUN mkdir -p /opt/android-sdk/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmdline-tools.zip && \
    unzip -q /tmp/cmdline-tools.zip -d /opt/android-sdk/cmdline-tools && \
    mv /opt/android-sdk/cmdline-tools/cmdline-tools /opt/android-sdk/cmdline-tools/latest && \
    rm /tmp/cmdline-tools.zip

ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV PATH=$PATH:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/build-tools/35.0.0

RUN yes | sdkmanager --licenses >/dev/null 2>&1 || true

RUN sdkmanager \
    "platform-tools" \
    "platforms;android-35" \
    "build-tools;35.0.0" \
    "ndk;27.2.12479018"

ENV ANDROID_NDK_HOME=/opt/android-sdk/ndk/27.2.12479018

# Clone Dex2C
RUN git clone --depth 1 https://github.com/Kirlif/d2c.git /opt/dex2c

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements.txt

# Install Dex2C dependencies separately
RUN pip install \
    "androguard>=3.4.0,<4" \
    "lxml>=4.9,<6"

COPY . /app

RUN chmod +x /app/*.sh 2>/dev/null || true

CMD ["python", "main.py"]