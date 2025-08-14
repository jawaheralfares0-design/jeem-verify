import os, json
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("JEEM_API_KEY", "")
CODES_PATH = os.environ.get("CODES_PATH", "jeem_codes.json")

def load_codes():
    try:
        with open(CODES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_codes(data):
    with open(CODES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.post("/verify")
def verify():
    # API key
    if request.headers.get("x-api-key") != API_KEY:
        return jsonify({"ok": False, "message": "unauthorized"}), 401

    body = request.get_json(force=True, silent=True) or {}
    code = (body.get("code") or "").strip().upper()
    user_id = str(body.get("user_id") or "").strip()

    if not code:
        return jsonify({"ok": False, "message": "missing code"}), 200
    if not user_id or user_id.lower() in {"null", "none"}:
        return jsonify({"ok": False, "message": "user_id required"}), 200

    codes = load_codes()
    info = codes.get(code)
    if not info:
        return jsonify({"ok": False, "message": "invalid code"}), 200

    # active?
    if not info.get("is_active", True):
        return jsonify({"ok": False, "message": "code disabled"}), 200

    # expiry
    try:
        exp = datetime.fromisoformat(info["expires_at"].replace("Z", "+00:00"))
    except Exception:
        return jsonify({"ok": False, "message": "bad code record"}), 200
    if datetime.now(timezone.utc) > exp:
        return jsonify({"ok": False, "message": "code expired"}), 200

    # already bound?
    used_by = info.get("used_by")
    if used_by and used_by != user_id:
        return jsonify({"ok": False, "message": "code already used"}), 200

    # optional quota
    if info.get("quota_total", 0):
        if info.get("quota_used", 0) >= info["quota_total"]:
            return jsonify({"ok": False, "message": "quota exceeded"}), 200
        info["quota_used"] = int(info.get("quota_used", 0)) + 1

    # bind & save
    info["used_by"] = user_id
    codes[code] = info
    save_codes(codes)

    return jsonify({"ok": True, "expires_at": info["expires_at"]}), 200

@app.get("/privacy")
def privacy():
    html = """
    <html><head><meta charset="utf-8"><title>Privacy Policy — Jeem AI</title></head>
    <body style="font-family:sans-serif;max-width:760px;margin:2rem auto;line-height:1.6">
      <h1>Privacy Policy — Jeem AI</h1>
      <p>نقوم بحفظ بيانات بسيطة للتحقق من الاشتراك:</p>
      <ul>
        <li>كود الاشتراك الذي تدخله.</li>
        <li>معرّف المستخدم (user_id) لربط الكود بحساب واحد.</li>
        <li>تواريخ التفعيل والانتهاء.</li>
      </ul>
      <p>لا نحتفظ بصور الشارت أو رسائل الدردشة هنا.</p>
      <p>للاستفسار: support@yourdomain.com</p>
    </body></html>
    """
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
