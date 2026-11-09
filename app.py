import streamlit as st
from zhipuai import ZhipuAI
import sqlite3
import bcrypt
import os
import json  

# ================= RAG 规则库加载模块 =================
RULES_FILE = "vuln_rules.json"

def load_rag_context():
    """加载本地规则库作为 RAG 上下文，不修改原有逻辑"""
    try:
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            context = "【审计知识库 - 请优先参考以下规则】\n"
            for rule in rules:
                context += f"- {rule['id']} {rule['name']}: {rule['description']} (严重度: {rule['severity']})\n"
            return context
    except Exception:
        pass
    return ""  # 加载失败时返回空字符串，不影响主流程
    
# ================= 数据库管理模块 =================
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
    
    # 2. 自动迁移逻辑：检查旧表是否缺少 api_key 列
    try:
        c.execute("SELECT api_key FROM users LIMIT 1")
    except sqlite3.OperationalError:
        try:
            c.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
            conn.commit()
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
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

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

# ================= 页面配置 =================
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
# --- 侧边栏 (左侧) ---
st.sidebar.title(f"👤 {st.session_state.username}")
if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# 1. API 设置模块
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ API 设置")
current_key = get_api_key(st.session_state.username)

# 【严格脱敏展示】
if current_key:
    if len(current_key) > 8:
        masked_key = current_key[:4] + "****" + current_key[-4:]
    else:
        masked_key = "******"
    st.sidebar.success(f"✅ 当前已配置 Key: `{masked_key}`")
else:
    st.sidebar.warning("⚠️ 尚未配置 Key")

# 使用 Session State 控制输入框清空
if 'input_key_value' not in st.session_state:
    st.session_state.input_key_value = ""

with st.sidebar.expander("配置新的 API Key", expanded=(not current_key)):
    new_key = st.text_input(
        "输入新的 ZhipuAI Key", 
        value=st.session_state.input_key_value, 
        type="password", 
        placeholder="sk-..."
    )
    confirm_check = st.checkbox("我已阅读并确认 Key 将加密存储", key="key_confirm")
    
    if st.button("保存 Key"):
        if not confirm_check:
            st.error("请先勾选确认框！")
        elif not new_key:
            st.warning("请输入 Key")
        else:
            st.info("⏳ 正在验证 Key 是否可用，请稍候...")
            try:
                test_client = ZhipuAI(api_key=new_key)
                test_response = test_client.chat.completions.create(
                    model="glm-5-flash",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=5
                )
                update_api_key(st.session_state.username, new_key)
                st.success("✅ Key 验证可用，保存成功！")
                
                # 【关键】保存成功后清空输入框变量，并刷新页面
                st.session_state.input_key_value = "" 
                st.rerun() 
            except Exception as e:
                st.error(f"❌ Key 不可用：{str(e)}")

# 2. 文件上传模块
st.sidebar.markdown("---")
st.sidebar.subheader("📂 上传合约文件")
uploaded_file = st.sidebar.file_uploader("上传 .sol 合约文件", type=["sol"])

if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    st.sidebar.success(f"已加载文件: {uploaded_file.name}")
    
    if st.sidebar.button("🚀 开始智能审计", type="primary"):
        api_key = get_api_key(st.session_state.username)
        if not api_key:
            st.sidebar.error("请先配置 API Key！")
        else:
            # 构造审计指令
            audit_prompt = f"请对以下智能合约文件进行严格审计：\n\n文件名：{uploaded_file.name}\n\n代码内容：\n```solidity\n{file_content}\n```"
            
            # 将审计指令加入历史记录，并标记需要立即触发 AI
            st.session_state.messages.append({"role": "user", "content": audit_prompt})
            st.session_state.trigger_audit = True # 设置触发标志
            st.rerun()

# 检查是否有 Key (用于主界面拦截)
my_api_key = get_api_key(st.session_state.username)
if not my_api_key:
    st.warning("⚠️ 请先在左侧栏配置您的 API Key 才能开始审计。")
    st.stop()

# --- 主界面 (右侧) ---
st.title("🛡️ ChainShield 智能合约审计")
st.caption("基于 Glm-5-Flash 驱动的区块链安全审计智能体")

# 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🛡️"):
        st.markdown(msg["content"])

# 处理“开始审计”触发的自动回复
if st.session_state.get('trigger_audit', False):
    st.session_state.trigger_audit = False # 重置标志
    
    # 获取最后一条用户消息（即刚才上传的代码）
    last_user_msg = st.session_state.messages[-1]["content"]
    
    # 构造 System Prompt (包含总分总 + 颜色圆点要求)
    system_prompt = """你是一位资深的区块链安全审计专家。请对用户提供的智能合约代码进行严格审计。

【输出格式要求】必须严格遵守以下结构，并使用中文回答：

1. 📝 **审计总结**：
   - 一句话概括合约的主要风险等级（高/中/低）和核心问题。

2. 🔍 **详细分析**（必须使用以下颜色圆点标注风险等级）：
   - 🔴 **严重漏洞**：如重入攻击、权限控制缺失、整数溢出等可能导致资金损失的问题。
   - 🟡 **中度风险**：如未检查返回值、Gas 优化空间、逻辑不严谨等。
   - 🟢 **轻微问题**：如代码规范建议、注释缺失、命名不规范等。
   - *针对每个问题，请引用具体代码片段并解释原理。*

3. 💡 **修复建议**：
   - 给出修改后的代码示例或具体的防御措施。

【重要】：审计完成后，你可以继续回答用户关于该合约的任何后续问题。"""

    messages_payload = [{"role": "system", "content": system_prompt}]
    messages_payload.extend(st.session_state.messages)

    # 【新增】注入 RAG 规则库上下文
    rag_ctx = load_rag_context()
    if rag_ctx:
        messages_payload[0]["content"] += "\n\n" + rag_ctx

    # 调用 AI 生成审计报告
    with st.chat_message("assistant", avatar="🛡️"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            client = ZhipuAI(api_key=my_api_key)
            response = client.chat.completions.create(
                model="glm-5-flash",
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

# 正常的聊天输入框 (支持后续追问)
if prompt := st.chat_input("请输入智能合约代码，或针对审计报告提问..."):
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # 2. 构造 Payload (包含历史上下文，实现多轮对话)
    system_prompt = """你是一位资深的区块链安全审计专家。
    如果用户发送了代码，请按照【审计总结 -> 详细分析(🔴🟡🟢分级) -> 修复建议】的格式输出。
    如果用户在审计后继续提问，请结合之前的代码和审计结果进行解答。
    所有回复必须使用中文。"""
    
    messages_payload = [{"role": "system", "content": system_prompt}]
    messages_payload.extend(st.session_state.messages)

    # 【新增】注入 RAG 规则库上下文
    rag_ctx = load_rag_context()
    if rag_ctx:
        messages_payload[0]["content"] += "\n\n" + rag_ctx

    # 3. 调用 AI
    with st.chat_message("assistant", avatar="🛡️"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            client = ZhipuAI(api_key=my_api_key)
            response = client.chat.completions.create(
                model="glm-5-flash",
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