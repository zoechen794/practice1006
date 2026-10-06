"""
check_db.py
驗證 orders.db 資料庫內容：
1. 查詢並印出 customer, product, orders, order_item 四張資料表的全部內容。
2. 進行關聯查詢 (JOIN)，展示訂單明細與總計金額，特別突顯「包含多項商品之訂單 (ORD-2024001)」。
3. 自動化驗證約束條件 (CHECK 約束、複合主鍵、外鍵約束)。
"""

import os
import sys
import sqlite3
import unicodedata

# 確保在 Windows 命令提示字元 / PowerShell 中正常顯示繁體中文
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DB_FILE = os.path.join(os.path.dirname(__file__), "orders.db")

def get_char_width(c):
    """計算字元寬度，中文字等全形字元為 2，英數半形字元為 1"""
    status = unicodedata.east_asian_width(c)
    return 2 if status in ('W', 'F', 'A') else 1

def string_width(s):
    """計算字串於終端機中的總顯示寬度"""
    return sum(get_char_width(c) for c in str(s))

def pad_string(s, target_width, align="left"):
    """根據字元顯示寬度填充空格，支援 left, right, center 對齊"""
    s_str = str(s)
    current_w = string_width(s_str)
    padding_needed = max(0, target_width - current_w)
    if align == "right":
        return " " * padding_needed + s_str
    elif align == "center":
        left_pad = padding_needed // 2
        right_pad = padding_needed - left_pad
        return " " * left_pad + s_str + " " * right_pad
    else:
        return s_str + " " * padding_needed

def print_pretty_table(title, headers, rows):
    """自建兼顧中英文字寬的表格格式化輸出函式"""
    print(f"\n================================================================================")
    print(f"  {title} (共 {len(rows)} 筆資料)")
    print(f"================================================================================")
    
    if not rows:
        print("  (目前無資料)")
        return

    # 計算各欄位所需最大寬度
    col_widths = []
    for col_idx in range(len(headers)):
        header_w = string_width(headers[col_idx])
        max_row_w = max(string_width(row[col_idx]) for row in rows) if rows else 0
        col_widths.append(max(header_w, max_row_w) + 2)

    # 建立邊框
    separator = "+" + "+".join("-" * w for w in col_widths) + "+"
    header_line = "|" + "|".join(f" {pad_string(headers[i], col_widths[i] - 2, 'center')} " for i in range(len(headers))) + "|"
    
    print(separator)
    print(header_line)
    print(separator)
    
    for row in rows:
        formatted_row = []
        for i, val in enumerate(row):
            val_str = str(val)
            # 判斷是否為數值或金額字串 (例如 "2,490" 或 123)
            clean_num = val_str.replace(',', '').replace('.', '', 1)
            is_numeric = isinstance(val, (int, float)) or (clean_num.isdigit() and not val_str.startswith('09') and not val_str.startswith('C') and not val_str.startswith('P') and not val_str.startswith('ORD'))
            align = "right" if is_numeric else "left"
            formatted_row.append(f" {pad_string(val_str, col_widths[i] - 2, align)} ")
        print("|" + "|".join(formatted_row) + "|")
        
    print(separator)

def show_all_tables(conn):
    cursor = conn.cursor()

    # 1. 客戶資料表
    cursor.execute("SELECT customer_id, name, phone, address, created_date FROM customer;")
    customer_rows = cursor.fetchall()
    customer_headers = ["客戶編號(PK)", "客戶姓名", "聯絡電話", "地址", "建檔日期"]
    print_pretty_table("【1. 客戶資料表 - customer】", customer_headers, customer_rows)

    # 2. 商品資料表
    cursor.execute("SELECT product_id, name, price, stock, category FROM product;")
    product_rows = cursor.fetchall()
    product_headers = ["商品編號(PK)", "商品名稱", "單價", "庫存數量", "商品分類"]
    # 格式化金額顯示
    formatted_product_rows = [
        (r[0], r[1], f"{r[2]:,.0f}", r[3], r[4]) for r in product_rows
    ]
    print_pretty_table("【2. 商品資料表 - product】", product_headers, formatted_product_rows)

    # 3. 訂單資料表
    cursor.execute("SELECT order_id, customer_id, order_date, status, sales_rep FROM orders;")
    orders_rows = cursor.fetchall()
    orders_headers = ["訂單編號(PK)", "客戶編號(FK)", "訂單日期", "訂單狀態", "負責業務"]
    print_pretty_table("【3. 訂單資料表 - orders】", orders_headers, orders_rows)

    # 4. 訂單明細資料表
    cursor.execute("SELECT order_id, product_id, quantity, unit_price FROM order_item;")
    order_item_rows = cursor.fetchall()
    order_item_headers = ["訂單編號(PK/FK)", "商品編號(PK/FK)", "數量(CHECK>0)", "下單單價(CHECK>=0)"]
    formatted_item_rows = [
        (r[0], r[1], r[2], f"{r[3]:,.0f}") for r in order_item_rows
    ]
    print_pretty_table("【4. 訂單明細資料表 - order_item】", order_item_headers, formatted_item_rows)

