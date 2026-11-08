import io
from datetime import date, timedelta

import docx
import pandas as pd
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from database import db

STAGES = [
    ("d10", "تقييم الـ 10 أيام الأولى", 10),
    ("d30", "تقييم الشهر الأول (30 يوماً)", 30),
    ("d90", "تقييم نهاية الاختبار (90 يوماً)", 90),
]
EXTENSION = ("ext", "تقييم فترة الامتداد (بعد الـ 90 يوماً)", 120)

DECISIONS = ["استمرار في الاختبار", "تثبيت", "مد الفترة", "إنهاء خدمة", "كان كاجوال"]
END_DECISIONS = {"إنهاء خدمة", "كان كاجوال"}

ELEMENTS = [
    "المقدرة على الاستيعاب", "المقدرة على اتباع التعليمات", "التفكير البناء والابتكار في العمل",
    "المقدرة على العمل دون مراقبة", "المقدرة على فرض الاحترام", "المقدرة على العمل مع الغير",
    "الدقة في العمل والمواعيد", "المثابرة في العمل", "السرعة في إنجاز العمل الموكل إليه",
    "مستوى المعلومات الفنية",
]


# ----------------------------------------------------------------- الموظفون
def add_employee(code, name, title, branch, department, emp_type, hire_date: date):
    code, name = code.strip(), name.strip()
    with db() as c:
        if c.execute("SELECT 1 FROM employees WHERE code=?", (code,)).fetchone():
            return False, f"الكود ({code}) مسجل مسبقاً، لم تتم الإضافة."
        c.execute(
            "INSERT INTO employees (code,name,title,branch,department,emp_type,hire_date) VALUES (?,?,?,?,?,?,?)",
            (code, name, title.strip(), branch.strip(), department.strip(), emp_type, hire_date.isoformat()),
        )
        c.executemany(
            "INSERT INTO evaluations (emp_code,stage_key,stage,due_date) VALUES (?,?,?,?)",
            [(code, k, lbl, (hire_date + timedelta(days=d)).isoformat()) for k, lbl, d in STAGES],
        )
    return True, f"تمت إضافة ({name}) وجدولة {len(STAGES)} مراحل تقييم تلقائياً."


def delete_employee(code):
    with db() as c:
        c.execute("DELETE FROM evaluations WHERE emp_code=?", (code,))
        c.execute("DELETE FROM employees WHERE code=?", (code,))


def get_employees():
    with db() as c:
        return pd.read_sql_query("""
            SELECT e.code, e.name, e.title, e.branch, e.department, e.emp_type, e.hire_date, e.status,
                   (SELECT MIN(due_date) FROM evaluations v
                     WHERE v.emp_code=e.code AND v.status='معلق') AS next_due
            FROM employees e ORDER BY e.hire_date DESC""", c)


def get_evaluations(code):
    with db() as c:
        return pd.read_sql_query(
            "SELECT id, stage, due_date, status, decision, score, evaluated_on, notes "
            "FROM evaluations WHERE emp_code=? ORDER BY due_date", c, params=(code,))


# ----------------------------------------------------------------- التنبيهات
def _level(days_left):
    if days_left < 0:
        return "🔴 متأخر"
    if days_left <= 3:
        return "🟠 عاجل"
    return "🟡 قريب"


def get_due_evaluations(days=7):
    limit = (date.today() + timedelta(days=days)).isoformat()
    with db() as c:
        df = pd.read_sql_query("""
            SELECT e.code, e.name, e.title, e.branch, e.department, e.hire_date,
                   v.id AS eval_id, v.stage, v.due_date
            FROM employees e JOIN evaluations v ON e.code=v.emp_code
            WHERE e.status='بالخدمة' AND v.status='معلق' AND v.due_date <= ?
            ORDER BY v.due_date""", c, params=(limit,))
    if not df.empty:
        df["days_left"] = (pd.to_datetime(df["due_date"]) - pd.Timestamp(date.today())).dt.days
        df["level"] = df["days_left"].map(_level)
    return df


