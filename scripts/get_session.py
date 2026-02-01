from playwright.sync_api import sync_playwright

def save_session():
    with sync_playwright() as p:
        # headless=False로 브라우저를 직접 띄움
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 티스토리 로그인 페이지로 이동
        page.goto("https://www.tistory.com/auth/login")
        
        print("1. 브라우저 창에서 카카오 로그인을 완료해줘.")
        print("2. 2단계 인증까지 끝내고 티스토리 메인 화면이 나오면 여기로 돌아와.")

        # 로그인 완료 후 티스토리 홈이나 관리자 페이지로 갈 때까지 무한 대기
        page.wait_for_url("**/tistory.com/**", timeout=0)
        
        # 현재 로그인된 모든 상태(쿠키, 세션 등)를 파일로 저장
        context.storage_state(path="state.json")
        print("성공! state.json 파일이 생성되었음.")
        browser.close()

if __name__ == "__main__":
    save_session()
