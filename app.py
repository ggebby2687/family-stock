import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import os
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from datetime import datetime, timedelta

st.set_page_config(page_title="가족 자산 대시보드", page_icon="💰", layout="wide")
st.title("💰 우리 가족 주식 통합 대시보드")
st.write("---")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

if "show_summary" not in st.session_state:
    st.session_state.show_summary = False
if "show_detail" not in st.session_state:
    st.session_state.show_detail = False
if "show_mdd" not in st.session_state:
    st.session_state.show_mdd = False

st.sidebar.markdown("### 🌐 필수 투자 참고 사이트")
st.sidebar.link_button("1. 🏦 금리변동예상 (FedWatch)", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html", use_container_width=True)
st.sidebar.link_button("2. 😱 공포탐욕지수 (CNN)", "https://edition.cnn.com/markets/fear-and-greed", use_container_width=True)
st.sidebar.link_button("3. 🗺️ S&P 500 MAP (Finviz)", "https://finviz.com/map.ashx", use_container_width=True)
st.sidebar.link_button("4. 📰 글로벌 주식 뉴스", "https://finance.naver.com/news/mainnews.naver", use_container_width=True)
st.sidebar.link_button("5. 📈 구글 파이낸스", "https://www.google.com/finance/?hl=ko", use_container_width=True)
st.sidebar.markdown("---")

st.sidebar.header("🤖 AI 멘토 상태")
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("✅ AI 멘토 시스템 연결 완벽!")
    st.sidebar.caption("비밀 금고에서 인증키를 자동으로 불러왔습니다.")
except:
    api_key = ""
    st.sidebar.error("⚠️ 비밀 금고에 키가 없습니다.")
    api_key = st.sidebar.text_input("Gemini API Key (로컬용)", type="password")

@st.cache_data
def load_stock_dict():
    krx = fdr.StockListing('KRX')
    krx_code_col = 'Code' if 'Code' in krx.columns else 'Symbol'
    dict_krx = dict(zip(krx[krx_code_col], krx['Name']))
    try:
        etf = fdr.StockListing('ETF/KR')
        etf_code_col = 'Code' if 'Code' in etf.columns else 'Symbol'
        dict_etf = dict(zip(etf[etf_code_col], etf['Name']))
        dict_krx.update(dict_etf)
    except:
        pass
    return dict_krx

stock_dict = load_stock_dict()

PORTFOLIO_FILE = "my_portfolio.csv"
DEPOSIT_FILE = "my_deposit.csv"
RECURRING_FILE = "my_recurring.csv"

if not os.path.exists(PORTFOLIO_FILE):
    pd.DataFrame(columns=["소유자", "계좌명", "거래종류", "종목코드(6자리)", "거래일자", "거래단가", "수량", "메모"]).to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
if not os.path.exists(DEPOSIT_FILE):
    pd.DataFrame(columns=["소유자", "계좌명", "입금일자", "입금액", "메모"]).to_csv(DEPOSIT_FILE, index=False, encoding='utf-8-sig')
if not os.path.exists(RECURRING_FILE):
    df_rec_init = pd.DataFrame(columns=["소유자", "계좌명", "종목코드(6자리)", "시작일자", "최근적용일자", "매수주기", "1회매수수량", "메모"])
    df_rec_init.loc[0] = ["아내", "연금계좌", "367380", "2026-02-01", "", "매일(영업일)", 1, "연금저축 자동모으기"]
    df_rec_init.to_csv(RECURRING_FILE, index=False, encoding='utf-8-sig')

df_stock = pd.read_csv(PORTFOLIO_FILE, dtype={"종목코드(6자리)": str, "거래일자": str, "메모": str}, encoding='utf-8-sig')
df_dep = pd.read_csv(DEPOSIT_FILE, dtype={"입금일자": str, "메모": str}, encoding='utf-8-sig')
df_rec = pd.read_csv(RECURRING_FILE, dtype={"종목코드(6자리)": str, "시작일자": str, "최근적용일자": str}, encoding='utf-8-sig')

if not df_stock.empty:
    df_stock = df_stock.sort_values(by="거래일자", ascending=False, na_position='last').reset_index(drop=True)
    df_stock['종목명'] = df_stock['종목코드(6자리)'].apply(lambda x: stock_dict.get(str(x).split('.')[0].zfill(6), "알 수 없는 종목"))
    df_stock = df_stock.reindex(columns=["소유자", "계좌명", "거래종류", "종목코드(6자리)", "종목명", "거래일자", "거래단가", "수량", "메모"])
else:
    df_stock = pd.DataFrame(columns=["소유자", "계좌명", "거래종류", "종목코드(6자리)", "종목명", "거래일자", "거래단가", "수량", "메모"])

if not df_dep.empty:
    df_dep = df_dep.sort_values(by="입금일자", ascending=False, na_position='last').reset_index(drop=True)

st.subheader("📝 1. 나의 자산 데이터 입력")
tab1, tab2, tab3 = st.tabs(["🛒 수동 매매 일지", "🏦 계좌 입금 내역", "⏳ 적립식 봇 설정 (자동)"])

with tab1:
    with st.expander("➕ 새로운 주식 매매 기록 추가하기", expanded=True):
        
        # 🌟 [업그레이드] 최근 5개 데이터 추출 마법
        recent_owners = df_stock['소유자'].dropna().drop_duplicates().head(5).tolist() if not df_stock.empty and '소유자' in df_stock.columns else []
        recent_accs = df_stock['계좌명'].dropna().drop_duplicates().head(5).tolist() if not df_stock.empty and '계좌명' in df_stock.columns else []
        recent_codes = df_stock['종목코드(6자리)'].dropna().drop_duplicates().head(5).tolist() if not df_stock.empty and '종목코드(6자리)' in df_stock.columns else []
        
        # 종목코드는 보기 편하게 '코드 (이름)' 형태로 변환
        recent_codes_display = []
        for c in recent_codes:
            code_str = str(c).split('.')[0].zfill(6)
            name = stock_dict.get(code_str, "")
            recent_codes_display.append(f"{code_str} ({name})" if name else code_str)

        with st.form("add_stock_form", clear_on_submit=True):
            st.caption("💡 **팁:** 위쪽 선택창에서 최근 5개 내역을 클릭만으로 쉽게 고르세요! (새로운 정보를 적으려면 [✍️ 새로 작성]을 고르고 아래 빈칸에 적으세요)")
            c1, c2, c3, c4 = st.columns(4)
            
            sel_owner = c1.selectbox("👤 소유자 (최근 5개)", ["✍️ 새로 작성"] + recent_owners)
            new_owner = c1.text_input("새 소유자 입력란", label_visibility="collapsed", placeholder="새로 작성시 여기에 입력")

            sel_acc = c2.selectbox("🏦 계좌명 (최근 5개)", ["✍️ 새로 작성"] + recent_accs)
            new_acc = c2.text_input("새 계좌명 입력란", label_visibility="collapsed", placeholder="새로 작성시 여기에 입력")

            new_type = c3.selectbox("🔄 거래종류", ["매수", "매도"])
            
            sel_code = c4.selectbox("📌 종목코드 (최근 5개)", ["✍️ 새로 작성"] + recent_codes_display)
            new_code = c4.text_input("새 종목코드 입력란", label_visibility="collapsed", placeholder="새로 작성시 6자리 입력")

            c5, c6, c7, c8 = st.columns(4)
            new_date = c5.date_input("📅 거래일자", value=datetime.today())
            new_price = c6.number_input("💵 거래단가 (원)", min_value=0, step=100)
            new_qty = c7.number_input("📦 수량 (주)", min_value=0.0, step=1.0)
            new_memo = c8.text_input("📝 메모 (선택)")

            submitted = st.form_submit_button("💾 이 기록 추가하기", use_container_width=True)
            if submitted:
                # 선택창과 직접입력창 값을 부드럽게 연결해주는 로직
                final_owner = new_owner.strip() if sel_owner == "✍️ 새로 작성" else sel_owner
                final_acc = new_acc.strip() if sel_acc == "✍️ 새로 작성" else sel_acc
                final_code = new_code.strip() if sel_code == "✍️ 새로 작성" else sel_code.split(" ")[0]

                if final_owner and final_acc and final_code and new_qty > 0:
                    new_row = pd.DataFrame([{"소유자": final_owner, "계좌명": final_acc, "거래종류": new_type, "종목코드(6자리)": final_code, "거래일자": new_date.strftime("%Y-%m-%d"), "거래단가": new_price, "수량": new_qty, "메모": new_memo}])
                    df_to_save = df_stock.drop(columns=['종목명'], errors='ignore')
                    df_stock_updated = pd.concat([new_row, df_to_save], ignore_index=True)
                    df_stock_updated.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
                    st.success("✅ 매매 기록이 성공적으로 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("⚠️ 소유자, 계좌명, 종목코드, 수량을 정확히 입력해주세요.")
    
    st.markdown("#### 📋 기존 매매 기록 수정 및 확인")
    edited_stock = st.data_editor(df_stock, num_rows="dynamic", use_container_width=True, height=200, key="stock", column_config={"거래종류": st.column_config.SelectboxColumn("매수/매도", options=["매수", "매도"], required=True), "종목명": st.column_config.TextColumn("종목명 (자동표시)", disabled=True)})

with tab2:
    with st.expander("➕ 새로운 입금 기록 추가하기", expanded=True):
        
        # 입금 기록에도 똑같이 최근 5개 불러오기 적용
        recent_dep_owners = df_dep['소유자'].dropna().drop_duplicates().head(5).tolist() if not df_dep.empty and '소유자' in df_dep.columns else []
        recent_dep_accs = df_dep['계좌명'].dropna().drop_duplicates().head(5).tolist() if not df_dep.empty and '계좌명' in df_dep.columns else []
        
        with st.form("add_dep_form", clear_on_submit=True):
            st.caption("💡 **팁:** 위쪽 선택창에서 최근 5개 내역을 클릭만으로 쉽게 고르세요!")
            c1, c2, c3 = st.columns(3)
            
            sel_dep_owner = c1.selectbox("👤 소유자 (최근 5개)", ["✍️ 새로 작성"] + recent_dep_owners)
            new_dep_owner = c1.text_input("새 소유자 입력란", label_visibility="collapsed", placeholder="새로 작성시 여기에 입력")

            sel_dep_acc = c2.selectbox("🏦 계좌명 (최근 5개)", ["✍️ 새로 작성"] + recent_dep_accs)
            new_dep_acc = c2.text_input("새 계좌명 입력란", label_visibility="collapsed", placeholder="새로 작성시 여기에 입력")

            new_dep_date = c3.date_input("📅 입금일자", value=datetime.today())

            c4, c5 = st.columns([1, 2])
            new_dep_amt = c4.number_input("💵 입금액 (원)", min_value=0, step=10000)
            new_dep_memo = c5.text_input("📝 메모 (선택)")

            submitted_dep = st.form_submit_button("💾 이 기록 추가하기", use_container_width=True)
            if submitted_dep:
                final_dep_owner = new_dep_owner.strip() if sel_dep_owner == "✍️ 새로 작성" else sel_dep_owner
                final_dep_acc = new_dep_acc.strip() if sel_dep_acc == "✍️ 새로 작성" else sel_dep_acc
                
                if final_dep_owner and final_dep_acc and new_dep_amt > 0:
                    new_row_dep = pd.DataFrame([{"소유자": final_dep_owner, "계좌명": final_dep_acc, "입금일자": new_dep_date.strftime("%Y-%m-%d"), "입금액": new_dep_amt, "메모": new_dep_memo}])
                    df_dep_updated = pd.concat([new_row_dep, df_dep], ignore_index=True)
                    df_dep_updated.to_csv(DEPOSIT_FILE, index=False, encoding='utf-8-sig')
                    st.success("✅ 입금 기록이 성공적으로 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("⚠️ 소유자, 계좌명, 입금액을 정확히 입력해주세요.")
                    
    st.markdown("#### 📋 기존 입금 내역 수정 및 확인")
    edited_dep = st.data_editor(df_dep, num_rows="dynamic", use_container_width=True, height=200, key="deposit")

with tab3:
    edited_rec = st.data_editor(df_rec, num_rows="dynamic", use_container_width=True, height=150, key="recurring", column_config={"매수주기": st.column_config.SelectboxColumn("매수주기", options=["매일(영업일)"], required=True)})
    if st.button("🚀 적립식 자동 매수 실행! (빈 날짜 영수증 싹 채우기)", use_container_width=True):
        edited_rec.to_csv(RECURRING_FILE, index=False, encoding='utf-8-sig')
        new_orders = []
        today_str = datetime.today().strftime('%Y-%m-%d')
        with st.spinner("봇이 과거 주식 시장 데이터를 뒤져 영수증을 찍어내고 있습니다..."):
            for idx, row in edited_rec.iterrows():
                if pd.isna(row["종목코드(6자리)"]) or pd.isna(row["시작일자"]): continue
                code = str(row["종목코드(6자리)"]).split('.')[0].zfill(6)
                start_dt = str(row["최근적용일자"]) if pd.notna(row["최근적용일자"]) and str(row["최근적용일자"]).strip() != "" else str(row["시작일자"])
                qty = float(row["1회매수수량"]) if pd.notna(row["1회매수수량"]) else 1
                if start_dt >= today_str: continue
                try:
                    price_df = fdr.DataReader(code, start_dt, today_str)
                    for date, price_row in price_df.iterrows():
                        date_str = date.strftime('%Y-%m-%d')
                        if date_str > start_dt: 
                            new_orders.append({"소유자": row["소유자"], "계좌명": row["계좌명"], "거래종류": "매수", "종목코드(6자리)": code, "거래일자": date_str, "거래단가": int(price_row['Close']), "수량": qty, "메모": row.get("메모", "자동적립 봇")})
                    edited_rec.at[idx, "최근적용일자"] = today_str
                except:
                    pass
        if new_orders:
            df_to_save = df_stock.drop(columns=['종목명'], errors='ignore')
            df_stock_updated = pd.concat([df_to_save, pd.DataFrame(new_orders)], ignore_index=True)
            df_stock_updated.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
            edited_rec.to_csv(RECURRING_FILE, index=False, encoding='utf-8-sig')
            st.success(f"🎉 성공! 총 {len(new_orders)}일 치의 자동 매수 영수증이 발급되었습니다!")
            st.rerun()
        else:
            st.info("✅ 이미 오늘까지의 적립식 매수가 모두 완료되어 최신 상태입니다.")

if st.button("💾 표에서 직접 수정한 데이터 저장 및 새로고침", use_container_width=True):
    edited_stock.drop(columns=['종목명'], errors='ignore').to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
    edited_dep.to_csv(DEPOSIT_FILE, index=False, encoding='utf-8-sig')
    st.success("✅ 표 수정 내역 저장 완료!")
    st.rerun()

st.write("---")
st.subheader("📊 2. 사람별/계좌별 전체 자산 요약")
all_owners = df_stock["소유자"].dropna().unique().tolist() if not df_stock.empty else []
all_accs = df_stock["계좌명"].dropna().unique().tolist() if not df_stock.empty else []

with st.form("summary_form"):
    st.info("💡 분석을 원하는 사람과 계좌를 선택한 후 **[📊 조회하기]** 버튼을 눌러야 화면이 나타납니다.")
    col_top1, col_top2 = st.columns(2)
    selected_owners = col_top1.multiselect("👤 사람 선택", all_owners, default=[])
    selected_accs = col_top2.multiselect("🏦 계좌 선택", all_accs, default=[])
    summary_submit = st.form_submit_button("📊 조회하기 (자산 요약 계산)", use_container_width=True)

if summary_submit:
    if not selected_owners or not selected_accs:
        st.warning("⚠️ 사람과 계좌를 각각 1개 이상 선택해주세요.")
        st.session_state.show_summary = False
    else:
        st.session_state.summary_owners = selected_owners
        st.session_state.summary_accs = selected_accs
        st.session_state.show_summary = True
        
        fs_raw = edited_stock[(edited_stock["소유자"].isin(selected_owners)) & (edited_stock["계좌명"].isin(selected_accs))]
        avail_codes = fs_raw['종목코드(6자리)'].unique().tolist()
        avail_names = [stock_dict.get(str(c).split('.')[0].zfill(6), f"알 수 없는 종목({c})") for c in avail_codes]
        st.session_state.graph_stocks = avail_names

if st.session_state.show_summary:
    with st.spinner("자산을 계산하고 주가를 불러오는 중입니다..."):
        fs_stock = edited_stock[(edited_stock["소유자"].isin(st.session_state.summary_owners)) & (edited_stock["계좌명"].isin(st.session_state.summary_accs))].copy()
        fs_dep = edited_dep[(edited_dep["소유자"].isin(st.session_state.summary_owners)) & (edited_dep["계좌명"].isin(st.session_state.summary_accs))].copy()

        fs_dep["입금액"] = pd.to_numeric(fs_dep["입금액"], errors='coerce').fillna(0)
        dep_summary = fs_dep.groupby(["소유자", "계좌명"])["입금액"].sum().reset_index()
        dep_summary.rename(columns={"입금액": "총입금액"}, inplace=True)

        fs_stock["거래단가"] = pd.to_numeric(fs_stock["거래단가"], errors='coerce').fillna(0)
        fs_stock["수량"] = pd.to_numeric(fs_stock["수량"], errors='coerce').fillna(0)
        fs_stock["현금흐름"] = fs_stock.apply(lambda x: -1 * x["거래단가"] * x["수량"] if x["거래종류"] == "매수" else x["거래단가"] * x["수량"], axis=1)
        
        buys = fs_stock[fs_stock["거래종류"] == "매수"].groupby(["소유자", "계좌명", "종목코드(6자리)"]).agg(총매수수량=("수량", "sum"), 총매수쓴돈=("현금흐름", lambda x: -x.sum())).reset_index()
        buys["평균매수단가"] = (buys["총매수쓴돈"] / buys["총매수수량"]).fillna(0)

        sells = fs_stock[fs_stock["거래종류"] == "매도"].groupby(["소유자", "계좌명", "종목코드(6자리)"]).agg(총매도수량=("수량", "sum")).reset_index()
        stock_merged = pd.merge(buys, sells, on=["소유자", "계좌명", "종목코드(6자리)"], how="left").fillna(0)
        stock_merged["잔여수량"] = stock_merged["총매수수량"] - stock_merged["총매도수량"]
        stock_merged = stock_merged[stock_merged["잔여수량"] > 0]
        stock_merged["주식투자원금"] = stock_merged["잔여수량"] * stock_merged["평균매수단가"]

        current_prices = {}
        for code in fs_stock["종목코드(6자리)"].dropna().unique():
            clean_code = str(code).split('.')[0].zfill(6)
            try:
                current_prices[clean_code] = int(fdr.DataReader(clean_code).iloc[-1]['Close'])
            except:
                current_prices[clean_code] = 0

        stock_eval_list = []
        for index, row in stock_merged.iterrows():
            clean_code = str(row["종목코드(6자리)"]).split('.')[0].zfill(6)
            stock_eval_list.append(current_prices.get(clean_code, 0) * row["잔여수량"])
        
        stock_merged["현재평가금액"] = stock_eval_list
        stock_summary = stock_merged.groupby(["소유자", "계좌명"]).agg(주식투자원금=("주식투자원금", "sum"), 주식평가금액=("현재평가금액", "sum")).reset_index()
        stock_cash_flow = fs_stock.groupby(["소유자", "계좌명"])["현금흐름"].sum().reset_index()

        account_summary = pd.merge(dep_summary, stock_cash_flow, on=["소유자", "계좌명"], how="outer").fillna(0)
        account_summary = pd.merge(account_summary, stock_summary, on=["소유자", "계좌명"], how="outer").fillna(0)
        
        account_summary["남은예수금"] = account_summary["총입금액"] + account_summary["현금흐름"]
        account_summary["계좌총자산"] = account_summary["남은예수금"] + account_summary["주식평가금액"]
        
        pie_acc_options = ["전체 합산"]
        if not account_summary.empty:
            for _, row in account_summary[['소유자', '계좌명']].drop_duplicates().iterrows():
                pie_acc_options.append(f"{row['소유자']} - {row['계좌명']}")
        
        st.write("")
        selected_pie_acc = st.selectbox("📊 아래 요약 전광판에서 보고 싶은 계좌를 고르세요", pie_acc_options)
        
        if selected_pie_acc == "전체 합산":
            pie_summary = account_summary
            pie_stock = stock_merged
        else:
            p_owner, p_acc = selected_pie_acc.split(" - ")
            pie_summary = account_summary[(account_summary["소유자"] == p_owner) & (account_summary["계좌명"] == p_acc)]
            pie_stock = stock_merged[(stock_merged["소유자"] == p_owner) & (stock_merged["계좌명"] == p_acc)]

        pie_total_asset = pie_summary["계좌총자산"].sum()
        pie_total_cash = pie_summary["남은예수금"].sum()
        pie_total_stock = pie_summary["주식평가금액"].sum()

        stock_pie_data = []
        for index, row in pie_stock.iterrows():
            clean_code = str(row["종목코드(6자리)"]).split('.')[0].zfill(6)
            name = stock_dict.get(clean_code, f"알 수 없는 종목({clean_code})")
            if row["현재평가금액"] > 0:
                stock_pie_data.append({"종목명": name, "평가금액": row["현재평가금액"]})
                
        df_stock_pie = pd.DataFrame(stock_pie_data)
        if not df_stock_pie.empty:
            df_stock_pie = df_stock_pie.groupby("종목명")["평가금액"].sum().reset_index()

        col3, col4, col5 = st.columns([1, 1.2, 1.2])
        
        with col3:
            st.markdown(f"### 💰 {selected_pie_acc} 요약")
            st.metric(label="총 자산", value=f"{int(pie_total_asset):,}원")
            st.metric(label="📈 주식 평가액", value=f"{int(pie_total_stock):,}원")
            st.metric(label="💵 대기 예수금", value=f"{int(pie_total_cash):,}원")
            
        with col4:
            chart_data_1 = pd.DataFrame({"자산 종류": ["투자된 주식", "대기 중인 현금"], "금액": [pie_total_stock, pie_total_cash]})
            fig1 = px.pie(chart_data_1, values='금액', names='자산 종류', hole=0.4, title="주식 vs 현금 비중", color='자산 종류', color_discrete_map={"투자된 주식":"#ef553b", "대기 중인 현금":"#00cc96"})
            fig1.update_traces(textinfo='percent+label', textposition='inside')
            fig1.update_layout(margin=dict(t=30, b=0, l=0, r=0), showlegend=False)
            st.plotly_chart(fig1, use_container_width=True)
            
        with col5:
            if not df_stock_pie.empty:
                fig2 = px.pie(df_stock_pie, values='평가금액', names='종목명', hole=0.4, title="포트폴리오 비중 (종목별)")
                fig2.update_traces(textinfo='percent+label', textposition='inside')
                fig2.update_layout(margin=dict(t=30, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("현재 보유 중인 주식이 없습니다.")

        st.write("---")
        st.markdown("### 📈 기간별 적립식 투자 성과 추이 (VIP 리포트 양식)")
        
        with st.form("graph_form"):
            col_g1, col_g2 = st.columns([2, 1])
            selected_graph_names = col_g1.multiselect("📊 차트에 표시할 종목 선택", st.session_state.graph_stocks, default=st.session_state.graph_stocks)
            time_res = col_g2.radio("⏱️ 조회 단위", ["일별 (매일의 흐름)", "월별 (월말 기준 요약)"], horizontal=True)
            graph_btn = st.form_submit_button("📈 그래프 업데이트")
            
        name_to_code = {v: k for k, v in stock_dict.items()}
        selected_graph_codes = [name_to_code.get(n) for n in selected_graph_names if name_to_code.get(n)]
        fs_graph = fs_stock[fs_stock['종목코드(6자리)'].isin(selected_graph_codes)].copy()
        
        if not fs_graph.empty:
            fs_graph['거래일자'] = pd.to_datetime(fs_graph['거래일자'])
            fs_graph = fs_graph.sort_values('거래일자')
            
            start_dt = fs_graph['거래일자'].min()
            today = pd.to_datetime('today')
            date_idx = pd.date_range(start_dt, today, freq='D')
            
            daily_invest = pd.Series(0.0, index=date_idx)
            daily_eval = pd.Series(0.0, index=date_idx)
            
            tickers = fs_graph['종목코드(6자리)'].unique()
            for ticker in tickers:
                t_fs = fs_graph[fs_graph['종목코드(6자리)'] == ticker].copy()
                t_fs['투자금액'] = t_fs.apply(lambda x: x['거래단가']*x['수량'] if x['거래종류']=='매수' else -x['거래단가']*x['수량'], axis=1)
                t_fs['수량변화'] = t_fs.apply(lambda x: x['수량'] if x['거래종류']=='매수' else -x['수량'], axis=1)
                
                daily_changes = t_fs.groupby('거래일자').agg({'투자금액':'sum', '수량변화':'sum'})
                daily_changes = daily_changes.reindex(date_idx, fill_value=0)
                
                cum_invest = daily_changes['투자금액'].cumsum()
                cum_qty = daily_changes['수량변화'].cumsum()
                daily_invest += cum_invest
                
                clean_code = str(ticker).split('.')[0].zfill(6)
                try:
                    p_df = fdr.DataReader(clean_code, start_dt, today)
                    p_series = p_df['Close'].reindex(date_idx).ffill().fillna(0) 
                except:
                    p_series = pd.Series(0, index=date_idx)
                
                daily_eval += (cum_qty * p_series)
            
            daily_profit = daily_eval - daily_invest
            
            if "월별" in time_res:
                try:
                    plot_invest = daily_invest.resample('ME').last()
                    plot_eval = daily_eval.resample('ME').last()
                    plot_profit = daily_profit.resample('ME').last()
                except:
                    plot_invest = daily_invest.resample('M').last()
                    plot_eval = daily_eval.resample('M').last()
                    plot_profit = daily_profit.resample('M').last()
                
                x_index = plot_invest.index
                x_tick_format = "%Y년 %m월"
                hover_fmt = "%Y년 %m월"
            else:
                plot_invest = daily_invest
                plot_eval = daily_eval
                plot_profit = daily_profit
                x_index = date_idx
                x_tick_format = "%m월 %d일" 
                hover_fmt = "%Y년 %m월 %d일"
            
            min_y = min(plot_invest.min(), plot_eval.min())
            max_y = max(plot_invest.max(), plot_eval.max())
            y_range = [min_y * 0.98, max_y * 1.02] 

            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=x_index, y=plot_eval, mode='lines+markers', name='평가금액', fill='tozeroy', line=dict(color='#00cc96', width=3), marker=dict(size=6), fillcolor='rgba(0, 204, 150, 0.2)'))
            fig_line.add_trace(go.Scatter(x=x_index, y=plot_invest, mode='lines+markers', name='누적투자', line=dict(color='#ef553b', width=3), marker=dict(size=6)))
            fig_line.add_trace(go.Scatter(x=x_index, y=plot_profit, mode='lines+markers', name='누적손익', line=dict(color='#1f77b4', width=2), marker=dict(size=6)))
            
            fig_line.update_layout(
                hovermode="x unified", margin=dict(t=30, b=0, l=0, r=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(title="", tickformat=x_tick_format, hoverformat=hover_fmt, showgrid=True),
                yaxis=dict(title="", range=y_range, tickformat=",", ticksuffix="원", showgrid=True)
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("선택하신 종목에 해당하는 거래 내역이 없습니다.")


st.write("---")
st.subheader("🔍 3. 내 입맛대로 골라보기 (종목/날짜 맞춤 필터)")
all_stocks_names = df_stock["종목명"].dropna().unique().tolist() if not df_stock.empty else []

with st.form("detail_form"):
    st.info("💡 원하는 종목과 날짜를 선택한 후 **[🔍 상세 내역 조회하기]** 버튼을 눌러주세요.")
    col_f1, col_f2 = st.columns(2)
    selected_stocks_table = col_f1.multiselect("📈 표에 표시할 종목 선택", all_stocks_names, default=[])
    date_filter = col_f2.date_input("📅 영수증 날짜별 조회 (시작일 - 종료일)", value=[])
    detail_submit = st.form_submit_button("🔍 상세 내역 조회하기", use_container_width=True)

if detail_submit:
    if not selected_stocks_table:
        st.warning("⚠️ 종목을 1개 이상 선택해주세요.")
        st.session_state.show_detail = False
    else:
        st.session_state.detail_stocks = selected_stocks_table
        st.session_state.detail_dates = date_filter
        st.session_state.show_detail = True

if st.session_state.get("show_detail"):
    with st.spinner("선택된 종목의 상세 수익률을 계산 중입니다..."):
        fs_detail = edited_stock[edited_stock["종목명"].isin(st.session_state.detail_stocks)].copy()
        
        fs_detail["거래단가"] = pd.to_numeric(fs_detail["거래단가"], errors='coerce').fillna(0)
        fs_detail["수량"] = pd.to_numeric(fs_detail["수량"], errors='coerce').fillna(0)
        fs_detail["현금흐름"] = fs_detail.apply(lambda x: -1 * x["거래단가"] * x["수량"] if x["거래종류"] == "매수" else x["거래단가"] * x["수량"], axis=1)
        
        detail_buys = fs_detail[fs_detail["거래종류"] == "매수"].groupby(["소유자", "계좌명", "종목코드(6자리)", "종목명"]).agg(총매수수량=("수량", "sum"), 총매수쓴돈=("현금흐름", lambda x: -x.sum())).reset_index()
        detail_buys["평균매수단가"] = (detail_buys["총매수쓴돈"] / detail_buys["총매수수량"]).fillna(0)
        detail_sells = fs_detail[fs_detail["거래종류"] == "매도"].groupby(["소유자", "계좌명", "종목코드(6자리)", "종목명"]).agg(총매도수량=("수량", "sum")).reset_index()
        
        detail_merged = pd.merge(detail_buys, detail_sells, on=["소유자", "계좌명", "종목코드(6자리)", "종목명"], how="left").fillna(0)
        detail_merged["잔여수량"] = detail_merged["총매수수량"] - detail_merged["총매도수량"]
        detail_merged = detail_merged[detail_merged["잔여수량"] > 0]
        
        detailed_data = []
        for index, row in detail_merged.iterrows():
            code = str(row["종목코드(6자리)"]).split('.')[0].zfill(6)
            try:
                curr_price = int(fdr.DataReader(code).iloc[-1]['Close'])
            except:
                curr_price = 0
            avg_price = float(row["평균매수단가"])
            qty = float(row["잔여수량"])
            return_rate = ((curr_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
            
            buy_dates = fs_detail[(fs_detail["종목코드(6자리)"] == row["종목코드(6자리)"]) & (fs_detail["거래종류"] == "매수")]["거래일자"].tolist()
            recent_buy_date = buy_dates[0] if buy_dates else "알수없음"

            detailed_data.append({"소유자": row["소유자"], "계좌명": row["계좌명"], "최근매수일": recent_buy_date, "종목명": row["종목명"], "평균매수단가": f"{int(avg_price):,}원", "현재가": f"{curr_price:,}원", "수익률": f"{return_rate:.2f}%", "보유수량": f"{int(qty)}주", "평가금액": f"{int(curr_price * qty):,}원"})
        
        df_detailed = pd.DataFrame(detailed_data)
        
        def color_returns(val):
            if isinstance(val, str) and '%' in val:
                try:
                    num = float(val.replace('%', ''))
                    if num > 0:
                        return 'color: #ff4b4b; font-weight: bold;'
                    elif num < 0:
                        return 'color: #1f77b4; font-weight: bold;'
                except:
                    pass
            return ''
        
        st.markdown("#### 📋 필터링된 보유 종목 상세")
        if not df_detailed.empty:
            try:
                styled_df = df_detailed.style.map(color_returns, subset=['수익률'])
            except AttributeError:
                styled_df = df_detailed.style.applymap(color_returns, subset=['수익률'])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("조건에 맞는 잔여 주식이 없습니다.")
        
        st.markdown("#### 📅 선택된 기간의 매매 영수증")
        filtered_history = fs_detail.copy()
        if len(st.session_state.detail_dates) == 2:
            start_date, end_date = st.session_state.detail_dates
            mask = (filtered_history['거래일자'] >= str(start_date)) & (filtered_history['거래일자'] <= str(end_date))
            filtered_history = filtered_history[mask]
            
        if not filtered_history.empty:
            st.dataframe(filtered_history, use_container_width=True, hide_index=True)
        else:
            st.info("해당 조건의 거래 내역이 없습니다.")


st.write("---")
st.subheader("🎯 4. 관심 종목 바겐세일(낙폭) 스캐너")
st.info("💡 종목을 고르고 **[🎯 스캔 시작]**을 눌러야만 최근 1개월 시장 고점 대비 하락률을 계산합니다.")

default_target_codes = ["367380", "360200", "460330"]
all_krx_names = list(stock_dict.values())
default_target_names = [stock_dict.get(c, c) for c in default_target_codes if c in stock_dict]

with st.form("mdd_form"):
    selected_watch_names = st.multiselect("🔍 감시할 관심 종목을 추가/삭제하세요", all_krx_names, default=default_target_names)
    mdd_submit = st.form_submit_button("🎯 바겐세일 스캔 시작", use_container_width=True)
    
if mdd_submit:
    if not selected_watch_names:
        st.warning("⚠️ 감시할 종목을 1개 이상 선택해주세요.")
        st.session_state.show_mdd = False
    else:
        st.session_state.mdd_stocks = selected_watch_names
        st.session_state.show_mdd = True
        
if st.session_state.get("show_mdd"):
    watch_results = []
    name_to_code = {v: k for k, v in stock_dict.items()}
    
    with st.spinner("AI가 최근 1개월 시장 최고점을 추적하여 현재 하락폭(MDD)을 계산 중입니다..."):
        for name in st.session_state.mdd_stocks:
            code = name_to_code.get(name)
            if code:
                end_d = datetime.today()
                start_d = end_d - timedelta(days=30)
                try:
                    df_hist = fdr.DataReader(code, start_d.strftime('%Y-%m-%d'), end_d.strftime('%Y-%m-%d'))
                    if not df_hist.empty:
                        high_price = int(df_hist['High'].max())
                        curr_price = int(df_hist['Close'].iloc[-1])
                        drop_rate = ((curr_price - high_price) / high_price) * 100
                        
                        signal = "관망 😐"
                        if drop_rate <= -10:
                            signal = "🚨 강력 매수 (3배 레버리지 투입!)"
                        elif drop_rate <= -5:
                            signal = "🟡 분할 매수 (2배 레버리지 투입)"
                        elif drop_rate >= 0:
                            signal = "고점 돌파 🚀"
                            
                        watch_results.append({
                            "종목명": name,
                            "최근 1달 고점": f"{high_price:,}원",
                            "현재가": f"{curr_price:,}원",
                            "고점 대비 하락률": drop_rate,
                            "포메뽀꼬 시그널": signal
                        })
                except:
                    pass
                    
    if watch_results:
        df_watch = pd.DataFrame(watch_results)
        def style_mdd(val):
            if isinstance(val, float):
                if val <= -10:
                    return "color: #ff4b4b; font-weight: bold;"
                elif val <= -5:
                    return "color: #ff9900; font-weight: bold;"
                elif val >= 0:
                    return "color: #1f77b4;"
            return ""
        
        df_watch_styled = df_watch.style.format({"고점 대비 하락률": "{:.2f}%"}).applymap(style_mdd, subset=['고점 대비 하락률'])
        st.dataframe(df_watch_styled, use_container_width=True, hide_index=True)


st.write("---")
st.subheader("💬 5. AI 멘토와 실시간 대화하기 (포메뽀꼬 모드)")
st.info("💡 위에서 즐겨찾기 한 글로벌 시황 사이트들을 볼 시간이 없다면, 아래의 [시황 브리핑] 버튼을 눌러 AI에게 대신 요약을 부탁해보세요!")

if not api_key:
    st.warning("⚠️ 비밀 금고에서 인증키를 찾을 수 없습니다. 설정을 확인해 주세요.")
else:
    col_chat1, col_chat2 = st.columns([3, 1])
    msg_to_send = None
    
    if col_chat1.button("🌍 AI 멘토에게 '오늘 글로벌 시장 흐름 종합 브리핑' 받기", use_container_width=True):
        msg_to_send = "최근의 미국 기준금리 변동 예상(FedWatch), 시장의 공포/탐욕 지수 상태, S&P 500 전반적인 흐름, 주요 경제 뉴스를 기반으로 현재 거시 경제 시황을 분석하고, 포메뽀꼬의 장기 투자 관점에서 내가 가져야 할 멘탈을 3줄로 요약해줘."

    if col_chat2.button("🔄 대화 내용 지우기", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_session = None
        st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("예: 나 당분간 돈 없어서 SCHD는 못 사는데, 상계 처리할 종목 딱 하나만 짚어줘.")
    if user_input:
        msg_to_send = user_input

    if msg_to_send:
        st.session_state.messages.append({"role": "user", "content": msg_to_send})
        with st.chat_message("user"):
            st.markdown(msg_to_send)

        with st.chat_message("assistant"):
            with st.spinner("AI 멘토가 데이터를 분석하며 답변을 작성 중입니다..."):
                try:
                    genai.configure(api_key=api_key)
                    portfolio_str = df_detailed.to_string() if 'df_detailed' in locals() else "상세 조회 내역 없음"
                    cash_str = account_summary[["소유자", "계좌명", "남은예수금", "계좌수익률(%)"]].to_string() if 'account_summary' in locals() else "계좌 요약 내역 없음"
                    
                    sys_instruct = f"""
                    당신은 '단 3개의 미국 ETF로 은퇴하라'의 저자 '포메뽀꼬(김지훈)'의 철학을 탑재한 나의 개인 자산관리 비서입니다.
                    
                    [나의 최신 계좌 데이터 (현재 조회된 데이터 기준)]
                    * 보유 주식: \n{portfolio_str}
                    * 남은 예수금: \n{cash_str}
                    
                    [답변 원칙]
                    1. 사용자가 시황 브리핑을 요구하면, 당신이 가지고 있는 최신 경제 지식(금리, 공포탐욕지수, S&P500 트렌드, 뉴스)을 바탕으로 냉철하게 시황을 분석하고 투자 멘탈을 잡아주세요.
                    2. 사용자가 내 계좌에 대해 질문하면, 두루뭉술하게 대답하지 말고 위 데이터를 보고 구체적인 수치와 종목명을 콕 집어주세요.
                    3. 포메뽀꼬의 철학(감정 배제, 3대 ETF 분산, 레버리지 상계 처리 등)을 근거로 설명하세요.
                    """
                    
                    model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=sys_instruct)
                    
                    if st.session_state.chat_session is None:
                        st.session_state.chat_session = model.start_chat(history=[])
                        
                    response = st.session_state.chat_session.send_message(msg_to_send)
                    st.markdown(response.text)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    
                except Exception as e:
                    st.error(f"AI 호출 중 오류가 발생했습니다. (에러: {e})")