def get_stats(days=7):
    today = date.today().isoformat()
    limit = (date.today() + timedelta(days=days)).isoformat()
    base = ("SELECT COUNT(*) FROM evaluations v JOIN employees e ON e.code=v.emp_code "
            "WHERE e.status='بالخدمة' AND v.status='معلق' AND ")
    with db() as c:
        emp = {r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM employees GROUP BY status")}
        overdue = c.execute(base + "v.due_date < ?", (today,)).fetchone()[0]
        soon = c.execute(base + "v.due_date BETWEEN ? AND ?", (today, limit)).fetchone()[0]
    return {"active": emp.get("بالخدمة", 0), "confirmed": emp.get("مثبت", 0),
            "out": emp.get("خارج الخدمة", 0), "overdue": overdue, "soon": soon}


def pending_by_stage():
    with db() as c:
        return pd.read_sql_query(
            "SELECT v.stage AS stage, COUNT(*) AS n FROM evaluations v "
            "JOIN employees e ON e.code=v.emp_code "
            "WHERE e.status='بالخدمة' AND v.status='معلق' GROUP BY v.stage ORDER BY MIN(v.due_date)", c)


# ----------------------------------------------------------------- القرارات
def record_decision(eval_id, decision, notes="", score=None):
    """يسجل القرار ويطبق أثره تلقائياً على حالة الموظف والمراحل المتبقية."""
    with db() as c:
        ev = c.execute("SELECT emp_code FROM evaluations WHERE id=?", (eval_id,)).fetchone()
        if not ev:
            return
        code = ev["emp_code"]
        c.execute("UPDATE evaluations SET status='تم التقييم', decision=?, notes=?, score=?, evaluated_on=? WHERE id=?",
                  (decision, notes, score, date.today().isoformat(), eval_id))
        if decision == "تثبيت" or decision in END_DECISIONS:
            new_status = "مثبت" if decision == "تثبيت" else "خارج الخدمة"
            c.execute("UPDATE employees SET status=? WHERE code=?", (new_status, code))
            c.execute("UPDATE evaluations SET status='ملغي' WHERE emp_code=? AND status='معلق'", (code,))
        elif decision == "مد الفترة":
            hire = date.fromisoformat(c.execute("SELECT hire_date FROM employees WHERE code=?", (code,)).fetchone()[0])
            k, lbl, d = EXTENSION
            c.execute("INSERT OR IGNORE INTO evaluations (emp_code,stage_key,stage,due_date) VALUES (?,?,?,?)",
                      (code, k, lbl, (hire + timedelta(days=d)).isoformat()))


# ----------------------------------------------------------------- Excel
def export_excel() -> bytes:
    with db() as c:
        emps = pd.read_sql_query(
            "SELECT code AS 'الكود', name AS 'الاسم', title AS 'الوظيفة', branch AS 'الفرع', department AS 'القسم', "
            "emp_type AS 'نوع العقد', hire_date AS 'تاريخ التعيين', status AS 'الحالة' FROM employees", c)
        evs = pd.read_sql_query(
            "SELECT e.code AS 'الكود', e.name AS 'الاسم', v.stage AS 'المرحلة', v.due_date AS 'تاريخ الاستحقاق', "
            "v.status AS 'حالة التقييم', v.decision AS 'القرار', v.score AS 'الدرجة', "
            "v.evaluated_on AS 'تاريخ التقييم', v.notes AS 'ملاحظات' "
            "FROM evaluations v JOIN employees e ON e.code=v.emp_code ORDER BY v.due_date", c)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in (("الموظفون", emps), ("التقييمات", evs)):
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.sheet_view.rightToLeft = True
            for col in ws.columns:
                width = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 3, 12), 45)
    return buf.getvalue()


# ----------------------------------------------------------------- نموذج Word (RTL حقيقي)
def _rtl_p(p, center=False):
    p._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)


def _write(p, text, bold=False, size=11):
    r = p.add_run(str(text))
    rPr = r._r.get_or_add_rPr()
    f = OxmlElement("w:rFonts")
    for a in ("ascii", "hAnsi", "cs"):
        f.set(qn("w:" + a), "Arial")
    rPr.append(f)
    if bold:
        rPr.append(OxmlElement("w:b"))
        rPr.append(OxmlElement("w:bCs"))
    for tag in ("w:sz", "w:szCs"):
        e = OxmlElement(tag)
        e.set(qn("w:val"), str(int(size * 2)))
        rPr.append(e)
    rPr.append(OxmlElement("w:rtl"))


