"""두 Streamable HTTP MCP Server를 사용하는 AI Agent CLI 진입점입니다."""

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
    "부산의 현재 날씨와 내일 예보를 확인하고, "
    "1박 15만원 이하 호텔과 대표 관광 명소를 찾아 주세요."
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="두 MCP 여행 브리프 Agent 실행")
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
