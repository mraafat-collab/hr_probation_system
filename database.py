import sqlite3

def get_connection():
    conn = sqlite3.connect('probation.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            title TEXT,
            branch TEXT,
            department TEXT,
            emp_type TEXT,
            hire_date DATE NOT NULL,
            status TEXT DEFAULT 'بالخدمة'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code TEXT,
            stage TEXT,
            due_date DATE,
            status TEXT DEFAULT 'معلق',
            decision TEXT DEFAULT 'غير محدد',
            notes TEXT,
            FOREIGN KEY (emp_code) REFERENCES employees (code)
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()