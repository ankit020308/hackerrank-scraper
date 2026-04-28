import requests
import sys

BASE_URL  = "https://www.hackerrank.com"
API_BASE  = f"{BASE_URL}/rest"

def build_session(cookie_string):
    session = requests.Session()
    for part in cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            session.cookies.set(k.strip(), v.strip(), domain=".hackerrank.com")
    session.headers.update({
        "User-Agent":       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept":           "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer":          BASE_URL,
    })
    return session

def verify_login(session):
    # Try fetching submissions directly since /auth/session is giving 500
    r = session.get(f"{API_BASE}/hackers/me/myrank_submissions?offset=0&limit=5", timeout=10)
    print(f"Submissions Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print("Successfully fetched submissions!")
        return "Verified User"
    else:
        print(f"Response: {r.text[:500]}")
    return None

if __name__ == "__main__":
    with open("cookie.txt", "r") as f:
        cookie_str = f.read().strip()
    session = build_session(cookie_str)
    username = verify_login(session)
    if username:
        print(f"Logged in as: {username}")
    else:
        print("Login failed")
