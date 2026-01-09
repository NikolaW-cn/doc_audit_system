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
    # 1. PDF -> Markdown (V6.0 通用防御版)
    # 核心升级：引入“正文保护机制”，防止误删边缘的正文内容
    # =========================================================================
    def pdf_to_markdown(self, pdf_path, output_path):
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # --- 阶段一：全书扫描 (建立特征库 & 确定正文基准) ---
            
            all_font_sizes = []
            text_frequency = Counter()
            
            # 临时存储所有块，避免二次读取 IO
            all_pages_blocks = []

            for page in doc:
                blocks = page.get_text("dict")["blocks"]
                all_pages_blocks.append(blocks)
                page_height = page.rect.height
                
                for b in blocks:
                    if b['type'] == 0: # 文本块
                        for line in b["lines"]:
                            # 1. 收集字号
                            for span in line["spans"]:
                                all_font_sizes.append(round(span["size"], 1))
                            
                            # 2. 收集边缘文本频率
                            text = "".join([span["text"] for span in line["spans"]]).strip()
                            if len(text) < 2: continue
                            
                            bbox = line["bbox"]
                            y_center = (bbox[1] + bbox[3]) / 2
                            
                            # 判定区域：上下 20%
                            if y_center < page_height * 0.20 or y_center > page_height * 0.80:
                                # 归一化：去空格、去数字、转小写
                                clean_key = re.sub(r'[\d\s]+', '', text).lower()
                                if clean_key:
                                    text_frequency[clean_key] += 1

            # A. 计算“正文基准字号” (出现次数最多的字号)
            if all_font_sizes:
                body_font_size = Counter(all_font_sizes).most_common(1)[0][0]
            else:
                body_font_size = 10.5
            
            print(f"🛡️ 正文保护机制已启动，基准字号: {body_font_size}pt")

            # B. 建立高频页眉库 (出现频率 > 30% 且位于边缘)
            hf_candidates = {
                key for key, count in text_frequency.items() 
                if count > (total_pages * 0.3)
            }

            # --- 阶段二：逐页提取 (带防御逻辑) ---
            
            md_content = ""
            extracted_headers = set()
            extracted_footers = set()
            
            # 增强版页码正则
            PAGE_NUM_PATTERNS = [
                r'^\d+$',                      # 1
                r'^\-?\s*\d+\s*\-?$',          # - 1 -
                r'^Page\s*\d+',                # Page 1
                r'^\d+\s*[\/\|\-]\s*\d+$',     # 1/10, 1 | 10
                r'^\d+\s*of\s*\d+$',           # 1 of 10
                r'^第\s*\d+\s*页$',             # 第 1 页
                r'^\d+\s*\/\s*\d+$'            # 1 / 7
            ]

            for i, page in enumerate(doc):
                page_height = page.rect.height
                
                # 1. 表格提取 (坚持 strategy='lines' 以保安全)
                # 只有看到明确边框才认为是表格，防止把对齐的文本误判
                tables = page.find_tables(strategy='lines')
                table_bboxes = [fitz.Rect(tab.bbox) for tab in tables]
                page_tables_md = {tab.bbox[1]: tab.to_markdown() for tab in tables}

                page_elements = []
                # 加入表格
                for y, md_text in page_tables_md.items():
                    page_elements.append({"y": y, "type": "table", "content": md_text})

                # 2. 文本提取
                blocks = all_pages_blocks[i] # 使用缓存
                
                for b in blocks:
                    if b['type'] == 0:
                        # 表格避让机制
                        block_rect = fitz.Rect(b["bbox"])
                        # 如果文本块重心在表格里，跳过
                        is_in_table = False
                        for t_rect in table_bboxes:
                            if block_rect.intersect(t_rect).get_area() > block_rect.get_area() * 0.5:
                                is_in_table = True
                                break
                        if is_in_table: continue

                        for line in b["lines"]:
                            line_text = "".join([span["text"] for span in line["spans"]]).strip()
                            if not line_text: continue
                            
                            bbox = line["bbox"]
                            y_center = (bbox[1] + bbox[3]) / 2
                            
                            # 获取该行最大字号
                            line_font_size = max([span["size"] for span in line["spans"]])
                            
                            # === 智能判别逻辑 ===
                            is_top = y_center < page_height * 0.20
                            is_bottom = y_center > page_height * 0.80
                            is_hf = False
                            
                            # 🛡️ 核心防御：如果是正文字号，且不是高频词，强制认为是正文！
                            # 容差 0.5pt (避免字体渲染微小差异)
                            is_body_size = abs(line_font_size - body_font_size) < 0.5
                            clean_key = re.sub(r'[\d\s]+', '', line_text).lower()
                            
                            # 判定条件 1: 高频词匹配 (且必须在边缘)
                            if (is_top or is_bottom) and clean_key in hf_candidates:
                                is_hf = True
                            
                            # 判定条件 2: 页码正则 (页码通常字号较小，或者位置很偏)
                            if (is_top or is_bottom):
                                for pattern in PAGE_NUM_PATTERNS:
                                    if re.match(pattern, line_text, re.IGNORECASE):
                                        is_hf = True
                                        break
                            
                            # 🛡️ 触发熔断：如果是正文字号，且没命中高频词库，取消页眉判定
                            if is_hf and is_body_size and clean_key not in hf_candidates:
                                # 但要注意，纯数字页码有时字号跟正文一样，这里要特判
                                if not re.match(r'^\d+$', line_text): 
                                    is_hf = False 
                            
                            # 执行分类
                            if is_hf:
                                if is_top: extracted_headers.add(line_text)
                                if is_bottom and not re.match(r'^[\d\s\/\-]+$', line_text):
                                    extracted_footers.add(line_text)
                                continue # 确认为页眉，跳过正文写入
                            
                            # === 正文写入 ===
                            prefix = ""
                            # 标题判定 (比正文大 4pt 为一级，大 1.5pt 为二级)
                            if line_font_size >= body_font_size + 4: prefix = "# "
                            elif line_font_size >= body_font_size + 1.5: prefix = "## "
                            elif line_font_size >= body_font_size + 0.5:
                                if not line_text.startswith("**"): line_text = f"**{line_text}**"

                            page_elements.append({
                                "y": bbox[1],
                                "type": "text",
                                "content": f"{prefix}{line_text}"
                            })

                # 排序合并
                page_elements.sort(key=lambda x: x["y"])
                for el in page_elements:
                    md_content += el["content"] + "\n\n"

            # --- 收尾 ---
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
    # 2. Markdown -> PDF (样式部分，无需改动)
    # =========================================================================
    def markdown_to_pdf(self, md_path, output_path):
        # 保持原有代码，确保样式一致
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)
            
            body_text = post.content
            header_text = post.get('header_text', '')
            footer_text = post.get('footer_text', '')
            
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
                table {{ 
                    border-collapse: collapse; 
                    width: 100%; 
                    margin: 1.5em 0;
                }}
                th, td {{ 
                    border: 1px solid #000; 
                    padding: 6px; 
                    text-align: left; 
                    font-size: 10pt;
                }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
            '''

            html = HTML(string=html_body, base_url=".")
            css = CSS(string=css_string)
            html.write_pdf(output_path, stylesheets=[css])
            return True
        except Exception as e:
            print(f"❌ 还原失败: {e}")
            return False