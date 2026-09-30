FROM eclipse-temurin:21-jre-jammy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 \
       python3-pip \
       ca-certificates \
       curl \
       unzip \
    && rm -rf /var/lib/apt/lists/*

# Download official DPT Shell v2.21.0
RUN mkdir -p /opt/dpt-package \
    && curl -fL \
       "https://github.com/luoyesiqiu/dpt-shell/releases/download/v2.21.0/dpt-shell-v2.21.0.zip" \
       -o /tmp/dpt.zip \
    && unzip -q /tmp/dpt.zip -d /opt/dpt-package \
    \
    # Find and install dpt.jar
    && DPT_JAR="$(find /opt/dpt-package -type f -name 'dpt.jar' | head -n 1)" \
    && test -n "$DPT_JAR" \
    && cp "$DPT_JAR" /opt/dpt.jar \
    \
    # Find and install required shell-files directory
    && SHELL_DIR="$(find /opt/dpt-package -type d -name 'shell-files' | head -n 1)" \
    && test -n "$SHELL_DIR" \
    && rm -rf /opt/shell-files \
    && cp -a "$SHELL_DIR" /opt/shell-files \
    \
    # Verify installation
    && test -f /opt/dpt.jar \
    && test -d /opt/shell-files \
    && echo "DPT JAR installed successfully" \
    && echo "shell-files installed successfully" \
    \
    # Cleanup
    && rm -rf /opt/dpt-package /tmp/dpt.zip

COPY requirements.txt /app/requirements.txt

RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/data /tmp/maxo_jobs

CMD ["python3", "main.py"]
