# 03 MCP Labs

## Lab 01 · 새로운 Tool 공개

`01_first_mcp_server.py`에 `get_exchange_rate(base, quote)` Tool을 추가하고
`02_list_and_call_tools.py`에서 발견·호출되는지 확인합니다. 결과는 고정된 교육용
환율 데이터로 만들어 API Key 없이 반복 실행할 수 있게 합니다.

## Lab 02 · Resource 추가

`travel://policy/refund` Resource를 추가하고 Client에서 읽습니다. 같은 정보를 Tool로
제공할 때와 Resource로 제공할 때 호출 의도가 어떻게 다른지 설명합니다.

## 완료 기준

- Client가 Tool 이름을 코드에 등록하지 않아도 `list_tools()`에서 발견합니다.
- 정상 arguments와 잘못된 arguments의 결과를 모두 확인합니다.
- 서버는 표준 출력에 디버그 문장을 출력하지 않습니다.
