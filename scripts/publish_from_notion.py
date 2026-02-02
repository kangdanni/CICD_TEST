import os
import requests
import time
from playwright.sync_api import sync_playwright
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# 환경 변수 (GitHub Actions Secrets에서 주입)
# ─────────────────────────────────────────────
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
WP_BASE_URL = os.environ["WP_BASE_URL"]
WP_USERNAME = os.environ["WP_USERNAME"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
TISTORY_ACCESS_TOKEN = os.environ["TISTORY_ACCESS_TOKEN"]
TISTORY_BLOG_NAME = os.environ["TISTORY_BLOG_NAME"]
WPCOM_CLIENT_ID = os.environ["WPCOM_CLIENT_ID"]
WPCOM_CLIENT_SECRET = os.environ["WPCOM_CLIENT_SECRET"]
KAKAO_EMAIL= os.environ["KAKAO_EMAIL"]
KAKAO_PASSWORD = os.environ["KAKAO_PASSWORD"]


NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ─────────────────────────────────────────────
# Notion Helper
# ─────────────────────────────────────────────
def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_ready_pages():
    """
    Status == 'Ready' 인 페이지들 조회
    """
    url = f"{NOTION_BASE_URL}/databases/{NOTION_DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "Status",
            "select": {"equals": "Ready"},
        }
    }
    resp = requests.post(url, json=payload, headers=notion_headers())
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


def get_page_title(page):
    title_prop = page["properties"]["Name"]["title"]
    if not title_prop:
        return "Untitled"
    return "".join([t["plain_text"] for t in title_prop])


def get_page_slugs(page):
    """
    Notion 페이지에서 'Slug' 프로퍼티를 읽어서 태그 후보 리스트로 변환.
    - Slug가 rich_text라고 가정
    - 예: "python, github-actions, security"
      -> ["python", "github-actions", "security"]
    """
    slug_prop = page["properties"].get("slug")
    if not slug_prop:
        return []

    rich = slug_prop.get("rich_text", [])
    if not rich:
        return []

    text = "".join([t.get("plain_text", "") for t in rich])
    slugs = [s.strip() for s in text.split(",") if s.strip()]
    return slugs


