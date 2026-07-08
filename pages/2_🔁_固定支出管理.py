import streamlit as st
import pandas as pd
import datetime
from app_common import (
    ensure_tables, apply_morandi_table_style, get_payment_method_names,
    get_payment_methods_df, get_fixed_expenses_df, add_fixed_expense,
    update_fixed_expense, delete_fixed_expense, get_generated_year_months,
    add_payment_method, update_payment_method, delete_payment_method,
    is_payment_method_in_use, auto_generate_fixed_expenses, CATEGORY_OPTIONS,
    CATEGORY_DISPLAY_MAP,
)

st.set_page_config(page_title="固定支出管理", page_icon="🔁", layout="wide")
st.title("🔁 Fixed Expenses & Cards | 固定支出與卡片管理")
st.markdown("---")

ensure_tables()

curr_options = ['EUR', 'CAD', 'TWD', 'USD', 'JPY']
today = datetime.date.today()
year_month = today.strftime('%Y-%m')

tab_overview, tab_manage, tab_cards = st.tabs(["📋 本月固定支出", "➕ 新增/編輯/刪除", "💳 卡片管理"])

# =====================================================================
# Tab 1: Overview
# =====================================================================
with tab_overview:
    st.caption("這裡列出所有固定支出，以及本月是否已產生對應的帳務紀錄。")

    if st.button("🔄 立即檢查並產生本月固定支出"):
        generated = auto_generate_fixed_expenses()
        st.cache_data.clear()
        if generated:
            st.success(f"✅ 已產生：{', '.join(generated)}")
        else:
            st.info("目前沒有需要新增的固定支出（可能都已產生，或還沒到付款日，或尚未設定付款日）。")
        st.rerun()

    fe_df = get_fixed_expenses_df()

    if fe_df.empty:
        st.info("尚未設定任何固定支出，請至「新增/編輯/刪除」分頁新增。")
    else:
        rows = []
        for _, r in fe_df.iterrows():
            generated_months = get_generated_year_months(r['id'])
            if pd.isnull(r['charge_day']):
                status = "⚠️ 未設定付款日"
            else:
                status = "✅ 已產生" if year_month in generated_months else "⏳ 尚未產生"
            rows.append({
                "名稱 Item": r['item_description'],
                "金額 Amount": f"{float(r['amount']):,.2f}" if pd.notnull(r['amount']) else "—",
                "幣別 Currency": r['currency'] or "—",
                "分類 Category": CATEGORY_DISPLAY_MAP.get(r['category'], r['category']) if r['category'] else "—",
                "付款方式 Payment": r['payment_method'] or "—",
                "每月幾號 Day": int(r['charge_day']) if pd.notnull(r['charge_day']) else "—",
                "本月狀態 Status": status,
            })
        overview_display = pd.DataFrame(rows)
        st.table(overview_display.style.pipe(apply_morandi_table_style).hide(axis="index"))

        totals = fe_df.dropna(subset=['amount', 'currency']).groupby('currency')['amount'].sum()
        if not totals.empty:
            total_strings = " ｜ ".join([f"{amt:,.2f} {curr}" for curr, amt in totals.items()])
            st.markdown(f"**💰 每月固定支出總計 (Monthly Fixed Total)：{total_strings}**")

