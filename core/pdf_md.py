import fitz  # PyMuPDF
import os
import frontmatter  # 处理 YAML 头信息
from markdown import markdown
from weasyprint import HTML, CSS

class PdfMdConverter:
    def __init__(self):
        pass

    # ==========================================
    # 1. 智能提取：PDF -> Markdown (带样式和元数据)
    # ==========================================
    def pdf_to_markdown(self, pdf_path, output_path):
        """
        将 PDF 转换为 Markdown，保留标题层级，提取页眉页脚到 YAML 头部
        """
        try:
            doc = fitz.open(pdf_path)
            
            # --- 1. 分析全文档的字体大小分布，确定什么是“正文”，什么是“标题” ---
            font_counts = {}
            for page in doc:
                blocks = page.get_text("dict")["blocks"]
                for b in blocks:
                    if b['type'] == 0:  # 文本块
                        for line in b["lines"]:
                            for span in line["spans"]:
                                size = round(span["size"], 1)
                                font_counts[size] = font_counts.get(size, 0) + len(span["text"])
            
            # 出现频率最高的字体大小判定为“正文大小”
            if font_counts:
                body_font_size = max(font_counts, key=font_counts.get)
            else:
                body_font_size = 11.0

            print(f"📊 分析完毕：正文字体大小约为 {body_font_size}pt")

            # --- 2. 逐页提取内容 ---
            md_content = ""
            headers_set = set() # 存储提取到的页眉
            footers_set = set() # 存储提取到的页脚
            
            page_height = 0

            for page in doc:
                page_height = page.rect.height
                blocks = page.get_text("dict")["blocks"]
                
                # 按垂直位置排序
                blocks.sort(key=lambda b: b["bbox"][1])

                for b in blocks:
                    if b['type'] == 0:
                        bbox = b["bbox"]
                        text_content = ""
                        max_size = 0
                        
                        # 获取这一块的文本和最大字号
                        for line in b["lines"]:
                            for span in line["spans"]:
                                text_content += span["text"]
                                if span["size"] > max_size:
                                    max_size = span["size"]
                        
                        text_content = text_content.strip()
                        if not text_content: continue

                        # === 判定页眉/页脚 ===
                        # 规则：页面顶部 10% 为页眉，底部 10% 为页脚
                        y0 = bbox[1] # 顶部坐标
                        y1 = bbox[3] # 底部坐标
                        
                        if y1 < page_height * 0.1:
                            headers_set.add(text_content)
                            continue # 跳过，不写入正文
                        elif y0 > page_height * 0.9:
                            footers_set.add(text_content)
                            continue # 跳过，不写入正文

                        # === 判定标题 ===
                        # 规则：比正文大 2pt 是二级标题，大 5pt 是一级标题
                        prefix = ""
                        if max_size > body_font_size + 5:
                            prefix = "# "
                        elif max_size > body_font_size + 2:
                            prefix = "## "
                        elif max_size > body_font_size + 0.5:
                            prefix = "**" #稍微大一点的加粗
                            if "**" not in text_content: # 防止重复
                                text_content = f"{text_content}**"

                        # 拼接 Markdown
                        md_content += f"{prefix}{text_content}\n\n"

            # --- 3. 构造带 YAML 头的 Markdown ---
            # 取出现次数最多的页眉页脚（通常全书统一）
            final_header = list(headers_set)[0] if headers_set else ""
            final_footer = list(footers_set)[0] if footers_set else ""

            post = frontmatter.Post(md_content)
            post['header_text'] = final_header
            post['footer_text'] = final_footer
            post['title'] = os.path.basename(pdf_path)
            
            # 写入文件
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
                
            print(f"✅ 转换完成。页眉：{final_header} | 页脚：{final_footer}")
            return True

        except Exception as e:
            print(f"❌ PDF转MD失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==========================================
    # 2. 完美还原：Markdown -> PDF (样式还原 + 页眉页脚注入)
    # ==========================================
    def markdown_to_pdf(self, md_path, output_path):
        """
        读取 Markdown (包含YAML头)，生成带页眉页脚和标题样式的 PDF
        """
        try:
            # 1. 读取 MD 和 元数据
            with open(md_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)
            
            body_text = post.content
            header_text = post.get('header_text', '')
            footer_text = post.get('footer_text', '')
            
            # 2. Markdown 转 HTML
            html_body = markdown(body_text)

            # 3. 构建 CSS (核心魔法)
            # 使用 CSS Paged Media 规范 (@page) 来控制页眉页脚
            css_string = f'''
                @page {{
                    size: A4;
                    margin: 2.5cm;
                    
                    /* 定义页眉区域 */
                    @top-center {{
                        content: "{header_text}";
                        font-family: "Microsoft YaHei", "SimHei", sans-serif;
                        font-size: 9pt;
                        color: #666;
                        border-bottom: 1px solid #ddd;
                        padding-bottom: 5px;
                    }}
                    
                    /* 定义页脚区域 (左边文字，右边页码) */
                    @bottom-center {{
                        content: "{footer_text}  |  第 " counter(page) " 页";
                        font-family: "Microsoft YaHei", "SimHei", sans-serif;
                        font-size: 9pt;
                        color: #666;
                        border-top: 1px solid #ddd;
                        padding-top: 5px;
                    }}
                }}

                body {{
                    font-family: "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", sans-serif;
                    font-size: 11pt;
                    line-height: 1.6;
                    color: #333;
                }}

                /* 标题样式还原 */
                h1 {{ 
                    font-size: 24pt; 
                    font-weight: bold; 
                    color: #2c3e50; 
                    border-bottom: 2px solid #eee; 
                    margin-top: 20px;
                }}
                h2 {{ 
                    font-size: 18pt; 
                    font-weight: bold; 
                    color: #34495e; 
                    margin-top: 15px;
                    padding-left: 10px;
                    border-left: 4px solid #007bff;
                }}
                p {{ margin-bottom: 10px; }}
            '''

            # 4. 生成 PDF
            html = HTML(string=html_body, base_url=".")
            css = CSS(string=css_string)
            
            html.write_pdf(output_path, stylesheets=[css])
            
            print(f"✅ PDF还原成功: {output_path}")
            return True

        except Exception as e:
            print(f"❌ MD转PDF失败: {e}")
            import traceback
            traceback.print_exc()
            return False