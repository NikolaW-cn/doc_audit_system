import fitz  # PyMuPDF
import os
import re
import frontmatter  # 需要安装 python-frontmatter
from markdown import markdown
from weasyprint import HTML, CSS
from collections import Counter

class PdfMdConverter:
    def __init__(self):
        pass

    # =========================================================================
    # 1. PDF -> Markdown 
    # 功能：智能分离页眉页脚到元数据，正文保留标题层级，不做人为内容过滤
    # =========================================================================
    def pdf_to_markdown(self, pdf_path, output_path):
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # --- 阶段一：全文档扫描 (分析字体大小 + 识别页眉页脚) ---
            
            # 1. 统计字体大小 (用于判定正文和标题)
            all_font_sizes = []
            # 2. 统计文本频率 (用于判定页眉页脚)
            text_frequency = Counter()
            # 3. 缓存所有块 (避免二次读取文件)
            all_pages_blocks = []

            for page in doc:
                page_height = page.rect.height
                # 获取页面所有文本块 (包含位置信息)
                blocks = page.get_text("dict")["blocks"]
                all_pages_blocks.append(blocks)
                
                for b in blocks:
                    if b['type'] == 0: # 0代表文本
                        # 收集字号
                        for line in b["lines"]:
                            for span in line["spans"]:
                                all_font_sizes.append(round(span["size"], 1))
                        
                        # 收集文本频率 (仅统计位于页面顶部15%或底部15%的内容)
                        text = "".join([span["text"] for line in b["lines"] for span in line["spans"]]).strip()
                        bbox = b["bbox"]
                        is_edge = (bbox[1] < page_height * 0.15) or (bbox[3] > page_height * 0.85)
                        
                        if text and is_edge:
                            # 简单去空处理，提高匹配率
                            clean_key = re.sub(r'\s+', '', text)
                            text_frequency[clean_key] += 1

            # 计算正文基准字号 (出现次数最多的字号)
            if all_font_sizes:
                body_font_size = Counter(all_font_sizes).most_common(1)[0][0]
            else:
                body_font_size = 10.5
            
            print(f"📊 分析结果：正文基准字号={body_font_size}pt")

            # 确定哪些是页眉页脚 (规则：位于边缘区域，且在超过 60% 的页面中都出现过)
            header_footer_candidates = {
                key for key, count in text_frequency.items() 
                if count > (total_pages * 0.6)
            }
            
            # --- 阶段二：逐页提取与转换 ---
            
            md_content = ""
            extracted_headers = set() # 收集具体的页眉文本
            extracted_footers = set() # 收集具体的页脚文本

            for i, blocks in enumerate(all_pages_blocks):
                page_height = doc[i].rect.height
                
                # 按垂直坐标 Y 排序，确保阅读顺序正确
                blocks.sort(key=lambda b: b["bbox"][1])

                for b in blocks:
                    if b['type'] == 0:
                        bbox = b["bbox"]
                        
                        # 1. 提取当前块的纯文本和最大字号
                        block_text = ""
                        max_size = 0
                        for line in b["lines"]:
                            for span in line["spans"]:
                                block_text += span["text"]
                                if span["size"] > max_size:
                                    max_size = span["size"]
                        
                        raw_text = block_text.strip()
                        if not raw_text: continue

                        # 2. 判断是否为页眉/页脚 (如果是，存入元数据，不写进正文)
                        check_key = re.sub(r'\s+', '', raw_text)
                        is_top = bbox[1] < page_height * 0.15
                        is_bottom = bbox[3] > page_height * 0.85
                        
                        if check_key in header_footer_candidates:
                            if is_top:
                                extracted_headers.add(raw_text)
                                continue # 跳过写入
                            if is_bottom:
                                extracted_footers.add(raw_text)
                                continue # 跳过写入

                        # 3. 标题样式判定 (基于字号)
                        prefix = ""
                        # 一级标题：比正文大 4pt
                        if max_size >= body_font_size + 4:
                            prefix = "# "
                        # 二级标题：比正文大 1.5pt
                        elif max_size >= body_font_size + 1.5:
                            prefix = "## "
                        # 粗体/小标题：比正文略大
                        elif max_size >= body_font_size + 0.5:
                            # 如果还没加粗，给它加上
                            if not raw_text.startswith("**"):
                                raw_text = f"**{raw_text}**"

                        # 4. 写入 Markdown (保留所有符号，不清洗)
                        # 为了模拟段落间距，加两个换行
                        if prefix:
                            md_content += f"\n\n{prefix}{raw_text}\n\n"
                        else:
                            # 普通正文
                            md_content += f"{raw_text}\n\n"

            # --- 阶段三：保存文件 (带 YAML 头信息) ---
            
            # 选取最长的一个作为代表 (防止有时候页眉提取不完整)
            final_header = max(extracted_headers, key=len) if extracted_headers else ""
            final_footer = max(extracted_footers, key=len) if extracted_footers else ""
            
            # 过滤掉纯页码 (如 "1/7")，我们会在生成PDF时自动加页码，不需要手动保留
            # 如果页脚包含文字+页码，我们尽量保留文字部分
            if re.match(r'^[\d\s/ofpage页]+$', final_footer, re.I):
                final_footer = "" # 纯页码直接清空，由CSS生成

            # 构建 FrontMatter 对象
            post = frontmatter.Post(md_content)
            post['title'] = os.path.basename(pdf_path)
            post['header_text'] = final_header
            post['footer_text'] = final_footer
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
                
            print(f"✅ PDF->MD 成功。提取页眉: [{final_header}] | 页脚: [{final_footer}]")
            return True

        except Exception as e:
            print(f"❌ PDF转MD失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # =========================================================================
    # 2. Markdown -> PDF
    # 功能：读取 YAML 元数据还原页眉页脚，利用 CSS 还原标题样式
    # =========================================================================
    def markdown_to_pdf(self, md_path, output_path):
        try:
            # 1. 读取 MD 内容和 YAML 头信息
            with open(md_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)
            
            body_text = post.content
            header_text = post.get('header_text', '')
            footer_text = post.get('footer_text', '')
            
            # 2. 转换正文为 HTML
            # 启用表格扩展，防止表格转换乱码
            html_body = markdown(body_text, extensions=['tables', 'fenced_code'])

            # 3. 核心样式还原 (CSS)
            # 重点：@page 用于控制页眉页脚，h1/h2 用于控制标题样式
            css_string = f'''
                @page {{
                    size: A4;
                    margin: 2.5cm; /* 设置页边距，给页眉页脚留空间 */
                    
                    /* --- 还原页眉 --- */
                    @top-center {{
                        content: "{header_text}";
                        font-family: "Microsoft YaHei", "SimHei", sans-serif;
                        font-size: 9pt;
                        color: #666;
                        border-bottom: 1px solid #ddd; /* 增加下划线，看起来更像页眉 */
                        padding-bottom: 5px;
                        margin-bottom: 20px;
                        white-space: pre-wrap; /* 保留换行 */
                    }}
                    
                    /* --- 还原页脚 (左侧文字 + 右侧页码) --- */
                    @bottom-center {{
                        content: "{footer_text}  " counter(page); /* 自动添加页码 */
                        font-family: "Microsoft YaHei", "SimHei", sans-serif;
                        font-size: 9pt;
                        color: #666;
                        border-top: 1px solid #ddd;
                        padding-top: 5px;
                        margin-top: 20px;
                    }}
                }}

                /* --- 全局样式 --- */
                body {{
                    font-family: "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", sans-serif;
                    font-size: 10.5pt; /* 标准五号字 */
                    line-height: 1.6;
                    color: #333;
                    text-align: justify; /* 两端对齐 */
                }}

                /* --- 标题样式还原 (对应 PDF 提取时的逻辑) --- */
                h1 {{ 
                    font-size: 22pt;      /* 对应 # */
                    font-weight: bold; 
                    color: #000;
                    text-align: center;   /* 一级标题通常居中 */
                    margin-top: 2em;
                    margin-bottom: 1em;
                }}
                
                h2 {{ 
                    font-size: 16pt;      /* 对应 ## */
                    font-weight: bold; 
                    color: #333;
                    margin-top: 1.5em;
                    margin-bottom: 0.8em;
                    border-left: 5px solid #007bff; /* 加上左边框，增加辨识度 */
                    padding-left: 10px;
                }}
                
                h3 {{
                    font-size: 14pt;
                    font-weight: bold;
                    margin-top: 1.2em;
                }}

                /* --- 其他元素 --- */
                p {{
                    margin-bottom: 0.8em;
                }}
                
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                }}
                
                th, td {{
                    border: 1px solid #999;
                    padding: 6px;
                    text-align: left;
                    font-size: 10pt;
                }}
                
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                
                /* 还原粗体 */
                strong {{
                    font-weight: bold;
                    color: #000;
                }}
            '''

            # 4. 生成 PDF
            html = HTML(string=html_body, base_url=".")
            css = CSS(string=css_string)
            
            html.write_pdf(output_path, stylesheets=[css])
            
            print(f"✅ MD->PDF 成功还原: {output_path}")
            return True

        except Exception as e:
            print(f"❌ MD转PDF失败: {e}")
            import traceback
            traceback.print_exc()
            return False