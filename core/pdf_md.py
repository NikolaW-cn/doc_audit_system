import fitz  # PyMuPDF
import os
import re
import frontmatter
from markdown import markdown
from weasyprint import HTML, CSS
from collections import Counter

class PdfMdConverter:
    def __init__(self):
        pass

    # =========================================================================
    # 1. PDF -> Markdown (忠实还原版)
    # 特点：只分离页眉页脚和表格，除此之外的正文内容（含错误提示、点点点）一律保留
    # =========================================================================
    def pdf_to_markdown(self, pdf_path, output_path):
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # --- 步骤 1: 识别页眉页脚 (通过位置+频率) ---
            # 我们先扫描全书，看看哪些文字总是出现在页面边缘
            text_frequency = Counter()
            
            for page in doc:
                page_height = page.rect.height
                blocks = page.get_text("dict")["blocks"]
                for b in blocks:
                    if b['type'] == 0: # 文本块
                        for line in b["lines"]:
                            text = "".join([span["text"] for span in line["spans"]]).strip()
                            if len(text) < 1: continue # 只有完全为空的才跳过
                            
                            bbox = line["bbox"]
                            y_center = (bbox[1] + bbox[3]) / 2
                            
                            # 判定区域：页面最上方 12% 和最下方 12%
                            if y_center < page_height * 0.12 or y_center > page_height * 0.88:
                                # 简单归一化统计 (去掉数字差异，比如 Page 1 和 Page 2 归为一类)
                                clean_key = re.sub(r'\d+', '', text.strip())
                                text_frequency[clean_key] += 1

            # 出现频率超过 30% 的边缘文本，被认定为“固定页眉/页脚”
            header_footer_candidates = {
                key for key, count in text_frequency.items() 
                if count > (total_pages * 0.3)
            }
            
            # --- 步骤 2: 逐页提取 (保留所有细节) ---
            md_content = ""
            extracted_headers = set()
            extracted_footers = set()
            
            # 统计字号用于判定标题
            all_font_sizes = []
            for page in doc:
                for b in page.get_text("dict")["blocks"]:
                    if b['type'] == 0:
                        for line in b["lines"]:
                            for span in line["spans"]:
                                all_font_sizes.append(round(span["size"], 1))
            
            if all_font_sizes:
                body_font_size = Counter(all_font_sizes).most_common(1)[0][0]
            else:
                body_font_size = 10.5

            # 定义页码的正则 (用于捕捉变动页码，将其移至元数据，不留在正文)
            PAGE_NUM_PATTERNS = [
                r'^\d+$', r'^Page\s*\d+', r'^\d+\s*[\/\|]\s*\d+$', r'^\-\s*\d+\s*\-$',
                r'^\d+\s*of\s*\d+$'
            ]

            for page in doc:
                page_height = page.rect.height
                
                # A. 优先提取表格 (防止表格被打散)
                tables = page.find_tables()
                table_bboxes = [fitz.Rect(tab.bbox) for tab in tables]
                # 将表格转为 Markdown 文本
                page_tables_md = {tab.bbox[1]: tab.to_markdown() for tab in tables}

                # B. 提取文本
                blocks = page.get_text("dict")["blocks"]
                page_elements = []

                # 先把表格加入队列
                for y, md_text in page_tables_md.items():
                    page_elements.append({"y": y, "type": "table", "content": md_text})

                for b in blocks:
                    if b['type'] == 0:
                        # 检查是否在表格区域内
                        block_rect = fitz.Rect(b["bbox"])
                        # 如果文本块重心在表格里，就跳过 (因为已经被表格引擎提取了)
                        if any(block_rect.intersect(t_rect).get_area() > block_rect.get_area() * 0.5 for t_rect in table_bboxes):
                            continue

                        for line in b["lines"]:
                            line_text = "".join([span["text"] for span in line["spans"]]).strip()
                            if not line_text: continue
                            
                            bbox = line["bbox"]
                            y_center = (bbox[1] + bbox[3]) / 2
                            is_top = y_center < page_height * 0.15
                            is_bottom = y_center > page_height * 0.85
                            
                            # === 页眉页脚判定 (仅做移动，不删除) ===
                            is_hf = False
                            clean_key = re.sub(r'\d+', '', line_text.strip())
                            
                            # 1. 命中固定高频词
                            if (is_top or is_bottom) and clean_key in header_footer_candidates:
                                is_hf = True
                            
                            # 2. 命中页码格式 (即使频率不高)
                            if (is_top or is_bottom):
                                for pattern in PAGE_NUM_PATTERNS:
                                    if re.match(pattern, line_text, re.IGNORECASE):
                                        is_hf = True
                                        break
                            
                            if is_hf:
                                if is_top: extracted_headers.add(line_text)
                                if is_bottom: 
                                    # 纯数字页码不存入 footer_text (因为还原时会自动生成)
                                    # 但如果是 "Page 1 / 10" 这种复杂格式，还是存一下比较稳
                                    if not re.match(r'^\d+$', line_text):
                                        extracted_footers.add(line_text)
                                continue # 移入元数据，正文跳过
                            
                            # === 正文样式处理 ===
                            # 没有任何过滤逻辑！保留错误信息、点点点等
                            
                            # 计算这一行的最大字号
                            max_size = max([span["size"] for span in line["spans"]])
                            prefix = ""
                            
                            if max_size >= body_font_size + 4: prefix = "# "
                            elif max_size >= body_font_size + 1.5: prefix = "## "
                            elif max_size >= body_font_size + 0.5:
                                if not line_text.startswith("**"): line_text = f"**{line_text}**"

                            page_elements.append({
                                "y": bbox[1],
                                "type": "text",
                                "content": f"{prefix}{line_text}"
                            })

                # C. 排序并合并
                page_elements.sort(key=lambda x: x["y"])
                for el in page_elements:
                    md_content += el["content"] + "\n\n"

            # --- 步骤 3: 写入文件 ---
            final_header = max(extracted_headers, key=len) if extracted_headers else ""
            final_footer = max(extracted_footers, key=len) if extracted_footers else ""
            
            post = frontmatter.Post(md_content)
            post['title'] = os.path.basename(pdf_path)
            post['header_text'] = final_header
            post['footer_text'] = final_footer
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
                
            return True

        except Exception as e:
            print(f"❌ 转换失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # =========================================================================
    # 2. Markdown -> PDF (样式还原版)
    # =========================================================================
    def markdown_to_pdf(self, md_path, output_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)
            
            body_text = post.content
            header_text = post.get('header_text', '')
            footer_text = post.get('footer_text', '')
            
            # 开启表格支持
            html_body = markdown(body_text, extensions=['tables', 'fenced_code'])

            css_string = f'''
                @page {{
                    size: A4;
                    margin: 2.5cm;
                    
                    @top-center {{
                        content: "{header_text}";
                        font-family: "Microsoft YaHei", "SimHei", sans-serif;
                        font-size: 9pt;
                        color: #666;
                        border-bottom: 1px solid #ddd;
                        padding-bottom: 5px;
                        margin-bottom: 20px;
                        white-space: pre-wrap; 
                    }}
                    
                    @bottom-center {{
                        content: "{footer_text}  " counter(page);
                        font-family: "Microsoft YaHei", "SimHei", sans-serif;
                        font-size: 9pt;
                        color: #666;
                        border-top: 1px solid #ddd;
                        padding-top: 5px;
                        margin-top: 20px;
                    }}
                }}

                body {{
                    font-family: "Microsoft YaHei", "SimHei", sans-serif;
                    font-size: 10.5pt;
                    line-height: 1.6;
                    color: #333;
                    text-align: justify;
                }}
                
                h1 {{ font-size: 22pt; font-weight: bold; text-align: center; margin: 2em 0 1em; }}
                h2 {{ font-size: 16pt; font-weight: bold; border-left: 5px solid #007bff; padding-left: 10px; margin: 1.5em 0 0.8em; }}
                h3 {{ font-size: 14pt; font-weight: bold; margin-top: 1.2em; }}
                
                /* 表格还原样式 */
                table {{ 
                    border-collapse: collapse; 
                    width: 100%; 
                    margin: 1.5em 0;
                    page-break-inside: auto;
                }}
                th, td {{ 
                    border: 1px solid #000; /* 还原为黑色边框，更清晰 */
                    padding: 6px; 
                    text-align: left; 
                    font-size: 10pt;
                }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                
                /* 目录点点点优化 */
                p {{ margin-bottom: 0.8em; }}
            '''

            html = HTML(string=html_body, base_url=".")
            css = CSS(string=css_string)
            html.write_pdf(output_path, stylesheets=[css])
            
            return True
        except Exception as e:
            print(f"❌ 还原失败: {e}")
            return False