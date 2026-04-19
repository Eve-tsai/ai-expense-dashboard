import streamlit as st
import pandas as pd
import pymysql
import plotly.express as px
import streamlit as st
import datetime
import calendar
import numpy as np


# --- 1. page configuration ---
st.set_page_config(
    page_title="AI expense assistant v2",
    page_icon="💰",
    layout="wide"
)

st.title("📊 AI 記帳助手 expense assistant - personal finance dashboard")
st.markdown("---")

# --- 2. database configuration ---
DB_CONFIG = st.secrets["mysql"]


def get_db_connection():
    config = DB_CONFIG.copy()
    if isinstance(config['password'], str):
        config['password'] = config['password'].encode('utf-8').decode('latin-1')
    
    return pymysql.connect(
        **config,
        ssl_verify_cert=True,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor # 讓回傳結果變成字典格式，方便處理
    )


@st.cache_data(ttl=5)
def load_data():
    try:
        # create copy of DB_CONFIG to avoid modifying the original dictionary
        config = DB_CONFIG.copy()


        # make sure password is a string and properly encoded (pymysql can be picky about this)
        if isinstance(config['password'], str):
            config['password'] = config['password'].encode('utf-8').decode('latin-1')


        # 1. connect to the database with SSL verification enabled
        conn = pymysql.connect(
            **config,
            ssl_verify_cert=True,
            charset='utf8mb4'
        )


        # 2. double-check
        with conn.cursor() as cursor:
            cursor.execute("USE test;")

       

        # 3. reasonable query to fetch data (only non-zero amounts, sorted by date)
        query = "SELECT * FROM test.daily_expenses WHERE amount_original != 0 ORDER BY transaction_date DESC;"
        df = pd.read_sql(query, conn)
        conn.close()

       

        # 4. ensure 'amount_original' is numeric (in case of any data issues) and fill non-convertible values with 0
        if not df.empty:
            df['amount_original'] = pd.to_numeric(df['amount_original'], errors='coerce').fillna(0)

        return df

       

    except Exception as e:
        st.error(f"❌ 資料庫連線失敗 failed to connect to database: {e}")
        return pd.DataFrame()

   



# 📥 從資料庫讀取預算
def get_budget_from_db(currency):
    try:
        conn = get_db_connection()
        # 💡 修正：直接呼叫 conn.cursor() 即可，不需要任何參數
        with conn.cursor() as cursor:
            cursor.execute("SELECT budget_amount FROM budget_settings WHERE currency = %s", (currency,))
            result = cursor.fetchone()
        conn.close()
        return float(result['budget_amount']) if result else 2000.0
    except Exception as e:
        # 如果發生錯誤 (例如資料表還沒建好)，給予預設值避免系統崩潰
        return 2000.0

# 📤 將預算存入資料庫
def save_budget_to_db(currency, amount):
    try:
        conn = get_db_connection()
        # 💡 修正：一樣直接呼叫 conn.cursor()
        with conn.cursor() as cursor:
            sql = "INSERT INTO budget_settings (currency, budget_amount) VALUES (%s, %s) ON DUPLICATE KEY UPDATE budget_amount = %s"
            cursor.execute(sql, (currency, amount, amount))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"儲存預算失敗: {e}")
   



## --- 3. conduct data reading and cleaning ---
df = load_data()



