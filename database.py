import sqlite3
import os
import json
from datetime import datetime, timedelta
import random

DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR, "xfn_erp.sqlite")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_erp_database():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Company Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # 2. Construction Sites / Projects
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE,
            location TEXT,
            manager_name TEXT,
            budget REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            start_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Workers / Employees (Capacity for 150+ workers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code TEXT UNIQUE,
            name TEXT NOT NULL,
            trade TEXT NOT NULL,
            daily_wage REAL DEFAULT 600.0,
            overtime_rate REAL DEFAULT 100.0,
            site_id INTEGER,
            phone TEXT,
            aadhaar TEXT,
            pin TEXT DEFAULT '1234',
            is_checked_in INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES sites(id)
        )
    ''')

    # 4. Attendance & Daily Labor Records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            site_id INTEGER,
            date TEXT NOT NULL,
            check_in TIMESTAMP NOT NULL,
            check_out TIMESTAMP,
            worked_hours REAL DEFAULT 0.0,
            overtime_hours REAL DEFAULT 0.0,
            daily_wage_earned REAL DEFAULT 0.0,
            status TEXT DEFAULT 'Present',
            notes TEXT,
            FOREIGN KEY(employee_id) REFERENCES employees(id),
            FOREIGN KEY(site_id) REFERENCES sites(id)
        )
    ''')

    # 5. Construction Materials / Inventory
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit TEXT NOT NULL,
            current_stock REAL DEFAULT 0,
            min_reorder_level REAL DEFAULT 10,
            standard_cost REAL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 6. Stock Movements (Inward MRN & Site Outward Issue)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_type TEXT NOT NULL, -- 'INWARD' (MRN) or 'OUTWARD' (Site Issue)
            item_id INTEGER NOT NULL,
            site_id INTEGER,
            quantity REAL NOT NULL,
            unit_rate REAL DEFAULT 0,
            total_value REAL DEFAULT 0,
            reference_no TEXT,
            handled_by TEXT,
            date TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(item_id) REFERENCES inventory(id),
            FOREIGN KEY(site_id) REFERENCES sites(id)
        )
    ''')

    # 7. Vendors / Suppliers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gstin TEXT,
            phone TEXT,
            email TEXT,
            category TEXT,
            city TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 8. Purchase Orders (With Indian GST calculation)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT UNIQUE NOT NULL,
            vendor_id INTEGER NOT NULL,
            site_id INTEGER,
            date TEXT NOT NULL,
            item_details TEXT NOT NULL, -- JSON array of line items
            subtotal REAL DEFAULT 0,
            gst_rate REAL DEFAULT 18.0,
            gst_amount REAL DEFAULT 0,
            grand_total REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending', -- 'Pending', 'Approved', 'Received', 'Paid'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id),
            FOREIGN KEY(site_id) REFERENCES sites(id)
        )
    ''')

    # 9. Client Invoices (GST Invoicing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            site_id INTEGER,
            date TEXT NOT NULL,
            hsn_code TEXT DEFAULT '9954', -- Construction services
            amount REAL DEFAULT 0,
            gst_rate REAL DEFAULT 18.0,
            tax_amount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Unpaid',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES sites(id)
        )
    ''')

    # 10. Site Expenses (Petty cash, machinery, fuel)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_to TEXT,
            date TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES sites(id)
        )
    ''')

    # Default Settings
    default_settings = [
        ('company_name', 'Xfinity Buildcon Private Limited'),
        ('gstin', '07AAACX1234F1Z5'),
        ('email', 'itsupport@xfinitybuildcon.com'),
        ('phone', '+91 98765 43210'),
        ('currency', '₹'),
        ('address', 'Corporate Tower, Construction Division, India')
    ]
    for k, v in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Seed Default Sites if none exist
    cursor.execute("SELECT COUNT(*) FROM sites")
    if cursor.fetchone()[0] == 0:
        sites_data = [
            ("Sector 62 Commercial Hub", "SITE-SEC62", "Noida, Sector 62", "Rajesh Kumar (Project Head)", 45000000, "Active", "2026-01-15"),
            ("Golf Course Extension Luxury Villas", "SITE-GCX", "Gurugram, GC Extn", "Amit Sharma (Site Engineer)", 78000000, "Active", "2026-02-01"),
            ("Expressway Logistics Park", "SITE-EXP99", "Greater Noida Expressway", "Vikas Verma (Senior PM)", 32000000, "Active", "2026-03-10")
        ]
        cursor.executemany('''
            INSERT INTO sites (name, code, location, manager_name, budget, status, start_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sites_data)

    # Seed Default Construction Materials / Inventory
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        materials = [
            ("MAT-CEM-01", "OPC 53 Grade Cement", "Cement", "Bags (50kg)", 850, 100, 380.0),
            ("MAT-CEM-02", "PPC Fly Ash Cement", "Cement", "Bags (50kg)", 620, 100, 350.0),
            ("MAT-STL-01", "TMT Steel Fe-550D (12mm)", "Steel", "Metric Ton (MT)", 18.5, 3.0, 58500.0),
            ("MAT-STL-02", "TMT Steel Fe-550D (16mm)", "Steel", "Metric Ton (MT)", 14.2, 2.5, 59000.0),
            ("MAT-STL-03", "TMT Steel Fe-550D (8mm)", "Steel", "Metric Ton (MT)", 9.8, 2.0, 60000.0),
            ("MAT-SND-01", "River Sand (Coarse / Plaster)", "Aggregates", "Brass (100 Cu.Ft)", 45.0, 5.0, 4200.0),
            ("MAT-AGG-01", "Blue Metal Coarse Aggregate (20mm)", "Aggregates", "Brass (100 Cu.Ft)", 60.0, 8.0, 3800.0),
            ("MAT-BRK-01", "Red Clay Burnt Bricks (Class A)", "Masonry", "Pieces (Nos)", 45000, 5000, 9.5),
            ("MAT-BLK-01", "AAC Lightweight Blocks (600x200x150)", "Masonry", "Pieces (Nos)", 12000, 1500, 65.0),
            ("MAT-PNT-01", "Exterior Weatherproof Emulsion Paint", "Finishing", "Buckets (20L)", 75, 10, 3400.0),
            ("MAT-RMC-01", "Ready Mix Concrete M25 Grade", "Concrete", "Cubic Meter (Cum)", 150.0, 20.0, 4600.0),
            ("MAT-PVC-01", "Heavy Duty PVC Conduit Pipes (25mm)", "Electrical", "Bundles (100m)", 40, 5, 1250.0)
        ]
        cursor.executemany('''
            INSERT INTO inventory (item_code, name, category, unit, current_stock, min_reorder_level, standard_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', materials)

    # Seed Default Vendors
    cursor.execute("SELECT COUNT(*) FROM vendors")
    if cursor.fetchone()[0] == 0:
        vendors_data = [
            ("Tata Tiscon Steel Distributors", "07AAACT1122K1Z8", "+91 98112 34567", "sales@tatatiscon-dist.in", "Steel & Metals", "Noida"),
            ("UltraTech Cement Depot", "07AAACU9988P1Z3", "+91 98223 45678", "orders@ultratechdepot.com", "Cement & RMC", "Greater Noida"),
            ("Jai Hind Building Material Suppliers", "07AABPJ3344R1Z1", "+91 98334 56789", "jaihindmaterials@gmail.com", "Sand, Bricks & Aggregate", "Gurugram"),
            ("Asian Paints & Finishing Store", "07AAACA5566T1Z5", "+91 98445 67890", "sales@asianpaints-store.com", "Paint & Finishing", "Delhi NCR")
        ]
        cursor.executemany('''
            INSERT INTO vendors (name, gstin, phone, email, category, city)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', vendors_data)

    # Seed 150 Real Construction Workers if empty
    cursor.execute("SELECT COUNT(*) FROM employees")
    if cursor.fetchone()[0] == 0:
        seed_150_workers(cursor)

    conn.commit()
    conn.close()
    print("XFN-ERP_NEXT Database Initialized Successfully!")

def seed_150_workers(cursor):
    first_names = [
        "Ramesh", "Suresh", "Mukesh", "Rajesh", "Dinesh", "Manoj", "Pramod", "Santosh", "Vijay", "Ajay",
        "Sunil", "Anil", "Deepak", "Raju", "Vinod", "Sanjay", "Mahesh", "Gopal", "Kishan", "Radhey",
        "Arun", "Pawan", "Dharmendra", "Jitendra", "Bablu", "Sonu", "Monu", "Pappu", "Chhotu", "Ram",
        "Shyam", "Guddu", "Ravi", "Amit", "Sumit", "Vicky", "Rohit", "Mohit", "Ashok", "Kailash",
        "Brijesh", "Kamlesh", "Harish", "Lalchand", "Bhagwan", "Chhotey", "Pradeep", "Satish", "Devendra", "Jagdish"
    ]
    last_names = ["Kumar", "Singh", "Yadav", "Sharma", "Verma", "Prasad", "Gupta", "Mandal", "Paswan", "Thakur", "Rathore", "Pandey", "Chauhan", "Nishad", "Mahato"]

    trades_pool = [
        ("Mason / Mistri", 750.0, 120.0, 30),
        ("Carpenter / Shuttering", 800.0, 130.0, 25),
        ("Bar Bender / Steel Fixer", 750.0, 120.0, 25),
        ("Electrician", 850.0, 140.0, 10),
        ("Plumber", 800.0, 130.0, 10),
        ("Painter", 700.0, 110.0, 15),
        ("Tile & Marble Setter", 850.0, 140.0, 10),
        ("Crane / JCB Operator", 1000.0, 160.0, 5),
        ("Site Supervisor", 1200.0, 200.0, 5),
        ("General Construction Helper", 500.0, 80.0, 50)
    ]

    workers = []
    worker_idx = 1

    for trade_name, wage, ot_rate, count in trades_pool:
        for _ in range(count):
            if worker_idx > 150:
                break
            f_name = random.choice(first_names)
            l_name = random.choice(last_names)
            full_name = f"{f_name} {l_name}"
            emp_code = f"XFN-W{worker_idx:03d}"
            site_id = random.choice([1, 2, 3])
            phone = f"+91 9{random.randint(600000000, 999999999)}"
            aadhaar = f"{random.randint(2000, 9999)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}"
            pin = f"{random.randint(1000, 9999)}"

            workers.append((emp_code, full_name, trade_name, wage, ot_rate, site_id, phone, aadhaar, pin))
            worker_idx += 1

    cursor.executemany('''
        INSERT INTO employees (emp_code, name, trade, daily_wage, overtime_rate, site_id, phone, aadhaar, pin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', workers)

    # Seed realistic today attendance for first 45 workers
    today_str = datetime.now().strftime('%Y-%m-%d')
    morning_checkin = f"{today_str} 08:30:00"
    for w_id in range(1, 46):
        cursor.execute("UPDATE employees SET is_checked_in = 1 WHERE id = ?", (w_id,))
        cursor.execute('''
            INSERT INTO attendances (employee_id, site_id, date, check_in, status, notes)
            VALUES (?, ?, ?, ?, 'Present', 'Shift started 8:30 AM')
        ''', (w_id, random.choice([1, 2, 3]), today_str, morning_checkin))

if __name__ == "__main__":
    init_erp_database()
