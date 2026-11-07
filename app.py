import streamlit as st
from zhipuai import ZhipuAI
import time

# ================= 1. 页面基础设置 =================
st.set_page_config(page_title="链盾 ChainShield", page_icon="🛡️", layout="wide")
st.title("🛡️ 链盾 ChainShield")
st.caption("基于 GLM-4-Flash 驱动的区块链安全审计智能体")

# ================= 2. 侧边栏：用户身份与配置 =================
st.sidebar.header("👤 用户身份验证")

# 【新增】账号输入部分
user_account = st.sidebar.text_input(
    "审计员账号 / User ID", 
    placeholder="例如: auditor_007"
)

st.sidebar.markdown("---") # 分割线

# API Key 配置逻辑
try:
    # 尝试从云端 Secrets 获取
    API_KEY = st.secrets["ZHIPU_API_KEY"]
except Exception:
    # 获取不到则手动输入
    st.sidebar.warning("⚠️ 未检测到云端密钥，请手动输入")
    API_KEY = st.sidebar.text_input("智谱 API Key", type="password")

# ================= 3. 初始化模型 =================
# 只有当 Key 存在时才初始化，防止报错
if API_KEY:
    client = ZhipuAI(api_key=API_KEY)
else:
    st.error("🚫 请先在左侧配置 API Key 才能使用！")
    st.stop()

# 简单的登录检查逻辑
if not user_account:
    st.info("👈 请先在左侧输入您的**审计员账号**以开始工作！")
    st.stop() 

# 如果账号输入了，显示欢迎语
st.success(f"✅ 欢迎您，审计员 **{user_account}**！系统已就绪。")

# ================= 4. 侧边栏：业务操作区 =================
st.sidebar.header("📝 合约代码输入")
contract_code = st.sidebar.text_area(
    "请粘贴 Solidity 合约代码：", 
    height=300, 
    placeholder="pragma solidity ^0.8.0; ..."
)

analyze_button = st.sidebar.button("🚀 开始深度审计", type="primary")

# ================= 5. 主界面：显示结果 =================
if analyze_button:
    if not contract_code:
        st.warning("⚠️ 请先在左侧粘贴合约代码！")
    else:
        with st.spinner(f"🤖 AI 正在为 {user_account} 分析合约漏洞..."):
            try:
                # 构造 Prompt
                prompt = f"""你是一位资深的区块链安全专家。当前审计员：{user_account}。
                
                请审计以下 Solidity 智能合约代码，找出潜在的安全漏洞（如重入攻击、整数溢出、权限控制缺失等）。
                
                代码内容：
                {contract_code}
                
                请按以下格式输出报告：
                1. **风险等级**：(高/中/低)
                2. **漏洞名称**：
                3. **问题描述**：
                4. **修复建议**：
                
                如果没有发现明显漏洞，请直接回复“✅ 代码看起来非常安全”。"""

                # 调用智谱 API
                response = client.chat.completions.create(
                    model="glm-4-flash", 
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                result = response.choices[0].message.content
                
                # 显示结果
                st.success("✅ 审计完成！")
                st.markdown(result)
                
            except Exception as e:
                st.error(f"❌ 调用 AI 失败：{str(e)}")
else:
    # 初始状态显示的提示
    if contract_code: 
        st.info("👈 代码已就绪，点击侧边栏的【开始深度审计】按钮")
    elif user_account:
        st.info("👈 请在左侧粘贴代码并点击开始审计")