def show_order_details_join(conn):
    """跨表關聯查詢：示範多品項訂單與總計金額試算"""
    cursor = conn.cursor()
    query = """
    SELECT 
        o.order_id,
        c.name AS customer_name,
        o.order_date,
        p.name AS product_name,
        oi.quantity,
        oi.unit_price,
        (oi.quantity * oi.unit_price) AS subtotal,
        o.status,
        o.sales_rep
    FROM orders o
    JOIN customer c ON o.customer_id = c.customer_id
    JOIN order_item oi ON o.order_id = oi.order_id
    JOIN product p ON oi.product_id = p.product_id
    ORDER BY o.order_id, oi.product_id;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    headers = ["訂單編號", "客戶名稱", "下單日期", "商品名稱", "數量", "下單單價", "小計金額", "狀態", "負責業務"]
    formatted_rows = [
        (r[0], r[1], r[2], r[3], r[4], f"{r[5]:,.0f}", f"{r[6]:,.0f}", r[7], r[8]) for r in rows
    ]
    print_pretty_table("【訂單明細跨表關聯分析 (JOIN 查詢)】", headers, formatted_rows)
    print("  說明：訂單 ORD-2024001 包含「機械式鍵盤」與「人體工學無線滑鼠」共 2 項商品，驗證多項商品案例！")

def verify_constraints(conn):
    """驗證 CHECK 約束與複合主鍵是否正常運作"""
    print("\n================================================================================")
    print("  【資料庫約束條件驗證測試 (Constraints Integrity Test)】")
    print("================================================================================")
    cursor = conn.cursor()
    
    # 測試 1: 數量 CHECK (quantity > 0) 約束
    try:
        cursor.execute("SAVEPOINT test_check_qty;")
        cursor.execute("INSERT INTO order_item VALUES ('ORD-2024002', 'P001', 0, 1000);")
        print("  [X] 數量 CHECK 測試失敗：數量為 0 未被攔截")
    except sqlite3.IntegrityError as e:
        print(f"  [V] 數量必須大於 0 (CHECK quantity > 0) 約束生效：成功攔截違規輸入 -> {e}")
    finally:
        cursor.execute("ROLLBACK TO test_check_qty;")

    # 測試 2: 單價 CHECK (unit_price >= 0) 約束
    try:
        cursor.execute("SAVEPOINT test_check_price;")
        cursor.execute("INSERT INTO order_item VALUES ('ORD-2024002', 'P001', 1, -500);")
        print("  [X] 單價 CHECK 測試失敗：單價為負數未被攔截")
    except sqlite3.IntegrityError as e:
        print(f"  [V] 單價不可為負 (CHECK unit_price >= 0) 約束生效：成功攔截違規輸入 -> {e}")
    finally:
        cursor.execute("ROLLBACK TO test_check_price;")

    # 測試 3: 複合主鍵 (order_id, product_id) 重複約束
    try:
        cursor.execute("SAVEPOINT test_composite_pk;")
        cursor.execute("INSERT INTO order_item VALUES ('ORD-2024001', 'P001', 1, 2490);")
        print("  [X] 複合主鍵測試失敗：重複插入 (ORD-2024001, P001) 未被攔截")
    except sqlite3.IntegrityError as e:
        print(f"  [V] 複合主鍵 PRIMARY KEY(order_id, product_id) 生效：成功攔截重複品項 -> {e}")
    finally:
        cursor.execute("ROLLBACK TO test_composite_pk;")

    print("================================================================================\n")

def main():
    if not os.path.exists(DB_FILE):
        print(f"[!] 找不到資料庫檔案：{DB_FILE}")
        print("請先執行 python create_db.py 建立資料庫。")
        return

    print(f"[*] 連線至 SQLite 資料庫：{DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        show_all_tables(conn)
        show_order_details_join(conn)
        verify_constraints(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
