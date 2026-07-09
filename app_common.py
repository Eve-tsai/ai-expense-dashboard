"""Shared DB connection, schema, and helper utilities used by web_app.py and pages/*.py."""
import streamlit as st
import pandas as pd
import pymysql
import datetime
import calendar

DB_CONFIG = dict(st.secrets["mysql"])

EXCHANGE_RATES = {
    'TWD': 1.0,
    'CAD': 23.5,
    'EUR': 34.8,
    'USD': 32.2,
    'JPY': 0.21
}

CATEGORY_DISPLAY_MAP = {
    "飲食": "飲食 Food", "Food": "飲食 Food",
    "生活": "生活 Living", "Living": "生活 Living",
    "交通": "交通 Transport", "Transport": "交通 Transport",
    "購物": "購物 Shopping", "Shopping": "購物 Shopping",
    "娛樂": "娛樂 Entertainment", "Entertainment": "娛樂 Entertainment",
    "投資": "投資 Investment", "Investment": "投資 Investment",
    "學習": "學習 Learning", "Learning": "學習 Learning",
    "收入": "收入 Income", "Income": "收入 Income",
    "轉帳": "轉帳 Transfer", "Transfer": "轉帳 Transfer",
}

CATEGORY_OPTIONS = ["飲食 Food", "生活 Living", "交通 Transport", "購物 Shopping",
                     "娛樂 Entertainment", "投資 Investment", "學習 Learning"]

FALLBACK_PAYMENT_METHODS = [
    "永豐信用卡 (SinoPac)",
    "Revolut",
    "BNP Paribas",
    "現金/其他 (Cash/Other)",
]


def check_password():
    """Gate access behind a shared password stored in st.secrets['app_password'].
    Call this at the top of every page (after st.set_page_config). Stops the
    script for unauthenticated users; authentication persists for the browser
    session across all pages once entered correctly."""
    if st.session_state.get("authenticated", False):
        return

    def password_entered():
        if st.session_state.get("password_input", "") == st.secrets.get("app_password", None):
            st.session_state["authenticated"] = True
        else:
            st.session_state["authenticated"] = False
        st.session_state["password_input"] = ""

    st.text_input(
        "🔒 請輸入密碼才能查看 (Enter password to view)",
        type="password",
        on_change=password_entered,
        key="password_input",
    )
    if st.session_state.get("authenticated") is False:
        st.error("❌ 密碼錯誤 Incorrect password")
    st.stop()


