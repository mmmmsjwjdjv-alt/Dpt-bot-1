FROM eclipse-temurin:11-jre-jammy

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates curl unzip file && rm -rf /var/lib/apt/lists/*

ARG DPT_VERSION=2.19.0
RUN mkdir -p /opt/dpt && curl -fsSL "https://github.com/luoyesiqiu/dpt-shell/releases/download/v${DPT_VERSION}/executable.zip" -o /tmp/dpt.zip && unzip -q /tmp/dpt.zip -d /opt/dpt && test -f /opt/dpt/dpt.jar && rm -f /tmp/dpt.zip

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY main.py .

CMD ["python3", "main.py"]
