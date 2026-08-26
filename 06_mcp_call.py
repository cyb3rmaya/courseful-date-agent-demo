"""PLAN.md 기반 MCP DateCourseAgent CLI 진입점입니다."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ai_agent import DateCourseAgent


COURSE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTION = (
    "부산에서 커플 2명이 14:00부터 21:00까지 대중교통으로 이동할 거예요. "
    "총 예산은 10만원이고 카페와 야경을 원하지만, 비가 오면 실내 코스로 바꿔 주세요."
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP 데이트 코스 Agent 실행")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    return parser.parse_args()


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(COURSE_ROOT / ".env")
    args = _arguments()
    agent = DateCourseAgent(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        api_key=os.getenv("OPENAI_API_KEY", ""),
    )
    try:
        result = await agent.answer(args.question)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
