import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import os
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from datetime import datetime

st.set_page_config(page_title="가족 자산 대시보드", page_icon="💰", layout="wide")
st.title("💰 우리 가족 주식 통합 대시보드")
st.write("---")

# --- 대화 기록 저장을 위한 메모리 초기화 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

st.sidebar.markdown("### 🌐 필수 투자 참고 사이트")
st.sidebar.link_button("1. 🏦 금리변동예상 (FedWatch)", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html", use_container_width=True)
st.sidebar.link_button("2. 😱 공포탐욕지수 (CNN)", "https://edition.cnn.com/markets/fear-and-greed", use_container_width=True)
st.sidebar.link_button("3. 🗺️ S&P 500 MAP (Finviz)", "https://finviz.com/map.ashx", use_container_width=True)
st.sidebar.link_button("4. 📰 글로벌 주식 뉴스", "https://finance.naver.com/news/mainnews.naver", use_container_width=True)
st.sidebar.link_button("5. 📈 구글 파이낸스", "https://www.google.com/finance/?hl=ko", use_container_width=True)
st.sidebar.markdown("---")

# ==============================================================================
# 🌟 API 키 자동 로그인 (Streamlit Secrets 활용)
# ==============================================================================
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

# --- 파일 설정 ---
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
if not df_dep.empty:
    df_dep = df_dep.sort_values(by="입금일자", ascending=False, na_position='last').reset_index(drop=True)

st.subheader("📝 1. 나의 자산 데이터 입력")
tab1, tab2, tab3 = st.tabs(["🛒 수동 매매 일지", "🏦 계좌 입금 내역", "⏳ 적립식 봇 설정 (자동)"])

with tab1:
    with st.expander("➕ 새로운 주식 매매 기록 추가하기", expanded=True):
        with st.form("add_stock_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            new_owner = c1.text_input("👤 소유자 (예: 남편, 아내)")
            new_acc = c2.text_input("🏦 계좌명 (예: ISA, 연금계좌)")
            new_type = c3.selectbox("🔄 거래종류", ["매수", "매도"])
            new_code = c4.text_input("📌 종목코드(6자리)")

            c5, c6, c7, c8 = st.columns(4)
            new_date = c5.date_input("📅 거래일자", value=datetime.today())
            new_price = c6.number_input("💵 거래단가 (원)", min_value=0, step=100)
            new_qty = c7.number_input("📦 수량 (주)", min_value=0.0, step=1.0)
            new_memo = c8.text_input("📝 메모 (선택)")

            submitted = st.form_submit_button("💾 이 기록 추가하기", use_container_width=True)
            if submitted:
                if new_owner and new_acc and new_code and new_qty > 0:
                    new_row = pd.DataFrame([{"소유자": new_owner, "계좌명": new_acc, "거래종류": new_type, "종목코드(6자리)": new_code, "거래일자": new_date.strftime("%Y-%m-%d"), "거래단가": new_price, "수량": new_qty, "메모": new_memo}])
                    df_stock_updated = pd.concat([new_row, df_stock], ignore_index=True)
                    df_stock_updated.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
                    st.success("✅ 매매 기록이 성공적으로 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("⚠️ 소유자, 계좌명, 종목코드, 수량을 정확히 입력해주세요.")
    
    st.markdown("#### 📋 기존 매매 기록 수정 및 확인")
    edited_stock = st.data_editor(df_stock, num_rows="dynamic", use_container_width=True, height=200, key="stock", column_config={"거래종류": st.column_config.SelectboxColumn("매수/매도", options=["매수", "매도"], required=True)})

with tab2:
    with st.expander("➕ 새로운 입금 기록 추가하기", expanded=True):
        with st.form("add_dep_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            new_dep_owner = c1.text_input("👤 소유자")
            new_dep_acc = c2.text_input("🏦 계좌명")
            new_dep_date = c3.date_input("📅 입금일자", value=datetime.today())

            c4, c5 = st.columns([1, 2])
            new_dep_amt = c4.number_input("💵 입금액 (원)", min_value=0, step=10000)
            new_dep_memo = c5.text_input("📝 메모 (선택)")

            submitted_dep = st.form_submit_button("💾 이 기록 추가하기", use_container_width=True)
            if submitted_dep:
                if new_dep_owner and new_dep_acc and new_dep_amt > 0:
                    new_row_dep = pd.DataFrame([{"소유자": new_dep_owner, "계좌명": new_dep_acc, "입금일자": new_dep_date.strftime("%Y-%m-%d"), "입금액": new_dep_amt, "메모": new_dep_memo}])
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
    # 🌟 [오타 수정 완료!] 
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
            df_stock_updated = pd.concat([df_stock, pd.DataFrame(new_orders)], ignore_index=True)
            df_stock_updated.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
            edited_rec.to_csv(RECURRING_FILE, index=False, encoding='utf-8-sig')
            st.success(f"🎉 성공! 총 {len(new_orders)}일 치의 자동 매수 영수증이 발급되었습니다!")
            st.rerun()
        else:
            st.info("✅ 이미 오늘까지의 적립식 매수가 모두 완료되어 최신 상태입니다.")

if st.button("💾 표에서 직접 수정한 데이터 저장 및 새로고침", use_container_width=True):
    edited_stock.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
    edited_dep.to_csv(DEPOSIT_FILE, index=False, encoding='utf-8-sig')
    st.success("✅ 표 수정 내역 저장 완료!")
    st.rerun()

st.write("---")
st.subheader("📊 2. 사람별/계좌별 전체 자산 요약")

if not edited_stock.empty or not edited_dep.empty:
    with st.spinner("자산 계산 및 과거 시계열 주가를 분석하는 중입니다..."):
        edited_dep["입금액"] = pd.to_numeric(edited_dep["입금액"], errors='coerce').fillna(0)
        dep_summary = edited_dep.groupby(["소유자", "계좌명"])["입금액"].sum().reset_index()
        dep_summary.rename(columns={"입금액": "총입금액"}, inplace=True)

        edited_stock["거래단가"] = pd.to_numeric(edited_stock["거래단가"], errors='coerce').fillna(0)
        edited_stock["수량"] = pd.to_numeric(edited_stock["수량"], errors='coerce').fillna(0)
        edited_stock["현금흐름"] = edited_stock.apply(lambda x: -1 * x["거래단가"] * x["수량"] if x["거래종류"] == "매수" else x["거래단가"] * x["수량"], axis=1)
        
        buys = edited_stock[edited_stock["거래종류"] == "매수"].groupby(["소유자", "계좌명", "종목코드(6자리)"]).agg(총매수수량=("수량", "sum"), 총매수쓴돈=("현금흐름", lambda x: -x.sum())).reset_index()
        buys["평균매수단가"] = (buys["총매수쓴돈"] / buys["총매수수량"]).fillna(0)

        sells = edited_stock[edited_stock["거래종류"] == "매도"].groupby(["소유자", "계좌명", "종목코드(6자리)"]).agg(총매도수량=("수량", "sum")).reset_index()
        stock_merged = pd.merge(buys, sells, on=["소유자", "계좌명", "종목코드(6자리)"], how="left").fillna(0)
        stock_merged["잔여수량"] = stock_merged["총매수수량"] - stock_merged["총매도수량"]
        stock_merged = stock_merged[stock_merged["잔여수량"] > 0]
        stock_merged["주식투자원금"] = stock_merged["잔여수량"] * stock_merged["평균매수단가"]

        stock_eval_list = []
        for index, row in stock_merged.iterrows():
            code = str(row["종목코드(6자리)"]).split('.')[0].zfill(6)
            try:
                current_price = int(fdr.DataReader(code).iloc[-1]['Close'])
            except:
                current_price = 0
            stock_eval_list.append(current_price * row["잔여수량"])
        
        stock_merged["현재평가금액"] = stock_eval_list
        stock_summary = stock_merged.groupby(["소유자", "계좌명"]).agg(주식투자원금=("주식투자원금", "sum"), 주식평가금액=("현재평가금액", "sum")).reset_index()
        stock_cash_flow = edited_stock.groupby(["소유자", "계좌명"])["현금흐름"].sum().reset_index()

        account_summary = pd.merge(dep_summary, stock_cash_flow, on=["소유자", "계좌명"], how="outer").fillna(0)
        account_summary = pd.merge(account_summary, stock_summary, on=["소유자", "계좌명"], how="outer").fillna(0)
        
        account_summary["남은예수금"] = account_summary["총입금액"] + account_summary["현금흐름"]
        account_summary["계좌총자산"] = account_summary["남은예수금"] + account_summary["주식평가금액"]
        account_summary["계좌수익률(%)"] = ((account_summary["계좌총자산"] - account_summary["총입금액"]) / account_summary["총입금액"] * 100).fillna(0)

        all_owners = account_summary["소유자"].unique().tolist()
        all_accs = account_summary["계좌명"].unique().tolist()
        
        col_top1, col_top2 = st.columns(2)
        selected_owners = col_top1.multiselect("👤 사람 선택", all_owners, default=all_owners)
        selected_accs = col_top2.multiselect("🏦 계좌 선택", all_accs, default=all_accs)

        filtered_summary = account_summary[(account_summary["소유자"].isin(selected_owners)) & (account_summary["계좌명"].isin(selected_accs))]
        
        pie_acc_options = ["전체 합산"]
        if not filtered_summary.empty:
            for _, row in filtered_summary[['소유자', '계좌명']].drop_duplicates().iterrows():
                pie_acc_options.append(f"{row['소유자']} - {row['계좌명']}")
        
        st.write("")
        selected_pie_acc = st.selectbox("📊 아래 요약 전광판에서 보고 싶은 계좌를 고르세요", pie_acc_options)
        
        if selected_pie_acc == "전체 합산":
            pie_summary = filtered_summary
            pie_stock = stock_merged[(stock_merged["소유자"].isin(selected_owners)) & (stock_merged["계좌명"].isin(selected_accs))]
        else:
            p_owner, p_acc = selected_pie_acc.split(" - ")
            pie_summary = filtered_summary[(filtered_summary["소유자"] == p_owner) & (filtered_summary["계좌명"] == p_acc)]
            pie_stock = stock_merged[(stock_merged["소유자"] == p_owner) & (stock_merged["계좌명"] == p_acc)]

        pie_total_asset = pie_summary["계좌총자산"].sum()
        pie_total_cash = pie_summary["남은예수금"].sum()
        pie_total_stock = pie_summary["주식평가금액"].sum()

        stock_pie_data = []
        for index, row in pie_stock.iterrows():
            code = str(row["종목코드(6자리)"]).split('.')[0].zfill(6)
            name = stock_dict.get(code, f"알 수 없는 종목({code})")
            eval_amt = row["현재평가금액"]
            if eval_amt > 0:
                stock_pie_data.append({"종목명": name, "평가금액": eval_amt})
                
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
        
        filtered_stock_raw = edited_stock[(edited_stock["소유자"].isin(selected_owners)) & (edited_stock["계좌명"].isin(selected_accs))]
        
        available_codes = filtered_stock_raw['종목코드(6자리)'].unique().tolist()
        available_names = []
        name_to_code = {}
        for c in available_codes:
            clean_code = str(c).split('.')[0].zfill(6)
            name = stock_dict.get(clean_code, f"알 수 없는 종목({clean_code})")
            if name in name_to_code:
                name = f"{name} ({clean_code})"
            available_names.append(name)
            name_to_code[name] = c

        col_g1, col_g2 = st.columns([2, 1])
        selected_graph_names = col_g1.multiselect("📊 차트에 표시할 종목만 고르기 (기본: 전체)", available_names, default=available_names)
        time_res = col_g2.radio("⏱️ 조회 단위", ["일별 (매일의 흐름)", "월별 (월말 기준 요약)"], horizontal=True)

        selected_graph_codes = [name_to_code[n] for n in selected_graph_names]
        fs = filtered_stock_raw[filtered_stock_raw['종목코드(6자리)'].isin(selected_graph_codes)].copy()
        
        if not fs.empty:
            fs['거래일자'] = pd.to_datetime(fs['거래일자'])
            fs = fs.sort_values('거래일자')
            
            start_dt = fs['거래일자'].min()
            today = pd.to_datetime('today')
            date_idx = pd.date_range(start_dt, today, freq='D')
            
            daily_invest = pd.Series(0.0, index=date_idx)
            daily_eval = pd.Series(0.0, index=date_idx)
            
            tickers = fs['종목코드(6자리)'].unique()
            for ticker in tickers:
                t_fs = fs[fs['종목코드(6자리)'] == ticker].copy()
                t_fs['투자금액'] = t_fs.apply(lambda x: x['거래단가']*x['수량'] if x['거래종류']=='매수' else -x['거래단가']*x['수량'], axis=1)
                t_fs['수량변화'] = t_fs.apply(lambda x: x['수량'] if x['거래종류']=='매수' else -x['수량'], axis=1)
                
                daily_changes = t_fs.groupby('거래일자').agg({'투자금액':'sum', '수량변화':'sum'})
                daily_changes = daily_changes.reindex(date_idx, fill_value=0)
                
                cum_invest = daily_changes['투자금액'].cumsum()
                cum_qty = daily_changes['수량변화'].cumsum()
                daily_invest += cum_invest
                
                code = str(ticker).split('.')[0].zfill(6)
                try:
                    p_df = fdr.DataReader(code, start_dt, today)
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
            st.info("선택하신 종목 또는 계좌에 해당하는 거래 내역이 없습니다.")

        st.write("---")
        st.subheader("🔍 3. 내 입맛대로 골라보기 (종목/날짜 맞춤 필터)")
        
        detailed_data = []
        for index, row in stock_merged.iterrows():
            code = str(row["종목코드(6자리)"]).split('.')[0].zfill(6)
            stock_name = stock_dict.get(code, "알 수 없는 종목")
            try:
                current_price = int(fdr.DataReader(code).iloc[-1]['Close'])
            except:
                current_price = 0
            avg_price = float(row["평균매수단가"])
            qty = float(row["잔여수량"])
            return_rate = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
            
            buy_dates = edited_stock[(edited_stock["종목코드(6자리)"] == row["종목코드(6자리)"]) & (edited_stock["거래종류"] == "매수")]["거래일자"].tolist()
            recent_buy_date = buy_dates[0] if buy_dates else "알수없음"

            detailed_data.append({"소유자": row["소유자"], "계좌명": row["계좌명"], "최근매수일": recent_buy_date, "종목명": stock_name, "평균매수단가": f"{int(avg_price):,}원", "현재가": f"{current_price:,}원", "수익률": f"{return_rate:.2f}%", "보유수량": f"{int(qty)}주", "평가금액": f"{int(current_price * qty):,}원"})
        
        df_detailed = pd.DataFrame(detailed_data)

        col_f1, col_f2 = st.columns(2)
        all_stocks = df_detailed["종목명"].unique().tolist() if not df_detailed.empty else []
        filtered_detailed = df_detailed[(df_detailed["소유자"].isin(selected_owners)) & (df_detailed["계좌명"].isin(selected_accs))]
        current_stocks = filtered_detailed["종목명"].unique().tolist() if not filtered_detailed.empty else []
        
        selected_stocks_table = col_f1.multiselect("📈 하단 표에 표시할 종목", all_stocks, default=current_stocks)
        date_filter = col_f2.date_input("📅 영수증 날짜별 조회 (시작일 - 종료일)", value=[])
        
        if not filtered_detailed.empty:
            final_filtered_df = filtered_detailed[filtered_detailed["종목명"].isin(selected_stocks_table)]
            
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
            try:
                styled_df = final_filtered_df.style.map(color_returns, subset=['수익률'])
            except AttributeError:
                styled_df = final_filtered_df.style.applymap(color_returns, subset=['수익률'])
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            if len(date_filter) == 2:
                start_date, end_date = date_filter
                st.markdown(f"#### 📅 {start_date} ~ {end_date} 기간의 매매 영수증")
                mask = (edited_stock['거래일자'] >= str(start_date)) & (edited_stock['거래일자'] <= str(end_date))
                filtered_history = edited_stock[mask]
                if not filtered_history.empty:
                    st.dataframe(filtered_history, use_container_width=True, hide_index=True)
                else:
                    st.info("해당 기간에는 거래 내역이 없습니다.")

        st.write("---")
        st.subheader("💬 4. AI 멘토와 실시간 대화하기 (포메뽀꼬 모드)")
        st.info("💡 위에서 즐겨찾기 한 글로벌 시황 사이트들을 볼 시간이 없다면, 아래의 [시황 브리핑] 버튼을 눌러 AI에게 대신 요약을 부탁해보세요!")

        if not api_key:
            st.warning("⚠️ 왼쪽 사이드바에 Gemini API Key를 먼저 입력해야 대화가 가능합니다.")
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
                            
                            portfolio_str = final_filtered_df.to_string()
                            cash_str = filtered_summary[["소유자", "계좌명", "남은예수금", "계좌수익률(%)"]].to_string()
                            
                            sys_instruct = f"""
                            당신은 '단 3개의 미국 ETF로 은퇴하라'의 저자 '포메뽀꼬(김지훈)'의 철학을 탑재한 나의 개인 자산관리 비서입니다.
                            
                            [나의 최신 계좌 데이터]
                            * 보유 주식: \n{portfolio_str}
                            * 남은 예수금: \n{cash_str}
                            
                            [답변 원칙]
                            1. 사용자가 시황 브리핑을 요구하면, 당신이 가지고 있는 최신 경제 지식(금리, 공포탐욕지수, S&P500 트렌드, 뉴스)을 바탕으로 냉철하게 시황을 분석하고 투자 멘탈을 잡아주세요.
                            2. 사용자가 내 계좌에 대해 질문하면, 두루뭉술하게 대답하지 말고 위 데이터를 보고 'A 주식을 5주 매도하세요' 처럼 구체적인 수치와 종목명을 콕 집어주세요.
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

else:
    st.info("데이터를 입력해주세요.")