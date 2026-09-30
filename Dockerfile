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
RUN mkdir -p /opt/dpt \
    && curl -fL \
       "https://github.com/luoyesiqiu/dpt-shell/releases/download/v2.21.0/dpt-shell-v2.21.0.zip" \
       -o /tmp/dpt.zip \
    && unzip -q /tmp/dpt.zip -d /opt/dpt \
    && DPT_JAR="$(find /opt/dpt -type f -name 'dpt.jar' | head -n 1)" \
    && test -n "$DPT_JAR" \
    && cp "$DPT_JAR" /opt/dpt.jar \
    && rm -rf /tmp/dpt.zip

COPY requirements.txt /app/requirements.txt

RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN mkdir -p /app/data /tmp/maxo_dpt_jobs

CMD ["python3", "main.py"]
