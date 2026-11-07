import streamlit as st
from zhipuai import ZhipuAI
import time

# ================= 1. 页面基础设置 =================
st.set_page_config(page_title="链盾 ChainShield Pro", page_icon="🛡️", layout="wide")

# 初始化 Session State (模拟数据库)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "audit_running" not in st.session_state:
    st.session_state.audit_running = False

# ================= 2. 登录/注册 界面逻辑 =================
def show_login_page():
    st.title("🛡️ 链盾 ChainShield")
    st.caption("企业级区块链安全审计平台")
    
    tab1, tab2 = st.tabs(["🔑 登录账号", "📝 注册新账号"])
    
    with tab1:
        u = st.text_input("用户名", key="login_user")
        p = st.text_input("密码", type="password", key="login_pass")
        if st.button("进入系统", type="primary", use_container_width=True):
            if u and p: 
                # 简单模拟验证（实际项目中应连接数据库）
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error("请输入用户名和密码")
                
    with tab2:
        nu = st.text_input("设置用户名", key="reg_user")
        np_ = st.text_input("设置密码", type="password", key="reg_pass")
        if st.button("立即注册", use_container_width=True):
            if nu and np_:
                st.success(f"账号 {nu} 注册成功！请切换到登录页登录。")
            else:
                st.error("用户名和密码不能为空")

# 如果未登录，直接显示登录页并终止后续代码运行
if not st.session_state.logged_in:
    show_login_page()
    st.stop()

# ================= 3. 主功能界面 (登录后显示) =================
# 侧边栏配置
with st.sidebar:
    st.success(f"✅ 欢迎, {st.session_state.username}")
    if st.button("🚪 退出登录"):
        st.session_state.logged_in = False
        st.session_state.messages = []
        st.rerun()
        
    st.markdown("---")
    st.header("⚙️ 审计配置")
    
    # API Key 配置
    try:
        API_KEY = st.secrets["ZHIPU_API_KEY"]
    except Exception:
        API_KEY = st.text_input("智谱 API Key", type="password")
        
    st.markdown("---")
    st.header("📂 合约上传")
    
    # 文件上传功能
    uploaded_file = st.file_uploader("上传 Solidity (.sol) 文件", type=["sol", "txt"])
    
    contract_code = ""
    if uploaded_file is not None:
        contract_code = uploaded_file.getvalue().decode("utf-8")
        st.success(f"已加载文件: {uploaded_file.name}")
    else:
        # 如果没有上传文件，允许手动粘贴
        contract_code = st.text_area("或在此粘贴代码:", height=200)

# 主界面标题
st.title(f"🛡️ 链盾审计工作台 - {st.session_state.username}")

# 初始化模型客户端
client = None
if API_KEY:
    client = ZhipuAI(api_key=API_KEY)
else:
    st.warning("⚠️ 请在左侧配置 API Key 以启用 AI 功能")

# ================= 4. 对话框与深度审计逻辑 =================
# 显示历史消息
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 底部输入框
prompt = st.chat_input("输入指令（例如：'帮我审计这段代码' 或 '解释这个漏洞'）...")

# 处理发送逻辑
if prompt or (st.session_state.get("trigger_audit")):
    # 确定要分析的内容
    content_to_analyze = contract_code if contract_code else "（未提供代码，仅进行通用对话）"
    
    # 构造完整的 Prompt
    full_prompt = f"""
    [系统角色]: 你是区块链安全专家。
    [用户指令]: {prompt if prompt else '请对以下代码进行深度安全审计'}
    [参考代码]: 
    ```solidity
    {content_to_analyze}
    ```
    """

    # 添加用户消息到历史
    st.session_state.messages.append({"role": "user", "content": prompt if prompt else "开始深度审计"})
    
    # 显示 AI 思考中
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        if not client:
            full_response = "❌ 错误：未配置 API Key。"
        else:
            try:
                # 调用流式 API
                response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[{"role": "user", "content": full_prompt}],
                    stream=True,
                    temperature=0.2
                )
                
                # 流式输出循环
                for chunk in response:
                    # 【关键】检查是否需要停止
                    if not st.session_state.get("audit_running", True) and prompt == "":
                         break 
                    
                    if chunk.choices[0].delta.content is not None:
                        full_response += chunk.choices[0].delta.content
                        message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
            except Exception as e:
                full_response = f"❌ 审计出错: {str(e)}"
                message_placeholder.markdown(full_response)

        # 保存 AI 回复
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# ================= 5. 悬浮控制栏 (深度审计 & 停止) =================
# 使用 columns 布局按钮
col1, col2, col3 = st.columns([6, 2, 2])

with col1:
    pass # 占位

with col2:
    if st.button("🚀 开始深度审计", type="primary", use_container_width=True):
        st.session_state.trigger_audit = True
        st.session_state.audit_running = True
        st.rerun()

with col3:
    if st.button("🛑 随时停止", type="secondary", use_container_width=True):
        st.session_state.audit_running = False
        st.warning("⚠️ 已发送停止信号，AI 将在生成完当前片段后停止。")
        # 注意：Streamlit 的 rerun 会打断当前的执行流