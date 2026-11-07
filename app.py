import streamlit as st
from zhipuai import ZhipuAI
import json
import time

# ================= 配置区域 =================
# 请将此处替换为你真实的智谱 API Key
API_KEY = "299781151d6347df8c982a8753e7cebc.oWwPRnAPGUfzPrC5" 
# ===========================================

# 1. 页面基础设置
st.set_page_config(page_title="链盾 ChainShield - 智能合约审计专家", page_icon="🛡️", layout="wide")
st.title("🛡️ 链盾 ChainShield")
st.caption("基于 GLM-5.3-Flash 驱动的区块链安全审计智能体")

# 2. 初始化会话状态 (用于保存对话历史及新增的控制状态)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好！我是链盾安全专家。请上传你的 Solidity (.sol) 文件，或直接粘贴代码片段，我将为你进行深度安全审计。"}
    ]

# 【新增】初始化暂停状态和流式生成状态
if "is_paused" not in st.session_state:
    st.session_state.is_paused = False
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

# 3. 侧边栏：文件上传与设置
with st.sidebar:
    st.header("⚙️ 控制面板")
    uploaded_file = st.file_uploader("上传 .sol 合约文件", type=["sol"])
    
    if uploaded_file is not None:
        # 读取文件内容
        file_content = uploaded_file.read().decode("utf-8")
        st.success(f"已加载文件: {uploaded_file.name}")
        
        # 触发自动审计逻辑
        if st.button("🚀 开始智能审计", type="primary"):
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
                client = ZhipuAI(api_key=API_KEY)
                response = client.chat.completions.create(
                    model="glm-5.3-flash", # 使用你购买的 Flash 模型
                    messages=[{"role": "user", "content": audit_prompt}]
                )
                
                audit_result = response.choices[0].message.content
                
                # 将结果加入对话历史
                st.session_state.messages.append({"role": "user", "content": f"请审计文件：{uploaded_file.name}"})
                st.session_state.messages.append({"role": "assistant", "content": audit_result})
                st.rerun() # 刷新页面显示结果


# 4. 主界面：对话窗口展示
# 遍历并显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 用户手动输入框 (支持追问)
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
        
        client = ZhipuAI(api_key=API_KEY)
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