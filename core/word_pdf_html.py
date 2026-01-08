import os
import fitz  # PyMuPDF
import mammoth

class DocToHtmlConverter:
    """
    Word 和 PDF 转换为 HTML
    """

    def word_to_html(self, docx_path, output_path):
        """
        功能：Word (.docx) -> HTML
        使用 mammoth，只提取语义内容。
        """
        if not os.path.exists(docx_path):
            print(f"❌ 错误：找不到文件 {docx_path}")
            return False

        print(f"🔄 [Word -> HTML] 正在转换: {os.path.basename(docx_path)}")

        try:
            with open(docx_path, "rb") as docx_file:
                # convert_to_html 会把 word 里的图片转成 base64 内嵌在 html 里
                result = mammoth.convert_to_html(docx_file)
                html_content = result.value
                messages = result.messages  # 警告信息（如果有的话）

            # 简单的包装一下，让它变成合法的 HTML 文档
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{os.path.basename(docx_path)}</title>
                <style>
                    body {{ font-family: sans-serif; max-width: 800px; margin: 20px auto; line-height: 1.6; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ccc; padding: 8px; }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_html)
            
            print(f"✅ [成功] 已保存至: {output_path}")
            if messages:
                print(f"   ⚠️ 转换警告: {[m.message for m in messages]}")
            return True

        except Exception as e:
            print(f"❌ [失败] Word 转 HTML 出错: {e}")
            return False

    def pdf_to_html(self, pdf_path, output_path):
        """
        功能：PDF -> HTML
        特点：保留 PDF 的原始布局结构
        """
        if not os.path.exists(pdf_path):
            print(f"❌ 错误：找不到文件 {pdf_path}")
            return False

        print(f"🔄 [PDF -> HTML] 正在转换: {os.path.basename(pdf_path)}")
        
        try:
            doc = fitz.open(pdf_path)
            body_content = ""
            
            for i, page in enumerate(doc):
                # 插入分页标记，方便查看
                #body_content += f'<div class="page-marker">--- 第 {i+1} 页 ---</div>'
                # get_text("html") 会生成带有绝对定位样式的 HTML
                body_content += page.get_text("html")
                #body_content += "<hr/>"
            
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    .page-marker {{ background: #eee; padding: 5px; font-weight: bold; margin-top: 20px; }}
                </style>
            </head>
            <body>
                {body_content}
            </body>
            </html>
            """
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_html)
                
            print(f"✅ [成功] 已保存至: {output_path}")
            return True

        except Exception as e:
            print(f"❌ [失败] PDF 转 HTML 出错: {e}")
            return False