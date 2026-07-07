from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pymysql
import datetime
import sys
from pathlib import Path
import re

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        class _FallbackToml:
            @staticmethod
            def load(f):
                content = f.read().decode()
                result = {}
                current_section = result
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('[') and line.endswith(']'):
                        section_name = line[1:-1].strip()
                        keys = section_name.split('.')
                        current_section = result
                        for k in keys:
                            current_section = current_section.setdefault(k, {})
                    elif '=' in line:
                        k, _, v = line.partition('=')
                        k = k.strip()
                        v = v.strip()
                        if v.lower() == 'true':
                            v = True
                        elif v.lower() == 'false':
                            v = False
                        else:
                            try:
                                v = int(v)
                            except ValueError:
                                try:
                                    v = float(v)
                                except ValueError:
                                    v = v.strip('"').strip("'")
                        current_section[k] = v
                return result
        tomllib = _FallbackToml()

app = FastAPI()

# 用 middleware 加 CORS header，不依賴 FastAPI 的 CORSMiddleware 處理 preflight
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

def get_db_config():
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    with open(secrets_path, "rb") as f:
        secrets = tomllib.load(f)
    config = dict(secrets["mysql"])
    if "port" in config:
        config["port"] = int(config["port"])
    return config

def get_conn():
    config = get_db_config()
    if isinstance(config.get("password"), str):
        config["password"] = config["password"].encode("utf-8").decode("latin-1")
    return pymysql.connect(
        **config,
        ssl_verify_cert=True,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

@app.get("/api/summary")
def summary():
    try:
        conn = get_conn()
        today = datetime.date.today()
        first_day = today.replace(day=1)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT SUM(amount_original) as total
                FROM test.daily_expenses
                WHERE currency = 'EUR'
                  AND category NOT IN ('收入','轉 當','Income','Transfer')
                  AND amount_original != 0
                  AND transaction_date >= %s
            """, (first_day,))
            row = cur.fetchone()
            month_eur = float(row["total"] or 0)

        weekday = today.weekday()
        week_start = today - datetime.timedelta(days=weekday)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM test.daily_expenses
                WHERE category NOT IN ('收入','轉帳','Income','Transfer')
                  AND amount_original != 0
                  AND transaction_date >= %s
            """, (week_start,))
            row = cur.fetchone()
            week_count = int(row["cnt"] or 0)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT category, SUM(amount_original) as total
                FROM test.daily_expenses
                WHERE currency = 'EUR'
                  AND category NOT IN ('收入','轉帳','Income','Transfer')
                  AND amount_original != 0
                  AND transaction_date >= %s
                GROUP BY category
                ORDER BY total DESC
            """, (first_day,))
            categories = cur.fetchall()

        conn.close()

        return {
            "month_total_eur": round(month_eur, 2),
            "week_count": week_count,
            "categories": [
                {"name": r["category"], "amount": round(float(r["total"]), 2)}
                for r in categories
            ],
            "as_of": str(today),
        }
    except Exception as e:
        return {"error": str(e)}

class ExpenseIn(BaseModel):
    item_description: str
    amount_original: float
    currency: str = "EUR"  # 👇 升級 A：把 API 接收的預設幣別直接綁定為 EUR
    category: str
    transaction_date: Optional[str] = None

# 👇 升級 B：雙效解析器 (同時捕捉「付款方式」與「隱藏的幣別」)
def parse_payment_and_currency(item_text, default_currency):
    payment_method = "永豐信用卡 (SinoPac)" # 預設付款方式
    final_currency = default_currency.upper() if default_currency else "EUR"
    clean_item = item_text

    # --- 1. 偵測並擷取隱藏的「幣別」 ---
    if re.search(r'(台幣|twd|nt)', clean_item, re.IGNORECASE):
        final_currency = "TWD"
        clean_item = re.sub(r'(台幣|twd|nt)', '', clean_item, flags=re.IGNORECASE)
    elif re.search(r'(加幣|cad)', clean_item, re.IGNORECASE):
        final_currency = "CAD"
        clean_item = re.sub(r'(加幣|cad)', '', clean_item, flags=re.IGNORECASE)
    elif re.search(r'(美金|usd)', clean_item, re.IGNORECASE):
        final_currency = "USD"
        clean_item = re.sub(r'(美金|usd)', '', clean_item, flags=re.IGNORECASE)
    elif re.search(r'(日幣|jpy)', clean_item, re.IGNORECASE):
        final_currency = "JPY"
        clean_item = re.sub(r'(日幣|jpy)', '', clean_item, flags=re.IGNORECASE)
    elif re.search(r'(歐元|eur|euro)', clean_item, re.IGNORECASE):
        final_currency = "EUR"
        clean_item = re.sub(r'(歐元|eur|euro)', '', clean_item, flags=re.IGNORECASE)

    # --- 2. 偵測並擷取隱藏的「付款方式」 ---
    if re.search(r'\b(bnp)\b', clean_item, re.IGNORECASE):
        payment_method = "BNP Paribas"
        clean_item = re.sub(r'\b(bnp)\b', '', clean_item, flags=re.IGNORECASE)
    elif re.search(r'\b(revolut|revo|rev)\b', clean_item, re.IGNORECASE):
        payment_method = "Revolut"
        clean_item = re.sub(r'\b(revolut|revo|rev)\b', '', clean_item, flags=re.IGNORECASE)
    elif re.search(r'(現金|cash)', clean_item, re.IGNORECASE):
        payment_method = "現金/其他 (Cash/Other)"
        clean_item = re.sub(r'(現金|cash)', '', clean_item, flags=re.IGNORECASE)
    elif re.search(r'(永豐|sinopac)', clean_item, re.IGNORECASE):
        payment_method = "永豐信用卡 (SinoPac)"
        clean_item = re.sub(r'(永豐|sinopac)', '', clean_item, flags=re.IGNORECASE)

    # 清除多餘的空白
    clean_item = re.sub(r'\s+', ' ', clean_item).strip()
    
    # 防呆：如果把幣別跟付款方式都拔掉後變空白了，給個預設值
    if not clean_item:
        clean_item = "未命名品項"

    return payment_method, final_currency, clean_item


@app.post("/api/add_expense")
def add_expense(expense: ExpenseIn):
    try:
        date_str = expense.transaction_date or str(datetime.date.today())
        datetime.datetime.strptime(date_str, "%Y-%m-%d")

        # 👇 在寫入前，同時解析付款方式與幣別
        final_payment, final_currency, final_item = parse_payment_and_currency(
            expense.item_description.strip(), 
            expense.currency.strip()
        )

        conn = get_conn()

        date_prefix = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%m%d")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as cnt FROM test.daily_expenses
                WHERE transaction_date = %s
            """, (date_str,))
            row = cur.fetchone()
            seq = int(row["cnt"] or 0) + 1
        next_id = f"{date_prefix}{seq:02d}"

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO test.daily_expenses
                  (display_id, transaction_date, item_description, category, amount_original, currency, payment_method)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(next_id),
                date_str,
                final_item,                 # 乾淨的品項名稱
                expense.category.strip(),
                expense.amount_original,
                final_currency,             # 👈 寫入自動判定後的幣別 (預設 EUR 或捕捉到的新幣別)
                final_payment               # 自動判定後的付款方式
            ))
        conn.commit()
        conn.close()

        return {"success": True, "display_id": next_id, "message": f"已新增：{final_item} {expense.amount_original} {final_currency} ({final_payment})"}

    except ValueError:
        return {"success": False, "message": "日期格式錯誤，請使用 YYYY-MM-DD"}
    except Exception as e:
        return {"success": False, "message": str(e)}