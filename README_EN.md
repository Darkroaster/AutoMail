**English** | [中文](README.md)

# AutoMail - Email Summary Bot for Feishu

Automatically fetch emails from a specified sender via IMAP, generate summaries using an LLM, and push them to a Feishu (Lark) group chat.

> This project uses [DeepLearning.AI DataPoints](https://www.deeplearning.ai/the-batch/) emails (`datapoints@deeplearning.ai`) as the default example. You can adapt it to any sender by configuring `TARGET_SENDER` and `SYSTEM_PROMPT`.

## Features

- Fetch emails from a specified sender via IMAP (using persistent IMAP UIDs, stable across sessions)
- Batch-fetch FROM headers for fast sender filtering, even in large mailboxes
- Parse HTML email content and extract clean body text
- Generate summaries via LLM API (output language & format fully customizable via `SYSTEM_PROMPT`), with multi-model automatic fallback
- Push message cards to Feishu via custom bot Webhook (supports Markdown bold, hyperlinks)
- First run processes only the latest email; subsequent runs process all new emails individually
- Track processed email UIDs to avoid duplicate pushes
- Support both one-time execution and scheduled daily runs

## Workflow

```
Connect to mailbox via IMAP
    ↓
Batch-fetch all email FROM headers, filter by TARGET_SENDER
    ↓
First run? → Yes: process only the latest email, mark older ones as processed
           → No:  process all unprocessed emails
    ↓
For each email:
  Parse HTML → extract & clean plain text
    ↓
  Call LLM API to generate summary (language/format determined by SYSTEM_PROMPT)
    ↓
  Push message card via Feishu Webhook
    ↓
  Mark email UID as processed (write to processed.json)
```

## Prerequisites

### 1. Enable IMAP on Your Mailbox

For 163 Mail: Log in to the web interface → Settings → POP3/SMTP/IMAP → Enable IMAP → Generate an **authorization code** (not your login password). Other providers (Gmail, Outlook, etc.) follow a similar process.

### 2. LLM API Key

Defaults to [OpenRouter](https://openrouter.ai/) (free model `z-ai/glm-4.5-air:free`). Also supports any OpenAI-compatible API provider (see "Custom LLM Settings" below).

### 3. Feishu Custom Bot

Add a custom bot in a Feishu group chat to get the Webhook URL. Path: Group Settings → Group Bots → Add Bot → Custom Bot.

## Installation

```bash
# Create virtual environment
uv venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
uv pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit the `.env` file with the required values:

```ini
EMAIL_ADDRESS=your_email@163.com
EMAIL_AUTH_CODE=your_imap_authorization_code
LLM_API_KEY=your_api_key
FEISHU_WEBHOOK_URL=your_feishu_webhook_url
```

Optional settings (all have defaults):

| Setting | Default | Description |
|---------|---------|-------------|
| `EMAIL_IMAP_HOST` | `imap.163.com` | IMAP server address |
| `LLM_API_URL` | `https://openrouter.ai/api/v1/chat/completions` | LLM API endpoint |
| `LLM_MODEL` | `z-ai/glm-4.5-air:free` | LLM model name |
| `TARGET_SENDER` | `datapoints@deeplearning.ai` | Target sender email address |
| `SYSTEM_PROMPT` | (built-in default) | System prompt sent to the LLM |
| `LLM_FALLBACK_MODELS` | 3 OpenRouter free models | Fallback model list (comma-separated, empty to disable) |
| `SCHEDULE_HOUR` | `7` | Hour of daily execution (0-23) |
| `SCHEDULE_MINUTE` | `30` | Minute of daily execution (0-59) |
| `IMAP_TIMEOUT` | `30` | IMAP connection timeout (seconds) |
| `FIRST_RUN_LIMIT` | `1` | Number of emails to fetch on first run |

## Usage

### Run Once

```bash
python main.py --once
```

### Scheduled (daily at 07:30 by default)

```bash
python main.py --schedule
```

Adjust the schedule via `SCHEDULE_HOUR` and `SCHEDULE_MINUTE` in `.env`.

### Step-by-Step Diagnostics

If you encounter issues, use the diagnostic script to test each component:

```bash
python test_steps.py
```

This script tests IMAP connection → text extraction → LLM summary → Feishu push, with detailed output for each step.

## Custom LLM Settings

This project defaults to [OpenRouter](https://openrouter.ai/) as the LLM API provider. To use another OpenAI Chat Completions-compatible provider (e.g., OpenAI, DeepSeek, SiliconFlow), simply modify these three values in `.env`:

```ini
LLM_API_URL=https://api.deepseek.com/chat/completions
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-chat
```

### Customizing Output Language & Format

The summary content pushed to Feishu is entirely controlled by `SYSTEM_PROMPT` — including **output language**, **summary format**, and **level of detail**. Set `SYSTEM_PROMPT` in `.env` to override the built-in default.

Examples:

**Output in Japanese:**

```ini
SYSTEM_PROMPT=あなたはニュース要約アシスタントです。ユーザーが提供する英文メールの内容を日本語で要約してください...
```

**Output in English:**

```ini
SYSTEM_PROMPT=You are a news summarizer. Summarize each news item from the email in English, no more than 2 sentences each...
```

**Full translation instead of summary:**

```ini
SYSTEM_PROMPT=Translate the following email content into Korean, preserving the original format and links...
```

If not set, the built-in Simplified Chinese news summary prompt is used.

### Fallback Models

Fallback models can also be configured via `.env`. The defaults are OpenRouter free models. Non-OpenRouter users should change them to models supported by their provider, or set empty to disable:

```ini
# Using OpenAI, set fallback models
LLM_FALLBACK_MODELS=gpt-4o,gpt-4o-mini

# Or leave empty to disable fallback
LLM_FALLBACK_MODELS=
```

## Project Structure

```
AutoMail/
├── automail/               # Core package
│   ├── __init__.py
│   ├── config.py           # Configuration (loads from .env)
│   ├── email_fetcher.py    # IMAP email fetching (UID management, first-run logic)
│   ├── email_parser.py     # HTML email parsing & text cleaning
│   ├── summarizer.py       # LLM summary generation (multi-model fallback)
│   └── feishu_bot.py       # Feishu Webhook message card push
├── main.py                 # Entry point (one-time / scheduled execution)
├── test_steps.py           # Step-by-step diagnostic script
├── .env.example            # Configuration template
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependencies
├── README.md               # 中文文档
├── README_EN.md            # English documentation (this file)
└── processed.json          # Processed email UID records (auto-generated, do not edit)
```
