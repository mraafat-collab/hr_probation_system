import os
from datetime import datetime, timedelta
import pandas as pd
from database import get_connection
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT

def calculate_due_dates(hire_date):
    return {
        '10_days': hire_date + timedelta(days=10),
        '30_days': hire_date + timedelta(days=30),
        '60_days': hire_date + timedelta(days=60),
        '90_days': hire_date + timedelta(days=90),
        'extension': hire_date + timedelta(days=120)
    }

def add_employee_with_stages(code, name, title, branch, department, emp_type, hire_date_str):
    conn = get_connection()
    cursor = conn.cursor()
    hire_date = datetime.strptime(hire_date_str, "%Y-%m-%d").date()
    
    cursor.execute('''
        INSERT OR REPLACE INTO employees (code, name, title, branch, department, emp_type, hire_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'بالخدمة')
    ''', (code, name, title, branch, department, emp_type, hire_date))
    
    due_dates = calculate_due_dates(hire_date)
    stage_labels = {
        '10_days': 'تقييم الـ 10 أيام الأولى',
        '30_days': 'تقييم الشهر الأول (30 يوم)',
        '60_days': 'تقييم الشهر الثاني (60 يوم)',
        '90_days': 'تقييم الـ 90 يوم (نهاية الاختبار)',
        'extension': 'تقييم فترة التمديد (120 يوم)'
    }
    
    for stage_key, due_date in due_dates.items():
        cursor.execute('''
            INSERT INTO evaluations (emp_code, stage, due_date, status, decision)
            VALUES (?, ?, ?, 'معلق', 'غير محدد')
        ''', (code, stage_labels[stage_key], due_date))
        
    conn.commit()
    conn.close()

def get_due_evaluations(days_threshold=7):
    """جلب التقييمات المستحقة حالياً والتقييمات على وشك الانتهاء خلال عدد أيام محدد"""
    conn = get_connection()
    today = datetime.now().date()
    target_date = today + timedelta(days=days_threshold)
    
    query = '''
        SELECT 
            e.code, e.name, e.title, e.branch, e.department, e.hire_date,
            v.id as eval_id, v.stage, v.due_date, v.status, v.decision, v.notes
        FROM employees e
        JOIN evaluations v ON e.code = v.emp_code
        WHERE e.status = 'بالخدمة' AND v.status = 'معلق' AND v.due_date <= ?
        ORDER BY v.due_date ASC
    '''
    df = pd.read_sql_query(query, conn, params=(target_date.strftime("%Y-%m-%d"),))
    conn.close()
    return df

def generate_docx_evaluation_form(emp_name, emp_code, dept, title, branch, hire_date, due_date, stage_title):
    """توليد مستند تقييم Word احترافي مطابق لنموذج تقييم الشركة 1.docx"""
    doc = docx.Document()
    
    # ضبط الاتجاه إلى RTL ليدعم اللغة العربية
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

    # عنوان التقرير
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run(f"تقرير تقييم الأداء - فترة الاختبار ({stage_title})")
    run.font.name = 'Arial'
    run.font.size = Pt(16)
    run.font.bold = True
    
    # جدول بيانات الموظف
    info_table = doc.add_table(rows=2, cols=4)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_table.autofit = False
    
    headers = [
        ("اسم الموظف:", emp_name, "الكود:", str(emp_code)),
        ("القسم / الفرع:", f"{dept} - {branch}", "الوظيفة:", title),
    ]
    
    for r_idx, row_data in enumerate(headers):
        row = info_table.rows[r_idx]
        row.cells[0].paragraphs[0].add_run(row_data[0]).font.bold = True
        row.cells[1].paragraphs[0].add_run(row_data[1])
        row.cells[2].paragraphs[0].add_run(row_data[2]).font.bold = True
        row.cells[3].paragraphs[0].add_run(row_data[3])
        
    p_dates = doc.add_paragraph()
    p_dates.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_dates.add_run(f"تاريخ التعيين: {hire_date}   |   تاريخ استحقاق التقييم: {due_date}").font.bold = True
    
    # جدول عناصر التقييم 10 عناصر
    doc.add_paragraph("\nعناصر التقييم:")
    eval_table = doc.add_table(rows=12, cols=7)
    eval_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    hdr_cells = eval_table.rows[0].cells
    hdr_titles = ["م", "عناصر التقييم", "4 (ممتاز)", "3 (جيد)", "2 (متوسط)", "1 (ضعيف)", "ملاحظات"]
    for i, t in enumerate(hdr_titles):
        cell_p = hdr_cells[i].paragraphs[0]
        r = cell_p.add_run(t)
        r.font.bold = True
        cell_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
    elements = [
        "المقدرة على الإستيعاب",
        "المقدرة على اتباع التعليمات",
        "التفكير البناء و الإبتكار في العمل",
        "المقدرة على العمل دون مراقبة",
        "المقدرة على فرض الإحترام",
        "المقدرة على العمل مع الغير",
        "الدقة في العمل و المواعيد",
        "المثابرة في العمل",
        "السرعة في انجاز العمل الموكل اليه",
        "مستوى المعلومات الفنية"
    ]
    
    for idx, elem in enumerate(elements, start=1):
        row_cells = eval_table.rows[idx].cells
        row_cells[0].paragraphs[0].add_run(str(idx))
        row_cells[1].paragraphs[0].add_run(elem)
        
    # التقييم العام
    total_row = eval_table.rows[11].cells
    total_row[1].paragraphs[0].add_run("التقييم العام للموظف").font.bold = True
    
    # توصيات وملاحظات
    doc.add_paragraph("\nنوع المخالفات وتكرارها إن وجد: ........................................................................")
    doc.add_paragraph("توصية المدير المباشر:  [  ] تثبيت الموظف    [  ] مد فترة الاختبار    [  ] إنهاء خدمة الموظف")
    doc.add_paragraph("توقيع المدير المباشر: ...........................   التاريخ:     /    / ")
    doc.add_paragraph("ملاحظات وتوقيع إدارة الموارد البشرية: ...........................................................")
    
    filename = f"evaluation_{emp_code}_{due_date}.docx"
    doc.save(filename)
    return filename