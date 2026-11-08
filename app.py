import streamlit as st
import pandas as pd
from datetime import datetime
from database import init_db, get_connection
from engine import add_employee_with_stages, get_due_evaluations, generate_docx_evaluation_form

init_db()

st.set_page_config(page_title="نظام متابعة فترات الاختبار التكاملي", layout="wide")

st.sidebar.title("نظام إدارة فترات الاختبار 📋")
menu = st.sidebar.radio("الانتقال إلى:", [
    "🚨 التنبيهات والتقييمات المستحقة", 
    "➕ إضافة موظف جديد", 
    "📊 السجل العام والتقرير النهائي",
    "📥 تصدير البيانات ونماذج التقييم"
])

# ----------------------------------------------------
# 1. صفحة التنبيهات والتقييمات المستحقة
# ----------------------------------------------------
if menu == "🚨 التنبيهات والتقييمات المستحقة":
    st.header("🚨 التنبيهات: الموظفون المستحق تقييمهم أو على وشك الانتهاء")
    
    days_ahead = st.slider("عرض الموظفين المستحقين خلال الأيام القادمة:", min_value=0, max_value=15, value=7)
    df_due = get_due_evaluations(days_threshold=days_ahead)
    
    if df_due.empty:
        st.success(f"🎉 لا توجد تقييمات مستحقة خلال الـ {days_ahead} أيام القادمة!")
    else:
        st.warning(f"يوجد عدد ({len(df_due)}) تقييم يحتاج لاتخاذ إجراء:")
        
        # عرض الجدول بالتفاصيل
        st.dataframe(
            df_due[['code', 'name', 'title', 'branch', 'department', 'stage', 'due_date']], 
            use_container_width=True
        )
        
        st.divider()
        st.subheader("📝 نموذج التقييم واتخاذ القرار")
        
        col1, col2 = st.columns(2)
        with col1:
            selected_emp = st.selectbox("اختر الموظف:", df_due['name'].tolist())
            emp_row = df_due[df_due['name'] == selected_emp].iloc[0]
            
            # زر إنشاء نموذج Word تلقائياً لطباعته
            docx_file = generate_docx_evaluation_form(
                emp_name=emp_row['name'],
                emp_code=emp_row['code'],
                dept=emp_row['department'] if emp_row['department'] else "عام",
                title=emp_row['title'],
                branch=emp_row['branch'],
                hire_date=str(emp_row['hire_date']),
                due_date=str(emp_row['due_date']),
                stage_title=emp_row['stage']
            )
            
            with open(docx_file, "rb") as fp:
                st.download_button(
                    label=f"📄 تحميل نموذج التقييم Word جاهز للطباعة ({emp_row['name']})",
                    data=fp,
                    file_name=docx_file,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

        with col2:
            decision = st.selectbox("القرار المتخذ بعد التقييم:", ["تثبيت", "مد الفترة", "إنهاء خدمة", "كان كاجوال"])
            notes = st.text_input("ملاحظات التقييم / توصية المدير:")
            
            if st.button("حفظ التقييم وتحديث الحالة"):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE evaluations 
                    SET status = 'تم التقييم', decision = ?, notes = ?
                    WHERE id = ?
                ''', (decision, notes, int(emp_row['eval_id'])))
                
                if decision == "إنهاء خدمة":
                    cursor.execute("UPDATE employees SET status = 'خارج الخدمة' WHERE code = ?", (emp_row['code'],))
                    
                conn.commit()
                conn.close()
                st.success(f"تم تسجيل القرار ({decision}) للموظف {selected_emp} بنجاح!")
                st.rerun()

# ----------------------------------------------------
# 2. صفحة إضافة موظف جديد
# ----------------------------------------------------
elif menu == "➕ إضافة موظف جديد":
    st.header("➕ تسجيل موظف جديد وإنشاء فترات التقييم تلقائياً")
    with st.form("add_emp_form"):
        col1, col2 = st.columns(2)
        with col1:
            code = st.text_input("كود الموظف*")
            name = st.text_input("الاسم بالكامل*")
            title = st.text_input("المسمى الوظيفي")
            emp_type = st.selectbox("نوع العقد", ["دائم", "كاجوال"])
        with col2:
            branch = st.text_input("الموقع / الفرع")
            department = st.text_input("القسم / الإدارة")
            hire_date = st.date_input("تاريخ التعيين", value=datetime.now())
            
        submit = st.form_submit_button("إضافة الموظف وإنشاء كافة مواعيد التقييم")
        if submit:
            if code and name:
                add_employee_with_stages(code, name, title, branch, department, emp_type, hire_date.strftime("%Y-%m-%d"))
                st.success(f"تمت إضافة الموظف ({name}) وتم جدول تقييمات الـ 10، 30، 60، 90، و120 يوماً تلقائياً!")
            else:
                st.error("يرجى إدخال الحقول المطلوبة (*)")

# ----------------------------------------------------
# 3. صفحة السجل العام والتقرير النهائي
# ----------------------------------------------------
elif menu == "📊 السجل العام والتقرير النهائي":
    st.header("📊 السجل الشامل لفترات اختبار جميع الموظفين")
    conn = get_connection()
    df_all = pd.read_sql_query('''
        SELECT 
            e.code as "الكود",
            e.name as "الاسم",
            e.title as "الوظيفة",
            e.branch as "الفرع",
            e.hire_date as "تاريخ التعيين",
            e.status as "حالة الخدمة",
            GROUP_CONCAT(v.stage || ': [' || v.decision || ' - ' || v.status || ']', '\n') as "سجل التقييمات المرحلية"
        FROM employees e
        LEFT JOIN evaluations v ON e.code = v.emp_code
        GROUP BY e.code
    ''', conn)
    conn.close()
    st.dataframe(df_all, use_container_width=True)

# ----------------------------------------------------
# 4. تصدير البيانات ونماذج التقييم
# ----------------------------------------------------
elif menu == "📥 تصدير البيانات ونماذج التقييم":
    st.header("📥 تصدير سجلات الموظفين والتقارير")
    conn = get_connection()
    df_export = pd.read_sql_query("SELECT * FROM employees", conn)
    conn.close()
    
    st.download_button(
        label="📥 تحميل كافة البيانات في ملف Excel / CSV",
        data=df_export.to_csv(index=False).encode('utf-8-sig'),
        file_name=f"جدول_تقييمات_الموظفين_{datetime.now().strftime('%Y-%m-%d')}.csv",
        mime='text/csv'
    )