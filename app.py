import streamlit as st
import sqlite3
import bcrypt
import json
from zhipuai import ZhipuAI

# ================== 1. 数据库与用户管理模块 (新增) ==================
DB_NAME = "chainshield.db"

def init_db():
    """初始化数据库，创建用户表和配置表"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE NOT NULL, 
                  password_hash TEXT NOT NULL)''')
    # 配置表 (存API Key)
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
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
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
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    
    if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
        return True
    return False

def set_api_key(key):
    """保存 API Key 到数据库"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('zhipu_api_key', ?)", (key,))
    conn.commit()
    conn.close()

def get_api_key():
    """从数据库读取 API Key"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key = 'zhipu_api_key'")
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# 初始化数据库
init_db()

# ================== 2. 登录/注册界面 (新增) ==================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🛡️ ChainShield 智能审计系统")
    tab1, tab2 = st.tabs(["🔐 登录", "📝 注册账号"])
    
    with tab1:
        with st.form("login_form"):
            user = st.text_input("用户名")
            pwd = st.text_input("密码", type="password")
            submit = st.form_submit_button("登录")
            if submit:
                if login_user(user, pwd):
                    st.session_state.logged_in = True
                    st.session_state.username = user
                    st.rerun()
                else:
                    st.error("用户名或密码错误")
    
    with tab2:
        with st.form("register_form"):
            new_user = st.text_input("设置用户名")
            new_pwd = st.text_input("设置密码", type="password")
            confirm_pwd = st.text_input("确认密码", type="password")
            reg_submit = st.form_submit_button("注册")
            if reg_submit:
                if new_pwd != confirm_pwd:
                    st.error("两次密码不一致")
                elif len(new_pwd) < 6:
                    st.error("密码长度至少6位")
                elif register_user(new_user, new_pwd):
                    st.success("注册成功！请切换到登录页登录")
                else:
                    st.error("用户名已存在")
    st.stop()

# ================== 3. 主程序逻辑 (保持原样) ==================
st.sidebar.title(f"👤 欢迎, {st.session_state.username}")
if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 系统设置")

# --- 后台管理 API Key ---
current_key = get_api_key()
with st.sidebar.expander("🔑 配置 API Key", expanded=(current_key is None)):
    api_key_input = st.text_input(
        "智谱 AI API Key", 
        value=current_key if current_key else "", 
        type="password",
        help="请输入您的 ZhipuAI API Key"
    )
    if st.button("保存 Key"):
        if api_key_input:
            set_api_key(api_key_input)
            st.success("✅ Key 已保存！")
            st.rerun()
        else:
            st.error("Key 不能为空")

if not current_key:
    st.warning("⚠️ 请先在左侧边栏配置 API Key 才能使用审计功能！")
    st.stop()

# 初始化客户端
client = ZhipuAI(api_key=current_key)

# --- 你的原有业务逻辑 (完全保留) ---
st.title("🛡️ ChainShield 区块链合约审计智能体")
st.caption("基于 GLM-5.3-Flash 驱动的安全审计系统")

uploaded_file = st.file_uploader("上传合约文件 (.sol / .vy)", type=["sol", "vy"])

if uploaded_file:
    code_content = uploaded_file.read().decode("utf-8")
    
    with st.spinner("正在深度分析合约漏洞..."):
        prompt = f"""你是一个专业的区块链安全审计专家。请对以下智能合约代码进行安全审计。
        
        代码内容：
        ```solidity
        {code_content}
        ```
        
        请按照以下格式输出审计报告：
        1. **风险等级**：(高/中/低)
        2. **漏洞描述**：详细说明漏洞原理。
        3. **受影响代码**：引用具体代码行。
        4. **修复建议**：给出具体的代码修改方案。
        
        如果没有发现明显漏洞，请输出“未发现高危漏洞”。"""
        
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        
        full_report = ""
        report_placeholder = st.empty()
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                full_report += chunk.choices[0].delta.content
                report_placeholder.markdown(full_report)
                
        st.session_state.last_report = full_report

if "last_report" in st.session_state:
    st.markdown("---")
    st.subheader("历史审计报告")
    st.markdown(st.session_state.last_report)