# Git AI - AI-Powered Git Commit Message Generator

Automatically generate standardized git commit messages using AI.

## Features

- Read git staged changes
- Generate Conventional Commits compliant messages via LLM API
- Support custom models and API configuration
- Support auto-commit and clipboard copy

## Installation

```bash
# Clone repository
git clone <repository-url>
cd gai

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env file with your API key and configuration
```

## Configuration

Configure variables in `.env`:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
COMMIT_LANG=zh
```

Supported APIs:
- OpenAI Official API
- Any OpenAI-compatible API (Ollama, local models, etc.)
- Azure OpenAI Service
- Other OpenAI-compatible API services

## Usage

### Basic

```bash
# Add files to staging
git add .

# Generate commit message
python gai.py
```

### Auto-commit

```bash
python gai.py -m
```

### Copy to clipboard

```bash
python gai.py --copy
```

### Specify language

```bash
python gai.py -l en    # English
python gai.py -l zh    # Chinese
python gai.py -l ja    # Japanese
python gai.py -l ko    # Korean
```

## Examples

```
$ git add .
$ python gai.py
Analyzing 3 file(s) (language: zh)...

Generated Commit Message:
==========================================================================
feat(auth): Add user authentication module

- Implement JWT token generation and verification
- Add login/logout functionality
- Integrate user permission control
==========================================================================

$ python gai.py -m
Analyzing 3 file(s) (language: zh)...
✓ Commit successful!
```

## License

MIT
