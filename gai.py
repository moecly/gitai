#!/usr/bin/env python3
"""
Git Commit Message Generator

读取git暂存区的变更，发送给LLM生成commit信息
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import Optional

import openai
from dotenv import load_dotenv


def get_staged_diff() -> str:
    """获取暂存区的差异内容"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get staged changes: {e}")
        sys.exit(1)


def get_staged_files() -> list[str]:
    """获取暂存区文件列表"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True
        )
        return [f for f in result.stdout.strip().split('\n') if f]
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get staged files: {e}")
        sys.exit(1)


def check_staged_changes() -> bool:
    """检查是否有暂存区的变更"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True
    )
    return bool(result.stdout.strip())


def generate_commit_message(diff: str, files: list[str], client: openai.OpenAI, model: str, lang: str = 'zh') -> str:
    """调用LLM生成commit信息"""
    
    lang_instructions = {
        'zh': {
            'system': '你是一个专业的代码贡献者，擅长生成简洁、清晰的中文git commit信息。',
            'prompt': '你是一个专业的git commit信息生成器。请根据以下代码变更，生成符合 Conventional Commits 规范的中文commit信息。'
        },
        'en': {
            'system': 'You are a professional code contributor, skilled at generating concise and clear English git commit messages.',
            'prompt': 'You are a professional git commit message generator. Based on the code changes below, generate an English commit message following Conventional Commits specification.'
        },
        'ja': {
            'system': 'あなたは簡潔で明確な日本語のgitコミットメッセージを作成するのが得意なプロフェッショナルなコード貢献者です。',
            'prompt': 'あなたはプロフェッショナルなgitコミットメッセージ生成者です。以下のコード変更に基づいて、Conventional Commits仕様に準拠した日本語のコミットメッセージを生成してください。'
        },
        'ko': {
            'system': '简洁하고 명확한 한국어 git 커밋 메시지를 작성하는 데 능숙한 전문 코드 기여자입니다.',
            'prompt': '당신은 전문적인 git 커밋 메시지 생성자입니다. 아래의 코드 변경 사항에 따라 Conventional Commits 사양을 준수하는 한국어 커밋 메시지를 생성해 주세요.'
        }
    }
    
    lang_config = lang_instructions.get(lang, lang_instructions['zh'])
    
    prompt = f"""{lang_config['prompt']}

暂存区变更的文件 / Changed files:
{', '.join(files) if files else '无文件列表 / No files listed'}

代码变更内容 / Code changes:
{diff if diff else '无变更内容 / No changes'}

请按以下格式生成commit信息 / Please generate commit message in this format:
1. 第一行 / First line: type(scope): description (不超过72字符 / max 72 chars)
2. 第二行 / Second line: 空行 / Blank line
3. 详细说明 / Detailed description: 简要描述这次变更的内容和原因 / Briefly describe the changes and reasons

type可选值 / Available types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, temp
scope: 此次变更影响的功能模块或文件 / The affected module or file

只返回commit信息，不要添加其他解释 / Only return the commit message, do not add other explanations."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": lang_config['system']
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=800
        )
        content = response.choices[0].message.content
        
        # Qwen等模型可能把思考过程放在reasoning_content中
        if not content:
            reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
            if reasoning:
                content = reasoning
        
        return content if content else ""
    except Exception as e:
        print(f"Error: LLM API call failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Generate git commit messages using AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gai                          # Generate commit message and display
  gai -m                       # Generate and auto-commit
  gai --copy                   # Copy to clipboard
  gai -l en                    # Generate English commit
  gai -l ja                    # Generate Japanese commit
        """
    )
    parser.add_argument(
        '-m', '--commit',
        action='store_true',
        help='Auto-commit after generation'
    )
    parser.add_argument(
        '-c', '--copy',
        action='store_true',
        help='Copy commit message to clipboard'
    )
    parser.add_argument(
        '--model',
        default=None,
        help='Specify model (default: from .env)'
    )
    parser.add_argument(
        '-l', '--lang',
        choices=['zh', 'en', 'ja', 'ko'],
        default=None,
        help='Commit message language (default: from .env)'
    )
    
    args = parser.parse_args()
    
    # 从环境变量读取默认语言
    default_lang = os.getenv('COMMIT_LANG', 'zh')
    if args.lang is None:
        args.lang = default_lang
    
    # 加载环境变量 - 支持多个位置
    env_loaded = False
    env_paths = [
        Path.cwd() / '.env',                    # 当前目录
        Path.home() / '.gai.env',               # home目录
        Path.home() / '.config' / 'gai' / '.env',  # ~/.config/gai/.env
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            env_loaded = True
            break
    
    if not env_loaded and not os.getenv('OPENAI_API_KEY'):
        print("Warning: .env file not found in:")
        for p in env_paths:
            print(f"  - {p}")
        print("Will use environment variables or defaults")
    
    # 检查暂存区
    if not check_staged_changes():
        print("Error: No staged changes found. Run 'git add' first.")
        sys.exit(1)
    
    # 获取API配置
    api_key = os.getenv('OPENAI_API_KEY', 'empty')
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    model = args.model or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    
    # 初始化OpenAI客户端
    # 本地部署（如Ollama）可能不需要API Key
    if api_key == 'empty':
        api_key = None
        print("Info: No API_KEY set, using no-auth mode (for local deployment)\n")
    
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    
    # 获取暂存区内容
    staged_diff = get_staged_diff()
    staged_files = get_staged_files()
    
    print(f"Analyzing {len(staged_files)} file(s) (language: {args.lang})...\n")
    
    # 生成commit信息
    commit_message = generate_commit_message(staged_diff, staged_files, client, model, args.lang)
    
    print("Generated Commit Message:\n")
    print("=" * 60)
    print(commit_message)
    print("=" * 60)
    
    # 复制到剪贴板
    if args.copy:
        try:
            import pyperclip
            pyperclip.copy(commit_message)
            print("\n✓ Copied to clipboard")
        except ImportError:
            print("\nWarning: pyperclip not installed")
            print("  pip install pyperclip")
    
    # 执行commit
    if args.commit:
        print("\nCommitting...")
        try:
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True
            )
            print("✓ Commit successful!")
        except subprocess.CalledProcessError as e:
            print(f"Error: Commit failed: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
