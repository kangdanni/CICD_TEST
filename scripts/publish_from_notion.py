import os
import requests
from datetime import datetime, timezone

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
WP_BASE_URL = os.environ["WP_BASE_URL"]
WP_USERNAME = os.environ["WP_USERNAME"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]
TISTORY_ACCESS_TOKEN = os.environ["TISTORY_ACCESS_TOKEN"]
TISTORY_BLOG_NAME = os.environ["TISTORY_BLOG_NAME"]
WPCOM_CLIENT_ID = os.environ["WPCOM_CLIENT_ID"]
WPCOM_CLIENT_SECRET= os.environ["WPCOM_CLIENT_SECRET"]

NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


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
            html_parts.append(f"<pre><code class=\"language-{lang}\">{text}</code></pre>")

        else:
            # 지원 안 하는 타입은 그냥 텍스트만
            rich = block.get(btype, {}).get("rich_text", [])
            text = rich_text_to_plain(rich) if rich else ""
            if text:
                html_parts.append(f"<p>{text}</p>")

    return "\n".join(html_parts)

#WordPress Token 
def get_wpcom_token():
    resp = requests.post(
        "https://public-api.wordpress.com/oauth2/token",
        data={
            "grant_type": "password",
            "client_id": WPCOM_CLIENT_ID,
            "client_secret": WPCOM_CLIENT_SECRET,
            "username": WPCOM_USERNAME,
            "password": WPCOM_APP_PASSWORD,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def publish_to_wordpress(title, content_html):
    """
    설치형 WordPress (wp-json/wp/v2/posts) 기준 게시 함수
    - Basic Auth (username + application password) 사용
    """
    url = f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/posts"
    auth = (WP_USERNAME, WP_APP_PASSWORD)
    payload = {
        "title": title,
        "content": content_html,
        "status": "publish",  # 필요하면 'draft'로 바꿔서 임시저장도 가능
    }

    print(f"[DEBUG][WP] POST {url}")
    print(f"[DEBUG][WP] username={WP_USERNAME}")

    resp = requests.post(url, auth=auth, json=payload)


    resp.raise_for_status()
    data = resp.json()
    print(f"[WP] Published: {data.get('id')} - {data.get('link')}")
    return data.get("id"), data.get("link")

def publish_to_tistory(title, content_html):
    url = "https://www.tistory.com/apis/post/write"
    data = {
        "access_token": TISTORY_ACCESS_TOKEN,
        "output": "json",
        "blogName": TISTORY_BLOG_NAME,
        "title": title,
        "content": content_html,
        "visibility": 3,  # 0: 비공개, 3: 발행
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    j = resp.json()
    post_id = j["tistory"]["post"]["id"]
    print(f"[Tistory] Published ID: {post_id}")
    return post_id


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


def main():
    pages = get_ready_pages()
    print(f"Found {len(pages)} Ready pages")

    for page in pages:
        page_id = page["id"]
        title = get_page_title(page)
        print(f"Processing page: {title} ({page_id})")

        blocks = get_page_blocks(page_id)
        html = blocks_to_html(blocks)

        # 1) WordPress 발행
        try:
            wp_id, wp_link = publish_to_wordpress(title, html)
        except Exception as e:
            print(f"[ERROR] WordPress publish failed: {e}")
            continue

        # # 2) Tistory 발행
        # try:
        #     tistory_id = publish_to_tistory(title, html)
        # except Exception as e:
        #     print(f"[ERROR] Tistory publish failed: {e}")
        #     continue

        # 3) Notion 상태 업데이트
        try:
            update_page_status_to_published(page_id)
        except Exception as e:
            print(f"[ERROR] Notion status update failed: {e}")
            continue

    print("Done.")


if __name__ == "__main__":
    main()
