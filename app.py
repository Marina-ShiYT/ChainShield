import streamlit as st
from zhipuai import ZhipuAI
import time

# ================= 1. 页面基础设置 =================
st.set_page_config(page_title="链盾 ChainShield", page_icon="🛡️", layout="wide")
st.title("🛡️ 链盾 ChainShield")
st.caption("基于 GLM-4-Flash 驱动的区块链安全审计智能体")

# ================= 2. 安全获取 API Key =================
# 尝试从 Streamlit Secrets 获取（云端部署时）
try:
    API_KEY = st.secrets["ZHIPU_API_KEY"]
except Exception:
    # 如果获取不到（比如本地运行），则使用侧边栏输入
    st.sidebar.warning("⚠️ 未检测到云端密钥，请在下方手动输入 API Key")
    API_KEY = st.sidebar.text_input("请输入智谱 API Key", type="password")

# ================= 3. 初始化模型 =================
if API_KEY:
    client = ZhipuAI(api_key=API_KEY)
else:
    st.error("🚫 请先配置 API Key 才能使用！")
    st.stop()

# ================= 4. 侧边栏：用户输入 =================
st.sidebar.header("📝 合约代码输入")
contract_code = st.sidebar.text_area("请粘贴 Solidity 合约代码：", height=300, placeholder="pragma solidity ^0.8.0; ...")

analyze_button = st.sidebar.button("🚀 开始审计", type="primary")

# ================= 5. 主界面：显示结果 =================
if analyze_button:
    if not contract_code:
        st.warning("⚠️ 请先在左侧粘贴合约代码！")
    else:
        with st.spinner("🤖 AI 正在深度分析合约漏洞..."):
            try:
                # 构造 Prompt
                prompt = f"""你是一位资深的区块链安全专家。请审计以下 Solidity 智能合约代码，找出潜在的安全漏洞（如重入攻击、整数溢出、权限控制缺失等）。
                
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
    st.info("👈 请在左侧粘贴代码并点击开始审计")