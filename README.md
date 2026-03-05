[English](README_EN.md) | **中文**

# AutoMail - 邮件摘要飞书推送机器人

自动从邮箱抓取指定发件人的邮件，使用 LLM 生成摘要，并推送到飞书群聊。

> 本项目以抓取 [DeepLearning.AI DataPoints](https://www.deeplearning.ai/the-batch/) 邮件（`datapoints@deeplearning.ai`）为默认示例，你可以通过配置 `TARGET_SENDER` 和 `SYSTEM_PROMPT` 来适配任意发件人的邮件摘要需求。

## 功能

- 通过 IMAP 自动抓取指定发件人的邮件（使用真实 IMAP UID 标识，跨会话稳定）
- 批量获取邮箱 FROM 头进行发件人过滤，大邮箱也能快速完成
- 解析 HTML 邮件内容，提取正文文本
- 调用 LLM API 生成摘要（输出语言和格式通过 `SYSTEM_PROMPT` 完全自定义），多模型自动 fallback
- 通过飞书自定义机器人 Webhook 推送消息卡片（支持 Markdown 加粗、超链接）
- 首次运行仅处理最新 1 封邮件，后续运行自动处理所有新增邮件并逐条推送
- 自动记录已处理邮件 UID，避免重复推送
- 支持手动执行和定时调度两种运行方式

## 工作流程

```
IMAP 连接邮箱
    ↓
批量获取所有邮件 FROM 头，过滤 TARGET_SENDER 指定的发件人
    ↓
首次运行？ → 是：仅取最新 1 封，旧邮件标记为已处理
           → 否：取所有未处理邮件
    ↓
逐封处理：
  HTML 解析 → 纯文本提取与清洗
    ↓
  调用 LLM API 生成摘要（语言/格式由 SYSTEM_PROMPT 决定）
    ↓
  飞书 Webhook 推送富文本消息
    ↓
  标记该邮件 UID 为已处理（写入 processed.json）
```

## 前置准备

### 1. 邮箱开启 IMAP

以 163 邮箱为例：登录网页版 → 设置 → POP3/SMTP/IMAP → 开启 IMAP 服务 → 生成**授权码**（非登录密码）。其他邮箱（Gmail、Outlook 等）同理，需开启 IMAP 并获取授权凭据。

### 2. LLM API Key

默认使用 [OpenRouter](https://openrouter.ai/)（免费模型 `z-ai/glm-4.5-air:free`），也支持其他兼容 OpenAI 格式的 API 供应商（见下方"自定义 LLM 设置"章节）。

### 3. 飞书自定义机器人

在飞书群聊中添加自定义机器人，获取 Webhook URL。路径：群设置 → 群机器人 → 添加机器人 → 自定义机器人。

## 安装

```bash
# 创建虚拟环境
uv venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 安装依赖
uv pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写必要项：

```ini
EMAIL_ADDRESS=your_email@163.com
EMAIL_AUTH_CODE=你的163邮箱授权码
LLM_API_KEY=你的API Key
FEISHU_WEBHOOK_URL=你的飞书Webhook地址
```

可选配置项（均有默认值，按需修改）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `EMAIL_IMAP_HOST` | `imap.163.com` | IMAP 服务器地址 |
| `LLM_API_URL` | `https://openrouter.ai/api/v1/chat/completions` | LLM API 地址 |
| `LLM_MODEL` | `z-ai/glm-4.5-air:free` | LLM 模型名称 |
| `TARGET_SENDER` | `datapoints@deeplearning.ai` | 目标发件人邮箱地址 |
| `SYSTEM_PROMPT` | （内置默认值） | 发送给 LLM 的系统提示词 |
| `LLM_FALLBACK_MODELS` | OpenRouter 免费模型（3 个） | Fallback 模型列表，逗号分隔，留空禁用 |
| `SCHEDULE_HOUR` | `7` | 每天执行的小时（0-23） |
| `SCHEDULE_MINUTE` | `30` | 每天执行的分钟（0-59） |
| `IMAP_TIMEOUT` | `30` | IMAP 连接超时（秒） |
| `FIRST_RUN_LIMIT` | `1` | 首次运行抓取邮件数量 |

## 使用

### 手动执行一次

```bash
python main.py --once
```

### 定时调度（默认每天 07:30 执行）

```bash
python main.py --schedule
```

执行时间通过 `.env` 中的 `SCHEDULE_HOUR` 和 `SCHEDULE_MINUTE` 调整。

### 逐步诊断

如果遇到问题，可以使用诊断脚本逐步排查每个环节：

```bash
python test_steps.py
```

该脚本会依次测试 IMAP 连接 → 文本提取 → LLM 摘要 → 飞书推送，并输出每步的详细结果。

## 自定义 LLM 设置

本项目默认使用 [OpenRouter](https://openrouter.ai/) 作为 LLM API 供应商。如果你使用其他兼容 OpenAI Chat Completions 格式的供应商（如 OpenAI 官方、DeepSeek、硅基流动等），只需在 `.env` 中修改以下三项：

```ini
LLM_API_URL=https://api.deepseek.com/chat/completions
LLM_API_KEY=你的API Key
LLM_MODEL=deepseek-chat
```

### 自定义输出语言与格式

推送到飞书的摘要内容完全由 `SYSTEM_PROMPT` 决定——包括**输出语言**、**摘要格式**、**详细程度**等。你可以在 `.env` 中设置 `SYSTEM_PROMPT` 来覆盖内置默认值。

以下是一些示例：

**输出日文摘要：**

```ini
SYSTEM_PROMPT=あなたはニュース要約アシスタントです。ユーザーが提供する英文メールの内容を日本語で要約してください...
```

**输出英文摘要：**

```ini
SYSTEM_PROMPT=You are a news summarizer. Summarize each news item from the email in English, no more than 2 sentences each...
```

**输出简体中文全文翻译（而非摘要）：**

```ini
SYSTEM_PROMPT=你是一个翻译助手，请将以下英文邮件完整翻译为简体中文，保留原文格式和链接...
```

不设置则使用内置的简体中文新闻摘要 prompt。

Fallback 模型同样可通过 `.env` 配置。默认值是 OpenRouter 的免费模型，非 OpenRouter 用户应改为自己供应商支持的模型，或设为空以禁用 fallback：

```ini
# 使用 OpenAI 官方时，可设置备选模型
LLM_FALLBACK_MODELS=gpt-4o,gpt-4o-mini

# 或留空禁用 fallback，只使用主模型
LLM_FALLBACK_MODELS=
```

## 项目结构

```
AutoMail/
├── automail/               # 核心业务包
│   ├── __init__.py
│   ├── config.py           # 配置管理（从 .env 加载）
│   ├── email_fetcher.py    # IMAP 邮件抓取（UID 管理、首次运行逻辑）
│   ├── email_parser.py     # HTML 邮件解析与文本清洗
│   ├── summarizer.py       # LLM 摘要生成（多模型 fallback）
│   └── feishu_bot.py       # 飞书 Webhook 富文本推送
├── main.py                 # 主入口（单次执行 / 定时调度）
├── test_steps.py           # 逐步诊断脚本
├── .env.example            # 配置模板（含所有可配置项说明）
├── .gitignore              # Git 忽略规则
├── requirements.txt        # Python 依赖（含版本范围）
├── README.md               # 本文件
└── processed.json          # 已处理邮件 UID 记录（自动生成，勿手动编辑）
```
