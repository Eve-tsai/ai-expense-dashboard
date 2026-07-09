import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from app_common import (
    load_data, ensure_tables, apply_morandi_table_style, EXCHANGE_RATES,
    CATEGORY_DISPLAY_MAP, get_payment_methods_df, get_statement_cycle,
    check_password,
)

st.set_page_config(page_title="付款方式總額", page_icon="💳", layout="wide")
check_password()
st.title("💳 Payment Method Totals | 付款方式總額")
st.markdown("---")

ensure_tables()
df = load_data()

if df.empty:
    st.info("👋 目前資料庫是空的。")
    st.stop()

df['amount_original'] = pd.to_numeric(df['amount_original'], errors='coerce').fillna(0)
df['transaction_date'] = pd.to_datetime(df['transaction_date']).dt.date
df['payment_method'] = df['payment_method'].fillna("永豐信用卡 (SinoPac)")

today = datetime.date.today()
first_day_of_month = today.replace(day=1)

st.markdown("### 🗓️ 統計區間 (Date Range)")
range_choice = st.radio("快速選擇：", ["本月 This Month", "全部 All Time", "自訂 Custom"], horizontal=True)

if range_choice == "本月 This Month":
    start_date, end_date = first_day_of_month, today
elif range_choice == "全部 All Time":
    start_date, end_date = df['transaction_date'].min(), df['transaction_date'].max()
else:
    custom_range = st.date_input("選擇日期區間：", value=(first_day_of_month, today))
    if len(custom_range) == 2:
        start_date, end_date = custom_range
    else:
        start_date, end_date = custom_range[0], today

only_expenses = st.checkbox("僅計算支出 (排除收入/轉帳) Exclude Income/Transfer", value=True)
scope_df = df[(df['transaction_date'] >= start_date) & (df['transaction_date'] <= end_date)].copy()
if only_expenses:
    scope_df = scope_df[~scope_df['category'].isin(['收入', '轉帳', 'Income', 'Transfer'])]

st.markdown("---")

if scope_df.empty:
    st.info("此區間內沒有交易紀錄。")
else:
    st.markdown(f"### 📊 各付款方式總額 ({start_date} ~ {end_date})")
    convert_to_twd = st.checkbox("換算成台幣統一顯示 (Convert All to TWD)", value=False)

    calc_df = scope_df.copy()
    if convert_to_twd:
        calc_df['display_amount'] = calc_df.apply(lambda r: r['amount_original'] * EXCHANGE_RATES.get(r['currency'], 1.0), axis=1)
        calc_df['display_currency'] = 'TWD'
    else:
        calc_df['display_amount'] = calc_df['amount_original']
        calc_df['display_currency'] = calc_df['currency']

    pivot = calc_df.groupby(['payment_method', 'display_currency'])['display_amount'].sum().reset_index()
    pivot.columns = ['Payment 付款方式', 'Currency 幣別', 'Total 總額']

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("#### 📋 明細表")
        table_display = pivot.copy()
        table_display['Total 總額'] = table_display['Total 總額'].apply(lambda x: f"{x:,.2f}")
        st.table(table_display.style.pipe(apply_morandi_table_style).hide(axis="index"))

    morandi_colors = ['#8B9DA3', '#D5C7BC', '#A8A39D', '#C0C5C1', '#D4CFC9', '#B7A99A']
    with c2:
        st.markdown("#### 🍕 佔比圖")
        fig_pie = px.pie(pivot, values='Total 總額', names='Payment 付款方式', hole=0.4, color_discrete_sequence=morandi_colors)
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("#### 📊 長條圖")
    fig_bar = px.bar(pivot, x='Payment 付款方式', y='Total 總額', color='Currency 幣別', barmode='group',
                      color_discrete_sequence=morandi_colors)
    fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# --- Credit card statement reconciliation ---
st.subheader("🧾 信用卡對帳 | Credit Card Statement Reconciliation")
st.caption("依信用卡的結帳日計算「帳單週期」內的消費總額，方便與銀行實際扣款金額核對。")

pm_df = get_payment_methods_df()
credit_cards = pd.DataFrame()
if not pm_df.empty:
    credit_cards = pm_df[pm_df['billing_day'].notna()]

if credit_cards.empty:
    st.info("尚未設定任何有「結帳日」的卡片。請至 🔁 固定支出管理 頁面的「卡片管理」新增或設定。")
else:
    card_names = credit_cards['card_name'].tolist()
    sel_card = st.selectbox("選擇卡片 (Select Card)：", card_names)
    card_row = credit_cards[credit_cards['card_name'] == sel_card].iloc[0]
    statement_day = int(card_row['billing_day'])

    col_y, col_m = st.columns(2)
    with col_y:
        cycle_year = st.number_input("結帳年份 (Year)", min_value=2000, max_value=2100, value=today.year, step=1)
    with col_m:
        cycle_month = st.number_input("結帳月份 (Month)", min_value=1, max_value=12, value=today.month, step=1)

    cycle_start, cycle_end = get_statement_cycle(statement_day, int(cycle_year), int(cycle_month))
    st.caption(f"帳單週期 (Billing Cycle)：{cycle_start} ～ {cycle_end}（結帳日 {statement_day} 號）")

    cycle_df = df[
        (df['payment_method'] == sel_card) &
        (df['transaction_date'] >= cycle_start) &
        (df['transaction_date'] <= cycle_end) &
        (~df['category'].isin(['收入', '轉帳', 'Income', 'Transfer']))
    ].copy()

    if cycle_df.empty:
        st.info("此帳單週期內沒有交易紀錄。")
    else:
        totals_by_currency = cycle_df.groupby('currency')['amount_original'].sum()
        total_strings = " ｜ ".join([f"{amt:,.2f} {curr}" for curr, amt in totals_by_currency.items()])
        st.success(f"💰 應繳總額 (Statement Total)：{total_strings}")

        cycle_display = cycle_df[['transaction_date', 'item_description', 'category', 'amount_original', 'currency']].copy()
        cycle_display.columns = ['Date 日期', 'Item 品項', 'Category 分類', 'Amount 金額', 'Currency 幣別']
        cycle_display['Category 分類'] = cycle_display['Category 分類'].replace(CATEGORY_DISPLAY_MAP)
        cycle_display = cycle_display.sort_values('Date 日期')
        cycle_display['Amount 金額'] = cycle_display['Amount 金額'].apply(lambda x: f"{x:,.2f}")
        st.table(cycle_display.style.pipe(apply_morandi_table_style).hide(axis="index"))