if not df.empty:
    df['amount_original'] = pd.to_numeric(df['amount_original'], errors='coerce').fillna(0)

   

    # --- filter currency ---
    st.markdown("### 💱 選擇顯示幣別 Currency")
    available_currencies = df['currency'].unique().tolist()
    default_idx = available_currencies.index('CAD') if 'CAD' in available_currencies else 0
    selected_currency = st.radio("目前結算幣別 Selected currency：", available_currencies, index=default_idx, horizontal=True)
    st.markdown("---")
    filtered_df = df[df['currency'] == selected_currency]



   

    # 1. 如果是第一次打開網頁，先在記憶體開一個空字典來放預算 (寫在 sidebar 外面即可)
    if 'budgets' not in st.session_state:
        st.session_state.budgets = {}



    # 2. 如果切換到新的幣別（且記憶體裡還沒有），給它一個合理的預設值

    if selected_currency not in st.session_state.budgets:
        if selected_currency == 'TWD':
            st.session_state.budgets[selected_currency] = 30000.0 # 台幣預設給 3 萬

        else:
            st.session_state.budgets[selected_currency] = 2000.0  # 外幣預設給 2 千



    # 💡 修正：整個側邊欄只需要呼叫一次 with st.sidebar

    with st.sidebar:
        st.header("⚙️ 設定與除錯 Settings")
        st.markdown("### 🎯 預算設定 (Budget)")

       
        db_budget = get_budget_from_db(selected_currency)

       

        with st.form(key=f'budget_form_{selected_currency}'):
            new_budget = st.number_input(
                f"設定本月 {selected_currency} 預算：",
                min_value=0.0,
                value=db_budget,  # 預設值顯示資料庫裡的數字
                step=100.0

            )

            submit_budget = st.form_submit_button(label="確定並儲存至資料庫")

           

            if submit_budget:

                save_budget_to_db(selected_currency, new_budget)
                st.success(f"✅ {selected_currency} 預算已永久儲存！")
                st.rerun()

       
        monthly_budget = get_budget_from_db(selected_currency)


        st.write("---")

        if st.button("🔄 手動更新資料 Refresh Data"):
            st.cache_data.clear()
            st.rerun()





           

    # --- 4. 數據看板 Data Board ---
    expense_df = filtered_df[~filtered_df['category'].isin(['收入', '轉帳'])]
    income_df = filtered_df[filtered_df['category'] == '收入']
    transfer_df = filtered_df[filtered_df['category'] == '轉帳']

   

    total_exp = expense_df['amount_original'].sum()
    total_inc = income_df['amount_original'].sum()
    transfer_net = transfer_df['amount_original'].sum()
    net_income = total_inc - total_exp + transfer_net



    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(f"總支出 ({selected_currency})", f"{total_exp:,.2f}", delta_color="inverse")

    with col2:
        st.metric(f"總收入 ({selected_currency})", f"{total_inc:,.2f}")

    with col3:
        st.metric(f"換匯流動 ({selected_currency})", f"{transfer_net:,.2f}", delta_color="normal")

    with col4:
        st.metric(f"本月淨流向 ({selected_currency})", f"{net_income:,.2f}", delta=f"{net_income:,.2f}")



    st.markdown("---")



    # --- 🤖 數據科學亮點：預測與洞察 ---
    st.subheader("🔮 AI 預測與消費洞察")


    today = datetime.date.today()
    _, days_in_month = calendar.monthrange(today.year, today.month)
    days_passed = today.day

   

    if days_passed > 0 and total_exp > 0:
        daily_run_rate = total_exp / days_passed
        projected_total = daily_run_rate * days_in_month
        target_daily_rate = monthly_budget / days_in_month

       

        p_col1, p_col2 = st.columns(2)

        with p_col1:
            st.info(f"📈 **目前日均花費 (Run Rate):**\n\n{daily_run_rate:,.2f} {selected_currency} / 天\n\n*(每日目標: {target_daily_rate:,.2f})*")

        with p_col2:
            st.warning(f"🎯 **本月預估總花費:**\n\n{projected_total:,.2f} {selected_currency}\n\n*(總預算: {monthly_budget:,.2f})*")

       
        projected_balance = monthly_budget - projected_total
        st.markdown(f"#### 🎯 預算達成率分析 (目標: {monthly_budget:,.0f} {selected_currency})")

       

        # 💡 整合：動態預算連動的 AI 評語

        if projected_total > monthly_budget:
            overspend_amt = projected_total - monthly_budget
            st.error(f"🚨 **警告：** 依照目前的燃燒率，月底將會 **超支 {overspend_amt:,.2f} {selected_currency}**！\n\n💡 **洞察：** 請立即啟動省錢模式，檢視近日的「購物」或「娛樂」分類是否超支。")

        elif projected_total > (monthly_budget * 0.8):
            st.warning(f"⚠️ **注意：** 預估花費已逼近預算的 80% 警戒線！\n\n💡 **洞察：** 目前的消耗速度偏快，接下來幾天請稍微留意開銷喔！")

        else:
            st.success(f"✅ **安全：** 步調良好，月底預計可 **結餘 {projected_balance:,.2f} {selected_currency}**。\n\n💡 **洞察：** 消耗速度非常健康，完美落在預算掌控內，請繼續保持！")

           

        current_spend_ratio = min(total_exp / monthly_budget, 1.0) if monthly_budget > 0 else 0.0
        st.write(f"目前已消耗預算：**{current_spend_ratio * 100:.1f}%**")
        st.progress(current_spend_ratio)

    else:
        st.info("💡 累積更多本月支出後，即可解鎖 AI 預測功能。")

   

    st.markdown("---")







    # --- 5. Chart analysis ---
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🍕 支出類別比例")
        if not expense_df.empty:
            # 💡 定義莫蘭迪專屬色票 (灰藍、藕粉、鼠尾草綠、暖灰、奶茶色)
            morandi_colors = ['#8B9DA3', '#D5C7BC', '#A8A39D', '#C0C5C1', '#D4CFC9']
            
            fig_pie = px.pie(
                expense_df, 
                values='amount_original', 
                names='category', 
                hole=0.4, 
                color_discrete_sequence=morandi_colors # 套用色票
            )
            # 讓圓餅圖背景透明，融入網頁背景
            fig_pie.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("📅 每日與累積支出走勢")
        if not expense_df.empty:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            daily_trend = expense_df.groupby('transaction_date')['amount_original'].sum().reset_index()
            daily_trend = daily_trend.sort_values('transaction_date', ascending=True)
            
            daily_trend['cumulative_amount'] = daily_trend['amount_original'].cumsum()
            daily_trend['transaction_date'] = daily_trend['transaction_date'].astype(str)
            
            fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
            
            # 📊 柱狀圖：莫蘭迪灰藍色 (#8B9DA3)
            fig_combo.add_trace(
                go.Bar(
                    x=daily_trend['transaction_date'],
                    y=daily_trend['amount_original'],
                    name="單日花費",
                    marker_color='#8B9DA3',  
                    marker_line_color='#4A4643',
                    marker_line_width=1,
                    opacity=0.85
                ),
                secondary_y=False,
            )
            
            # 📈 折線圖：莫蘭迪深棕灰 (#6B655F)
            fig_combo.add_trace(
                go.Scatter(
                    x=daily_trend['transaction_date'],
                    y=daily_trend['cumulative_amount'],
                    name="累積總額",
                    mode='lines+markers',
                    line=dict(color='#6B655F', width=3), 
                    marker=dict(size=8, color='#F4F1ED', line=dict(width=2, color='#6B655F')) # 點點變成白底棕邊
                ),
                secondary_y=True,
            )
            
            # 💡 關鍵修正 1：找出所有數據中的最大值，並乘上 1.1 留出一點頂部空白
            max_y = daily_trend['cumulative_amount'].max() * 1.1
            
            fig_combo.update_layout(
                xaxis=dict(type='category'), 
                hovermode="x unified",       
                margin=dict(l=20, r=20, t=20, b=20),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                legend=dict(
                    orientation="h",         
                    yanchor="bottom", y=1.02, 
                    xanchor="right", x=1
                )
            )
            
            # 💡 關鍵修正 2：強制左右 Y 軸的 range 都設定為 [0, max_y]
            fig_combo.update_yaxes(title_text="單日金額", secondary_y=False, showgrid=False, range=[0, max_y])
            fig_combo.update_yaxes(title_text="累積總額", secondary_y=True, showgrid=True, gridcolor='rgba(0,0,0,0.1)', range=[0, max_y])
            
            st.plotly_chart(fig_combo, use_container_width=True)
        else:
            st.info("目前尚無趨勢資料")


    st.markdown("---")


    
    # --- 6. 完整記帳明細 ---
    st.subheader("📝 完整記帳明細")
    styled_df = df[['display_id', 'transaction_date', 'item_description', 'category', 'amount_original', 'currency']].copy()
    styled_df.columns = ['編號 ID', '日期 Date', '品項 Item', '分類 Category', '金額 Amount', '幣別 Currency']

    # 💡 保留：智慧小數點處理 (整數不顯示小數點，非整數保留兩位)
    styled_df['金額 Amount'] = styled_df['金額 Amount'].apply(
        lambda x: int(x) if x % 1 == 0 else round(x, 2)
    )

    # 💡 新增：莫蘭迪專屬表格樣式設定器
    def apply_morandi_table_style(styler):
        # 1. 設定「明細資料列」的樣式 (淺米白背景)
        styler.set_properties(**{
            'background-color': '#F8F6F0',  # 淺米白色
            'color': '#4A4643',             # 深棕灰文字，閱讀起來不刺眼
            'border-bottom': '1px solid #E8E4D9' # 柔和的底部分隔線
        })
        
        # 2. 設定「標頭 (Header)」的樣式 (莫蘭迪淺藍背景)
        styler.set_table_styles([
            {
                'selector': 'th',  # CSS 選擇器：專門針對表頭
                'props': [
                    ('background-color', '#B3C6C9'), # 莫蘭迪淺藍色
                    ('color', '#4A4643'),            # 深棕灰文字
                    ('font-weight', 'bold'),         # 粗體字
                    ('border-bottom', '2px solid #8B9DA3') # 標頭下方加粗一條灰藍色線增加層次
                ]
            }
        ])
        return styler

    

    st.table(styled_df.style.pipe(apply_morandi_table_style).hide(axis="index"))


else:
    st.info("👋 歡迎！目前資料庫是空的。請在 LINE 機器人輸入第一筆帳務（例如：今天晚餐 20 加幣）後重新整理此頁面。")
    st.info("👀 Welcome! The database is currently empty. Please input your first transaction through the LINE bot (e.g., 'Spent 20 Canadian Dollars for dinner today') and refresh this page.")


