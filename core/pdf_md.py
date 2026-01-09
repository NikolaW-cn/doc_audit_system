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
    # 1. PDF -> Markdown (V7.0 表格校验 + 粘连解离版)
    # =========================================================================
    def pdf_to_markdown(self, pdf_path, output_path):
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # --- 步骤 A: 建立页眉页脚特征库 ---
            text_frequency = Counter()
            all_font_sizes = []
            
            # 预扫描全书
            for page in doc:
                page_height = page.rect.height
                blocks = page.get_text("dict")["blocks"]
                for b in blocks:
                    if b['type'] == 0:
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
                                # 归一化处理
                                clean_key = re.sub(r'[\d\s]+', '', text).lower()
                                if clean_key:
                                    text_frequency[clean_key] += 1

            # 计算正文基准字号
            body_font_size = Counter(all_font_sizes).most_common(1)[0][0] if all_font_sizes else 10.5
            
            # 筛选高频特征 (频率 > 30%)
            hf_candidates = {
                key for key, count in text_frequency.items() 
                if count > (total_pages * 0.3)
            }
            
            print(f"🕵️ 特征库: {list(hf_candidates)[:5]}...") # 打印前5个看看

            # --- 步骤 B: 逐页提取 ---
            md_content = ""
            extracted_headers = set()
            extracted_footers = set()
            
            # 页码正则
            PAGE_NUM_PATTERNS = [
                r'^\d+$', r'^\-?\s*\d+\s*\-?$', r'^Page\s*\d+', 
                r'^\d+\s*[\/\|\-]\s*\d+$', r'^\d+\s*of\s*\d+$',
                r'^第\s*\d+\s*页$', r'^\d+\s*\/\s*\d+$'
            ]

            for i, page in enumerate(doc):
                page_height = page.rect.height
                
                # 1. 表格提取 (带合法性校验)
                tables = page.find_tables(strategy='lines')
                page_tables_md = {}
                table_bboxes = []
                
                for tab in tables:
                    # --- 🛑 表格合法性校验 (防止标题变表格) ---
                    # 规则1: 如果表格只有1行，且列数>3，大概率是标题被拆分了 -> 丢弃
                    if tab.row_count == 1 and tab.col_count > 3:
                        continue
                    # 规则2: 如果表格几乎是空的 -> 丢弃
                    if len(tab.extract()) < 1:
                        continue
                    
                    # 通过校验，认为是真表格
                    table_bboxes.append(fitz.Rect(tab.bbox))
                    page_tables_md[tab.bbox[1]] = tab.to_markdown()

                page_elements = []
                # 加入表格
                for y, md_text in page_tables_md.items():
                    page_elements.append({"y": y, "type": "table", "content": md_text})

                # 2. 文本提取
                blocks = page.get_text("dict")["blocks"]
                
                for b in blocks:
                    if b['type'] == 0:
                        # 表格避让
                        block_rect = fitz.Rect(b["bbox"])
                        if any(block_rect.intersect(t_rect).get_area() > block_rect.get_area() * 0.5 for t_rect in table_bboxes):
                            continue

                        for line in b["lines"]:
                            line_text = "".join([span["text"] for span in line["spans"]]).strip()
                            if not line_text: continue
                            
                            bbox = line["bbox"]
                            y_center = (bbox[1] + bbox[3]) / 2
                            line_font_size = max([span["size"] for span in line["spans"]])
                            
                            # === 智能判别逻辑 (V7.0) ===
                            is_top = y_center < page_height * 0.20
                            is_bottom = y_center > page_height * 0.80
                            is_strict_zone = y_center < page_height * 0.08 or y_center > page_height * 0.92
                            
                            is_hf = False
                            clean_key = re.sub(r'[\d\s]+', '', line_text).lower()
                            
                            # ✂️ 粘连解离检测 (Partial Match)
                            # 检查这行字是否以某个页眉特征开头？如果是，说明粘连了
                            matched_candidate = None
                            if is_top:
                                for cand in hf_candidates:
                                    # 简单检查：如果 clean_key 包含 candidate
                                    if cand in clean_key and len(cand) > 3: 
                                        matched_candidate = cand
                                        break
                            
                            if matched_candidate:
                                # 这是一个混合行 (页眉+正文)，我们需要极其小心
                                # 简单策略：如果整行都很短，或者主要由页眉组成，就视为页眉删掉
                                # 如果很长，可能是正文，这里为了安全，若位于严格边缘，倾向于删除
                                is_hf = True
                            elif clean_key in hf_candidates:
                                is_hf = True
                            
                            # 正则匹配页码
                            if not is_hf and (is_top or is_bottom):
                                for pattern in PAGE_NUM_PATTERNS:
                                    if re.match(pattern, line_text, re.IGNORECASE):
                                        is_hf = True
                                        break
                            
                            # 🛡️ 正文保护 (Body Guard)
                            # 如果字号是正文大小，且不在绝对禁区(8%)，且不是完全匹配的高频词 -> 它是正文
                            is_body_size = abs(line_font_size - body_font_size) < 0.5
                            if is_hf and is_body_size and not is_strict_zone and clean_key not in hf_candidates:
                                # 可能是被正则误判的页码 (如 "1." 这种序号)
                                if not re.match(r'^\d+$', line_text): 
                                    is_hf = False
                            
                            # 执行分类
                            if is_hf:
                                if is_top: extracted_headers.add(line_text)
                                if is_bottom and not re.match(r'^[\d\s\/\-]+$', line_text):
                                    extracted_footers.add(line_text)
                                continue 
                            
                            # === 正文写入 ===
                            prefix = ""
                            if line_font_size >= body_font_size + 4: prefix = "# "
                            elif line_font_size >= body_font_size + 1.5: prefix = "## "
                            elif line_font_size >= body_font_size + 0.5:
                                if not line_text.startswith("**"): line_text = f"**{line_text}**"

                            page_elements.append({
                                "y": bbox[1],
                                "type": "text",
                                "content": f"{prefix}{line_text}"
                            })

                # 排序并合并
                page_elements.sort(key=lambda x: x["y"])
                for el in page_elements:
                    md_content += el["content"] + "\n\n"

            # --- 步骤 C: 最终清洗 (Post-Processing) ---
            # 有时候 PyMuPDF 提取顺序问题导致页码夹在中间，用正则最后扫一遍
            lines = md_content.split('\n')
            clean_lines = []
            for line in lines:
                strip_line = line.strip().replace('*', '') # 去掉 markdown 标记再检查
                is_noise = False
                
                # 再次检查是否为纯页码残留
                for pattern in PAGE_NUM_PATTERNS:
                    if re.match(pattern, strip_line, re.IGNORECASE):
                        is_noise = True
                        break
                
                # 再次检查是否为高频页眉残留
                if not is_noise:
                    k = re.sub(r'[\d\s]+', '', strip_line).lower()
                    if k in hf_candidates:
                        is_noise = True

                if not is_noise:
                    clean_lines.append(line)
            
            md_content = "\n".join(clean_lines)

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