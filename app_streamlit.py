import streamlit as st
import os
import tempfile
import shutil
from streamlit_pdf_viewer import pdf_viewer 

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

# (❌ 原来的 show_pdf 函数删掉，不再需要了)

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
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, uploaded_file.name)
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.info(f"正在处理: {uploaded_file.name}")
        
        base_name = os.path.splitext(uploaded_file.name)[0]
        output_path = ""
        success = False
        
        if st.button("🚀 开始处理", type="primary"):
            with st.spinner("正在转换中，请稍候..."):
                try:
                    # --- 分发逻辑 ---
                    if "OCR" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}_ocr.html")
                        converter = RapidOcrConverter(poppler_path=None) 
                        success = converter.scanned_pdf_to_html(input_path, output_path)

                    elif "数字 PDF" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}_digital.html")
                        converter = DocToHtmlConverter()
                        success = converter.pdf_to_html(input_path, output_path)

                    elif "Word" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}.html")
                        converter = DocToHtmlConverter()
                        success = converter.word_to_html(input_path, output_path)

                    elif "PDF -> Markdown" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}.md")
                        converter = PdfMdConverter()
                        success = converter.pdf_to_markdown(input_path, output_path)

                    elif "Markdown -> PDF" in mode:
                        output_path = os.path.join(temp_dir, f"{base_name}_restored.pdf")
                        converter = PdfMdConverter()
                        success = converter.markdown_to_pdf(input_path, output_path)

                    # --- 结果展示 ---
                    if success and os.path.exists(output_path):
                        st.success("✅ 转换成功！")
                        
                        # 下载按钮
                        with open(output_path, "rb") as f:
                            st.download_button(
                                label="💾 下载结果文件",
                                data=f,
                                file_name=os.path.basename(output_path),
                                mime="application/octet-stream"
                            )
                        
                        st.markdown("### 📄 结果预览")
                        
                        if output_path.endswith(".html"):
                            with open(output_path, "r", encoding="utf-8") as f:
                                st.components.v1.html(f.read(), height=600, scrolling=True)
                        
                        elif output_path.endswith(".md"):
                            with open(output_path, "r", encoding="utf-8") as f:
                                st.markdown(f.read())
                        
                        elif output_path.endswith(".pdf"):
                            # ✅ 使用新库进行预览 (它把PDF渲染成图片，Chrome 不会拦截)
                            # width 设置为 800 或更大以适应宽屏
                            pdf_viewer(input=output_path, width=800, height=1000)

                    else:
                        st.error("❌ 转换失败，请检查文件内容或日志。")

                except Exception as e:
                    st.error(f"发生系统错误: {e}")
                    # 打印详细堆栈方便调试
                    import traceback
                    st.text(traceback.format_exc())
else:
    st.info("👈 请先在左侧侧边栏上传文件")