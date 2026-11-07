import streamlit as st
from zhipuai import ZhipuAI
import sqlite3
import bcrypt
import time
import os

# ================= 数据库管理模块 (已修复：增加自动迁移逻辑) =================
DB_NAME = "chainshield_users.db"

def init_db():
    """初始化数据库，并自动处理旧版本表的升级"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. 创建用户表 (如果不存在)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, 
                  password_hash TEXT NOT NULL,
                  api_key TEXT)''')
    
    # 2. 【关键修复】自动迁移逻辑：检查旧表是否缺少 api_key 列
    try:
        c.execute("SELECT api_key FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # 如果报错，说明是旧表，执行升级操作
        print("检测到旧版数据库，正在自动迁移...")
        # 备份旧数据
        c.execute("ALTER TABLE users RENAME TO old_users")
        # 创建新表
        c.execute('''CREATE TABLE users
                     (username TEXT PRIMARY KEY, 
                      password_hash TEXT NOT NULL,
                      api_key TEXT)''')
        # 迁移数据
        c.execute("INSERT INTO users (username, password_hash) SELECT username, password_hash FROM old_users")
        c.execute("DROP TABLE old_users")
        conn.commit()
        print("数据库迁移完成！")
    
    conn.close()

def register_user(username, password):
    """注册用户"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                  (username, hashed.decode('utf-8')))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    """验证用户"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    
    if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
        return True
    return False

def save_api_key(username, api_key):
    """保存 API Key 到当前用户记录"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET api_key = ? WHERE username = ?", (api_key, username))
    conn.commit()
    conn.close()

def get_api_key(username):
    """获取当前用户的 API Key"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT api_key FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# ================= 初始化数据库 =================
init_db()

# ================= 登录/注册界面 =================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        with st.form("login_form"):
            user = st.text_input("用户名")
            pwd = st.text_input("密码", type="password")
            submit = st.form_submit_button("登录")
            if submit:
                if verify_user(user, pwd):
                    st.session_state.logged_in = True
                    st.session_state.username = user
                    st.rerun()
                else:
                    st.error("用户名或密码错误")
    
    with tab2:
        with st.form("register_form"):
            new_user = st.text_input("新用户名")
            new_pwd = st.text_input("新密码", type="password")
            reg_submit = st.form_submit_button("注册")
            if reg_submit:
                if register_user(new_user, new_pwd):
                    st.success("注册成功，请登录")
                else:
                    st.error("用户名已存在")
    st.stop()

# ================= 主应用界面 =================
st.sidebar.title("控制面板")
st.sidebar.write(f"欢迎, {st.session_state.username}")

# --- 配置 API Key 区域 (已增加确认机制) ---
st.sidebar.header("配置 API Key")
current_key = get_api_key(st.session_state.username)

# 显示状态：如果有 key，显示脱敏后的 key；如果没有，显示提示
if current_key:
    masked_key = current_key[:6] + "****" + current_key[-4:] if len(current_key) > 10 else "****"
    st.sidebar.success(f"当前 Key: {masked_key}")
else:
    st.sidebar.warning("尚未配置 Key")

new_key = st.sidebar.text_input("输入新的 API Key", type="password", key="new_key_input")

# 【新增】确认勾选框
confirm_save = st.sidebar.checkbox("我已阅读并确认保存此 Key", key="confirm_checkbox")

if st.sidebar.button("保存 Key"):
    if not new_key:
        st.sidebar.error("请输入 Key")
    elif not confirm_save:
        # 【新增】如果不勾选，卡住并提示
        st.sidebar.error("⚠️ 请先勾选上方的确认框才能保存！")
    else:
        save_api_key(st.session_state.username, new_key)
        st.sidebar.success("保存成功！")
        st.rerun()

if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.session_state.username = None
    st.rerun()

# --- 审计功能区域 ---
st.title("🛡️ 链盾 ChainShield")
st.caption("基于 GLM-5.3-Flash 驱动的区块链安全审计智能体")

audit_text = st.text_area("请输入智能合约代码或交易描述", height=200)

if st.button("开始审计"):
    current_key = get_api_key(st.session_state.username)
    if not current_key:
        st.error("请先在侧边栏配置 API Key")
    elif not audit_text:
        st.error("请输入审计内容")
    else:
        try:
            client = ZhipuAI(api_key=current_key)
            
            # 【恢复】总-分-总 Prompt 结构
            audit_prompt = f"""你是一位资深的区块链安全审计专家。请对以下内容进行深度安全审计。

【输出格式要求】
请严格按照以下结构输出报告：
1. **📌 审计总结**：用一句话概括风险等级和核心问题。
2. **🔍 详细分析**：分点列出具体漏洞、风险点及其原理。
3. **💡 修复建议**：针对每个问题给出具体的代码级修复方案。

【待审计内容】
{audit_text}
"""
            
            response = client.chat.completions.create(
                model="glm-5.3-flash",
                messages=[{"role": "user", "content": audit_prompt}],
                temperature=0.1
            )
            
            st.markdown("### 📝 审计报告")
            st.markdown(response.choices[0].message.content)
            
        except Exception as e:
            st.error(f"审计失败: {str(e)}")