
import streamlit as st
from zhipuai import ZhipuAI
import json
import os
import time

# ================= 1. 页面基础设置 =================
st.set_page_config(
    page_title="链盾 ChainShield Pro",
    page_icon="🛡️",
    layout="wide"
)

# ================= 2. 核心工具函数 =================

def load_vuln_rules(file_path="vuln_rules.json"):
    """加载漏洞规则库"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return []
    except Exception:
        return []

def build_audit_prompt(code_content, rules):
    """构建专业审计 Prompt，要求 AI 输出结构化 JSON"""
    rules_text = ""
    if rules:
        rules_text = "【已知漏洞特征库】\n"
        for i, rule in enumerate(rules, 1):
            rules_text += f"{i}. {rule['name']}：{rule['description']}\n"
            if 'code_pattern' in rule and rule['code_pattern']:
                rules_text += f"   关键特征：{rule['code_pattern']}\n"
            rules_text += "\n"

    prompt = f"""你是一位拥有10年经验的区块链安全审计专家，精通 Solidity 智能合约安全审计。

{rules_text}
请对以下 Solidity 代码进行严格的安全审计。

【代码内容】：
```solidity
{code_content}
```

【输出要求】：
1. 请严格按照以下 JSON 格式输出分析结果，不要输出任何多余的文字、解释或 Markdown 代码块标记。
2. 如果代码安全无漏洞，vulnerabilities 数组为空。
3. risk_level 只能取 "High"、"Medium" 或 "Low"。

