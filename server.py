import http.server
import socketserver
import sqlite3
import json
import os
import urllib.parse
from datetime import datetime
import socket
import csv
import io

DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR, "xfn_erp.sqlite")
PORT = int(os.environ.get("PORT", 8000))

# Ensure database is initialized
from database import init_erp_database, get_connection
init_erp_database()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class XFNERPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE, PUT')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            html_path = os.path.join(DIR, "static", "index.html")
            with open(html_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if path.startswith("/api/"):
            self.handle_api_get(path, query)
            return

        # Serve static assets from static directory
        if path.startswith("/static/"):
            rel_file = path[len("/static/"):]
            file_path = os.path.join(DIR, "static", rel_file)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.send_response(200)
                if file_path.endswith(".css"):
                    self.send_header('Content-Type', 'text/css')
                elif file_path.endswith(".js"):
                    self.send_header('Content-Type', 'application/javascript')
                elif file_path.endswith(".png"):
                    self.send_header('Content-Type', 'image/png')
                elif file_path.endswith(".svg"):
                    self.send_header('Content-Type', 'image/svg+xml')
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path.startswith("/api/"):
            self.handle_api_post(path, data)
            return

        self.send_error(404, "Route Not Found")

    def handle_api_get(self, path, query):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if path == "/api/dashboard":
                today = datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute("SELECT COUNT(*) FROM employees WHERE active = 1")
                total_workers = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM employees WHERE is_checked_in = 1")
                checked_in_now = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM sites WHERE status = 'Active'")
                active_sites = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM inventory WHERE current_stock <= min_reorder_level")
                low_stock_count = cursor.fetchone()[0]

                cursor.execute("SELECT SUM(daily_wage_earned) FROM attendances WHERE date = ?", (today,))
                today_wages = cursor.fetchone()[0] or 0.0

                cursor.execute("SELECT SUM(grand_total) FROM purchase_orders WHERE status != 'Cancelled'")
                total_pos = cursor.fetchone()[0] or 0.0

                # Recent attendances
                cursor.execute('''
                    SELECT a.id, e.name as worker_name, e.trade, s.name as site_name, a.check_in, a.check_out, a.status, a.daily_wage_earned
                    FROM attendances a
                    JOIN employees e ON a.employee_id = e.id
                    LEFT JOIN sites s ON a.site_id = s.id
                    ORDER BY a.id DESC LIMIT 10
                ''')
                recent_logs = [dict(row) for row in cursor.fetchall()]

                self.send_json({
                    "success": True,
                    "metrics": {
                        "total_workers": total_workers,
                        "checked_in_now": checked_in_now,
                        "active_sites": active_sites,
                        "low_stock_count": low_stock_count,
                        "today_wages": round(today_wages, 2),
                        "total_pos": round(total_pos, 2)
                    },
                    "recent_logs": recent_logs
                })

            elif path == "/api/workers":
                trade_filter = query.get('trade', [None])[0]
                site_filter = query.get('site_id', [None])[0]
                search = query.get('search', [None])[0]

                sql = '''
                    SELECT e.*, s.name as site_name
                    FROM employees e
                    LEFT JOIN sites s ON e.site_id = s.id
                    WHERE e.active = 1
                '''
                params = []
                if trade_filter:
                    sql += " AND e.trade = ?"
                    params.append(trade_filter)
                if site_filter:
                    sql += " AND e.site_id = ?"
                    params.append(site_filter)
                if search:
                    sql += " AND (e.name LIKE ? OR e.emp_code LIKE ? OR e.phone LIKE ?)"
                    p = f"%{search}%"
                    params.extend([p, p, p])

                sql += " ORDER BY e.id ASC"
                cursor.execute(sql, params)
                workers = [dict(row) for row in cursor.fetchall()]
                self.send_json({"success": True, "workers": workers, "count": len(workers)})

            elif path == "/api/sites":
                cursor.execute('''
                    SELECT s.*, 
                    (SELECT COUNT(*) FROM employees WHERE site_id = s.id AND active = 1) as worker_count,
                    (SELECT COUNT(*) FROM employees WHERE site_id = s.id AND is_checked_in = 1) as present_count
                    FROM sites s
                    ORDER BY s.id ASC
                ''')
                sites = [dict(row) for row in cursor.fetchall()]
                self.send_json({"success": True, "sites": sites})

            elif path == "/api/inventory":
                cursor.execute("SELECT * FROM inventory ORDER BY category, name ASC")
                items = [dict(row) for row in cursor.fetchall()]
                self.send_json({"success": True, "items": items})

            elif path == "/api/vendors":
                cursor.execute("SELECT * FROM vendors ORDER BY name ASC")
                vendors = [dict(row) for row in cursor.fetchall()]
                self.send_json({"success": True, "vendors": vendors})

            elif path == "/api/purchase-orders":
                cursor.execute('''
                    SELECT po.*, v.name as vendor_name, s.name as site_name
                    FROM purchase_orders po
                    JOIN vendors v ON po.vendor_id = v.id
                    LEFT JOIN sites s ON po.site_id = s.id
                    ORDER BY po.id DESC
                ''')
                pos = [dict(row) for row in cursor.fetchall()]
                for p in pos:
                    try:
                        p['item_details'] = json.loads(p['item_details'])
                    except Exception:
                        pass
                self.send_json({"success": True, "purchase_orders": pos})

            elif path == "/api/stock-movements":
                cursor.execute('''
                    SELECT sm.*, i.name as item_name, i.unit, s.name as site_name
                    FROM stock_movements sm
                    JOIN inventory i ON sm.item_id = i.id
                    LEFT JOIN sites s ON sm.site_id = s.id
                    ORDER BY sm.id DESC LIMIT 50
                ''')
                moves = [dict(row) for row in cursor.fetchall()]
                self.send_json({"success": True, "movements": moves})

            elif path == "/api/payroll":
                date_from = query.get('from', [datetime.now().strftime('%Y-%m-01')])[0]
                date_to = query.get('to', [datetime.now().strftime('%Y-%m-%d')])[0]

                cursor.execute('''
                    SELECT e.id, e.emp_code, e.name, e.trade, e.daily_wage, e.overtime_rate, s.name as site_name,
                           COUNT(a.id) as days_present,
                           SUM(a.worked_hours) as total_hours,
                           SUM(a.overtime_hours) as total_ot_hours,
                           SUM(a.daily_wage_earned) as total_wage_earned
                    FROM employees e
                    LEFT JOIN sites s ON e.site_id = s.id
                    LEFT JOIN attendances a ON e.id = a.employee_id AND a.date BETWEEN ? AND ?
                    WHERE e.active = 1
                    GROUP BY e.id
                    ORDER BY e.id ASC
                ''', (date_from, date_to))
                payroll = [dict(row) for row in cursor.fetchall()]
                for p in payroll:
                    p['days_present'] = p['days_present'] or 0
                    p['total_hours'] = round(p['total_hours'] or 0.0, 1)
                    p['total_ot_hours'] = round(p['total_ot_hours'] or 0.0, 1)
                    p['total_wage_earned'] = round(p['total_wage_earned'] or 0.0, 2)

                self.send_json({"success": True, "payroll": payroll, "from": date_from, "to": date_to})

            elif path == "/api/export-payroll-csv":
                date_from = query.get('from', [datetime.now().strftime('%Y-%m-01')])[0]
                date_to = query.get('to', [datetime.now().strftime('%Y-%m-%d')])[0]

                cursor.execute('''
                    SELECT e.emp_code, e.name, e.trade, e.daily_wage, e.overtime_rate, s.name as site_name,
                           COUNT(a.id) as days_present,
                           SUM(a.worked_hours) as total_hours,
                           SUM(a.overtime_hours) as total_ot_hours,
                           SUM(a.daily_wage_earned) as total_wage_earned
                    FROM employees e
                    LEFT JOIN sites s ON e.site_id = s.id
                    LEFT JOIN attendances a ON e.id = a.employee_id AND a.date BETWEEN ? AND ?
                    WHERE e.active = 1
                    GROUP BY e.id
                    ORDER BY e.id ASC
                ''', (date_from, date_to))
                rows = cursor.fetchall()

                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Worker Code', 'Worker Name', 'Trade / Skill', 'Daily Wage (INR)', 'Site', 'Days Present', 'Total Hours', 'OT Hours', 'Total Wages Earned (INR)'])
                for r in rows:
                    writer.writerow([r['emp_code'], r['name'], r['trade'], r['daily_wage'], r['site_name'] or 'General', r['days_present'] or 0, round(r['total_hours'] or 0, 1), round(r['total_ot_hours'] or 0, 1), round(r['total_wage_earned'] or 0, 2)])

                csv_data = output.getvalue().encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv')
                self.send_header('Content-Disposition', f'attachment; filename="Xfinity_Muster_Roll_{date_from}_to_{date_to}.csv"')
                self.end_headers()
                self.wfile.write(csv_data)
                return

            else:
                self.send_error(404, "API endpoint not found")
        finally:
            conn.close()

    def handle_api_post(self, path, data):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        today_str = now.strftime('%Y-%m-%d')

        try:
            # 1-Tap Kiosk Check-In / Check-Out
            if path == "/api/kiosk/punch":
                worker_id = data.get('worker_id')
                pin = data.get('pin')
                site_id = data.get('site_id')

                cursor.execute("SELECT * FROM employees WHERE id = ? AND active = 1", (worker_id,))
                worker = cursor.fetchone()
                if not worker:
                    self.send_json({"success": False, "message": "Worker not found or inactive"}, status=404)
                    return

                if pin and worker['pin'] and pin != worker['pin']:
                    self.send_json({"success": False, "message": "Incorrect PIN entered!"}, status=403)
                    return

                # Toggle Check-In or Check-Out
                is_in = worker['is_checked_in']
                if not is_in:
                    # Perform Check-In
                    target_site = site_id or worker['site_id'] or 1
                    cursor.execute('''
                        INSERT INTO attendances (employee_id, site_id, date, check_in, status, notes)
                        VALUES (?, ?, ?, ?, 'Present', 'Punch via Kiosk')
                    ''', (worker['id'], target_site, today_str, now_str))
                    cursor.execute("UPDATE employees SET is_checked_in = 1, site_id = ? WHERE id = ?", (target_site, worker['id']))
                    conn.commit()
                    self.send_json({
                        "success": True,
                        "action": "CHECK_IN",
                        "worker_name": worker['name'],
                        "trade": worker['trade'],
                        "time": now.strftime('%I:%M %p'),
                        "message": f"Welcome, {worker['name']}! Checked In at {now.strftime('%I:%M %p')}"
                    })
                else:
                    # Perform Check-Out and calculate hours + wages
                    cursor.execute('''
                        SELECT * FROM attendances 
                        WHERE employee_id = ? AND check_out IS NULL 
                        ORDER BY id DESC LIMIT 1
                    ''', (worker['id'],))
                    att = cursor.fetchone()
                    if att:
                        check_in_dt = datetime.strptime(att['check_in'], '%Y-%m-%d %H:%M:%S')
                        diff = now - check_in_dt
                        worked_hours = max(round(diff.total_seconds() / 3600.0, 2), 0.1)
                        # Assume 8 hr standard shift
                        ot_hours = max(worked_hours - 8.0, 0.0)
                        regular_hours = min(worked_hours, 8.0)
                        
                        daily_wage = worker['daily_wage'] or 600.0
                        ot_rate = worker['overtime_rate'] or 100.0

                        # Wage calculation: Full day if >= 7.5 hrs, half day if >= 4 hrs, proportional otherwise
                        if worked_hours >= 7.5:
                            earned_wage = daily_wage + (ot_hours * ot_rate)
                        elif worked_hours >= 4.0:
                            earned_wage = (daily_wage * 0.5)
                        else:
                            earned_wage = round((daily_wage / 8.0) * worked_hours, 2)

                        cursor.execute('''
                            UPDATE attendances 
                            SET check_out = ?, worked_hours = ?, overtime_hours = ?, daily_wage_earned = ?
                            WHERE id = ?
                        ''', (now_str, worked_hours, ot_hours, earned_wage, att['id']))
                    
                    cursor.execute("UPDATE employees SET is_checked_in = 0 WHERE id = ?", (worker['id'],))
                    conn.commit()
                    self.send_json({
                        "success": True,
                        "action": "CHECK_OUT",
                        "worker_name": worker['name'],
                        "trade": worker['trade'],
                        "time": now.strftime('%I:%M %p'),
                        "message": f"Goodbye, {worker['name']}! Checked Out at {now.strftime('%I:%M %p')}. Wage earned today: ₹{earned_wage if att else 0}"
                    })

            elif path == "/api/workers/add":
                name = data.get('name')
                trade = data.get('trade', 'General Helper')
                daily_wage = float(data.get('daily_wage', 600.0))
                ot_rate = float(data.get('overtime_rate', 100.0))
                site_id = data.get('site_id', 1)
                phone = data.get('phone', '')
                aadhaar = data.get('aadhaar', '')
                pin = data.get('pin', '1234')

                cursor.execute("SELECT COUNT(*) FROM employees")
                cnt = cursor.fetchone()[0] + 1
                emp_code = f"XFN-W{cnt:03d}"

                cursor.execute('''
                    INSERT INTO employees (emp_code, name, trade, daily_wage, overtime_rate, site_id, phone, aadhaar, pin)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (emp_code, name, trade, daily_wage, ot_rate, site_id, phone, aadhaar, pin))
                conn.commit()
                self.send_json({"success": True, "message": f"Worker {name} ({emp_code}) registered successfully!", "id": cursor.lastrowid})

            elif path == "/api/inventory/add":
                name = data.get('name')
                category = data.get('category', 'General')
                unit = data.get('unit', 'Bags')
                qty = float(data.get('current_stock', 0))
                reorder = float(data.get('min_reorder_level', 10))
                cost = float(data.get('standard_cost', 0))
                
                cursor.execute("SELECT COUNT(*) FROM inventory")
                cnt = cursor.fetchone()[0] + 1
                code = f"MAT-{cnt:03d}"

                cursor.execute('''
                    INSERT INTO inventory (item_code, name, category, unit, current_stock, min_reorder_level, standard_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (code, name, category, unit, qty, reorder, cost))
                conn.commit()
                self.send_json({"success": True, "message": f"Material {name} added to inventory."})

            elif path == "/api/stock/movement":
                movement_type = data.get('movement_type') # 'INWARD' or 'OUTWARD'
                item_id = int(data.get('item_id'))
                site_id = int(data.get('site_id', 1))
                quantity = float(data.get('quantity', 0))
                unit_rate = float(data.get('unit_rate', 0))
                ref = data.get('reference_no', '')
                handled_by = data.get('handled_by', 'Storekeeper')
                notes = data.get('notes', '')

                total_val = quantity * unit_rate

                cursor.execute("SELECT current_stock, name FROM inventory WHERE id = ?", (item_id,))
                item = cursor.fetchone()
                if not item:
                    self.send_json({"success": False, "message": "Material not found"}, status=404)
                    return

                if movement_type == 'OUTWARD' and item['current_stock'] < quantity:
                    self.send_json({"success": False, "message": f"Insufficient stock! Available: {item['current_stock']}"}, status=400)
                    return

                # Record movement
                cursor.execute('''
                    INSERT INTO stock_movements (movement_type, item_id, site_id, quantity, unit_rate, total_value, reference_no, handled_by, date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (movement_type, item_id, site_id, quantity, unit_rate, total_val, ref, handled_by, today_str, notes))

                # Update stock
                new_stock = item['current_stock'] + quantity if movement_type == 'INWARD' else item['current_stock'] - quantity
                cursor.execute("UPDATE inventory SET current_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_stock, item_id))
                conn.commit()
                self.send_json({"success": True, "message": f"Stock {movement_type} recorded successfully. New Stock: {new_stock}"})

            elif path == "/api/purchase-orders/create":
                vendor_id = int(data.get('vendor_id'))
                site_id = int(data.get('site_id', 1))
                items = data.get('items', [])
                gst_rate = float(data.get('gst_rate', 18.0))

                subtotal = sum(float(i.get('quantity', 0)) * float(i.get('rate', 0)) for i in items)
                gst_amt = subtotal * (gst_rate / 100.0)
                grand_total = subtotal + gst_amt

                cursor.execute("SELECT COUNT(*) FROM purchase_orders")
                cnt = cursor.fetchone()[0] + 1
                po_num = f"PO-XFN-{datetime.now().year}-{cnt:04d}"

                cursor.execute('''
                    INSERT INTO purchase_orders (po_number, vendor_id, site_id, date, item_details, subtotal, gst_rate, gst_amount, grand_total, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Approved')
                ''', (po_num, vendor_id, site_id, today_str, json.dumps(items), subtotal, gst_rate, gst_amt, grand_total))
                conn.commit()
                self.send_json({"success": True, "message": f"Purchase Order {po_num} created for ₹{grand_total:,.2f}", "po_number": po_num})

            else:
                self.send_error(404, "API endpoint not found")
        finally:
            conn.close()

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))

def start_server():
    global PORT
    for attempt in range(10):
        try:
            with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), XFNERPRequestHandler) as httpd:
                local_ip = get_local_ip()
                print(f"============================================================")
                print(f" XFN-ERP_XT ENTERPRISE CONSTRUCTION SERVER RUNNING")
                print(f"============================================================")
                print(f" -> Local Laptop Access:   http://localhost:{PORT}")
                print(f" -> Mobile / Site Access:  http://{local_ip}:{PORT}")
                print(f"============================================================")
                httpd.serve_forever()
        except OSError:
            print(f"Port {PORT} busy, trying {PORT + 1}...")
            PORT += 1

if __name__ == "__main__":
    start_server()
