"""إرسال ملخص يومي بالتقييمات المستحقة بالبريد.
التشغيل اليومي: cron (لينكس) أو Task Scheduler (ويندوز):  python notify.py
المتغيرات: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_TO (عدة عناوين بفاصلة), ALERT_DAYS
"""
import os
import smtplib
from email.mime.text import MIMEText

from database import init_db
from engine import get_due_evaluations


def main():
    init_db()
    df = get_due_evaluations(int(os.environ.get("ALERT_DAYS", 7)))
    if df.empty:
        print("لا توجد تقييمات مستحقة.")
        return
    rows = "".join(
        f"<tr><td>{r.level}</td><td>{r.code}</td><td>{r['name']}</td><td>{r.branch or ''}</td>"
        f"<td>{r.stage}</td><td>{r.due_date}</td><td>{r.days_left}</td></tr>" for _, r in df.iterrows())
    html = ("<div dir='rtl' style='font-family:Arial'><h3>تقييمات فترة الاختبار المستحقة</h3>"
            "<table border='1' cellpadding='6' style='border-collapse:collapse'>"
            "<tr><th>الأولوية</th><th>الكود</th><th>الاسم</th><th>الفرع</th><th>المرحلة</th>"
            f"<th>الاستحقاق</th><th>الأيام</th></tr>{rows}</table></div>")
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = f"تنبيه: {len(df)} تقييم يحتاج إجراء"
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["MAIL_TO"]
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg, to_addrs=[a.strip() for a in os.environ["MAIL_TO"].split(",")])
    print("تم الإرسال.")


if __name__ == "__main__":
    main()