def get_page_blocks(page_id):
    """
    페이지의 블록(본문)을 가져오기
    """
    url = f"{NOTION_BASE_URL}/blocks/{page_id}/children"
    results = []
    start_cursor = None

    while True:
        params = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        resp = requests.get(url, headers=notion_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return results


def rich_text_to_plain(rich_text_array):
    return "".join([t.get("plain_text", "") for t in rich_text_array])


def blocks_to_html(blocks):
    """
    매우 단순한 Notion → HTML 변환기.
    필요하면 나중에 더 리치하게 확장하면 됨.
    """
    html_parts = []

    for block in blocks:
        btype = block["type"]

        if btype == "paragraph":
            text = rich_text_to_plain(block["paragraph"]["rich_text"])
            html_parts.append(f"<p>{text}</p>")

        elif btype == "heading_1":
            text = rich_text_to_plain(block["heading_1"]["rich_text"])
            html_parts.append(f"<h1>{text}</h1>")

        elif btype == "heading_2":
            text = rich_text_to_plain(block["heading_2"]["rich_text"])
            html_parts.append(f"<h2>{text}</h2>")

        elif btype == "heading_3":
            text = rich_text_to_plain(block["heading_3"]["rich_text"])
            html_parts.append(f"<h3>{text}</h3>")

        elif btype == "bulleted_list_item":
            text = rich_text_to_plain(block["bulleted_list_item"]["rich_text"])
            html_parts.append(f"<ul><li>{text}</li></ul>")

        elif btype == "numbered_list_item":
            text = rich_text_to_plain(block["numbered_list_item"]["rich_text"])
            html_parts.append(f"<ol><li>{text}</li></ol>")

        elif btype == "code":
            text = rich_text_to_plain(block["code"]["rich_text"])
            lang = block["code"].get("language", "")
            html_parts.append(
                f'<pre><code class="language-{lang}">{text}</code></pre>'
            )
        #이미지 업로드 추가
        elif btype == "image":
            img = block["image"]
            if img["type"] == "file":
                img_url = img["file"]["url"]
            else:  # "external"
                img_url = img["external"]["url"]

            caption = rich_text_to_plain(img.get("caption", []))
            try:
                wp_img_url = upload_image_to_wordpress_from_url(img_url)
                # 가독성을 위해 style 추가: 최대 너비 100%, 중앙 정렬
                # 특정 고정 크기를 원하면 width="800" 등으로 명시 가능
                img_style = 'style="max-width: 100%; height: auto; display: block; margin: 20px auto; border-radius: 8px;"'
                
                figure_html = f'<figure style="text-align: center;">'
                figure_html += f'<img src="{wp_img_url}" alt="{caption}" {img_style}/>'
                
                if caption:
                    figure_html += f'<figcaption style="font-size: 0.9em; color: #666; margin-top: 8px;">{caption}</figcaption>'
                
                figure_html += "</figure>"
                html_parts.append(figure_html)
            except Exception as e:
                print(f"[WARN] Failed to handle image block: {e}")
                # 실패 시 Notion URL 그대로라도 넣고 싶으면:
                # html_parts.append(f'<p><img src="{img_url}" alt="{caption}"/></p>')

        else:
            # 지원 안 하는 타입은 그냥 텍스트만
            rich = block.get(btype, {}).get("rich_text", [])
            text = rich_text_to_plain(rich) if rich else ""
            if text:
                html_parts.append(f"<p>{text}</p>")

    return "\n".join(html_parts)


# ─────────────────────────────────────────────
# WordPress Helper (태그 포함)
# ─────────────────────────────────────────────
def get_or_create_wp_tag(slug, name=None):
    """
    주어진 slug에 해당하는 WordPress 태그 ID를 반환.
    - 없으면 새로 태그를 생성하고 그 ID를 리턴.
    """
    url = f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/tags"
    auth = (WP_USERNAME, WP_APP_PASSWORD)

    # 1) slug로 조회
    params = {"slug": slug}
    resp = requests.get(url, auth=auth, params=params)
    resp.raise_for_status()
    data = resp.json()

    if data:
        tag_id = data[0]["id"]
        print(f"[WP] Found existing tag: {slug} (id={tag_id})")
        return tag_id

    # 2) 없으면 새 태그 생성
    payload = {
        "name": name or slug,
        "slug": slug,
    }
    print(f"[WP] Creating new tag: {slug}")
    resp = requests.post(url, auth=auth, json=payload)
    resp.raise_for_status()
    data = resp.json()
    tag_id = data["id"]
    print(f"[WP] Created tag: {slug} (id={tag_id})")
    return tag_id


def get_wp_tag_ids_from_slugs(slugs):
    """
    ['python', 'github-actions'] -> [tag_id1, tag_id2]
    """
    tag_ids = []
    for s in slugs:
        try:
            tag_id = get_or_create_wp_tag(slug=s, name=s)
            tag_ids.append(tag_id)
        except Exception as e:
            print(f"[WARN] Failed to get/create tag '{s}': {e}")
    return tag_ids

def upload_image_to_wordpress_from_url(image_url, filename=None):
    """
    Notion 파일/외부 URL에서 이미지를 받아서
    WordPress 미디어 라이브러리에 업로드하고 최종 URL을 반환.
    """
    print(f"[WP][IMAGE] Downloading image from Notion: {image_url}")
    img_resp = requests.get(image_url)
    img_resp.raise_for_status()
    img_bytes = img_resp.content

    # 파일명 추출 (대충 URL 마지막 부분에서 가져오고, 없으면 기본값)
    if not filename:
        base = image_url.split("?")[0].rstrip("/").split("/")[-1]
        if not base:
            base = "notion-image"
        filename = base

    content_type = img_resp.headers.get("Content-Type", "image/jpeg")

    media_url = f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/media"
    auth = (WP_USERNAME, WP_APP_PASSWORD)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": content_type,
    }

    print(f"[WP][IMAGE] Uploading to WP media: {media_url}, filename={filename}")
    resp = requests.post(media_url, headers=headers, auth=auth, data=img_bytes)
    resp.raise_for_status()
    j = resp.json()
    wp_image_url = j.get("source_url")
    print(f"[WP][IMAGE] Uploaded image URL: {wp_image_url}")
    return wp_image_url

def publish_to_wordpress(title, content_html, tag_slugs=None):
    """
    설치형 WordPress (wp-json/wp/v2/posts) 기준 게시 함수
    - Basic Auth (username + application password) 사용
    - tag_slugs: ['python', 'github-actions'] 형태 (Notion Slug에서 온 값)
    """
    url = f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/posts"
    auth = (WP_USERNAME, WP_APP_PASSWORD)

    tag_ids = []
    if tag_slugs:
        tag_ids = get_wp_tag_ids_from_slugs(tag_slugs)

    payload = {
        "title": title,
        "content": content_html,
        "status": "publish",  # 필요하면 'draft'로 바꿔서 임시저장도 가능
    }
    if tag_ids:
        payload["tags"] = tag_ids

    print(f"[DEBUG][WP] POST {url}")
    print(f"[DEBUG][WP] username={WP_USERNAME}")
    print(f"[DEBUG][WP] tags={tag_ids}")

    resp = requests.post(url, auth=auth, json=payload)
    resp.raise_for_status()
    data = resp.json()
    print(f"[WP] Published: {data.get('id')} - {data.get('link')}")
    return data.get("id"), data.get("link")


# ─────────────────────────────────────────────
# (선택) Tistory 발행
# ─────────────────────────────────────────────

