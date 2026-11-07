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
st.sidebar.title(f"👤 {st.session_state.username}")
if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# --- Key 设置模块 (带确认勾选框 & 真实验证 & 严格脱敏 & 自动清空) ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ API 设置")

# 获取当前数据库中的 Key
current_key_db = get_api_key(st.session_state.username)

# 【严格脱敏展示】如果数据库里有 key，只显示前4位和后4位
if current_key_db:
    if len(current_key_db) > 8:
        masked_key = current_key_db[:4] + "****" + current_key_db[-4:]
    else:
        masked_key = "******"
    st.sidebar.success(f"✅ 当前已配置 Key: `{masked_key}`")
else:
    st.sidebar.warning("⚠️ 尚未配置 Key")

# 初始化输入框的状态变量，确保刷新时能控制它的值
if 'input_key_value' not in st.session_state:
    st.session_state.input_key_value = ""

with st.sidebar.expander("配置新的 API Key", expanded=(not current_key_db)):
    # 【关键点】value 绑定 session_state，type=password 确保即使有缓存也是黑点
    new_key_input = st.text_input(
        "输入新的 ZhipuAI Key", 
        value=st.session_state.input_key_value, 
        type="password", 
        placeholder="sk-..."
    )
    
    confirm_check = st.checkbox("我已阅读并确认 Key 将加密存储", key="key_confirm")
    
    if st.button("保存 Key"):
        if not confirm_check:
            st.error("请先勾选确认框！")
        elif not new_key_input:
            st.warning("请输入 Key")
        else:
            # 【真实可用性验证】以"可以使用"为保存标准
            with st.spinner("⏳ 正在连接智谱 AI 验证 Key 可用性..."):
                try:
                    test_client = ZhipuAI(api_key=new_key_input)
                    # 发送一个极小的请求测试连通性
                    test_response = test_client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=5
                    )
                    
                    # 测试通过，说明 Key 可用，执行保存
                    update_api_key(st.session_state.username, new_key_input)
                    
                    # 【关键修复】保存成功后，强制清空输入框的状态变量
                    st.session_state.input_key_value = ""
                    
                    st.success("✅ Key 验证可用，已安全保存！输入框已清空。")
                    st.rerun() # 刷新页面，此时输入框会因为 value="" 而变空
                    
                except Exception as e:
                    st.error(f"❌ Key 验证失败：{str(e)}")
                    st.warning("请检查 Key 是否正确，或账户余额是否充足。")

# ================= 审计功能模块 =================
st.sidebar.markdown("---")
st.sidebar.subheader("📂 上传合约文件")

# 初始化审计触发器
if 'trigger_audit' not in st.session_state:
    st.session_state.trigger_audit = False
if 'audit_content' not in st.session_state:
    st.session_state.audit_content = ""

uploaded_file = st.sidebar.file_uploader("上传 .sol 合约文件", type=["sol"])

# 处理文件上传后的按钮点击
if uploaded_file is not None:
    # 读取文件内容
    file_content = uploaded_file.read().decode("utf-8")
    st.sidebar.success(f"已加载文件: {uploaded_file.name}")
    
    if st.sidebar.button("🚀 开始智能审计", type="primary"):
        api_key = get_api_key(st.session_state.username)
        if not api_key:
            st.sidebar.error("⚠️ 请先在上方配置 API Key！")
        else:
            # 设置触发器和内容
            st.session_state.audit_content = f"请审计以下智能合约文件：\n\n```solidity\n{file_content}\n```"
            st.session_state.trigger_audit = True
            st.rerun()

# 检查是否有 Key (如果没有 Key，禁止进行后续聊天操作，但不影响上传)
my_api_key = get_api_key(st.session_state.username)
if not my_api_key:
    st.info("💡 提示：请先在左侧栏配置您的 API Key 才能开始审计对话。")
    # 注意：这里不再使用 st.stop()，以免阻断页面渲染导致看不到上传组件

# --- 聊天界面 ---
st.title("🛡️ ChainShield 智能合约审计")
st.caption("基于 GLM-4-Flash 驱动的区块链安全审计智能体")

# 初始化历史记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# 【关键修复】处理审计触发逻辑
# 如果是通过点击“开始审计”触发的刷新，且还没有把这条消息加入历史，则加入
if st.session_state.trigger_audit and st.session_state.audit_content:
    # 检查最后一条消息是不是这个内容，防止重复添加
    if not st.session_state.messages or st.session_state.messages[-1]['content'] != st.session_state.audit_content:
        st.session_state.messages.append({"role": "user", "content": st.session_state.audit_content})
        
        # 构造 AI 回复
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
        
        # 重置触发器，防止刷新页面重复审计
        st.session_state.trigger_audit = False
        st.session_state.audit_content = ""
        st.rerun() 

# 渲染历史消息 (带头像)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🛡️"):
        st.markdown(msg["content"])

# 手动输入框 (支持直接粘贴代码)
if prompt := st.chat_input("或者在此处直接粘贴智能合约代码..."):
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # 2. 构造 Prompt
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

    # 3. 调用 AI
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