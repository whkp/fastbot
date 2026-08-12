<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./images/readme-cover-dark.svg">
  <img alt="fastbot README cover" src="./images/readme-cover-light.svg">
</picture>

<div align="center">
  <p>
    Upstream docs:
    <a href="https://nanobot.wiki/docs/latest/getting-started/nanobot-overview">English</a> |
    <a href="https://nanobot.wiki/cn/docs/latest/getting-started/nanobot-overview">简体中文</a> |
    <a href="https://nanobot.wiki/zh-Hant/docs/latest/getting-started/nanobot-overview">繁體中文</a> |
    <a href="https://nanobot.wiki/es/docs/latest/getting-started/nanobot-overview">Español</a> |
    <a href="https://nanobot.wiki/fr/docs/latest/getting-started/nanobot-overview">Français</a> |
    <a href="https://nanobot.wiki/id/docs/latest/getting-started/nanobot-overview">Bahasa Indonesia</a> |
    <a href="https://nanobot.wiki/ja/docs/latest/getting-started/nanobot-overview">日本語</a> |
    <a href="https://nanobot.wiki/ko/docs/latest/getting-started/nanobot-overview">한국어</a> |
    <a href="https://nanobot.wiki/ru/docs/latest/getting-started/nanobot-overview">Русский</a> |
    <a href="https://nanobot.wiki/vi/docs/latest/getting-started/nanobot-overview">Tiếng Việt</a>
  </p>
  <p>
    <a href="https://github.com/whkp/fastbot"><img src="https://img.shields.io/github/stars/whkp/fastbot?style=flat&logo=github" alt="GitHub stars"></a>
    <a href="https://github.com/whkp/fastbot/actions"><img src="https://github.com/whkp/fastbot/actions/workflows/ci.yml/badge.svg?branch=main" alt="Test Suite"></a>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/badge/runtime-nanobot--ai-blue" alt="nanobot-ai compatibility"></a>
    <a href="./LICENSE"><img src="https://img.shields.io/github/license/whkp/fastbot" alt="MIT License"></a>
    <a href="https://nanobot.wiki/docs/latest/getting-started/nanobot-overview"><img src="https://img.shields.io/badge/upstream_docs-nanobot.wiki-blue" alt="nanobot upstream documentation"></a>
  </p>
  <p>
    <a href="https://discord.gg/MnCvHqpUGB">nanobot Discord</a> ·
    <a href="https://github.com/whkp/fastbot">GitHub</a> ·
    <a href="https://github.com/HKUDS/nanobot">nanobot upstream</a>
  </p>
</div>

# fastbot

