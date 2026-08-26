# 03 MCP 과제

도서관 MCP Server를 만듭니다.

## 요구사항

- `search_books(keyword: str)` Tool을 제공합니다.
- `borrow_book(book_id: str, user_id: str)` Tool을 제공하되 빈 값은 거부합니다.
- `library://policy/loan` Resource로 대출 기간 정책을 제공합니다.
- stdio Client가 Tool 목록, 정상 호출, 검증 오류, Resource 내용을 출력합니다.
- Client는 서버의 Tool 함수를 직접 import하지 않습니다.

## 제출물

- MCP Server 파일
- MCP Client 파일
- 실행 결과와 Tool·Resource 선택 이유를 설명한 README