# =====================================================================
# Tab 2: Add / Edit / Delete fixed expenses
# =====================================================================
with tab_manage:
    payment_options = get_payment_method_names()
    if not payment_options:
        st.warning("⚠️ 尚未設定任何付款方式，請先至「卡片管理」新增。")
    else:
        sub_add, sub_edit, sub_del = st.tabs(["➕ 新增 (Add)", "✏️ 編輯 (Edit)", "🗑️ 刪除 (Delete)"])

        with sub_add:
            if st.session_state.get("fe_add_success_msg"):
                st.success(st.session_state["fe_add_success_msg"])
                del st.session_state["fe_add_success_msg"]

            with st.form("fixed_expense_add_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                fe_name = col1.text_input("名稱 (Item)", placeholder="例如：電話費、YouTube Premium、Claude、房屋保險...")
                fe_amount = col2.number_input("金額 (Amount)", min_value=0.0, step=1.0)
                fe_cat = col1.selectbox("分類 (Category)", CATEGORY_OPTIONS)
                fe_curr = col2.selectbox("幣別 (Currency)", curr_options)
                fe_pay = col1.selectbox("付款方式 (Payment Method)", payment_options)
                fe_day = col2.number_input("每月付款日 (Payment Day, 1-31)", min_value=1, max_value=31, value=1, step=1)

                submitted = st.form_submit_button("送出新增 (Submit)")
                if submitted:
                    if fe_name.strip() == "":
                        st.warning("⚠️ 請填寫名稱！")
                    elif fe_amount <= 0:
                        st.warning("⚠️ 金額必須大於 0！")
                    else:
                        db_cat = fe_cat.split()[0]
                        if add_fixed_expense(fe_name, fe_amount, fe_curr, db_cat, fe_pay, int(fe_day)):
                            st.session_state["fe_add_success_msg"] = f"✅ 新增成功！【{fe_name}】{fe_amount} {fe_curr} / 每月 {fe_day} 號 via {fe_pay}"
                            st.cache_data.clear()
                            st.rerun()

        fe_df_all = get_fixed_expenses_df()
        if not fe_df_all.empty:
            fe_df_all['label'] = fe_df_all.apply(
                lambda r: f"{r['item_description']} | {r['amount']} {r['currency']} / 每月{r['charge_day']}號 via {r['payment_method']}",
                axis=1
            )
            fe_label_map = dict(zip(fe_df_all['label'], fe_df_all['id']))
            fe_options_list = ["請選擇... (Select)"] + list(fe_label_map.keys())
        else:
            fe_options_list = ["尚無紀錄 (No records)"]
            fe_label_map = {}

        with sub_edit:
            if st.session_state.get("fe_edit_success_msg"):
                st.success(st.session_state["fe_edit_success_msg"])
                del st.session_state["fe_edit_success_msg"]
            if st.session_state.get("fe_need_reset_edit"):
                st.session_state["fe_edit_select"] = fe_options_list[0]
                del st.session_state["fe_need_reset_edit"]

            sel_edit = st.selectbox("選擇要修改的固定支出", fe_options_list, key="fe_edit_select")
            if sel_edit not in ["請選擇... (Select)", "尚無紀錄 (No records)"]:
                target_id = fe_label_map[sel_edit]
                target_row = fe_df_all[fe_df_all['id'] == target_id].iloc[0]

                with st.form("fixed_expense_edit_form"):
                    col1, col2 = st.columns(2)
                    edit_name = col1.text_input("名稱 (Item)", value=target_row['item_description'] or "")
                    edit_amount = col2.number_input("金額 (Amount)", min_value=0.0, value=float(target_row['amount']) if pd.notnull(target_row['amount']) else 0.0, step=1.0)

                    mapped_cat = CATEGORY_DISPLAY_MAP.get(target_row['category'], target_row['category'])
                    default_cat_idx = CATEGORY_OPTIONS.index(mapped_cat) if mapped_cat in CATEGORY_OPTIONS else 0
                    edit_cat = col1.selectbox("分類 (Category)", CATEGORY_OPTIONS, index=default_cat_idx)

                    default_curr_idx = curr_options.index(target_row['currency']) if target_row['currency'] in curr_options else 0
                    edit_curr = col2.selectbox("幣別 (Currency)", curr_options, index=default_curr_idx)

                    default_pay_idx = payment_options.index(target_row['payment_method']) if target_row['payment_method'] in payment_options else 0
                    edit_pay = col1.selectbox("付款方式 (Payment Method)", payment_options, index=default_pay_idx)

                    default_day = int(target_row['charge_day']) if pd.notnull(target_row['charge_day']) else 1
                    edit_day = col2.number_input("每月付款日 (Payment Day, 1-31)", min_value=1, max_value=31, value=default_day, step=1)

                    submitted_edit = st.form_submit_button("儲存修改 (Save Changes)")
                    if submitted_edit:
                        if edit_name.strip() == "":
                            st.warning("⚠️ 請填寫名稱！")
                        else:
                            db_cat = edit_cat.split()[0]
                            if update_fixed_expense(target_id, edit_name, edit_amount, edit_curr, db_cat, edit_pay, int(edit_day)):
                                st.session_state["fe_edit_success_msg"] = f"✅ 修改成功！【{edit_name}】已更新"
                                st.session_state["fe_need_reset_edit"] = True
                                st.cache_data.clear()
                                st.rerun()

        with sub_del:
            if st.session_state.get("fe_del_success_msg"):
                st.success(st.session_state["fe_del_success_msg"])
                del st.session_state["fe_del_success_msg"]
            if st.session_state.get("fe_need_reset_del"):
                st.session_state["fe_delete_select"] = fe_options_list[0]
                del st.session_state["fe_need_reset_del"]

            sel_del = st.selectbox("選擇要刪除的固定支出", fe_options_list, key="fe_delete_select")
            if sel_del not in ["請選擇... (Select)", "尚無紀錄 (No records)"]:
                target_id_del = fe_label_map[sel_del]
                st.error(f"⚠️ 確定要永久刪除嗎？\n\n**{sel_del}**\n\n（過去已產生的帳務紀錄不會被刪除，只會停止未來自動產生。）")
                if st.button("🚨 確認刪除 (Confirm Delete)", type="primary", key="fe_confirm_del_btn"):
                    if delete_fixed_expense(target_id_del):
                        del_name = sel_del.split(" | ")[0]
                        st.session_state["fe_del_success_msg"] = f"✅ 刪除成功！已移除【{del_name}】"
                        st.session_state["fe_need_reset_del"] = True
                        st.cache_data.clear()
                        st.rerun()

# =====================================================================
# Tab 3: Card / payment method management (test.user_cards)
# =====================================================================
with tab_cards:
    if st.session_state.get("pm_success_msg"):
        st.success(st.session_state["pm_success_msg"])
        del st.session_state["pm_success_msg"]

    pm_df = get_payment_methods_df()
    st.markdown("### 📋 目前的付款方式")
    if pm_df.empty:
        st.info("尚無付款方式。")
    else:
        pm_display = pm_df.copy()
        pm_display['billing_day'] = pm_display['billing_day'].apply(lambda x: f"每月 {int(x)} 號" if pd.notnull(x) else "—")
        pm_display['payment_due_day'] = pm_display['payment_due_day'].apply(lambda x: f"每月 {int(x)} 號" if pd.notnull(x) else "—")
        pm_display = pm_display[['card_name', 'billing_day', 'payment_due_day']]
        pm_display.columns = ['名稱 Name', '結帳日 Billing Day', '繳款日 Payment Due Day']
        st.table(pm_display.style.pipe(apply_morandi_table_style).hide(axis="index"))

    st.markdown("### ➕ 新增付款方式 / 卡片")
    st.caption("結帳日、繳款日僅信用卡需要，現金或其他付款方式可留白（填 0 代表不設定）。")
    with st.form("pm_add_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        pm_name = col1.text_input("名稱 (Name)", placeholder="例如：國泰世華信用卡")
        pm_billing_day = col2.number_input("結帳日 (Billing Day)", min_value=0, max_value=31, value=0, step=1)
        pm_due_day = col3.number_input("繳款日 (Payment Due Day)", min_value=0, max_value=31, value=0, step=1)
        submitted_pm = st.form_submit_button("新增 (Add)")
        if submitted_pm:
            existing_names = pm_df['card_name'].tolist() if not pm_df.empty else []
            if pm_name.strip() == "":
                st.warning("⚠️ 請填寫名稱！")
            elif pm_name in existing_names:
                st.warning("⚠️ 此名稱已存在！")
            else:
                billing_val = int(pm_billing_day) if pm_billing_day > 0 else None
                due_val = int(pm_due_day) if pm_due_day > 0 else None
                if add_payment_method(pm_name, billing_val, due_val):
                    st.session_state["pm_success_msg"] = f"✅ 新增成功！已加入付款方式：【{pm_name}】"
                    st.cache_data.clear()
                    st.rerun()

    st.markdown("### ✏️ 編輯 / 🗑️ 刪除付款方式")
    if pm_df.empty:
        st.info("尚無可編輯的付款方式。")
    else:
        pm_options_list = ["請選擇... (Select)"] + pm_df['card_name'].tolist()
        sel_pm = st.selectbox("選擇付款方式", pm_options_list, key="pm_select")

        if sel_pm != "請選擇... (Select)":
            target_pm_row = pm_df[pm_df['card_name'] == sel_pm].iloc[0]

            with st.form("pm_edit_form"):
                st.text_input("名稱 (Name)", value=sel_pm, disabled=True, help="名稱無法修改，因為既有交易紀錄以此名稱關聯付款方式；如需改名請新增一筆並刪除舊的。")
                col1, col2 = st.columns(2)
                default_billing = int(target_pm_row['billing_day']) if pd.notnull(target_pm_row['billing_day']) else 0
                default_due = int(target_pm_row['payment_due_day']) if pd.notnull(target_pm_row['payment_due_day']) else 0
                edit_billing_day = col1.number_input("結帳日 (Billing Day)", min_value=0, max_value=31, value=default_billing, step=1)
                edit_due_day = col2.number_input("繳款日 (Payment Due Day)", min_value=0, max_value=31, value=default_due, step=1)

                submitted_pm_edit = st.form_submit_button("儲存修改 (Save)")
                if submitted_pm_edit:
                    billing_val = int(edit_billing_day) if edit_billing_day > 0 else None
                    due_val = int(edit_due_day) if edit_due_day > 0 else None
                    if update_payment_method(sel_pm, billing_val, due_val):
                        st.session_state["pm_success_msg"] = f"✅ 修改成功！【{sel_pm}】已更新"
                        st.cache_data.clear()
                        st.rerun()

            if st.button(f"🚨 刪除【{sel_pm}】", key="pm_delete_btn"):
                if is_payment_method_in_use(sel_pm):
                    st.error("❌ 此付款方式仍有交易紀錄或固定支出使用中，無法刪除。請先移除相關紀錄，或改為編輯保留。")
                else:
                    if delete_payment_method(sel_pm):
                        st.session_state["pm_success_msg"] = f"✅ 已刪除付款方式：【{sel_pm}】"
                        st.cache_data.clear()
                        st.rerun()
