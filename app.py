
import streamlit as st
from zhipuai import ZhipuAI
import json
import time
import sqlite3
import bcrypt

# ================= 数据库管理 =================
DB_NAME = "chainshield.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()

def register_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[0]):
        return True
    return False

def set_api_key(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config VALUES ('api_key', ?)", (key,))
    conn.commit()
    conn.close()

def get_api_key():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key='api_key'")
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# 初始化数据库
init_db()

# ================= 配置区域 =================
# API Key 已移至数据库管理，通过侧边栏"配置 API Key"设置
# ===========================================

# 1. 页面基础设置
st.set_page_config(page_title="链盾 ChainShield - 智能合约审计专家", page_icon="🛡️", layout="wide")
st.title("🛡️ 链盾 ChainShield")
st.caption("基于 GLM-5.3-Flash 驱动的区块链安全审计智能体")

# 2. 登录/注册检查
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["登录", "注册"])

    with tab1:
        with st.form("login_form"):
            l_user = st.text_input("用户名", key="l_user")
            l_pass = st.text_input("密码", type="password", key="l_pass")
            submit = st.form_submit_button("登录")
            if submit:
                if l_user and l_pass:
                    if login_user(l_user, l_pass):
                        st.session_state.logged_in = True
                        st.session_state.username = l_user
                        api_key = get_api_key()
                        if api_key:
                            st.session_state.api_key = api_key
                        st.success("登录成功！")
                        st.rerun()
                    else:
                        st.error("用户名或密码错误")
                else:
                    st.warning("请输入用户名和密码")

    with tab2:
        with st.form("register_form"):
            r_user = st.text_input("用户名", key="r_user")
            r_pass = st.text_input("密码", type="password", key="r_pass")
            r_pass2 = st.text_input("确认密码", type="password", key="r_pass2")
            submit = st.form_submit_button("注册")
            if submit:
                if r_user and r_pass and r_pass2:
                    if r_pass == r_pass2:
                        if register_user(r_user, r_pass):
                            st.success("注册成功！请登录。")
                        else:
                            st.error("用户名已存在")
                    else:
                        st.error("两次密码不一致")
                else:
                    st.warning("请填写所有字段")

    st.stop()

# 3. 初始化会话状态 (用于保存对话历史及新增的控制状态)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好！我是链盾安全专家。请上传你的 Solidity (.sol) 文件，或直接粘贴代码片段，我将为你进行深度安全审计。"}
    ]

# 【新增】初始化暂停状态和流式生成状态
if "is_paused" not in st.session_state:
    st.session_state.is_paused = False
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

# 4. 侧边栏：API Key 管理与文件上传
with st.sidebar:
    st.header("🔐 后台管理")
    current_key = get_api_key()
    if current_key:
        st.success(f"API Key 已配置 (尾缀: ...{current_key[-4:]})")
    else:
        st.warning("⚠️ 尚未配置 API Key，请在下方配置")

    with st.expander("🔑 配置 API Key"):
        new_key = st.text_input("智谱 API Key", type="password", help="填入你的智谱 AI API Key")
        if st.button("保存 Key"):
            if new_key:
                set_api_key(new_key)
                st.session_state.api_key = new_key
                st.success("API Key 已保存！")
            else:
                st.error("请输入 API Key")

    st.divider()
    st.header("⚙️ 控制面板")
    uploaded_file = st.file_uploader("上传 .sol 合约文件", type=["sol"])

    if uploaded_file is not None:
        # 读取文件内容
        file_content = uploaded_file.read().decode("utf-8")
        st.success(f"已加载文件: {uploaded_file.name}")

        # 触发自动审计逻辑
        if st.button("🚀 开始智能审计", type="primary"):
            api_key = get_api_key()
            if not api_key:
                st.error("请先在上方配置 API Key")
            else:
                with st.spinner("正在分析代码逻辑与漏洞特征..."):
                    # 构造审计专用的 Prompt
                    audit_prompt = f"""
                    你是一位拥有10年经验的区块链安全审计专家。请对以下 Solidity 代码进行严格审计。

                    【代码内容】：
                    ```solidity
                    {file_content}
                    ```

                    【任务要求】：
                    1. 识别代码中的高危漏洞（如重入攻击、整数溢出、权限控制缺失等）。
                    2. 如果没有漏洞，请明确指出代码是安全的。
                    3. 输出格式必须包含：[风险等级]、[漏洞类型]、[代码行号]、[修复建议]。
                    4. 请用 Markdown 格式输出报告，保持专业且简洁。
                    """

                    # 调用 GLM-5.3-Flash
                    client = ZhipuAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="glm-5.3-flash", # 使用你购买的 Flash 模型
                        messages=[{"role": "user", "content": audit_prompt}]
                    )

                    audit_result = response.choices[0].message.content

                    # 将结果加入对话历史
                    st.session_state.messages.append({"role": "user", "content": f"请审计文件：{uploaded_file.name}"})
                    st.session_state.messages.append({"role": "assistant", "content": audit_result})
                    st.rerun() # 刷新页面显示结果

# 5. 主界面：对话窗口展示
# 遍历并显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 6. 用户手动输入框 (支持追问)
if prompt := st.chat_input("你可以针对审计报告继续提问，例如：'如何修复第3行的重入漏洞？'"):
    # 显示用户输入
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 模拟 AI 思考并回复
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # 构造包含上下文的请求
        messages_payload = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]

        api_key = get_api_key()
        client = ZhipuAI(api_key=api_key)
        response = client.chat.completions.create(
            model="glm-5.3-flash",
            messages=messages_payload,
            stream=True # 开启流式输出，体验更好
        )

        # 标记开始生成
        st.session_state.is_generating = True

        # 逐字打印效果
        for chunk in response:
            # 【新增】检查是否被暂停，如果暂停则跳出循环
            if st.session_state.is_paused:
                break

            if chunk.choices[0].delta.content is not None:
                full_response += chunk.choices[0].delta.content
                message_placeholder.markdown(full_response + "▌")

        message_placeholder.markdown(full_response)

    # 标记生成结束
    st.session_state.is_generating = False
    # 生成结束后重置暂停状态
    st.session_state.is_paused = False

    st.session_state.messages.append({"role": "assistant", "content": full_response})

# 退出登录按钮
if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.session_state.messages = []
    st.rerun()