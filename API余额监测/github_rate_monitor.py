import streamlit as st
import requests
from datetime import datetime
import time
import urllib3

# 禁用不安全请求的警告 (因为我们要设置 verify=False，否则控制台会有很多红色警告)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 页面配置 ---
st.set_page_config(
    page_title="GitHub Rate Limit",
    page_icon="🐙",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# --- 工具函数 ---

def fetch_rate_limit(token):
    """调用 GitHub API 获取速率限制数据"""
    url = "https://api.github.com/rate_limit"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        # 关键修改：verify=False 禁用 SSL 验证，解决证书报错
        response = requests.get(url, headers=headers, timeout=10, verify=False)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            return {"error": "Authentication Failed: Invalid Token"}
        else:
            return {"error": f"API Error: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def format_timestamp(ts):
    """将 Unix 时间戳转换为可读格式"""
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def get_minutes_until_reset(ts):
    """计算距离重置还有多少分钟"""
    now = time.time()
    diff = ts - now
    if diff < 0:
        return 0
    return int(diff / 60)


def visualize_resource_card(name, data):
    """渲染单个资源卡片的 UI"""
    limit = data.get('limit', 0)
    used = data.get('used', 0)
    remaining = data.get('remaining', 0)
    reset_ts = data.get('reset', 0)

    # 避免除以零
    percent = (used / limit) if limit > 0 else 0

    # 样式容器
    with st.container():
        st.markdown(f"#### 📦 {name.replace('_', ' ').title()}")

        col_metric, col_time = st.columns([1, 1])
        with col_metric:
            st.metric("Used / Limit", f"{used} / {limit}")
        with col_time:
            mins = get_minutes_until_reset(reset_ts)
            st.metric("Reset In", f"{mins} min", delta_color="off")

        # 进度条
        st.progress(min(percent, 1.0))
        st.caption(f"Reset at: {format_timestamp(reset_ts)}")
        st.divider()


# --- Session State 管理 ---
if 'api_token' not in st.session_state:
    st.session_state.api_token = None
if 'data' not in st.session_state:
    st.session_state.data = None

# --- UI 逻辑 ---

# 1. 登录界面
if not st.session_state.api_token:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🐙 GitHub Rate Limit")
        st.subheader("Visualize your API usage quotas")
        st.markdown("Please enter your **GitHub Personal Access Token** to inspect your API limits.")

        token_input = st.text_input("Personal Access Token (PAT)", type="password")
        if st.button("Connect", type="primary"):
            if token_input:
                st.session_state.api_token = token_input
                st.rerun()
            else:
                st.warning("Please enter a token.")
    st.stop()  # 停止渲染后续内容

# 2. 只有登录后才会执行以下代码

# 顶部导航栏布局
col_header, col_actions = st.columns([3, 1])
with col_header:
    st.title("GitHub Rate Limit")
    st.markdown("**Visualize your API usage quotas**")

with col_actions:
    a1, a2 = st.columns(2)
    with a1:
        if st.button("🔄 Refresh"):
            st.session_state.data = None  # 强制重新获取
            st.rerun()
    with a2:
        if st.button("🚪 Logout"):
            st.session_state.api_token = None
            st.session_state.data = None
            st.rerun()

# 数据获取
if not st.session_state.data:
    with st.spinner("Fetching API quotas..."):
        result = fetch_rate_limit(st.session_state.api_token)

        if "error" in result:
            st.error(result["error"])
            if "Authentication Failed" in str(result["error"]):
                # 允许用户重新登录
                if st.button("Try Login Again"):
                    st.session_state.api_token = None
                    st.rerun()
            st.stop()
        else:
            st.session_state.data = result
            st.rerun()  # 获取数据后刷新以展示

data = st.session_state.data
resources = data.get("resources", {})
rate = data.get("rate", {})  # 有些旧版API直接返回rate在根目录，新版在resources.core中

# 兼容性处理：如果根目录有rate对象，视为Core API
if not resources.get("core") and rate:
    resources["core"] = rate

# --- 3. Overall API Rate (大卡片) ---
st.header("📊 Overall API Rate (Core)")
overall_core = resources.get("core", {})

if overall_core:
    limit = overall_core.get('limit', 0)
    used = overall_core.get('used', 0)
    remaining = overall_core.get('remaining', 0)
    reset_ts = overall_core.get('reset', 0)

    reset_time = format_timestamp(reset_ts)
    mins_left = get_minutes_until_reset(reset_ts)
    percent_val = (used / limit) if limit > 0 else 0

    # 使用大指标展示
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Quota", limit)
    m2.metric("Used", used)
    m3.metric("Remaining", remaining, delta=remaining, delta_color="normal")
    m4.metric("Resets In", f"{mins_left} min")

    st.progress(min(percent_val, 1.0))
    st.caption(f"Reset Time: {reset_time}")
else:
    st.warning("Core rate limit information not found.")

st.markdown("---")

# --- 4. Resource Specific Limits (网格布局) ---
st.header("🧩 Resource Specific Limits")

# 获取所有特定资源，排除已经在上面显示过的 'core'
resource_keys = [k for k in resources.keys() if k != 'core']

if resource_keys:
    # 创建网格，每行显示 3 个卡片
    cols = st.columns(3)
    for i, key in enumerate(resource_keys):
        res_data = resources[key]
        with cols[i % 3]:  # 循环放入列中
            visualize_resource_card(key, res_data)
else:
    st.info("No additional specific resource limits found.")
