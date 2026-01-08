import os
import logging
import numpy as np
from pdf2image import convert_from_path

# 1. 尝试导入 RapidOCR
try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPID = True
except ImportError:
    HAS_RAPID = False

class RapidOcrConverter:
    """
    RapidOCR 版核心转换器 (ONNX Runtime)
    特点：
    1. 速度极快 (CPU 优化)
    2. 无需安装 PaddlePaddle 框架
    3. 移植了之前 PaddleOCR 版本的所有后处理规则 (Unclip=2.0, 关键词替换等)
    """

    def __init__(self, poppler_path=None):
        self.ocr_engine = None
        self.poppler_path = poppler_path

        if HAS_RAPID:
            try:
                print("   🚀 正在初始化 RapidOCR 引擎 (ONNX版)...")
                # === 参数调优 (对标 PaddleOCR 的优化配置) ===
                self.ocr_engine = RapidOCR(
                    # 1. 检测阈值 (对应 det_db_thresh=0.1)
                    # 让模型更敏感，防止漏掉颜色淡的字
                    det_thresh=0.1,

                    # 2. 框置信度 (对应 det_db_box_thresh=0.3)
                    det_box_thresh=0.3,

                    # 3. 扩张比例 (对应 det_db_unclip_ratio=2.0)
                    # 强行合并间距较大的词 (如 "名   称")
                    det_unclip_ratio=2.0
                )
            except Exception as e:
                print(f"⚠️ RapidOCR 初始化失败: {e}")

    def scanned_pdf_to_html(self, pdf_path, output_path):
        if not HAS_RAPID or self.ocr_engine is None:
            print("❌ 错误：RapidOCR 库未安装或初始化失败。请运行 pip install rapidocr_onnxruntime")
            return False

        if self.poppler_path and not os.path.exists(self.poppler_path):
             print(f"❌ 错误：Poppler 路径无效: {self.poppler_path}")
             return False

        print(f"🔄 [RapidOCR] 正在处理: {os.path.basename(pdf_path)}")

        try:
            # 1. Poppler 转图
            # 保持 300 DPI 以确保“冻干/冻于”等形近字的清晰度
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

                # RapidOCR 也可以直接处理 PIL Image，但转成 numpy 更稳妥
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img_np = np.array(img)

                try:
                    # RapidOCR 调用方式：result, elapse = engine(img)
                    result, _ = self.ocr_engine(img_np)
                except Exception as e:
                    print(f"      ⚠️ 识别 API 报错: {e}")
                    continue

                # 2. 解析结果
                # RapidOCR 返回结构通常是: [[box, text, score], [box, text, score], ...]
                # 如果没识别到，返回 None
                if result is None:
                    result = []

                # 提取文本并排序
                raw_texts = self._parse_rapid_result(result)

                # 3. 后处理 (规则引擎，与 Paddle 版本保持一致)
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

    def _parse_rapid_result(self, result):
        """
        解析 RapidOCR 的结果列表
        Item 结构: [ [[x1,y1], [x2,y2]...], "文本内容", 置信度 ]
        """
        parsed_lines = []
        for item in result:
            # item 长度通常是 3
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    box = item[0]
                    text = item[1]
                    # score = item[2]

                    # 获取 Y 坐标用于排序 (左上角 Y)
                    y_coord = box[0][1] if isinstance(box, (list, np.ndarray)) else 0
                    parsed_lines.append((y_coord, text))
                except:
                    continue

        # 按 Y 轴排序
        if parsed_lines:
            parsed_lines.sort(key=lambda x: x[0])
            return [item[1] for item in parsed_lines]
        return []

    def _post_process_texts(self, text_list):
        """
        后处理规则 (与 Paddle 版本完全一致)
        """
        valid_texts = []
        for text in text_list:
            text = text.strip()

            # 规则1: 噪点过滤
            if len(text) == 1 and not '\u4e00' <= text <= '\u9fa5':
                 continue

            # 规则2: 关键词矫正字典
            replacements = {
                "冻于": "冻干",
                "国é采": "国e采",
                "010--": "010-",
                "卢的": "卢昀",
            }

            for wrong, correct in replacements.items():
                if wrong in text:
                    text = text.replace(wrong, correct)

            if text:
                valid_texts.append(text)

        return valid_texts

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