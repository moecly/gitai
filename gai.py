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

【固定格式 - 必须严格按照这个输出】

第一行格式：
type(scope): 简短描述 (不超过72字符)

空一行

本次提交主要[一句话总结这次变更的核心内容]。

1. [功能模块1名称]：
   - [具体修改内容]
   - [具体修改内容]

2. [功能模块2名称]：
   - [具体修改内容]
   - [具体修改内容]

【示例】

feat(auth): 添加用户登录和会话管理功能

本次提交主要实现了完整的用户认证系统和会话管理机制。

1. 添加用户认证模块：
   - 实现用户名密码验证逻辑
   - 添加JWT token生成和验证
   - 集成登录/登出功能

2. 集成会话管理：
   - 添加会话存储和过期处理
   - 实现多设备登录限制
   - 添加会话刷新机制

【type类型】feat | fix | docs | style | refactor | test | chore | perf | ci | build

请严格按照上述格式输出，只返回commit信息，不要添加任何其他解释。'''
        },
        'en': {
            'system': 'You are a professional code contributor, skilled at generating concise and clear English git commit messages. All output must be in English.',
            'prompt': '''You are a professional git commit message generator.
Task: Based on the code changes below, generate an English commit message following Conventional Commits specification.

【Fixed Format - Must follow exactly】

First line format:
type(scope): brief description (max 72 chars)

Blank line

This commit [one sentence summary of core changes].

1. [Module name]:
   - [specific change]
   - [specific change]

2. [Module name]:
   - [specific change]
   - [specific change]

【Example】

feat(auth): add user login and session management

This commit implements a complete user authentication system and session management mechanism.

1. Add user authentication module:
   - Implement username/password validation logic
   - Add JWT token generation and verification
   - Integrate login/logout functionality

2. Integrate session management:
   - Add session storage and expiration handling
   - Implement multi-device login limit
   - Add session refresh mechanism

【type】feat | fix | docs | style | refactor | test | chore | perf | ci | build

Output must follow the format exactly.'''
        },
        'ja': {
            'system': 'あなたは簡潔で明確な日本語のgitコミットメッセージを作成するのが得手なプロフェッショナルなコード貢献者です。すべての出力が日本語である必要があります。',
            'prompt': '''あなたはプロフェッショナルなgitコミットメッセージ生成者です。
タスク：以下のコード変更に基づいて、Conventional Commits仕様に準拠した日本語のコミットメッセージを生成してください。

【固定形式 - 厳密に守る】

1行目形式：
feat(scope): 簡単な説明 (72文字以内)

空白行

本次のコミットは[変更の核心内容の要約]です。

1. [モジュール名]：
   - [具体的な変更内容]
   - [具体的な変更内容]

2. [モジュール名]：
   - [具体的な変更内容]
   - [具体的な変更内容]

【例】

feat(認証): ユーザーログイン機能を追加

本次のコミットはユーザー認証システムとセッション管理機構を実装しました。

1. ユーザー認証モジュールを追加：
   - ユーザー名とパスワードの検証ロジックを実装
   - JWTトークン生成と検証を追加
   - ログイン/ログアウト機能を統合

2. セッション管理を統合：
   - セッション存储と有効期限 обработкаを追加
   - マルチデバイスログイン制限を実装
   - セッション更新メカニズムを追加

【type】feat | fix | docs | style | refactor | test | chore

形式を厳密に守って出力'''
        },
        'ko': {
            'system': '당신은 한국어 git 커밋 메시지를 작성하는 데 능숙한 전문 코드 기여자입니다. 모든 출력은 한국어로 해야 합니다.',
            'prompt': '''당신은 전문적인 git 커밋 메시지 생성자입니다.
과제: 아래의 코드 변경 사항에 따라 Conventional Commits 사양을 준수하는 한국어 커밋 메시지를 생성해 주세요.

【고정 형식 - 엄격히 준수】

첫 번째 줄 형식：
feat(scope): 간단한 설명 (72자 이내)

빈 줄

이번 커밋은 [변경의 핵심 내용 요약]입니다.

1. [모듈명]：
   - [구체적인 변경 내용]
   - [구체적인 변경 내용]

2. [모듈명]：
   - [구체적인 변경 내용]
   - [구체적인 변경 내용]

【예시】

feat(인증): 사용자 로그인 기능 추가

이번 커밋은 완전한 사용자 인증 시스템과 세션 관리 메커니즘을 구현했습니다.

1. 사용자 인증 모듈 추가：
   - 사용자 이름/비밀번호 검증 로직 구현
   - JWT 토큰 생성 및 검증 추가
   - 로그인/로그아웃 기능 통합

2. 세션 관리 통합：
   - 세션 저장 및 만료 처리 추가
   - 다중 장치 로그인 제한 구현
   - 세션 갱신 메커니즘 추가

【type】feat | fix | docs | style | refactor | test | chore

형식을 엄격히 준수하여 출력'''
        }
    }
    
    lang_config = lang_instructions.get(lang, lang_instructions['zh'])
    
    prompt = f"""{lang_config['prompt']}

变更的文件:
{', '.join(files) if files else '无文件列表'}

代码变更内容:
{diff if diff else '无变更内容'}"""

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