def get_db_connection():
    config = DB_CONFIG.copy()
    if isinstance(config['password'], str):
        config['password'] = config['password'].encode('utf-8').decode('latin-1')
    return pymysql.connect(
        **config,
        ssl_verify_cert=True,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def apply_morandi_table_style(styler):
    styler.set_properties(**{
        'background-color': "#F5EEE5",
        'color': '#4A4643',
        'border-bottom': '1px solid #E8E4D9'
    })
    styler.set_table_styles([
        {
            'selector': 'th',
            'props': [
                ('background-color', "#C4D6D9"),
                ('color', '#4A4643'),
                ('font-weight', 'bold'),
                ('border-bottom', '1px solid #8B9DA3')
            ]
        }
    ])
    return styler


@st.cache_data(ttl=5)
def load_data():
    try:
        config = DB_CONFIG.copy()
        if isinstance(config['password'], str):
            config['password'] = config['password'].encode('utf-8').decode('latin-1')

        conn = pymysql.connect(
            **config,
            ssl_verify_cert=True,
            charset='utf8mb4'
        )

        with conn.cursor() as cursor:
            cursor.execute("USE test;")
            query = "SELECT * FROM test.daily_expenses WHERE amount_original != 0 ORDER BY transaction_date DESC;"
            df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            df['amount_original'] = pd.to_numeric(df['amount_original'], errors='coerce').fillna(0)
            if 'payment_method' not in df.columns:
                df['payment_method'] = "永豐信用卡 (SinoPac)"
            else:
                df['payment_method'] = df['payment_method'].fillna("永豐信用卡 (SinoPac)")

        return df

    except Exception as e:
        st.error(f"❌ Failed to connect to database 資料庫連線失敗: {e}")
        return pd.DataFrame()


# --- Schema provisioning -----------------------------------------------
# NOTE: test.user_cards and test.fixed_expenses already exist in the shared
# TiDB "test" schema (used by other personal tools too). These CREATE TABLE
# IF NOT EXISTS calls only matter for a fresh database and mirror the real,
# already-deployed column layout exactly - they are no-ops here.

def ensure_tables():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test.user_cards (
                    card_name VARCHAR(50) PRIMARY KEY,
                    billing_day INT,
                    payment_due_day INT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test.fixed_expenses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    item_description VARCHAR(100),
                    amount DECIMAL(10,2),
                    currency VARCHAR(10),
                    category VARCHAR(50),
                    payment_method VARCHAR(50),
                    charge_day INT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test.fixed_expense_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    fixed_expense_id INT NOT NULL,
                    `year_month` VARCHAR(7) NOT NULL,
                    display_id VARCHAR(50),
                    UNIQUE KEY uniq_fixed_month (fixed_expense_id, `year_month`)
                )
            """)
        conn.commit()
    finally:
        conn.close()


# --- Payment methods / cards (test.user_cards) ---------------------------

@st.cache_data(ttl=5)
def get_payment_methods_df():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM test.user_cards ORDER BY card_name")
            rows = cursor.fetchall()
    finally:
        conn.close()
    return pd.DataFrame(rows)


def get_payment_method_names():
    df = get_payment_methods_df()
    if df.empty:
        return list(FALLBACK_PAYMENT_METHODS)
    return df['card_name'].tolist()


def add_payment_method(card_name, billing_day, payment_due_day):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO test.user_cards (card_name, billing_day, payment_due_day) VALUES (%s, %s, %s)",
                (card_name, billing_day, payment_due_day)
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 新增付款方式失敗: {e}")
        return False
    finally:
        conn.close()


def update_payment_method(card_name, billing_day, payment_due_day):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE test.user_cards SET billing_day=%s, payment_due_day=%s WHERE card_name=%s",
                (billing_day, payment_due_day, card_name)
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 更新付款方式失敗: {e}")
        return False
    finally:
        conn.close()


def is_payment_method_in_use(card_name):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS cnt FROM test.daily_expenses WHERE payment_method=%s", (card_name,))
            in_expenses = cursor.fetchone()['cnt'] > 0
            cursor.execute("SELECT COUNT(*) AS cnt FROM test.fixed_expenses WHERE payment_method=%s", (card_name,))
            in_fixed = cursor.fetchone()['cnt'] > 0
        return in_expenses or in_fixed
    finally:
        conn.close()


def delete_payment_method(card_name):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM test.user_cards WHERE card_name=%s", (card_name,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 刪除付款方式失敗: {e}")
        return False
    finally:
        conn.close()


# --- Fixed (recurring) expenses (test.fixed_expenses) --------------------

@st.cache_data(ttl=5)
def get_fixed_expenses_df():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM test.fixed_expenses ORDER BY charge_day, id")
            rows = cursor.fetchall()
    finally:
        conn.close()
    df = pd.DataFrame(rows)
    if not df.empty and 'amount' in df.columns:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    return df


def add_fixed_expense(item_description, amount, currency, category, payment_method, charge_day):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO test.fixed_expenses
                   (item_description, amount, currency, category, payment_method, charge_day)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (item_description, amount, currency, category, payment_method, charge_day)
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 新增固定支出失敗: {e}")
        return False
    finally:
        conn.close()


def update_fixed_expense(fe_id, item_description, amount, currency, category, payment_method, charge_day):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE test.fixed_expenses
                   SET item_description=%s, amount=%s, currency=%s, category=%s, payment_method=%s, charge_day=%s
                   WHERE id=%s""",
                (item_description, amount, currency, category, payment_method, charge_day, fe_id)
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 更新固定支出失敗: {e}")
        return False
    finally:
        conn.close()


def delete_fixed_expense(fe_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM test.fixed_expenses WHERE id=%s", (fe_id,))
            cursor.execute("DELETE FROM test.fixed_expense_log WHERE fixed_expense_id=%s", (fe_id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ 刪除固定支出失敗: {e}")
        return False
    finally:
        conn.close()


def get_generated_year_months(fe_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT `year_month` FROM test.fixed_expense_log WHERE fixed_expense_id=%s", (fe_id,))
            rows = cursor.fetchall()
        return {r['year_month'] for r in rows}
    finally:
        conn.close()


def auto_generate_fixed_expenses():
    """Insert a daily_expenses row for each fixed expense that is due this month
    and hasn't already been generated. Returns the list of item_descriptions inserted."""
    today = datetime.date.today()
    year_month = today.strftime('%Y-%m')
    _, days_in_month = calendar.monthrange(today.year, today.month)

    conn = get_db_connection()
    inserted = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM test.fixed_expenses WHERE charge_day IS NOT NULL")
            fixed_list = cursor.fetchall()

            for fe in fixed_list:
                charge_day = min(fe['charge_day'], days_in_month)
                if charge_day > today.day:
                    continue

                cursor.execute(
                    "SELECT id FROM test.fixed_expense_log WHERE fixed_expense_id=%s AND `year_month`=%s",
                    (fe['id'], year_month)
                )
                if cursor.fetchone():
                    continue

                txn_date = today.replace(day=charge_day)
                mmdd = txn_date.strftime("%m%d")
                cursor.execute(
                    "SELECT display_id FROM test.daily_expenses WHERE display_id LIKE %s ORDER BY display_id DESC LIMIT 1",
                    (f"F{mmdd}%",)
                )
                last_record = cursor.fetchone()
                seq = int(last_record['display_id'][-2:]) + 1 if last_record and last_record['display_id'] else 1
                display_id = f"F{mmdd}{seq:02d}"

                cursor.execute(
                    """INSERT INTO test.daily_expenses
                       (display_id, transaction_date, item_description, category, amount_original, currency, payment_method)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (display_id, txn_date, fe['item_description'], fe['category'], fe['amount'], fe['currency'], fe['payment_method'])
                )
                cursor.execute(
                    "INSERT INTO test.fixed_expense_log (fixed_expense_id, `year_month`, display_id) VALUES (%s, %s, %s)",
                    (fe['id'], year_month, display_id)
                )
                inserted.append(fe['item_description'])
        conn.commit()
    finally:
        conn.close()
    return inserted


# --- Credit card statement cycle -----------------------------------------

def get_statement_cycle(statement_day, cycle_year, cycle_month):
    """Billing cycle (start_date, end_date) that CLOSES on statement_day within cycle_year/cycle_month."""
    _, days_in_month = calendar.monthrange(cycle_year, cycle_month)
    end_day = min(statement_day, days_in_month)
    end_date = datetime.date(cycle_year, cycle_month, end_day)

    prev_month = cycle_month - 1 if cycle_month > 1 else 12
    prev_year = cycle_year if cycle_month > 1 else cycle_year - 1
    _, prev_days_in_month = calendar.monthrange(prev_year, prev_month)
    start_day = min(statement_day, prev_days_in_month) + 1

    if start_day > prev_days_in_month:
        start_date = datetime.date(cycle_year, cycle_month, 1)
    else:
        start_date = datetime.date(prev_year, prev_month, start_day)

    return start_date, end_date
