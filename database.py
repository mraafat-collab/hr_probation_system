import os
import sqlite3
from contextlib import contextmanager

# يمكن تغيير مكان قاعدة البيانات بمتغير بيئة (مفيد للاستضافة مع قرص دائم)
DB_PATH = os.environ.get("PROBATION_DB", "probation.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    """اتصال آمن: حفظ تلقائي عند النجاح، تراجع عند الخطأ، وإغلاق دائماً."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def init_db():
    with db() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                title TEXT,
                branch TEXT,
                department TEXT,
                emp_type TEXT,
                hire_date DATE NOT NULL,
                status TEXT DEFAULT 'بالخدمة'
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_code TEXT NOT NULL,
                stage TEXT,
                due_date DATE,
                status TEXT DEFAULT 'معلق',
                decision TEXT DEFAULT 'غير محدد',
                notes TEXT,
                FOREIGN KEY (emp_code) REFERENCES employees (code) ON DELETE CASCADE
            )""")
        # ترقية قواعد البيانات القديمة دون فقدان البيانات
        cols = _columns(c, "evaluations")
        for col, ddl in [("stage_key", "TEXT"), ("score", "REAL"), ("evaluated_on", "DATE")]:
            if col not in cols:
                c.execute(f"ALTER TABLE evaluations ADD COLUMN {col} {ddl}")
        # يمنع تكرار نفس المرحلة لنفس الموظف
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_eval_stage ON evaluations(emp_code, stage_key)")
        # مرحلة الـ 60 يوماً أُلغيت من النظام: تُلغى المعلقة منها للبيانات القديمة
        c.execute("UPDATE evaluations SET status='ملغي' WHERE stage_key='d60' AND status='معلق'")
        c.execute("CREATE INDEX IF NOT EXISTS ix_eval_due ON evaluations(status, due_date)")


if __name__ == "__main__":
    init_db()