def publish_to_tistory(title, html_content):
    tistory_blog_name = os.getenv("TISTORY_BLOG_NAME")
    
    with sync_playwright() as p:
        # 브라우저 실행 옵션 (기존과 동일)
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            storage_state="state.json",
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1. 새 에디터 주소로 접속
            write_url = f"https://{tistory_blog_name}.tistory.com/manage/newpost/?type=post&returnURL=%2Fmanage%2Fposts%2F"
            print(f"[DEBUG] Accessing: {write_url}")
            page.goto(write_url, wait_until="domcontentloaded", timeout=60000)
            
            # 안정화 대기
            page.wait_for_timeout(3000)

            # 2. [수정됨] 새 에디터 제목 입력창 찾기
            print("[DEBUG] Waiting for #post-title-inp...")
            page.wait_for_selector("#post-title-inp", state="visible", timeout=30000)
            page.fill("#post-title-inp", title)

            # 3. [수정됨] 본문 입력 (HTML 모드로 전환하여 주입하는 방식이 가장 안전함)
            # iframe 내부 조작은 복잡하므로, DOM에 직접 JS로 삽입 시도
            # 새 에디터는 본문 영역 ID가 없거나 동적이므로, iframe 내부를 공략해야 함
            
            try:
                # 방법 A: iframe 내부에 HTML 주입 (가장 표준적인 방법)
                # 티스토리 에디터 iframe 찾기
                frame = page.frame_locator("iframe#editor-tistory_ifr") 
                if frame:
                    # iframe 내부의 body를 찾아 내용 교체
                    frame.locator("body#tinymce").evaluate(f'node => node.innerHTML = `{html_content}`')
                else:
                    # iframe을 못 찾으면 JS로 강제 주입 (Fallback)
                    raise Exception("Editor iframe not found")
            except:
                # 방법 B: HTML 모드 전환 버튼을 찾아서 입력 (비상용)
                print("[WARN] iframe injection failed. Trying alternative...")
                # (이 부분은 일단 iframe 방식이 90% 먹히므로 생략, 필요시 추가 제공)

           # 4. [수정됨] '완료' 버튼 클릭 (클래스명 대신 텍스트로 찾기)
            print("[DEBUG] Clicking '완료' button...")
            # 화면 하단에 있는 '완료'라는 글자가 포함된 버튼을 찾아서 클릭
            page.click("button:has-text('완료')") 

            # 5. [수정됨] 발행 설정 레이어 대기 및 최종 발행
            print("[DEBUG] Waiting for publish layer...")
            
            # '발행'이라는 텍스트가 포함된 버튼이 보일 때까지 대기 (레이어가 떴다는 증거)
            # 보통 레이어 안의 최종 버튼은 '공개발행' 또는 '발행'이라고 적혀있음
            # 라디오 버튼(공개/비공개)은 기본값이 '공개'이므로 바로 발행 눌러도 됨
            
            publish_btn_selector = "button:has-text('발행')"
            page.wait_for_selector(publish_btn_selector, state="visible", timeout=10000)
            
            # 간혹 레이어 애니메이션 때문에 클릭이 씹힐 수 있으니 잠시 대기
            page.wait_for_timeout(1000)
            
            # 최종 클릭
            page.click(publish_btn_selector)
            
            print(f"[Tistory] Published Successfully: {title}")

        except Exception as e:
            # 디버깅용 덤프 저장 (기존과 동일)
            print(f"[ERROR] {e}")
            page.screenshot(path="tistory_debug.png", full_page=True)
            with open("tistory_debug.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            raise e
        finally:
            browser.close()
# ─────────────────────────────────────────────
# Notion Status 업데이트
# ─────────────────────────────────────────────
def update_page_status_to_published(page_id):
    url = f"{NOTION_BASE_URL}/pages/{page_id}"
    payload = {
        "properties": {
            "Status": {
                "select": {"name": "Published"}
            },
        }
    }
    resp = requests.patch(url, json=payload, headers=notion_headers())
    resp.raise_for_status()
    print(f"[Notion] Page {page_id} status updated to Published")


# ─────────────────────────────────────────────
# 메인 로직
# ─────────────────────────────────────────────
def main():
    pages = get_ready_pages()
    print(f"Found {len(pages)} Ready pages")

    
    for page in pages:

        page_id = page["id"]
        title = get_page_title(page)
        print(f"Processing page: {title} ({page_id})")
    
        # 본문 HTML 변환
        blocks = get_page_blocks(page_id)
        html = blocks_to_html(blocks)
    
        # Notion Slug -> WordPress tags
        slugs = get_page_slugs(page)
        print(f"[INFO] Slugs for this page: {slugs}")
    
        # # 1) WordPress 발행
        # try:
        #     wp_id, wp_link = publish_to_wordpress(title, html, tag_slugs=slugs)
        # except Exception as e:
        #     print(f"[ERROR] WordPress publish failed: {e}")
        #     continue
    
        # 2) Tistory 발행 (필요하면 주석 해제)
        try:
            publish_to_tistory(title, html)
                       
            # 3) Notion 상태 업데이트
            update_page_status_to_published(page_id)
        except Exception as e:
            print(f"[ERROR] Tistory publish failed: {e}")
     

         

    print("Done.")


if __name__ == "__main__":
    main()
