import os
import fitz  # PyMuPDF
from markdownify import markdownify as md_converter
import markdown
from weasyprint import HTML, CSS

class PdfMdConverter:
    """
    Step 1: PDF 和 Markdown 之间的相互转换
    """

    def pdf_to_markdown(self, pdf_path, output_path):
        """
        功能：将 PDF 转换为 Markdown
        PDF -> HTML (保留排版结构) -> Markdown
        """
        # 检查文件是否存在
        if not os.path.exists(pdf_path):
            print(f"❌ 错误：找不到文件 {pdf_path}")
            return False

        print(f"🔄 [PDF -> MD] 正在转换: {os.path.basename(pdf_path)}")
        
        try:
            # 1. 打开 PDF
            doc = fitz.open(pdf_path)
            full_html = ""
            
            # 2. 逐页提取 HTML
            for page in doc:
                full_html += page.get_text("html")
            
            # 3. 将 HTML 转换为 Markdown
            # heading_style="ATX" 表示使用 # ## ### 这种标题风格
            # strip=['a'] 表示去除超链接标签但保留文字
            md_text = md_converter(full_html, heading_style="ATX")
            
            # 4. 简单的清洗：去除连续的空行，让文档更紧凑
            lines = md_text.splitlines()
            # 过滤掉只有空白符的行，但保留必要的段落间隔
            clean_lines = [line for line in lines if line.strip()] 
            final_md = "\n\n".join(clean_lines)

            # 5. 保存文件
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_md)
            
            print(f"✅ [成功] 已保存至: {output_path}")
            return True

        except Exception as e:
            print(f"❌ [失败] PDF 转 Markdown 出错: {e}")
            return False

    def markdown_to_pdf(self, md_path, output_path):
        """
        功能：将 Markdown 转换为 PDF
        原理：Markdown -> HTML (渲染) -> PDF (打印)
        关键：使用 CSS 控制 PDF 的样式，支持高亮显示
        """
        if not os.path.exists(md_path):
            print(f"❌ 错误：找不到文件 {md_path}")
            return False

        print(f"🔄 [MD -> PDF] 正在转换: {os.path.basename(md_path)}")

        try:
            # 1. 读取 Markdown 内容
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()

            # 2. MD 转 HTML (开启表格支持)
            html_body = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])

            # 3. 定义 PDF 样式
            # 预埋了 .highlight 样式，未来大模型审核结果高亮时会用到
            css_style = CSS(string='''
                @page { size: A4; margin: 2.5cm; }
                body { 
                    font-family: "Microsoft YaHei", "SimHei", sans-serif; 
                    font-size: 11pt; 
                    line-height: 1.6;
                    color: #333;
                }
                h1, h2, h3 { color: #2c3e50; margin-top: 1em; }
                h1 { border-bottom: 2px solid #eee; padding-bottom: 10px; }
                
                /* 表格样式 */
                table { 
                    border-collapse: collapse; 
                    width: 100%; 
                    margin: 20px 0; 
                    font-size: 10pt;
                }
                th, td { 
                    border: 1px solid #dfe2e5; 
                    padding: 8px 12px; 
                }
                th { background-color: #f8f9fa; font-weight: bold; }
                
                /* 代码块样式 */
                pre { background: #f6f8fa; padding: 10px; border-radius: 4px; }
                code { font-family: Consolas, monospace; background: #f0f0f0; padding: 2px 4px; }

                /* 关键：高亮样式 (未来使用) */
                mark, .highlight { 
                    background-color: #ffe066; 
                    padding: 2px 0;
                    border-radius: 2px;
                }
            ''')

            # 4. 组装完整的 HTML 页面
            final_html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="utf-8"></head>
            <body>
            {html_body}
            </body>
            </html>
            """

            # 5. 生成 PDF
            HTML(string=final_html).write_pdf(output_path, stylesheets=[css_style])
            
            print(f"✅ [成功] 已保存至: {output_path}")
            return True

        except Exception as e:
            print(f"❌ [失败] Markdown 转 PDF 出错: {e}")
            return False