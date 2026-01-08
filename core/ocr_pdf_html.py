import os
import logging
import numpy as np 
from pdf2image import convert_from_path 

# 1. 全局屏蔽 Paddle 的调试日志
os.environ['FLAGS_allocator_strategy'] = 'auto_growth'
logging.getLogger("ppocr").setLevel(logging.ERROR)

try:
    from paddleocr import PaddleOCR
    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False

class OcrConverter:
    """
    Step 3: 完美收官版 (OCR + 规则后处理)
    1. 参数调优：Unclip=2.0 (解决“名称”断行)
    2. 逻辑降噪：过滤孤立数字 (解决多余的“1”)
    3. 文本矫正：内置替换字典 (解决“冻于”、“国é采”)
    """

    def __init__(self, poppler_path=None):
        self.ocr_engine = None
        self.poppler_path = poppler_path 
        
        if HAS_PADDLE:
            try:
                print("   🚀 正在初始化 PaddleOCR 引擎 (最终优化版)...")
                self.ocr_engine = PaddleOCR(
                    use_angle_cls=True, 
                    lang="ch",
                    ocr_version='PP-OCRv4',
                    
                    # === 🎯 针对排版断行的激进优化 ===
                    # 1. 检测阈值保持极低，防止漏字
                    det_db_thresh=0.1,
                    det_db_box_thresh=0.3,
                    
                    # 2. 关键修改：将扩张比例调大到 2.0 (原1.6)
                    # 作用：让检测框横向扩张得更厉害，
                    # 强行把 "名   称" 中间的空白“吃”进去，合并成一个框。
                    det_db_unclip_ratio=2.0
                )
            except Exception as e:
                print(f"⚠️ PaddleOCR 初始化失败: {e}")

    def scanned_pdf_to_html(self, pdf_path, output_path):
        if not HAS_PADDLE or self.ocr_engine is None:
            print("❌ 错误：OCR 引擎不可用。")
            return False
        
        if self.poppler_path and not os.path.exists(self.poppler_path):
             print(f"❌ 错误：Poppler 路径无效: {self.poppler_path}")
             return False

        print(f"🔄 [Final Polish] 正在处理: {os.path.basename(pdf_path)}")
        
        try:
            # 保持 300 DPI 以确保清晰度
            print("   📸 正在将 PDF 转换为高清图像 (DPI=300)...")
            try:
                images = convert_from_path(pdf_path, dpi=300, poppler_path=self.poppler_path)
            except Exception as e:
                print(f"❌ PDF 转图片失败: {e}")
                return False

            html_body = ""
            total_pages = len(images)

            for i, img in enumerate(images):
                print(f"      📖 正在识别第 {i + 1}/{total_pages} 页...")
                
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img_np = np.array(img)

                try:
                    result = self.ocr_engine.ocr(img_np)
                except Exception as e:
                    print(f"      ⚠️ API 报错: {e}")
                    continue
                
                # 1. 获取原始文本列表
                raw_texts = self._parse_paddle_result(result)
                
                # 2. 执行后处理清洗 (矫正错字、过滤噪点)
                cleaned_texts = self._post_process_texts(raw_texts)
                
                print(f"      ✅ 成功提取: {len(cleaned_texts)} 行有效文字")

                page_html = []
                for text in cleaned_texts:
                    text = text.replace("<", "&lt;").replace(">", "&gt;")
                    page_html.append(f"<p>{text}</p>")

                page_content = "\n".join(page_html)
                if not page_content:
                    page_content = "<p><i>[本页无文字]</i></p>"
                    
                html_body += f"<div class='ocr-page'>{page_content}</div><hr/>"

            self._save_html(html_body, output_path)
            print(f"✅ [OCR 成功] 已保存: {output_path}")
            return True

        except Exception as e:
            print(f"❌ [OCR 失败] 未知错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _post_process_texts(self, text_list):
        """
        核心后处理逻辑：就像一个编辑，负责校对和清洗
        """
        valid_texts = []
        
        for text in text_list:
            text = text.strip()
            
            # --- 规则1: 噪点过滤 (解决多余的 "1") ---
            # 如果一行只有一个字符，且是数字或标点，通常是噪点或页码，丢弃
            if len(text) == 1 and not '\u4e00' <= text <= '\u9fa5': # 不是汉字
                 # 这里特指你遇到的那个孤立的 "1"
                 continue
            
            # --- 规则2: 关键词矫正 (解决形近字) ---
            # 针对你发现的错误建立“替换字典”
            replacements = {
                "冻于": "冻干",      # 修复：冻干甲型...
                "国é采": "国e采",    # 修复：电子采购系统
                "010--": "010-",    # 修复：电话号码
                "卢的": "卢昀",      # 修复：人名 (根据上下文)
                # "名 称": "名称",   # 修复：如果Unclip没生效，可以用这里强行合并
            }
            
            for wrong, correct in replacements.items():
                if wrong in text:
                    text = text.replace(wrong, correct)

            # --- 规则3: 格式美化 ---
            # 去掉文字中不必要的空格 (OCR经常在汉字间插入空格)
            # 这里的逻辑是：如果包含汉字，就尝试去掉空格
            # (简易版，防止把英文单词拼在一起，这里暂不激进处理)
            
            if text:
                valid_texts.append(text)
                
        return valid_texts

    def _parse_paddle_result(self, result):
        """ 万能解析器 (保持不变) """
        if not result: return []
        data = result[0] if isinstance(result, list) and len(result) > 0 else result
        parsed_lines = []

        if isinstance(data, dict) and 'rec_texts' in data:
            texts = data.get('rec_texts', [])
            polys = data.get('rec_polys', []) or data.get('dt_polys', [])
            if isinstance(texts, list) and len(texts) > 0:
                if isinstance(polys, list) and len(polys) == len(texts):
                    for idx, text in enumerate(texts):
                        poly = polys[idx]
                        try:
                            y_coord = poly[0][1] if isinstance(poly, (np.ndarray, list)) else 0
                            parsed_lines.append((y_coord, text))
                        except:
                            parsed_lines.append((0, text))
                else:
                    return texts
        elif isinstance(data, list):
            for line in data:
                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    try:
                        box = line[0]; text_part = line[1]; text = text_part[0]; y_coord = box[0][1]
                        parsed_lines.append((y_coord, text))
                    except: continue

        if parsed_lines:
            parsed_lines.sort(key=lambda x: x[0])
            return [item[1] for item in parsed_lines]
        
        return self._recursive_find_text(result)

    def _recursive_find_text(self, data):
        found = []
        if isinstance(data, dict):
            if 'text' in data and isinstance(data['text'], str): return [data['text']]
            for val in data.values(): found.extend(self._recursive_find_text(val))
        elif isinstance(data, list):
            for item in data: found.extend(self._recursive_find_text(item))
        elif isinstance(data, str) and len(data) > 1: return [data]
        return found

    def _save_html(self, content, path):
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8">
        <style>
            body{{ font-family: "Microsoft YaHei", sans-serif; max-width: 900px; margin: 20px auto; line-height: 1.6; padding: 40px; background: #f5f5f5; color: #333; }}
            .ocr-page {{ background: white; padding: 50px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); border-radius: 8px; min-height: 1000px; }}
            p {{ margin-bottom: 0.8em; text-align: justify; }}
            hr {{ border: 0; margin: 40px 0; border-top: 1px dashed #ccc; }}
        </style>
        </head><body>{content}</body></html>
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(full_html)