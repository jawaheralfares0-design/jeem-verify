import os
import json
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===================== الإعدادات =====================
# مفتاح الحماية بين الـGPT Action والسيرفر (لا علاقة له بمفتاح OpenAI)
API_KEY = os.environ.get("JEEM_API_KEY", "")

# مكان ملف الأكواد (على Render نستخدم قرص دائم في /var/data)
CODES_PATH = os.environ.get("CODES_PATH", "jeem_codes.json")

# مدة الخطة الافتراضية بالأيام (شهر = 30، ويمكن تغييرها من Render: JEEM_PLAN_DAYS=30)
PLAN_DAYS = int(os.environ.get("JEEM_PLAN_DAYS", "30"))


# ===================== وظائف مساعدة =====================
def load_codes():
    """قراءة ملف الأكواد كقاموس JSON. يرجّع {} لو ما وجد الملف."""
    try:
        with open(CODES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_codes(data):
    """حفظ القاموس إلى ملف الأكواد."""
    with open(CODES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_iso(dt_str: str):
    """تحويل نص ISO إلى datetime مع دعم 'Z'. يرجّع None عند الفشل/الفراغ."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


# ===================== مسارات الـAPI =====================
@app.post("/verify")
def verify():
    # تحقق من الهيدر السري
    if request.headers.get("x-api-key") != API_KEY:
        return jsonify({"ok": False, "message": "unauthorized"}), 401

    # بيانات الطلب
    body = request.get_json(force=True, silent=False) or {}
    code = (body.get("code") or "").strip().upper()
    user_id = str(body.get("user_id") or "").strip()

    if not code:
        return jsonify({"ok": False, "message": "missing code"}), 200
    if not user_id or user_id.lower() in {"null", "none"}:
        return jsonify({"ok": False, "message": "user_id required"}), 200

    # قراءة الأكواد
    codes = load_codes()
    info = codes.get(code)
    if not info:
        return jsonify({"ok": False, "message": "invalid code"}), 200

    # موقّف؟
    if not info.get("is_active", True):
        return jsonify({"ok": False, "message": "code disabled"}), 200

    now = datetime.now(timezone.utc)
    exp = parse_iso(info.get("expires_at") or "")
    used_by = info.get("used_by")

    # الكود مربوط بشخص آخر؟
    if used_by and used_by != user_id:
        return jsonify({"ok": False, "message": "code already used"}), 200

    # لو منتهي أصلاً
    if exp and now > exp:
        return jsonify({"ok": False, "message": "code expired"}), 200

    # تاريخ نهاية الخطة المقترح (شهر افتراضيًا)
    plan_end = now + timedelta(days=PLAN_DAYS)

    # أول تفعيل: اربطه بالمستخدم وحدّث الانتهاء إن كان مفقودًا أو أقصر من الخطة
    if not used_by:
        if (not exp) or (exp < plan_end):
            info["expires_at"] = plan_end.isoformat(timespec="minutes")
        info["used_by"] = user_id
        codes[code] = info
        save_codes(codes)
        return jsonify({"ok": True, "expires_at": info["expires_at"], "message": "activated"}), 200

    # تفعيل لاحق لنفس المستخدم:
    # لو ما فيه تاريخ انتهاء، حط تاريخ نهاية الخطة (لا يقصّر إن كان أطول)
    if not exp:
        info["expires_at"] = plan_end.isoformat(timespec="minutes")
        codes[code] = info
        save_codes(codes)
        return jsonify({"ok": True, "expires_at": info["expires_at"], "message": "activated"}), 200

    # غير منتهٍ ومربوط بنفس المستخدم
    return jsonify({"ok": True, "expires_at": info["expires_at"]}), 200


@app.get("/privacy")
def privacy():
    html = """
    <html><head><meta charset="utf-8"><title>Privacy Policy — Jeem AI</title></head>
    <body style="font-family:sans-serif;max-width:760px;margin:2rem auto;line-height:1.6">
      <h1>Privacy Policy — Jeem AI</h1>
      <p>نحفظ بيانات محدودة للتحقق من الاشتراك:</p>
      <ul>
        <li>كود الاشتراك الذي تدخله</li>
        <li>معرّف المستخدم (user_id) لربط الكود بحساب واحد</li>
        <li>تواريخ التفعيل والانتهاء</li>
      </ul>
      <p>لا نخزّن صور الشارت أو محتوى المحادثات هنا.</p>
      <p>تواصل: support@yourdomain.com</p>
    </body></html>
    """
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ===================== تشغيل محلي =====================
if __name__ == "__main__":
    # للتشغيل المحلي/الاختبار فقط
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