【JSON 输出格式】：
{{
    "contract_name": "合约名称(从代码中推断)",
    "overall_risk": "High/Medium/Low/Safe",
    "summary": "简要总结代码安全状况（2-3句话）",
    "stats": {{
        "high_count": 高危漏洞数量,
        "medium_count": 中危漏洞数量,
        "low_count": 低危漏洞数量
    }},
    "vulnerabilities": [
        {{
            "type": "漏洞类型名称",
            "risk_level": "High/Medium/Low",
            "location": "涉及的函数名或代码位置",
            "description": "漏洞原理描述",
            "fix_suggestion": "修复建议或修复后的代码片段"
        }}
    ],
    "optimization_suggestions": ["Gas优化或代码规范建议1", "建议2"]
}}
"""
    return prompt

def parse_audit_result(raw_text):
    """解析 AI 返回的 JSON 结果，增强容错"""
    text = raw_text.strip()
    # 去掉可能的 ```json ... ``` 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else lines[1] if len(lines) > 1 else ""
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "overall_risk": "Unknown",
            "summary": "AI 返回结果格式异常，请尝试重新审计。",
            "stats": {"high_count": 0, "medium_count": 0, "low_count": 0},
            "vulnerabilities": [],
            "optimization_suggestions": []
        }

def get_risk_color(risk_level):
    """获取风险等级对应的颜色"""
    color_map = {
        "High": "#ff4444",
        "Medium": "#ff9800",
        "Low": "#4caf50",
        "Safe": "#4caf50",
    }
    return color_map.get(risk_level, "#666666")

def get_risk_emoji(risk_level):
    """获取风险等级对应的表情"""
    emoji_map = {
        "High": "🔴",
        "Medium": "🟡",
        "Low": "🟢",
        "Safe": "✅",
    }
    return emoji_map.get(risk_level, "⚪")

def display_audit_report(result):
    """专业排版展示审计报告"""
    contract_name = result.get("contract_name", "未知合约")
    overall_risk = result.get("overall_risk", "Unknown")
    summary = result.get("summary", "暂无摘要")
    stats = result.get("stats", {"high_count": 0, "medium_count": 0, "low_count": 0})
    vulnerabilities = result.get("vulnerabilities", [])
    optimization = result.get("optimization_suggestions", [])

    # === 第一部分：审计概览横幅 + 指标卡片 ===
    st.markdown("---")
    
    risk_color = get_risk_color(overall_risk)
    risk_emoji = get_risk_emoji(overall_risk)
    
    # 左侧横幅 + 右侧指标卡片
    col_banner, col_metric1, col_metric2, col_metric3 = st.columns([2.5, 1, 1, 1])
    
    with col_banner:
        st.markdown(f"""
        <div style="background-color: {risk_color}15; border-left: 5px solid {risk_color}; 
                    padding: 18px; border-radius: 6px;">
            <h3 style="margin: 0 0 4px 0; color: {risk_color}; font-size: 20px;">{risk_emoji} 审计完成</h3>
            <p style="margin: 0; font-size: 14px; color: #555;">合约：{contract_name}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_metric1:
        st.metric(
            label="🔴 高危漏洞",
            value=stats.get("high_count", 0),
            delta_color="inverse" if stats.get("high_count", 0) > 0 else "normal"
        )
    with col_metric2:
        st.metric(
            label="🟡 中危漏洞",
            value=stats.get("medium_count", 0),
            delta_color="inverse" if stats.get("medium_count", 0) > 0 else "normal"
        )
    with col_metric3:
        st.metric(
            label="🟢 低危问题",
            value=stats.get("low_count", 0)
        )

    # 安全总评
    st.markdown(f"**安全总评：** {summary}")
    st.markdown("---")

    # === 第二部分：漏洞详情表格 ===
    st.subheader("🔍 漏洞详情")
    
    if vulnerabilities:
        table_data = []
        for vuln in vulnerabilities:
            risk = vuln.get("risk_level", "Unknown")
            table_data.append({
                "风险等级": f"{get_risk_emoji(risk)} {risk}",
                "漏洞类型": vuln.get("type", "未知类型"),
                "代码位置": vuln.get("location", "未标注"),
                "问题描述": vuln.get("description", "暂无描述"),
                "修复建议": vuln.get("fix_suggestion", "暂无建议")
            })
        
        import pandas as pd
        df = pd.DataFrame(table_data)
        
        st.dataframe(
            df,
            column_config={
                "风险等级": st.column_config.TextColumn("风险等级", width="medium"),
                "漏洞类型": st.column_config.TextColumn("漏洞类型", width="medium"),
                "代码位置": st.column_config.TextColumn("代码位置", width="medium"),
                "问题描述": st.column_config.TextColumn("问题描述", width="large"),
                "修复建议": st.column_config.TextColumn("修复建议", width="large"),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("✅ 未检测到已知高危漏洞！代码整体安全性良好。")
        st.info("建议持续关注最新安全动态，定期进行代码审查。")

    st.markdown("---")

    # === 第三部分：优化建议 ===
    if optimization:
        st.subheader("💡 优化建议")
        for i, suggestion in enumerate(optimization, 1):
            st.info(f"**建议 {i}：** {suggestion}")

    st.markdown("---")
    st.caption(f"🛡️ 审计报告生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')} | 链盾 ChainShield Pro")

# ================= 3. 初始化会话状态 =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好！我是链盾安全专家。系统已加载专业漏洞规则库。请上传 .sol 文件开始深度审计。"}
    ]

if "is_paused" not in st.session_state:
    st.session_state.is_paused = False
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

# 审计触发状态
if "trigger_audit" not in st.session_state:
    st.session_state.trigger_audit = False
if "audit_file_name" not in st.session_state:
    st.session_state.audit_file_name = ""
if "audit_file_content" not in st.session_state:
    st.session_state.audit_file_content = ""

# ================= 4. 登录/注册 界面逻辑 =================
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

# ================= 5. 主应用界面逻辑 =================
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

    # ================= 侧边栏 =================
    with st.sidebar:
        st.header("⚙️ 审计控制台")
        
        # API Key 获取
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
        
        # 加载漏洞规则库
        vuln_rules = load_vuln_rules()
        if vuln_rules:
            st.success(f"已加载 {len(vuln_rules)} 条漏洞检测规则")
        else:
            st.warning("未找到 vuln_rules.json，使用通用审计模式")
        
        st.divider()
        
        # 文件上传
        uploaded_file = st.file_uploader("上传 .sol 合约文件", type=["sol"])
        
        if uploaded_file is not None:
            file_content = uploaded_file.read().decode("utf-8")
            st.success(f"已加载: {uploaded_file.name}")
            
            # 开始审计按钮
            if st.button("🚀 开始深度审计", type="primary", disabled=st.session_state.is_generating):
                # 设置审计触发状态
                st.session_state.trigger_audit = True
                st.session_state.audit_file_name = uploaded_file.name
                st.session_state.audit_file_content = file_content
                st.session_state.is_generating = True
                st.rerun()

        st.divider()
        
        # 停止生成按钮
        if st.session_state.is_generating:
            st.warning("⚠️ AI 正在生成中...")
            if st.button("⏹️ 停止生成", type="secondary"):
                st.session_state.is_paused = True
                st.success("已发送停止指令，AI 将在当前词元后停止。")
        else:
            st.info("💡 提示：生成过程中可点击停止")

    # ================= 处理审计触发 =================
    if st.session_state.trigger_audit and st.session_state.audit_file_content:
        file_content = st.session_state.audit_file_content
        file_name = st.session_state.audit_file_name
        
        # 添加用户消息
        st.session_state.messages.append({
            "role": "user", 
            "content": f"📄 请审计文件：**{file_name}**"
        })
        
        # 显示加载状态
        with st.spinner("🔍 正在深度分析合约代码，请稍候..."):
            try:
                # 构建专业审计 Prompt
                audit_prompt = build_audit_prompt(file_content, vuln_rules)
                
                # 调用 AI
                response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[{"role": "user", "content": audit_prompt}],
                    temperature=0.1
                )
                
                raw_text = response.choices[0].message.content
                
                # 解析 JSON 结果
                result = parse_audit_result(raw_text)
                
                # 添加审计报告消息
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "audit_report",
                    "report_data": result
                })
                
            except Exception as e:
                st.error(f"❌ 审计调用失败: {str(e)}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"❌ 审计失败：{str(e)}"
                })
            finally:
                st.session_state.trigger_audit = False
                st.session_state.is_generating = False
                st.rerun()

    # ================= 对话窗口展示 =================
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            if message.get("content") == "audit_report" and "report_data" in message:
                # 专业排版展示审计报告
                display_audit_report(message["report_data"])
            else:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # ================= 底部对话框 =================
    if prompt := st.chat_input("你可以针对审计报告继续提问，例如：'如何修复第3行的重入漏洞？'"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 构造包含上下文的请求（排除审计报告消息）
        messages_payload = [
            {"role": m["role"], "content": m["content"]} 
            for m in st.session_state.messages 
            if m.get("content") != "audit_report"
        ]
        
        # 调用 AI 进行流式回复
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            st.session_state.is_generating = True
            st.session_state.is_paused = False
            
            try:
                response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=messages_payload,
                    stream=True
                )
                
                for chunk in response:
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