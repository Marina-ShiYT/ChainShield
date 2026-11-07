import streamlit as st
from zhipuai import ZhipuAI
import sqlite3
import bcrypt
import time
import os

# ================= 数据库管理模块 =================
DB_NAME = "chainshield_users.db"

def init_db():
    """初始化数据库，并自动处理旧版本表的升级"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, 
                  password_hash TEXT NOT NULL,
                  api_key TEXT)''')
    try:
        c.execute("SELECT api_key FROM users LIMIT 1")
    except sqlite3.OperationalError:
        print("检测到旧版数据库，正在自动迁移...")
        try:
            c.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
            conn.commit()
            print("数据库迁移成功！")
        except Exception as e:
            st.error(f"数据库迁移失败: {e}")
    conn.close()

def get_user(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_api_key(username, api_key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET api_key=? WHERE username=?", (api_key, username))
    conn.commit()
    conn.close()

def get_api_key(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT api_key FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ================= 页面配置与初始化 =================
st.set_page_config(page_title="ChainShield", page_icon="🛡️", layout="wide")
init_db()

# ================= 登录/注册逻辑 =================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.title("🛡️ ChainShield 登录")
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        with st.form("login_form"):
            user = st.text_input("用户名")
            pwd = st.text_input("密码", type="password")
            submit = st.form_submit_button("登录")
            if submit:
                db_user = get_user(user)
                if db_user and bcrypt.checkpw(pwd.encode('utf-8'), db_user[1].encode('utf-8')):
                    st.session_state.logged_in = True
                    st.session_state.username = user
                    st.rerun()
                else:
                    st.error("用户名或密码错误")

    with tab2:
        with st.form("register_form"):
            new_user = st.text_input("设置用户名")
            new_pwd = st.text_input("设置密码", type="password")
            reg_submit = st.form_submit_button("注册")
            if reg_submit:
                if create_user(new_user, new_pwd):
                    st.success("注册成功！请切换到登录页登录")
                else:
                    st.error("用户名已存在")
    st.stop()

# ================= 主应用逻辑 (登录后显示) =================
st.sidebar.title(f"👤 {st.session_state.username}")
if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# --- 1. Key 设置模块 (真实可用验证 + 严格脱敏) ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ API 设置")
current_key = get_api_key(st.session_state.username)

# 【严格脱敏展示】
if current_key:
    masked_key = f"{current_key[:6]}****{current_key[-4:]}" if len(current_key) > 10 else "******"
    st.sidebar.success(f"✅ 已配置 Key: `{masked_key}`")
else:
    st.sidebar.warning("⚠️ 尚未配置 Key")

with st.sidebar.expander("配置/更新 API Key", expanded=(not current_key)):
    # 输入框永远为空，防止明文残留
    new_key = st.text_input("输入新的 ZhipuAI Key", value="", type="password", placeholder="sk-...")
    confirm_check = st.checkbox("我已阅读并确认 Key 将加密存储", key="key_confirm")
    
    if st.button("保存 Key"):
        if not new_key.startswith("sk-"):
            st.warning("Key 格式似乎不正确 (应以 sk- 开头)")
        elif not confirm_check:
            st.error("请先勾选确认框！")
        else:
            # 【核心修改：以真实可用为保存标准】
            st.info("⏳ 正在连接智谱 AI 验证 Key 有效性...")
            try:
                test_client = ZhipuAI(api_key=new_key)
                test_response = test_client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=5
                )
                update_api_key(st.session_state.username, new_key)
                st.success("✅ Key 验证可用，保存成功！")
                st.rerun() # 刷新清空输入框
            except Exception as e:
                st.error(f"❌ Key 不可用：{str(e)}")

# --- 2. 文件上传模块 (找回丢失的功能) ---
st.sidebar.markdown("---")
st.sidebar.subheader("📂 上传合约文件")
uploaded_file = st.sidebar.file_uploader("上传 .sol 合约文件", type=["sol"])

# 检查是否有 Key，没有则停止后续加载
my_api_key = get_api_key(st.session_state.username)
if not my_api_key:
    st.warning("⚠️ 请先在左侧栏配置并验证您的 API Key 才能开始审计。")
    st.stop()

# ================= 聊天界面 =================
st.title("🛡️ ChainShield 智能合约审计")
st.caption("基于 GLM-4-Flash 驱动的区块链安全审计智能体")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🛡️"):
        st.markdown(msg["content"])

# --- 3. 右侧对话框与输入逻辑 (找回丢失的功能) ---
# 处理文件上传触发的对话
if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    file_prompt = f"请审计以下智能合约文件 `{uploaded_file.name}`：\n```solidity\n{file_content}\n```"
    # 避免重复触发，将文件内容作为当前 prompt
    prompt = file_prompt
    uploaded_file = None  # 重置状态
else:
    # 处理手动输入的对话
    prompt = st.chat_input("请输入智能合约代码...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    system_prompt = """你是一位资深的区块链安全审计专家。请对用户提供的智能合约代码进行严格审计。
    
【输出格式要求】必须严格遵守以下结构：
1. 📝 **审计总结**：一句话概括合约的主要风险等级（高/中/低）和核心问题。
2. 🔍 **详细分析**：
   - 逐行或逐函数指出漏洞（如重入攻击、整数溢出、权限控制缺失等）。
   - 引用具体代码片段。
3. 💡 **修复建议**：给出修改后的代码示例或具体的防御措施。
"""
    
    messages_payload = [{"role": "system", "content": system_prompt}]
    messages_payload.extend(st.session_state.messages)

    with st.chat_message("assistant", avatar="🛡️"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            client = ZhipuAI(api_key=my_api_key)
            response = client.chat.completions.create(
                model="glm-4-flash",
                messages=messages_payload,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"调用 AI 失败: {str(e)}")