**fastbot** is a lightweight, self-hosted personal AI agent framework based on
[HKUDS/nanobot](https://github.com/HKUDS/nanobot). It retains nanobot's WebUI, terminal,
chat-app, memory, MCP, model-routing, automation, and API capabilities, then adds
model-managed planning and role-aware delegation without introducing a second orchestration
runtime.

> [!NOTE]
> Fastbot currently keeps the upstream Python package, module, and configuration directory
> names for compatibility. The recommended CLI is now
> `fastbot`; the original `nanobot` command remains available as a compatibility alias.

## Start Here

| You want to... | Go to |
|---|---|
| Install fastbot with no terminal/config background | [Start Without Technical Background](./docs/start-without-technical-background.md) |
| Install quickly and get one CLI reply | [Install](#-install) and [Quick Start](#-quick-start) |
| Open the bundled browser UI | [WebUI](#-webui) |
| Connect Telegram, Discord, WeChat, Slack, Email, Mattermost, or another chat app | [Chat Apps](./docs/chat-apps.md) |
| Configure providers, fallback models, Langfuse, MCP, web tools, or security | [Docs](./docs/README.md) and [Configuration](./docs/configuration.md) |
| Understand or extend the internals | [Architecture](./docs/architecture.md) and [Development](./docs/development.md) |
| Deploy to the cloud or keep fastbot running as a service | [Deployment](./docs/deployment.md) |

## What can fastbot do?

fastbot is a self-hosted personal AI agent runtime. It can:

- run in a browser WebUI or terminal
- connect to Telegram, Discord, Slack, WeChat, Email, Mattermost, and other chat apps
- use tools such as files, shell, web search, web fetch, MCP, cron, image generation, and subagents
- keep session history and long-term memory through Dream
- run long-horizon goals and scheduled automations
- expose a Python SDK and OpenAI-compatible API for integrations
- deploy as a long-running local or server-side agent gateway

## Fastbot Changes From nanobot

Fastbot is a modified fork of nanobot. It keeps nanobot's lightweight ReAct runtime and adds
model-managed planning and role-aware subagents. The additions are intentionally implemented as
regular tools so the model can choose the smallest workflow for each request:

- **Automatic planning choice**: simple requests continue through the normal single-agent
  loop; for genuinely multi-step work, the model can call `update_plan` without a `/plan`
  command or a separate planning mode.
- **Live plan snapshots**: `update_plan` stores one short, complete plan snapshot in the
  current session. The latest active plan is injected into each subsequent model request,
  including the next request in the same tool-calling turn, so the model can revise it as
  evidence changes.
- **Role-aware subagents**: complex plan steps can call `spawn(..., role=..., wait=true)`.
  The built-in roles are `researcher`, `analyst`, `reviewer`, `implementer`, and `default`,
  each with focused instructions and real tool permissions. Read-only roles cannot edit files,
  execute commands, spawn more agents, or update the main plan.
- **Lightweight integration**: the feature reuses existing sessions, tool registries,
  workspace boundaries, and subagent delivery. It does not add a planner service, DAG
  scheduler, new CLI command, or WebUI plan panel.

Planning is disabled by default. Enable it in the agent defaults when you want the main agent
to have access to `update_plan`:

```json
{
  "agents": {
    "defaults": {
      "plan": {
        "enabled": true
      }
    }
  }
}
```

## 💡 Why fastbot

- **Persistent workflows**: goals, memory, tools, and chat context survive long-running work.
- **Chat-native reach**: WebUI, API, Telegram, Feishu, Slack, Discord, Teams, email, and Mattermost.
- **Model freedom**: OpenAI-compatible APIs, local LLMs, image generation, search, and fallbacks.
- **Small core**: readable internals with MCP, memory, deployment, and automation built in.
- **Own your stack**: inspect, customize, self-host, and extend without a giant platform.

## 📦 Install

> [!IMPORTANT]
> Fastbot changes are available only from this repository. The published `nanobot-ai` package
> and the upstream installer install nanobot, not this fork.

Prerequisites: Python 3.11 or newer, Git, and `bun` or `npm` to build the bundled WebUI.
From an activated virtual environment:

If terminals, API keys, or config files are new to you, use the guided zero-background walkthrough in [Start Without Technical Background](./docs/start-without-technical-background.md) instead of this compact README path.

```bash
git clone https://github.com/whkp/fastbot.git
cd fastbot
python -m pip install .
```

On Windows, if pip reports that it cannot launch `npm`, run `cd webui`, `npm.cmd install --package-lock=false`, `npm.cmd run build`, and `cd ..` in order, then retry the install. Contributors who need an editable checkout should follow [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`webui/README.md`](./webui/README.md).

The installed package and Python module still use the upstream-compatible names `nanobot-ai` and
`nanobot`. The installation also provides the shorter `fastbot` executable; the original
`nanobot` executable remains available as a compatibility alias.

Verify the install:

```bash
fastbot --version
```

If `fastbot` is not on `PATH`, use the Python executable from the environment where Fastbot was
installed, for example `python -m nanobot --version` in the activated virtual environment.

## 🚀 Quick Start

**Open fastbot in your browser**

```bash
fastbot webui
```

This is the recommended first run. The launcher creates the config and workspace when needed, safely enables the local WebSocket channel after confirmation, starts the gateway, and opens [`http://127.0.0.1:8765`](http://127.0.0.1:8765). A fresh install can open before a model is configured, so setup continues in the browser instead of beginning in a JSON file. The first-run WebUI binds to localhost by default and is not exposed to your LAN.

**Your first three steps**

1. Open **Settings → Models** and choose a provider, credential, and model.
2. Start a new topic and send `Hello!` to verify the connection.
3. Before project work, choose the intended workspace and access mode from the composer.

Any normal reply means the provider, model, workspace, and browser gateway are working together.

**Keep fastbot running after you close the terminal**

```bash
fastbot webui --background
```

This starts the same full gateway as `fastbot webui`, opens the browser, and leaves channels and automations running after the launcher exits. Complete first-time model setup with foreground `fastbot webui` before switching to background mode.

```bash
fastbot gateway status
fastbot gateway logs
fastbot gateway restart
fastbot gateway stop
```

**Prefer a gateway-first workflow?**

```bash
fastbot gateway
```

This skips WebUI setup and browser opening, then runs the same complete gateway in the current terminal. It is the familiar entry point if you are coming from OpenClaw or already operate agents as long-lived services. The WebUI remains available when its channel is configured; open it manually when needed.

Use `fastbot gateway --background` for the same direct entry point without keeping the terminal attached. For automatic startup and supervision by the operating system, see [Deployment](./docs/deployment.md).

**Prefer to work entirely in the terminal?**

```bash
fastbot agent
```

This opens an interactive terminal chat with the same configured model, workspace, and tools while keeping its own CLI session history. It does not open a browser or keep chat channels and automations running after you exit. Type `exit` or press `Ctrl+C` when you are done.

For one request and an immediate exit, use:

```bash
fastbot agent -m "Hello!"
```

The one-shot form is useful for a quick provider check, shell scripts, and local automation. If you have not configured a model yet, run `fastbot webui` and open **Settings → Models** first.

Need manual JSON, another device on your LAN, or help with provider/model matching? Continue with [Install and Quick Start](./docs/quick-start.md), [WebUI](./docs/webui.md), or [Troubleshooting](./docs/troubleshooting.md).

If fastbot worked for you, a star on GitHub is the simplest way to support the project.

- Want a pasteable provider setup? See [Provider Cookbook](./docs/provider-cookbook.md)
- Want to understand provider/model matching? See [Providers and Models](./docs/providers.md)
- Want web search, MCP, security settings, or more config options? See [Configuration](./docs/configuration.md)
- Want to run locally? See [Ollama](./docs/providers.md#ollama), [vLLM or another local OpenAI-compatible server](./docs/providers.md#vllm-or-other-local-openai-compatible-server), and the full [provider reference](./docs/configuration.md#providers).
- Want to run fastbot in chat apps like Telegram, Discord, WeChat or Feishu? See [Chat Apps](./docs/chat-apps.md)
- Want Docker or Linux service deployment? See [Deployment](./docs/deployment.md)

<a id="deploy-to-render"></a>

## ☁️ Deploy

**Render — one click**

Deploy fastbot's gateway and bundled WebUI from this repository's Blueprint:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/whkp/fastbot)

Render will ask for `ANTHROPIC_API_KEY` and a private `NANOBOT_WEB_TOKEN`, then provision persistent storage for sessions, memory, and WebUI history. Persistent disks require a paid Render service. The container keeps the upstream-compatible `nanobot` command; local installations can use `fastbot`.

**Self-host**

Prefer your own infrastructure? Follow the [deployment guide](./docs/deployment.md) for Docker, Docker Compose, Linux services, and macOS LaunchAgent setup.

## 🌐 WebUI

The WebUI ships with Fastbot's source distribution and requires no separate runtime frontend
service. It is the browser workbench for persistent topics, visible agent activity, workspace
controls, Apps, Skills, Automations, and settings.

<p align="center">
  <img src="images/nanobot_webui.png" alt="fastbot webui preview" width="900">
</p>

Use it to:

- keep separate topics for different tasks and projects;
- inspect reasoning, tool calls, file edits, diffs, command output, and generated artifacts;
- switch models and workspaces without leaving the conversation;
- configure providers, chat channels, Apps, Skills, and Automations from one place.

See the [WebUI guide](./docs/webui.md) for LAN access, background operation, workspace controls, and the full feature tour. Working on the frontend itself? Use [`webui/README.md`](./webui/README.md).

## 🏗️ Architecture

<p align="center">
  <img src="images/nanobot_arch.png" alt="fastbot architecture" width="800">
</p>

fastbot stays lightweight by centering everything around nanobot's small agent loop: messages
come in from chat apps, the LLM decides when tools are needed, and memory or skills are pulled
in only as context instead of becoming a heavy orchestration layer. Fastbot's planning and
delegation changes remain inside that loop rather than adding a second coordinator.

## 📚 Docs

Browse the [repo docs](./docs/README.md) for Fastbot's local codebase and development version.
The [nanobot wiki](https://nanobot.wiki/docs/latest/getting-started/nanobot-overview) remains the
reference for upstream features that Fastbot has not changed.

- Use task-oriented guides: [Guides](./docs/guides/README.md)
- Start with no technical background: [Start Without Technical Background](./docs/start-without-technical-background.md)
- Start from zero with developer basics: [Install and Quick Start](./docs/quick-start.md)
- Understand the runtime model: [Concepts](./docs/concepts.md)
- Read the source-level map: [Architecture](./docs/architecture.md)
- Choose a provider/model: [Providers and Models](./docs/providers.md)
- Copy provider setup recipes: [Provider Cookbook](./docs/provider-cookbook.md)
- Debug setup and runtime failures: [Troubleshooting](./docs/troubleshooting.md)
- Talk to fastbot with familiar chat apps: [Chat App AI Agent](./docs/guides/chat-app-ai-agent.md) · [Chat Apps](./docs/chat-apps.md)
- Schedule or trigger agent work: [Automations](./docs/automations.md)
- Configure providers, web search, MCP, and runtime behavior: [Configuration](./docs/configuration.md)
- Integrate fastbot with local tools and automations: [OpenAI-Compatible API](./docs/openai-api.md) · [Python SDK](./docs/python-sdk.md)
- Run fastbot with Docker or as a Linux service: [Deployment](./docs/deployment.md)

## Upstream Releases

Fastbot tracks [nanobot's upstream releases](https://github.com/HKUDS/nanobot/releases) and
adds the changes documented above. The upstream release notes remain useful for behavior shared
with nanobot, but they do not describe Fastbot-specific planning and role permissions.

**Upstream v0.3.0: [The Agency Release](https://github.com/HKUDS/nanobot/releases/tag/v0.3.0)**

The Agency Release turns nanobot from a durable workbench into an agent runtime that can
coordinate helpers, switch models per session, and carry authorized work through to completion.

- Consult inline subagents without leaving the current task
- Switch model presets per session directly from the composer
- Start from a guided WebUI setup with clearer execution controls
- Apply configuration changes live across a more reliable provider, channel, and tool runtime

[Read the v0.3.0 release notes](https://github.com/HKUDS/nanobot/releases/tag/v0.3.0)

## Upstream Recent Updates

- **2026-07-24** Guided first-run setup, inline subagents, and model switching from the composer.
- **2026-07-23** Grok OAuth with hosted X Search, live image settings, and clearer fallback models.
- **2026-07-22** Parallel Search, live configuration reloads, richer app discovery, and a smoother mobile WebUI.
- **2026-07-21** Codex fast mode, visible skill references, safer configuration saves, and sturdier task cleanup.
- **2026-07-20** Cleaner code blocks and copy actions, self-contained channels, and steadier QQ reconnects.

For older upstream updates, see the [release archive](./docs/release-archive.md) or
[nanobot GitHub releases](https://github.com/HKUDS/nanobot/releases).

## Upstream Open Source Partners

<p align="center">
  <a href="https://platform.kimi.com?aff=nanobot"><picture><source media="(prefers-color-scheme: dark)" srcset="https://kimi-file.moonshot.cn/prod-chat-kimi/kfs/4/1/2026-06-05/1d8h69mt3v89kkekg24gg"><img alt="Kimi Open Source Friends" height="44" src="https://kimi-file.moonshot.cn/prod-chat-kimi/kfs/4/1/2026-06-05/1d8h69fudcmosb3pipls0"></picture></a>
  <a href="https://platform.minimaxi.com/subscribe/token-plan?code=GILTJpMTqZ&source=link"><img alt="MiniMax" height="40" src="https://mintcdn.com/minimax-zh/1UjvBcdoC6r0UeyA/logo/light.svg?fit=max&auto=format&n=1UjvBcdoC6r0UeyA&q=85&s=672d724b639b2d88d0702fae329ea4f8"></a>
</p>

## 🤝 Contribute

Use fastbot for a real task, report what broke, and then pick a focused improvement.

- Read [CONTRIBUTING.md](./CONTRIBUTING.md) for the development workflow.
- Browse [fastbot issues](https://github.com/whkp/fastbot/issues) for problems to investigate.
- Open a [fastbot pull request](https://github.com/whkp/fastbot/pulls) for a focused fix or integration.

## Upstream Attribution

Fastbot is a modified fork of [HKUDS/nanobot](https://github.com/HKUDS/nanobot), which was
started by [Xubin Ren](https://github.com/re-bin) and is maintained with open-source
contributors. Fastbot retains the upstream MIT license and preserves upstream notices; report
Fastbot-specific issues through this repository and use the upstream repository for issues that
also reproduce without Fastbot's changes.

### Contributors

<a href="https://github.com/whkp/fastbot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=whkp/fastbot&max=100&columns=12" alt="fastbot contributors" />
</a>

<p align="center">
  <em> Thanks for visiting fastbot!</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=whkp.fastbot&style=for-the-badge&color=00d4ff" alt="Views">
</p>
