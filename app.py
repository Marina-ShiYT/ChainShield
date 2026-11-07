import streamlit as st
import sqlite3
import bcrypt
import json
from zhipuai import ZhipuAI

# ================== 1. 数据库与用户管理模块 ==================
DB_NAME = "chainshield.db"

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE NOT NULL, 
                  password_hash TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS config 
                 (key TEXT PRIMARY KEY, 
                  value TEXT NOT NULL)''')
    conn.commit()
    conn.close()

def register_user(username, password):
    """注册用户"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                  (username, password_hash.decode('utf-8')))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    """验证用户登录"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    
    if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
        return True
    return False

def save_api_key(api_key):
    """保存API Key到数据库"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('zhipu_api_key', ?)", (api_key,))
    conn.commit()
    conn.close()

def get_api_key():
    """从数据库获取API Key"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key='zhipu_api_key'")
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# ================== 2. 审计核心逻辑 (保持原样) ==================
def audit_code(code_content):
    """调用智谱AI进行代码审计，返回格式化报告"""
    api_key = get_api_key()
    if not api_key:
        return "❌ **错误**：请先在左侧边栏配置 API Key！"
    
    client = ZhipuAI(api_key=api_key)
    
    prompt = f"""
    请对以下区块链智能合约代码进行安全审计。
    请严格按照以下Markdown格式输出报告：
    
    ### 🛡️ 审计报告
    
    #### 1. 风险概览
    - **风险等级**: [高/中/低]
    - **漏洞数量**: [数字]
    
    #### 2. 详细分析
    - **漏洞名称**: [例如: 重入攻击]
    - **风险等级**: [高/中/低]
    - **代码位置**: 
    ```solidity
    [有问题的代码片段]
    ```
    - **修复建议**: 
    > [具体的修复建议]
    
    #### 3. 总结
    [简短总结]
    
    ---
    待审计代码：
    {code_content}
    """
    
    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ **API调用失败**: {str(e)}"

# ================== 3. Streamlit 界面逻辑 ==================
st.set_page_config(page_title="ChainShield", page_icon="🛡️", layout="wide")
init_db()

# 初始化 Session State
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- 登录/注册页面 ---
if not st.session_state.logged_in:
    st.title("🛡️ ChainShield 登录")
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        username = st.text_input("用户名", key="login_user")
        password = st.text_input("密码", type="password", key="login_pass")
        if st.button("登录"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("用户名或密码错误")
    
    with tab2:
        new_user = st.text_input("新用户名", key="reg_user")
        new_pass = st.text_input("新密码", type="password", key="reg_pass")
        confirm_pass = st.text_input("确认密码", type="password", key="reg_confirm")
        if st.button("注册"):
            if new_pass != confirm_pass:
                st.error("两次密码不一致")
            elif len(new_pass) < 6:
                st.error("密码长度至少6位")
            else:
                if register_user(new_user, new_pass):
                    st.success("注册成功！请登录")
                else:
                    st.error("用户名已存在")
    st.stop()

# --- 主应用页面 (登录后显示) ---
st.sidebar.title("⚙️ 后台管理")

# API Key 配置区域
current_key = get_api_key()
if current_key:
    masked_key = current_key[:4] + "..." + current_key[-4:] if len(current_key) > 8 else "****"
    st.sidebar.success(f"✅ API Key 已配置: `{masked_key}`")
else:
    st.sidebar.warning("⚠️ 未配置 API Key")

with st.sidebar.expander("🔑 配置 API Key"):
    new_key = st.text_input("输入智谱 API Key", type="password", key="api_key_input")
    if st.button("保存 Key"):
        if new_key:
            save_api_key(new_key)
            st.success("保存成功！")
            st.rerun()
        else:
            st.error("Key 不能为空")

st.sidebar.markdown("---")
if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.rerun()

# 主界面内容
st.title("🛡️ ChainShield 区块链安全审计")
st.markdown("基于 GLM-4-Flash 驱动的智能合约审计系统")

code_input = st.text_area("请输入智能合约代码 (Solidity)", height=300, placeholder="// SPDX-License-Identifier: MIT...")

col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🚀 开始审计", type="primary"):
        if code_input.strip():
            with st.spinner("正在分析代码..."):
                report = audit_code(code_input)
                st.session_state.report = report
        else:
            st.warning("请输入代码内容")

# 输出区域 (完全还原格式)
if 'report' in st.session_state:
    st.markdown("---")
    st.subheader("📊 审计结果")
    # 使用 st.markdown 渲染 AI 返回的完整 Markdown 报告
    st.markdown(st.session_state.report)