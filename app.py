import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import engine as eng
from database import DB_PATH, init_db

st.set_page_config(page_title="RUFI", page_icon="📋", layout="wide", initial_sidebar_state="collapsed")
init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
html, body, .stApp, .stMarkdown, button, input, textarea, select { font-family: 'Cairo', sans-serif !important; }
.stApp { direction: rtl; }
section[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"],
div[data-testid="collapsedControl"], button[kind="header"] { display: none !important; }
.brand { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:10px; }
.brand .logo { font-size:2rem; font-weight:700; color:#1F3864; letter-spacing:3px; }
.brand .logo span { color:#ED7D31; }
.brand .sub { color:#5b6577; font-size:.9rem; margin-right:10px; }
.badge { padding:6px 14px; border-radius:20px; font-weight:600; font-size:.9rem; }
.badge.red { background:#fde8e8; color:#C00000; } .badge.orange { background:#fff1e3; color:#c25a00; }
.badge.green { background:#e6f4ec; color:#2E8B57; }
div[data-testid="stRadio"] > div[role="radiogroup"] { gap:6px; flex-wrap:wrap; background:#f4f6fa;
        padding:6px; border-radius:14px; }
div[data-testid="stRadio"] label { background:transparent; padding:8px 18px; border-radius:10px; cursor:pointer; margin:0; }
div[data-testid="stRadio"] label > div:first-child { display:none; }
div[data-testid="stRadio"] label:has(input:checked) { background:#1F3864; }
div[data-testid="stRadio"] label:has(input:checked) p { color:#fff !important; font-weight:700; }
.stTextInput input, .stTextArea textarea, .stNumberInput input { direction: rtl; text-align: right; }
.block-container { padding-top: 1.5rem; max-width: 1300px; }
.hero { background: linear-gradient(135deg,#1F3864,#2F5597); color:#fff; padding:22px 28px;
        border-radius:16px; margin-bottom:20px; }
.hero h1 { margin:0; font-size:1.7rem; color:#fff; } .hero p { margin:4px 0 0; opacity:.85; }
.kpi { background:#fff; border-radius:14px; padding:16px 18px; border:1px solid #e6e9ef;
       box-shadow:0 2px 8px rgba(20,40,80,.06); border-right:6px solid var(--c); }
.kpi .n { font-size:2rem; font-weight:700; color:var(--c); line-height:1.1; }
.kpi .l { color:#5b6577; font-size:.95rem; }
div[data-testid="stSidebar"] { background:#f4f6fa; }
.stButton > button, .stDownloadButton > button { border-radius:10px; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------ حماية اختيارية بكلمة مرور
def _password():
    pwd = os.environ.get("APP_PASSWORD")
    if not pwd:
        try:
            pwd = st.secrets.get("APP_PASSWORD")
        except Exception:
            pwd = None
    return pwd


pwd = _password()
if pwd and not st.session_state.get("auth"):
    st.markdown('<div class="hero"><h1>🔒 RUFI</h1><p>تسجيل الدخول</p></div>',
                unsafe_allow_html=True)
    entered = st.text_input("كلمة المرور", type="password")
    if st.button("دخول", type="primary"):
        if entered == pwd:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("كلمة المرور غير صحيحة")
    st.stop()


def hero(title, sub=""):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)


def kpi(col, label, value, color):
    col.markdown(f'<div class="kpi" style="--c:{color}"><div class="n">{value}</div>'
                 f'<div class="l">{label}</div></div>', unsafe_allow_html=True)


# ------------------------------------------------------------ الشريط العلوي
if "days" not in st.session_state:
    st.session_state["days"] = 7
days = st.session_state["days"]
stats = eng.get_stats(days)
if stats["overdue"]:
    badge = f'<span class="badge red">🔴 {stats["overdue"]} تقييم متأخر</span>'
elif stats["soon"]:
    badge = f'<span class="badge orange">🟠 {stats["soon"]} تقييم قريب الاستحقاق</span>'
else:
    badge = '<span class="badge green">✅ لا توجد تقييمات عاجلة</span>'
st.markdown(f'<div class="brand"><div><span class="logo">RU<span>FI</span></span>'
            f'<span class="sub">متابعة فترات الاختبار · {date.today():%Y-%m-%d}</span></div>{badge}</div>',
            unsafe_allow_html=True)

nav_col, set_col = st.columns([5, 1.6])
with nav_col:
    page = st.radio("القائمة", ["🏠 لوحة المتابعة", "📝 التقييمات المستحقة", "➕ إضافة موظف",
                                "📊 السجل العام", "📥 التصدير والنسخ الاحتياطي"],
                    horizontal=True, label_visibility="collapsed")
with set_col:
    st.number_input("نافذة التنبيه (أيام)", min_value=0, max_value=30, key="days")
st.write("")

COLS = {"code": "الكود", "name": "الاسم", "title": "الوظيفة", "branch": "الفرع", "department": "القسم",
        "stage": "المرحلة", "due_date": "تاريخ الاستحقاق", "days_left": "الأيام المتبقية", "level": "الأولوية",
        "emp_type": "نوع العقد", "hire_date": "تاريخ التعيين", "status": "الحالة", "next_due": "أقرب استحقاق",
        "decision": "القرار", "score": "الدرجة", "evaluated_on": "تاريخ التقييم", "notes": "ملاحظات"}

# ------------------------------------------------------------ 1. لوحة المتابعة
if page == "🏠 لوحة المتابعة":
    hero("لوحة المتابعة", "نظرة شاملة على حالة الموظفين والتقييمات القادمة")
    k = st.columns(5)
    kpi(k[0], "على رأس العمل (تحت الاختبار)", stats["active"], "#2F5597")
    kpi(k[1], "تقييمات متأخرة", stats["overdue"], "#C00000")
    kpi(k[2], f"مستحقة خلال {days} أيام", stats["soon"], "#ED7D31")
    kpi(k[3], "تم تثبيتهم", stats["confirmed"], "#2E8B57")
    kpi(k[4], "خارج الخدمة", stats["out"], "#7F7F7F")
    st.write("")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("🚨 يحتاج إجراء الآن")
        due = eng.get_due_evaluations(days)
        if due.empty:
            st.success(f"لا توجد تقييمات مستحقة خلال {days} أيام 🎉")
        else:
            st.dataframe(due[["level", "code", "name", "branch", "stage", "due_date", "days_left"]]
                         .rename(columns=COLS), use_container_width=True, hide_index=True)
    with c2:
        st.subheader("التقييمات المعلقة حسب المرحلة")
        ps = eng.pending_by_stage()
        if ps.empty:
            st.info("لا توجد بيانات بعد.")
        else:
            fig = px.bar(ps, x="n", y="stage", orientation="h", text="n", color_discrete_sequence=["#2F5597"])
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), yaxis_title=None, xaxis_title=None,
                              font=dict(family="Cairo"), yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------ 2. التقييمات المستحقة
elif page == "📝 التقييمات المستحقة":
    hero("التقييمات المستحقة", f"الموظفون المستحق تقييمهم خلال {days} أيام (والمتأخرون)")
    due = eng.get_due_evaluations(days)
    if due.empty:
        st.success("🎉 لا توجد تقييمات مستحقة حالياً.")
    else:
        st.dataframe(due[["level", "code", "name", "title", "branch", "department", "stage", "due_date", "days_left"]]
                     .rename(columns=COLS), use_container_width=True, hide_index=True)
        st.divider()
        idx = st.selectbox("اختر الموظف / المرحلة", due.index,
                           format_func=lambda i: f"{due.at[i, 'code']} — {due.at[i, 'name']} — {due.at[i, 'stage']}")
        row = due.loc[idx]
        left, right = st.columns(2)
        with left:
            st.markdown("#### 📄 نموذج التقييم")
            st.caption("نموذج Word عربي (من اليمين لليسار) جاهز للطباعة والتوقيع.")
            data = eng.generate_evaluation_docx({k: row[k] for k in
                                                 ["name", "code", "title", "branch", "department", "hire_date",
                                                  "due_date", "stage"]})
            st.download_button("📄 تحميل نموذج التقييم", data, f"تقييم_{row['code']}_{row['due_date']}.docx",
                               "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               use_container_width=True)
        with right:
            st.markdown("#### ✅ تسجيل القرار")
            with st.form("decision"):
                decision = st.selectbox("القرار", eng.DECISIONS)
                score = st.number_input("الدرجة العامة (من 4) — اختياري", 0.0, 4.0, 0.0, 0.1)
                notes = st.text_area("ملاحظات / توصية المدير", height=80)
                if st.form_submit_button("حفظ القرار", type="primary", use_container_width=True):
                    eng.record_decision(int(row["eval_id"]), decision, notes, score or None)
                    st.success("تم حفظ القرار وتحديث حالة الموظف.")
                    st.rerun()
            st.caption("تثبيت أو إنهاء خدمة ⇐ تُلغى المراحل المتبقية تلقائياً. مد الفترة ⇐ تُضاف مرحلة الـ 120 يوماً.")

# ------------------------------------------------------------ 3. إضافة موظف
elif page == "➕ إضافة موظف":
    hero("إضافة موظف جديد", "تُجدول مواعيد التقييم (10 / 30 / 90 يوماً + الامتداد) تلقائياً")
    with st.form("add_emp", clear_on_submit=True):
        a, b = st.columns(2)
        code = a.text_input("كود الموظف *")
        name = a.text_input("الاسم بالكامل *")
        title = a.text_input("المسمى الوظيفي")
        emp_type = a.selectbox("نوع العقد", ["دائم", "كاجوال"])
        branch = b.text_input("الموقع / الفرع")
        department = b.text_input("القسم / الإدارة")
        hire_date = b.date_input("تاريخ التعيين", value=date.today())
        if st.form_submit_button("إضافة الموظف", type="primary"):
            if code.strip() and name.strip():
                ok, msg = eng.add_employee(code, name, title, branch, department, emp_type, hire_date)
                (st.success if ok else st.error)(msg)
            else:
                st.error("يرجى إدخال الكود والاسم.")

# ------------------------------------------------------------ 4. السجل العام
elif page == "📊 السجل العام":
    hero("السجل العام", "ابحث، افتح ملف أي موظف، وراجع كل تقييماته")
    emps = eng.get_employees()
    f1, f2 = st.columns([3, 1])
    q = f1.text_input("🔍 بحث بالاسم أو الكود أو الفرع")
    stt = f2.selectbox("الحالة", ["الكل", "بالخدمة", "مثبت", "خارج الخدمة"])
    if q:
        mask = emps[["code", "name", "branch", "department"]].fillna("").apply(
            lambda s: s.str.contains(q, case=False, regex=False)).any(axis=1)
        emps = emps[mask]
    if stt != "الكل":
        emps = emps[emps["status"] == stt]
    st.dataframe(emps.rename(columns=COLS), use_container_width=True, hide_index=True)

    if not emps.empty:
        st.divider()
        code = st.selectbox("ملف الموظف", emps["code"],
                            format_func=lambda c: f"{c} — {emps.set_index('code').at[c, 'name']}")
        ev = eng.get_evaluations(code)
        st.dataframe(ev.drop(columns="id").rename(columns=COLS), use_container_width=True, hide_index=True)
        with st.expander("⚠️ حذف الموظف نهائياً"):
            if st.checkbox("أؤكد رغبتي في حذف الموظف وكل تقييماته", key="delconfirm"):
                if st.button("حذف نهائي"):
                    eng.delete_employee(code)
                    st.rerun()

# ------------------------------------------------------------ 5. التصدير والنسخ الاحتياطي
else:
    hero("التصدير والنسخ الاحتياطي", "تقارير للإدارة العليا وحماية البيانات")
    a, b = st.columns(2)
    with a:
        st.markdown("#### 📊 تقرير Excel كامل")
        st.caption("ورقتان: الموظفون والتقييمات، بتنسيق من اليمين لليسار.")
        st.download_button("تحميل Excel", eng.export_excel(), f"تقرير_الاختبار_{date.today()}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with b:
        st.markdown("#### 💾 نسخة احتياطية من قاعدة البيانات")
        st.caption("احتفظ بنسخة دورية، خصوصاً إذا كان التطبيق على استضافة قد تمسح الملفات عند إعادة التشغيل.")
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as fp:
                st.download_button("تحميل النسخة الاحتياطية", fp.read(), f"probation_backup_{date.today()}.db",
                                   use_container_width=True)
        up = st.file_uploader("استرجاع نسخة (.db)", type="db")
        if up and st.checkbox("أؤكد استبدال البيانات الحالية بالنسخة المرفوعة"):
            if st.button("استرجاع", type="primary"):
                with open(DB_PATH, "wb") as fp:
                    fp.write(up.getvalue())
                init_db()
                st.success("تم الاسترجاع.")
                st.rerun()
