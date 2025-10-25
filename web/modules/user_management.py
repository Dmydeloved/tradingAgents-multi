import streamlit as st

import re
import datetime


def initial_user_page():
    # 初始化
    if "user_page" not in st.session_state:
        st.session_state.user_page = "home"
    # 设置按钮大小一致
    st.markdown("""
    <style>
        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            height: 50px;
            margin-bottom: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

    # 侧边栏按钮
    st.sidebar.title("导航")
    if st.sidebar.button("🏠 首页"):
        st.session_state.user_page = "home"
        st.rerun()
    if st.sidebar.button("📊 市场分析"):
        st.session_state.user_page = "market_analysis"
        st.rerun()


    # 页面渲染
    if st.session_state.user_page == "home":
        st.title("🏠 首页")
        st.write("欢迎来到首页")
    elif st.session_state.user_page == "market_analysis":
        st.title("📊 市场分析对话")
        # 输入框，存到 session_state 中
        if "analysis_input" not in st.session_state:
            st.session_state.analysis_input = "股票代码{000001};时间{2023-10-05}:message:{帮我分析下这只股票}"

        # 对话输入框
        st.text_area("请输入您的问题：", value=st.session_state.analysis_input, key="analysis_input")

        # 发送按钮
        if st.button("发送", key="analysis_send"):
            # 获state
            user_input = st.session_state.analysis_input.strip()
            if user_input:
                st.write(f"🧑 用户输入：{user_input}")
                from web.utils.multi_agents import market_agent
                result = market_agent(parse_stock_info(user_input))
                if isinstance(result, str):
                    render_stock_analysis(result)
                # st.write(f"===结果===\n{result}")
            else:
                st.warning("⚠️ 请输入内容后再发送。")


def render_stock_analysis(report: str):
    """渲染股票技术分析报告"""

    if not report or not report.strip():
        st.warning("暂无分析报告")
        return

    # 添加分隔线
    st.markdown("---")
    st.header("📑 技术分析报告")

    # 直接展示报告内容
    # 支持 Markdown 格式展示
    st.markdown(report, unsafe_allow_html=True)


def parse_stock_info(input_str):
    # 使用正则表达式匹配{}中的内容
    pattern = r'\{([^}]+)\}'
    matches = re.findall(pattern, input_str)

    # 初始化默认值
    stock_code = ""
    trade_date = datetime.date.today().isoformat()
    message = ""

    # 提取匹配到的内容
    if len(matches) >= 1:
        stock_code = matches[0]
    if len(matches) >= 2:
        trade_date = matches[1]
    if len(matches) >= 3:
        message = matches[2]

    # 组装成指定的state结构
    state = {
        "trade_date": trade_date,
        "company_of_interest": stock_code,
        "messages": [message] if message else [],
    }

    return state
