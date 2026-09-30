# MAXO DPT Bot — Railway

Files:
- `main.py`
- `Dockerfile`
- `requirements.txt`
- `railway.toml`
- `.dockerignore`

Railway Variables:
- `BOT_TOKEN` = Telegram bot token
- `ADMIN_ID` = numeric Telegram admin ID

The Dockerfile uses Eclipse Temurin Java 11 and downloads the official DPT Shell v2.19.0 `executable.zip` release at build time. DPT's official README documents Java CLI usage with `java -jar dpt.jar -f <package>` and `-o <output directory>`.

Only APK input is accepted. Input/output limit is 50 MB. Temporary job files are deleted after each job.