def _para(d, text, bold=False, size=11, center=False):
    p = d.add_paragraph()
    _rtl_p(p, center)
    _write(p, text, bold, size)


def _cell(cell, text, width, bold=False, center=False, shade=None, size=10):
    cell.width = Cm(width)
    p = cell.paragraphs[0]
    _rtl_p(p, center)
    _write(p, text, bold, size)
    if shade:
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), shade)
        cell._tc.get_or_add_tcPr().append(shd)


def _rtl_table(t):
    t.autofit = False
    tblPr = t._tbl.tblPr
    tblPr.insert_element_before(
        OxmlElement("w:bidiVisual"), "w:tblStyleRowBandSize", "w:tblStyleColBandSize", "w:tblW", "w:jc",
        "w:tblCellSpacing", "w:tblInd", "w:tblBorders", "w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook")


def generate_evaluation_docx(emp: dict) -> bytes:
    """emp: name, code, title, branch, department, hire_date, due_date, stage"""
    d = docx.Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin = s.right_margin = Cm(1.5)
    s.top_margin = s.bottom_margin = Cm(1.3)

    _para(d, "تقرير تقييم الأداء – فترة الاختبار", True, 17, True)
    _para(d, emp["stage"], True, 12, True)

    info = d.add_table(rows=3, cols=4, style="Table Grid")
    _rtl_table(info)
    dept = f"{emp.get('department') or '-'} / {emp.get('branch') or '-'}"
    rows = [("اسم الموظف", emp["name"], "الكود", emp["code"]),
            ("الوظيفة", emp.get("title") or "-", "القسم / الفرع", dept),
            ("تاريخ التعيين", emp["hire_date"], "تاريخ استحقاق التقييم", emp["due_date"])]
    w = [3.2, 5.8, 3.4, 5.6]
    for col, cw in zip(info.columns, w):
        col.width = Cm(cw)
    for r, vals in zip(info.rows, rows):
        for i, (cell, v) in enumerate(zip(r.cells, vals)):
            _cell(cell, v, w[i], bold=i % 2 == 0, shade="DCE6F2" if i % 2 == 0 else None)

    _para(d, "")
    _para(d, "عناصر التقييم", True, 12)
    t = d.add_table(rows=len(ELEMENTS) + 2, cols=7, style="Table Grid")
    _rtl_table(t)
    w = [0.9, 6.0, 1.6, 1.6, 1.6, 1.6, 4.7]
    for col, cw in zip(t.columns, w):
        col.width = Cm(cw)
    heads = ["م", "عناصر التقييم", "4 ممتاز", "3 جيد", "2 متوسط", "1 ضعيف", "ملاحظات"]
    for i, (cell, h) in enumerate(zip(t.rows[0].cells, heads)):
        _cell(cell, h, w[i], True, True, "DCE6F2")
    for n, el in enumerate(ELEMENTS, 1):
        cells = t.rows[n].cells
        for i, cell in enumerate(cells):
            _cell(cell, n if i == 0 else el if i == 1 else "", w[i], center=i == 0)
    for r in t.rows[1:]:
        r.height = Cm(0.85)
    last = t.rows[-1].cells
    for i, cell in enumerate(last):
        _cell(cell, "التقييم العام للموظف" if i == 1 else "", w[i], bold=True, shade="F2F2F2")

    _para(d, "")
    _para(d, "نوع المخالفات وتكرارها إن وجد: " + "." * 70)
    _para(d, "توصية المدير المباشر:   [    ] تثبيت الموظف     [    ] مد فترة الاختبار     [    ] إنهاء خدمة الموظف", True)
    _para(d, "")
    _para(d, "توقيع المدير المباشر: ......................     التاريخ:    /    /")
    _para(d, "ملاحظات وتوقيع إدارة الموارد البشرية: " + "." * 55)

    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
