import streamlit as st
import os
import tempfile
import shutil

# === 导入共用核心模块 ===
try:
    from core.rapidocr import RapidOcrConverter
    from core.word_pdf_html import DocToHtmlConverter
    from core.pdf_md import PdfMdConverter
except ImportError as e:
    st.error(f"核心模块导入失败: {e}")

# === 页面配置 ===
st.set_page_config(page_title="智能文档审计系统", layout="wide", page_icon="📄")

st.title("📄 智能文档审计系统 (Web版)")
st.markdown("支持 OCR、PDF转Markdown、Word转HTML 等多种格式互转。")

# === 侧边栏配置 ===
with st.sidebar:
    st.header("功能设置")
    mode = st.radio(
        "选择功能模式",
        (
            "📄 扫描件 OCR -> HTML",
            "💻 数字 PDF -> HTML",
            "📝 Word -> HTML",
            "⬇️ PDF -> Markdown",
            "⬆️ Markdown -> PDF"
        )
    )
    st.markdown("---")
    uploaded_file = st.file_uploader("请上传文件", type=["pdf", "docx", "md"])

# === 主逻辑区域 ===
if uploaded_file:
    # 创建临时文件夹处理文件 (Web版不能直接读用户硬盘)
    with tempfile.TemporaryDirectory() as temp_dir:
        # 保存上传文件
        input_path = os.path.join(temp_dir, uploaded_file.name)
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.info(f"正在处理: {uploaded_file.name}")
        
        # 准备输出路径
        base_name = os.path.splitext(uploaded_file.name)[0]
        output_path = ""
        success = False
        
        # 按钮触发
        if st.button("🚀 开始处理", type="primary"):
            with st.spinner("正在转换中，请稍候..."):
                try:
                    # --- OCR 模式 ---
                    if "OCR" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}_ocr.html")
                        # 关键点：Web版在Linux运行，poppler通常已安装在系统路径
                        # 所以这里传 None，让 pdf2image 自动查找
                        converter = RapidOcrConverter(poppler_path=None) 
                        success = converter.scanned_pdf_to_html(input_path, output_path)

                    # --- 数字 PDF ---
                    elif "数字 PDF" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}_digital.html")
                        converter = DocToHtmlConverter()
                        success = converter.pdf_to_html(input_path, output_path)

                    # --- Word 转 HTML ---
                    elif "Word" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}.html")
                        converter = DocToHtmlConverter()
                        success = converter.word_to_html(input_path, output_path)

                    # --- PDF 转 MD ---
                    elif "PDF -> Markdown" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}.md")
                        converter = PdfMdConverter()
                        success = converter.pdf_to_markdown(input_path, output_path)

                    # --- MD 转 PDF ---
                    elif "Markdown -> PDF" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}_restored.pdf")
                        converter = PdfMdConverter()
                        success = converter.markdown_to_pdf(input_path, output_path)

                    # --- 结果展示 ---
                    if success and os.path.exists(output_path):
                        st.success("✅ 转换成功！")
                        
                        # 1. 提供下载按钮
                        with open(output_path, "rb") as f:
                            st.download_button(
                                label="💾 下载转换结果",
                                data=f,
                                file_name=os.path.basename(output_path),
                                mime="application/octet-stream"
                            )
                        
                        # 2. 预览区域 (HTML或MD)
                        st.markdown("### 📄 结果预览")
                        if output_path.endswith(".html"):
                            with open(output_path, "r", encoding="utf-8") as f:
                                st.components.v1.html(f.read(), height=600, scrolling=True)
                        elif output_path.endswith(".md"):
                            with open(output_path, "r", encoding="utf-8") as f:
                                st.markdown(f.read())
                    else:
                        st.error("❌ 转换失败，请检查文件内容或日志。")

                except Exception as e:
                    st.error(f"发生系统错误: {e}")
else:
    st.info("👈 请先在左侧侧边栏上传文件")