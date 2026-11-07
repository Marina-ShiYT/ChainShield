import streamlit as st
from zhipuai import ZhipuAI
import time

# ================= 1. 页面基础设置 =================
st.set_page_config(page_title="链盾 ChainShield Pro", page_icon="🛡️", layout="wide")

# ================= 2. 初始化会话状态 (Session State) =================
# 用户状态
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# 对话历史
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好！我是链盾安全专家。请上传你的 Solidity (.sol) 文件，或在对话框输入指令，我将为你进行深度安全审计。"}
    ]

# 控制状态 (流式输出与停止)
if "is_paused" not in st.session_state:
    st.session_state.is_paused = False
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

# ================= 3. 模拟登录/注册 界面逻辑 =================
def show_login_page():
    st.title("🛡️ 链盾 ChainShield Pro")
    st.caption("企业级区块链智能合约审计平台")
    
    tab1, tab2 = st.tabs(["🔑 用户登录", "📝 新用户注册"])
    
    with tab1:
        u = st.text_input("账号", key="login_user")
        p = st.text_input("密码", type="password", key="login_pass")
        if st.button("进入系统", type="primary", use_container_width=True):
            if u and p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error("请输入账号和密码")
                
    with tab2:
        st.info("模拟注册：输入任意账号密码即可创建账户")
        ru = st.text_input("设置账号", key="reg_user")
        rp = st.text_input("设置密码", type="password", key="reg_pass")
        if st.button("立即注册并登录", use_container_width=True):
            if ru and rp:
                st.session_state.logged_in = True
                st.session_state.username = ru
                st.success(f"欢迎 {ru}，注册成功！")
                time.sleep(1)
                st.rerun()

# ================= 4. 主应用界面逻辑 =================
def show_main_app():
    # 顶部导航栏
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title(f"🛡️ 链盾 ChainShield - {st.session_state.username} 的工作台")
    with col2:
        if st.button("退出登录"):
            st.session_state.logged_in = False
            st.session_state.messages = [] 
            st.rerun()

    st.divider()

    # 左侧：控制面板 (Key配置 + 文件上传 + 停止按钮)
    with st.sidebar:
        st.header("⚙️ 审计控制台")
        
        # 【核心】安全获取 API Key (沿用之前的安全方案)
        try:
            API_KEY = st.secrets["ZHIPU_API_KEY"]
        except Exception:
            st.sidebar.warning("⚠️ 未检测到云端密钥，请手动输入")
            API_KEY = st.sidebar.text_input("智谱 API Key", type="password")
            
        if not API_KEY:
            st.error("🚫 请先配置 API Key 才能使用！")
            st.stop()
            
        client = ZhipuAI(api_key=API_KEY)
        
        st.divider()
        
        # 【功能】文件上传
        uploaded_file = st.file_uploader("上传 .sol 合约文件", type=["sol"])
        
        if uploaded_file is not None:
            file_content = uploaded_file.read().decode("utf-8")
            st.success(f"已加载: {uploaded_file.name}")
            
            # 【功能】开始审计按钮
            if st.button("🚀 开始深度审计", type="primary", disabled=st.session_state.is_generating):
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
                
                st.session_state.messages.append({"role": "user", "content": f"请审计文件：{uploaded_file.name}"})
                process_ai_response(client, audit_prompt, is_audit=True)

        st.divider()
        
        # 【功能】随时停止按钮
        if st.session_state.is_generating:
            st.warning("⚠️ AI 正在生成中...")
            if st.button("⏹️ 停止生成", type="secondary"):
                st.session_state.is_paused = True
                st.success("已发送停止指令，AI 将在当前词元后停止。")
        else:
            st.info("💡 提示：生成过程中可点击停止")

    # 右侧：对话窗口展示 (完全保留你的核心代码逻辑)
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # 【功能】底部对话框 (支持追问)
    if prompt := st.chat_input("你可以针对审计报告继续提问，例如：'如何修复第3行的重入漏洞？'"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 构造包含上下文的请求
        messages_payload = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        
        # 调用 AI 进行流式回复
        process_ai_response(client, prompt, messages_payload=messages_payload)

# ================= 5. AI 处理核心函数 (封装流式逻辑) =================
def process_ai_response(client, prompt_text=None, messages_payload=None, is_audit=False):
    """
    处理 AI 调用的通用函数，支持流式输出和暂停功能
    """
    if is_audit:
        api_messages = [{"role": "user", "content": prompt_text}]
    else:
        api_messages = messages_payload

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        st.session_state.is_generating = True
        st.session_state.is_paused = False
        
        try:
            response = client.chat.completions.create(
                model="glm-4-flash", # 保持使用 glm-4-flash
                messages=api_messages,
                stream=True 
            )
            
            for chunk in response:
                # 【核心】检查是否被暂停
                if st.session_state.is_paused:
                    full_response += "\n\n*(⚠️ 用户已手动停止生成)*"
                    break
                    
                if chunk.choices[0].delta.content is not None:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            st.error(f"❌ 调用失败: {str(e)}")
            full_response = f"Error: {str(e)}"
        
        finally:
            st.session_state.is_generating = False
            st.session_state.is_paused = False
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.rerun()

# ================= 6. 路由控制 =================
if not st.session_state.logged_in:
    show_login_page()
else:
    show_main_app()