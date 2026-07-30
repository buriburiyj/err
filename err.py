#!/usr/bin/env python3
"""
err - 에러 발생 시 한국어 설명을 제공하는 CLI 도구
사용법: err <명령어> [인자들...]
"""

import sys
import subprocess
import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


ERROR_DICTIONARY: Dict[str, Dict[str, str]] = {
    "403 forbidden": {
        "meaning": "서버가 요청을 이해했지만 접근을 거부했습니다.",
        "cause": "인증 토큰이 없거나 만료됨, 권한이 부족함, IP 차단, CSRF 토큰 누락 등",
        "fix": "올바른 인증 헤더/토큰을 보내는지 확인, 권한 설정 확인, API 키 유효성 검사"
    },
    "413 payload too large": {
        "meaning": "요청 본문 크기가 서버가 허용하는 최대 크기를 초과했습니다.",
        "cause": "파일 업로드 크기 초과, JSON 본문이 너무 큼, 멀티파트 요청 크기 제한",
        "fix": "파일 크기 줄이기, 청크 업로드 구현, 서버 설정(client_max_body_size 등) 조정"
    },
    "429 rate limit": {
        "meaning": "단위 시간당 허용된 요청 횟수를 초과했습니다.",
        "cause": "API 호출이 너무 빈번함, 무료 티어 한도 초과, 버스트 제한 초과",
        "fix": "지수 백오프로 재시도, 요청 간격 두기, 캐싱 활용, 유료 플랜 업그레이드"
    },
    "404 not found": {
        "meaning": "요청한 리소스가 서버에 존재하지 않습니다.",
        "cause": "잘못된 URL/엔드포인트, 리소스 ID 오타, 리소스가 삭제됨, API 버전 불일치",
        "fix": "URL 철자 확인, API 문서에서 올바른 경로 확인, 리소스 존재 여부 사전 조회"
    },
    "500 server error": {
        "meaning": "서버 내부에서 처리할 수 없는 예외가 발생했습니다.",
        "cause": "서버 버그, DB 연결 실패, 설정 오류, 의존 서비스 장애, 메모리 부족",
        "fix": "서버 로그 확인, 재시도(일시적 장애일 수 있음), 관리자/운영팀에 문의"
    },
    "modulenotfounderror": {
        "meaning": "가져오려는 모듈을 찾을 수 없습니다.",
        "cause": "패키지가 설치되지 않음, 가상환경이 활성화되지 않음, 패키지명 오타, Python 경로 문제",
        "fix": "pip install <패키지명>, 가상환경 활성화, requirements.txt 확인, PYTHONPATH 확인"
    },
    "syntaxerror": {
        "meaning": "파이썬 문법이 올바르지 않습니다.",
        "cause": "따옴표/괄호 불일치, 들여쓰기 오류, 예약어 오용, 콜론 누락, f-string 문법 오류",
        "fix": "에러가 난 줄 번호 확인, IDE/린터로 문법 검사, 최근 수정한 부분 되돌리기"
    },
    "indentationerror": {
        "meaning": "들여쓰기가 일관되지 않거나 잘못되었습니다.",
        "cause": "탭과 스페이스 혼용, 블록 들여쓰기 누락/과다, if/for/while/def 뒤 들여쓰기 없음",
        "fix": "에디터에서 '탭을 스페이스로 변환' 설정, 일관된 들여쓰기(4칸 스페이스) 사용, 자동 포맷터(black) 적용"
    },
    "nameerror": {
        "meaning": "정의되지 않은 변수나 이름을 사용했습니다.",
        "cause": "변수명 오타, 스코프 밖 변수 사용, import 누락, 순환 import로 인한 미정의",
        "fix": "변수명 철자 확인, 변수 정의 위치 확인, 필요한 import 추가, 순환 import 해결"
    },
    "command not found": {
        "meaning": "실행하려는 명령어를 시스템이 찾을 수 없습니다.",
        "cause": "명령어 오타, PATH에 없는 프로그램, 패키지 미설치, alias/함수 정의 누락",
        "fix": "명령어 철자 확인, which/whereis로 경로 확인, 패키지 설치(brew/apt/pip), PATH 환경변수 확인"
    },
    "permission denied": {
        "meaning": "파일/디렉토리/실행 권한이 없어 접근이 거부되었습니다.",
        "cause": "파일 권한 부족(읽기/쓰기/실행), 소유자 불일치, 루트 권한 필요, selinux/apparmor 차단",
        "fix": "chmod로 권한 부여, chown으로 소유자 변경, sudo 사용, 권한 설정 확인(ls -la)"
    },
    "jsondecodeerror": {
        "meaning": "JSON 형식이 올바르지 않아 파싱에 실패했습니다.",
        "cause": "따옴표 누락/불일치, 후행 콤마, 주석 포함, 이스케이프 문자 오류, 빈 문자열",
        "fix": "JSON 유효성 검사기(jsonlint) 사용, 원본 데이터 확인, try/except로 예외 처리"
    },
    "connectionerror": {
        "meaning": "네트워크 연결을 설정할 수 없습니다.",
        "cause": "서버 다운, 방화벽 차단, DNS 오류, 프록시 설정 오류, 네트워크 단절",
        "fix": "ping/curl로 연결 테스트, 방화벽/프록시 설정 확인, DNS 플러시, 서버 상태 확인"
    },
    "timeouterror": {
        "meaning": "지정된 시간 내에 응답을 받지 못했습니다.",
        "cause": "서버 응답 지연, 네트워크 레이턴시, 타임아웃 값이 너무 짧음, 무한 대기 루프",
        "fix": "타임아웃 값 늘리기, 재시도 로직 추가, 비동기/병렬 처리, 서버 성능 개선"
    },
    "filenotfounderror": {
        "meaning": "지정된 경로에 파일이 존재하지 않습니다.",
        "cause": "경로 오타, 상대/절대 경로 혼동, 파일이 이동/삭제됨, 작업 디렉토리 불일치",
        "fix": "절대 경로 사용, os.path.exists()로 사전 확인, 작업 디렉토리 확인(os.getcwd())"
    }
}


