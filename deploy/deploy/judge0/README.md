# Setting up the code judge

Student code must run somewhere safe. This project supports two judges. Pick with `JUDGE_BACKEND` in `backend/.env`.

| | `local` | `judge0` |
|---|---|---|
| For | Developing on your own computer | Real students (production) |
| Safe? | **NO.** No sandbox at all | Yes, if set up as below |
| Needs | Compilers on your computer | A Linux server with Docker |
| Refuses to start when | `APP_ENV` is not `development` | never |

## Part 1: Developing on your computer (`JUDGE_BACKEND=local`)

In `backend/.env`:

```
APP_ENV=development
JUDGE_BACKEND=local
```

Install the compilers for the languages you want to test. Python works with no extra step.

- **C and C++:** Windows: install MSYS2 or WinLibs (GCC) and add its `bin` folder to PATH. Mac: `xcode-select --install`. Linux: `sudo apt install build-essential`.
- **Java:** install a JDK (for example Temurin 17 from adoptium.net). You need `javac`, not only `java`.

Check what works:

```
cd backend
python -m app.scripts.check_judge
```

Lines marked `SKIP` are languages that are not installed. That is fine.

Warnings about the local judge:

- It runs the code **directly on your computer**. A student program could delete files or use the network. Only run code you wrote or trust.
- On Windows it has only a time limit. A program that eats memory or fills the disk can slow your computer down.
- The check "Network is blocked" will say `FAIL` on your laptop. That is correct: the local judge cannot block the network.

## Part 2: Judge0 on a Linux server (`JUDGE_BACKEND=judge0`)

Judge0 is a free open source sandbox. We use **version 1.13.1 or newer**. Older versions (1.13.0 and before) had a published sandbox escape bug. Never use them.

> **Honest note:** the steps below follow the official Judge0 deployment guide and its documented settings.
> I could not run a real Judge0 server while writing this, so I could not test them end to end.
> That is why `check_judge` exists. Run it on your server and trust only what it says.

### What you need

- A Linux server (a small VPS with 2 CPU and 4 GB RAM is enough to start)
- Docker and Docker Compose installed
- **cgroup v1.** This is the most common problem. Judge0 1.13.1 does not work on hosts that use cgroup v2 only.
  Newer Ubuntu and Debian, Docker Desktop, and WSL2 often use v2. If your judge says "Internal Error" for every program, this is probably why.
  The official Judge0 deployment guide explains how to switch Ubuntu 22.04 to cgroup v1: add `systemd.unified_cgroup_hierarchy=0` to `GRUB_CMDLINE_LINUX` in `/etc/default/grub`, run `sudo update-grub`, then reboot.
  Read the current text on the official site before you do it, because it can change.
  Alternatively choose a server image that already uses cgroup v1 (for example Ubuntu 20.04, if your provider still offers it).

This is also why Judge0 is for the server only. Do not fight with it on a Windows laptop. Use the local judge there.

### Install (official steps)

```
wget https://github.com/judge0/judge0/releases/download/v1.13.1/judge0-v1.13.1.zip
unzip judge0-v1.13.1.zip
cd judge0-v1.13.1
```

Edit `judge0.conf`:

```
# passwords: use long random values (python3 -c "import secrets; print(secrets.token_hex(24))")
REDIS_PASSWORD=...
POSTGRES_PASSWORD=...

# safety: code cannot use the network, and nobody can switch the network on
ALLOW_ENABLE_NETWORK=false
ENABLE_NETWORK=false

# only our backend may talk to Judge0
AUTHN_HEADER=X-Auth-Token
AUTHN_TOKEN=put-a-long-random-value-here

# limits that match our app (see backend/app/core/config.py)
MAX_QUEUE_SIZE=1000
MAX_MEMORY_LIMIT=512000
# MAX_CPU_TIME_LIMIT=15 and MAX_WALL_TIME_LIMIT=20 are already the defaults
```

The names above come from Judge0's own configuration list. If your `judge0.conf` spells one differently, follow the comments in that file.

Keep Judge0 private. In `docker-compose.yml` change the server port line to
`"127.0.0.1:2358:2358"` if the backend runs on the same server, or close port 2358 in the firewall for everyone except your backend.

Start it:

```
docker-compose up -d db redis
sleep 10
docker-compose up -d
```

Then open `http://localhost:2358/about` on the server to see that it answers.

### Connect the backend

In `backend/.env` on the server:

```
APP_ENV=production
JUDGE_BACKEND=judge0
JUDGE0_URL=http://localhost:2358
JUDGE0_AUTH_TOKEN=the-same-value-as-AUTHN_TOKEN
```

### Test it. Do not skip this.

```
cd backend
python -m app.scripts.check_judge
```

Every line must say `PASS` (`SKIP` is fine for a language you do not offer). Pay most attention to:

- **Infinite loop is stopped**
- **Memory hog is stopped**
- **Output flood is stopped**
- **Network is blocked**

If any of these fail, do not let students use the server. Fix it, or ask for help with the exact output.

### Things to know

- Keep Judge0 updated. Sandbox bugs get fixed over time, so check the Judge0 releases page every few months.
- Each test case is run as its own job, so a problem with 10 tests means 10 jobs. Judge0 compiles C, C++ and Java again for every job. A small server handles one class well. For bigger use, add Judge0 workers or a bigger server.
- Time limits are multiplied for slower languages (Python x3, Java x2). See `backend/app/services/languages.py`.
- Java classes must be named `Main`. The starter template says so.
- "Memory limit exceeded" is shown as a runtime error, because Judge0 reports it that way.
