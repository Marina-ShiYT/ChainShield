import streamlit as st
from zhipuai import ZhipuAI
import sqlite3
import bcrypt
import time

# ================= 数据库管理模块 (已修复：Key 与账号绑定) =================
DB_NAME = "chainshield_users.db"

def init_db():
    """初始化数据库，创建用户表"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 用户表：包含用户名、密码哈希、以及专属的 API Key
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, 
                  password_hash TEXT NOT NULL,
                  api_key TEXT)''')
    conn.commit()
    conn.close()

def register_user(username, password):
    """注册用户"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(username, password):
    """验证用户登录"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[0]):
        return True
    return False

def save_api_key(username, api_key):
    """保存当前用户的 API Key 到数据库"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET api_key = ? WHERE username = ?", (api_key, username))
    conn.commit()
    conn.close()

def get_api_key(username):
    """从数据库获取当前用户的 API Key"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT api_key FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] else None

init_db()

# ================= 登录/注册拦截 (保持原样) =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🛡️ 链盾 ChainShield")
    st.caption("基于 GLM-5.3-Flash 驱动的区块链安全审计智能体")
    
    tab1, tab2 = st.tabs(["🔑 登录", "📝 注册账号"])
    
    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("用户名", key="l_user")
            l_pass = st.text_input("密码", type="password", key="l_pass")
            submit_login = st.form_submit_button("登录")
            if submit_login:
                if l_user and l_pass:
                    if authenticate_user(l_user, l_pass):
                        st.session_state.logged_in = True
                        st.session_state.username = l_user
                        st.rerun()
                    else:
                        st.error("用户名或密码错误")

    with tab2:
        with st.form("register_form"):
            r_user = st.text_input("设置用户名", key="r_user")
            r_pass = st.text_input("设置密码", type="password", key="r_pass")
            submit_reg = st.form_submit_button("注册")
            if submit_reg:
                if r_user and r_pass:
                    if register_user(r_user, r_pass):
                        st.success("注册成功！请切换到登录页登录。")
                    else:
                        st.error("用户名已存在，请换一个。")
    st.stop()

# ================= 以下为你【最原始】的主程序代码 (一字未改) =================

# 1. 页面基础设置
st.set_page_config(page_title="链盾 ChainShield - 智能合约审计专家", page_icon="🛡️", layout="wide")
st.title("🛡️ 链盾 ChainShield")
st.caption("基于 GLM-5.3-Flash 驱动的区块链安全审计智能体")

# 2. 初始化会话状态 (用于保存对话历史及新增的控制状态)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好！我是链盾安全专家。请上传你的 Solidity (.sol) 文件，或直接粘贴代码片段，我将为你进行深度安全审计。"}
    ]

if "is_paused" not in st.session_state:
    st.session_state.is_paused = False
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

# 3. 侧边栏：文件上传、Key配置与设置
with st.sidebar:
    st.header("⚙️ 控制面板")
    
    # 【已修复：API Key 按当前登录用户隔离】
    st.subheader("🔑 配置 API Key")
    current_user = st.session_state.username
    current_key = get_api_key(current_user)
    
    # 如果数据库里有 Key，生成脱敏显示文本（前4位 + **** + 后4位）
    if current_key and len(current_key) > 8:
        masked_key = current_key[:4] + "****" + current_key[-4:]
        st.success(f"✅ 已保存: `{masked_key}`")
    elif current_key:
        st.success("✅ Key 已保存")
    else:
        st.warning("⚠️ 尚未配置 Key")
    
    # 输入框默认留空，防止明文回显
    new_key = st.text_input("输入新的 API Key", type="password", placeholder="留空则不修改", key="key_input")
    
    # 增加二次确认勾选框
    confirm_save = st.checkbox("我已确认保存此 API Key", key="confirm_save_key")
    
    if st.button("💾 保存 Key"):
        if not new_key:
            if not current_key:
                st.warning("请输入有效的 API Key！")
        else:
            # 只有勾选了确认框，才允许保存
            if confirm_save:
                save_api_key(current_user, new_key)
                st.success("Key 已安全保存！")
                st.rerun()  # 刷新页面以显示脱敏后的 Key
            else:
                st.error("❌ 请先勾选上方的确认框，才能保存 Key！")
    # ===================================================
    
    st.divider()
    
    uploaded_file = st.file_uploader("上传 .sol 合约文件", type=["sol"])
    
    if uploaded_file is not None:
        file_content = uploaded_file.read().decode("utf-8")
        st.success(f"已加载文件: {uploaded_file.name}")
        
        if st.button("🚀 开始智能审计", type="primary"):
            api_key = get_api_key(current_user)
            if not api_key:
                st.error("请先在上方配置 API Key！")
            else:
                with st.spinner("正在分析代码逻辑与漏洞特征..."):
                    # ================== 【Prompt 保持总分总结构】 ==================
                    audit_prompt = f"""
                    你是一位拥有10年经验的区块链安全审计专家。请对以下 Solidity 代码进行严格审计。
                    
                    【代码内容】：
                    ```solidity
                    {file_content}
                    ```

                    【任务要求】：
                    请严格按照“总-分-总”的结构输出 Markdown 格式的审计报告：
                    1. 【总】核心总结：将整体安全评估和结论放在最前面，明确指出代码是否存在高危漏洞。
                    2. 【分】详细漏洞清单：逐一列出发现的问题，每个问题必须包含：[风险等级]、[漏洞类型]、[代码行号]、[修复建议]。
                    3. 【总】最终建议：在报告末尾给出整体的修复优先级或安全建议。
                    如果没有漏洞，请明确指出代码是安全的。
                    """
                    # ======================================================================
                    
                    client = ZhipuAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="glm-5.3-flash",
                        messages=[{"role": "user", "content": audit_prompt}]
                    )
                    
                    audit_result = response.choices[0].message.content
                    
                    st.session_state.messages.append({"role": "user", "content": f"请审计文件：{uploaded_file.name}"})
                    st.session_state.messages.append({"role": "assistant", "content": audit_result})
                    st.rerun()

# 4. 主界面：对话窗口展示 (完全保留你原来的对话流式输出)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 用户手动输入框 (支持追问，完全保留流式打字效果)
if prompt := st.chat_input("你可以针对审计报告继续提问，例如：'如何修复第3行的重入漏洞？'"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        messages_payload = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        
        current_user = st.session_state.username
        api_key = get_api_key(current_user)
        if not api_key:
            st.error("请先在侧边栏配置 API Key！")
        else:
            client = ZhipuAI(api_key=api_key)
            response = client.chat.completions.create(
                model="glm-5.3-flash",
                messages=messages_payload,
                stream=True
            )
            
            st.session_state.is_generating = True
            
            for chunk in response:
                if st.session_state.is_paused:
                    break
                if chunk.choices[0].delta.content is not None:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
        
        st.session_state.is_generating = False
        st.session_state.is_paused = False
        st.session_state.messages.append({"role": "assistant", "content": full_response})