def find_error_explanation(stderr: str) -> Optional[Dict[str, str]]:
    """stderr에서 알려진 에러 패턴을 찾아 설명을 반환"""
    stderr_lower = stderr.lower()

    for pattern, explanation in ERROR_DICTIONARY.items():
        if pattern in stderr_lower:
            return explanation
    return None


def call_ai_for_explanation(stderr: str) -> Optional[Dict[str, str]]:
    """NVIDIA API를 호출해 에러 설명을 받아옴"""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return None

    prompt = (
        "다음 에러를 초보 개발자에게 한국어로 설명해줘. "
        "무슨 뜻인지, 왜 났는지, 어떻게 고치는지 세 가지로 나눠서 간단히 알려줘:\n\n"
        + stderr.strip()
    )

    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.3
    }

    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"].strip()
            return parse_ai_response(content)
    except urllib.error.HTTPError as e:
        print(f"\n⚠️ AI API 오류 (HTTP {e.code}): {e.read().decode()}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"\n⚠️ AI 네트워크 오류: {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"\n⚠️ AI 호출 실패: {e}", file=sys.stderr)

    return None


def parse_ai_response(content: str) -> Dict[str, str]:
    """AI 응답을 파싱해 세 부분으로 나눔"""
    meaning = ""
    cause = ""
    fix = ""

    lines = content.split("\n")
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "무슨 뜻" in line or "의미" in line or "뜻" in line:
            current_section = "meaning"
            continue
        elif "왜 났" in line or "원인" in line or "이유" in line:
            current_section = "cause"
            continue
        elif "어떻게 고치" in line or "해결" in line or "고치는" in line or "방법" in line:
            current_section = "fix"
            continue

        if current_section == "meaning":
            meaning += line + " "
        elif current_section == "cause":
            cause += line + " "
        elif current_section == "fix":
            fix += line + " "

    if not meaning and not cause and not fix:
        # 파싱 실패 시 전체를 의미로 넣음
        meaning = content

    return {
        "meaning": meaning.strip() or "AI가 설명을 생성했습니다.",
        "cause": cause.strip() or "AI가 원인을 분석했습니다.",
        "fix": fix.strip() or "AI가 해결 방법을 제안했습니다."
    }


def run_command(cmd: list) -> tuple[int, str, str]:
    """명령어 실행 후 종료코드, stdout, stderr 반환"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "명령어 실행 시간 초과 (5분)"
    except FileNotFoundError:
        return 127, "", f"명령어를 찾을 수 없음: {cmd[0]}"
    except Exception as e:
        return -1, "", f"실행 오류: {e}"


def main():
    console = Console()

    if len(sys.argv) < 2:
        console.print("사용법: err <명령어> [인자들...]")
        console.print("예: err python app.py")
        sys.exit(1)

    cmd = sys.argv[1:]

    # 명령어 실행 부분을 빨간색 Panel로 감싸서 출력
    cmd_text = Text(f"$ {' '.join(cmd)}", style="bold red")
    cmd_panel = Panel(cmd_text, title="❌ 에러 발생", border_style="red", expand=False)
    console.print(cmd_panel)

    exit_code, stdout, stderr = run_command(cmd)

    if stdout:
        console.print(stdout)

    if stderr:
        console.print(stderr, style="red")

    if exit_code != 0:
        explanation = find_error_explanation(stderr)

        if explanation:
            # 사전 설명 - 파란색 Panel
            explanation_panel = create_explanation_panel(
                explanation, title="📋 에러 설명", border_style="blue"
            )
            console.print(explanation_panel)
        else:
            # 사전에 없으면 AI 호출
            api_key = os.environ.get("NVIDIA_API_KEY")
            if not api_key:
                # 사전에도 없고 API 키도 없을 때
                explanation_panel = Panel(
                    Text("  아직 등록되지 않은 에러입니다.\n  💡 NVIDIA_API_KEY 환경변수를 설정하면 AI가 자동으로 설명해줍니다.", style="white"),
                    title="📋 에러 설명",
                    border_style="blue",
                    expand=False
                )
                console.print(explanation_panel)
            else:
                # AI에게 물어보는 중 스피너 표시
                with console.status("[bold blue]🤖 AI에게 물어보는 중...[/bold blue]", spinner="dots"):
                    ai_explanation = call_ai_for_explanation(stderr)

                if ai_explanation:
                    # AI 설명 - 파란색 Panel, 제목은 '🤖 AI 에러 설명'
                    explanation_panel = create_explanation_panel(
                        ai_explanation, title="🤖 AI 에러 설명", border_style="blue"
                    )
                    console.print(explanation_panel)
                else:
                    explanation_panel = Panel(
                        Text("  AI 설명을 가져오지 못했습니다.", style="white"),
                        title="📋 에러 설명",
                        border_style="blue",
                        expand=False
                    )
                    console.print(explanation_panel)

    sys.exit(exit_code)


def create_explanation_panel(explanation: Dict[str, str], title: str, border_style: str) -> Panel:
    """에러 설명을 예쁜 Panel로 만들어 반환"""
    content = Text()
    
    # 무슨 뜻: - 흰색 굵게
    content.append("  무슨 뜻: ", style="bold white")
    content.append(f"{explanation['meaning']}\n", style="white")
    
    # 왜 났나: - 노란색 굵게
    content.append("  왜 났나: ", style="bold yellow")
    content.append(f"{explanation['cause']}\n", style="yellow")
    
    # 어떻게 고치나: - 초록색 굵게
    content.append("  어떻게 고치나: ", style="bold green")
    content.append(f"{explanation['fix']}", style="green")
    
    return Panel(content, title=title, border_style=border_style, expand=False)


if __name__ == "__main__":
    main()