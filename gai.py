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


def get_exe_dir() -> Path:
    """获取exe所在目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的 exe
        return Path(sys.executable).parent
    # 开发环境
    return Path(__file__).parent


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
            'system': '你是一个专业的代码贡献者，擅长生成简洁、清晰的中文git commit信息。所有输出必须使用中文。',
            'prompt': '''你是一个专业的git commit信息生成器。
任务：根据以下代码变更，生成符合 Conventional Commits 规范的中文commit信息。

要求：
1. 整个输出必须完全使用中文
2. 不要在输出中夹杂任何英文或拼音
3. type使用英文缩写，但description和详细说明必须用中文

格式：
type(scope): description (不超过72字符)
[空行]
详细说明：简要描述这次变更的内容和原因'''
        },
        'en': {
            'system': 'You are a professional code contributor, skilled at generating concise and clear English git commit messages. All output must be in English.',
            'prompt': '''You are a professional git commit message generator.
Task: Based on the code changes below, generate an English commit message following Conventional Commits specification.

Requirements:
1. All output must be completely in English
2. Do not mix in any other languages
3. Use English for everything including description and details

Format:
type(scope): description (max 72 chars)
[blank line]
Detailed description: Briefly describe the changes and reasons'''
        },
        'ja': {
            'system': 'あなたは簡潔で明確な日本語のgitコミットメッセージを作成するのが得意なプロフェッショナルなコード貢献者です。すべての出力が日本語である必要があります。',
            'prompt': '''あなたはプロフェッショナルなgitコミットメッセージ生成者です。
タスク：以下のコード変更に基づいて、Conventional Commits仕様に準拠した日本語のコミットメッセージを生成してください。

要件：
1. 出力を完全に日本語にする
2. 他の言語を混ぜない
3. typeは英略語を使用、説明は日本語

形式：
type(scope): description (72文字以内)
[空白行]
詳細説明：変更の内容と理由を簡単に説明'''
        },
        'ko': {
            'system': 'あなたは簡潔で明確な日本語のgitコミットメッセージを作成するのが得意なプロフェッショナルなコード貢献者입니다。すべての出力が日本語である必要があります。',
            'prompt': '''당신은 전문적인 git 커밋 메시지 생성자입니다.
과제: 아래의 코드 변경 사항에 따라 Conventional Commits 사양을 준수하는 한국어 커밋 메시지를 생성해 주세요.

요구사항:
1. 모든 출력을 한국어로 작성
2. 다른 언어를 섞지 않기
3. type은 영어 약어 사용, 설명은 한국어

형식:
type(scope): description (72자 이내)
[빈 줄]
상세 설명: 변경 내용과 이유를 간단히 설명'''
        }
    }
    
    lang_config = lang_instructions.get(lang, lang_instructions['zh'])
    
    prompt = f"""{lang_config['prompt']}

变更的文件:
{', '.join(files) if files else '无文件列表'}

代码变更内容:
{diff if diff else '无变更内容'}

只返回commit信息，不要添加任何其他解释。"""

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
    
    # 加载环境变量 - 优先查找exe所在目录
    env_loaded = False
    exe_dir = get_exe_dir()
    env_paths = [
        exe_dir / '.env',              # exe所在目录 (优先)
        Path.cwd() / '.env',          # 当前目录
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            env_loaded = True
            print(f"Info: Loading config from {env_path}\n")
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
