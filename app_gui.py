import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess

# --- 核心引擎加载逻辑 ---
# 自动识别你用的是 RapidOCR 还是 PaddleOCR
try:
    from core.rapidocr import RapidOcrConverter as OcrConverter
    ENGINE_NAME = "RapidOCR (极速版)"
except ImportError:
    try:
        from core.ocr_pdf_html import OcrConverter
        ENGINE_NAME = "PaddleOCR (精准版)"
    except ImportError:
        # 如果都找不到，弹窗提示
        tk.messagebox.showerror("错误", "找不到核心代码！请确保 core 文件夹下有 ocr_pdf_html.py 或 ocr_rapid_html.py")
        sys.exit(1)

class OcrApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"智能文档扫描还原系统 - {ENGINE_NAME}")
        self.root.geometry("750x550")
        
        # ==========================================
        # 🔧 路径配置 (最关键的部分)
        # ==========================================
        # 1. 开发环境路径 (你现在的 D 盘路径)
        self.dev_poppler = r"D:\poppler-25.12.0\Library\bin"
        
        # 2. 发布环境路径 (打包 exe 后用的相对路径)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.dist_poppler = os.path.join(base_dir, "poppler", "Library", "bin")
        # ==========================================

        self.init_ui()

    def init_ui(self):
        # 1. 顶部：文件选择区域
        frame_top = tk.LabelFrame(self.root, text="第一步：选择文件", padx=10, pady=10)
        frame_top.pack(fill="x", padx=10, pady=5)
        
        self.entry_path = tk.Entry(frame_top, width=60)
        self.entry_path.pack(side="left", padx=5)
        
        tk.Button(frame_top, text="📂 浏览 PDF", command=self.select_file).pack(side="left", padx=5)

        # 2. 中部：开始按钮
        frame_btn = tk.Frame(self.root, pady=5)
        frame_btn.pack(fill="x", padx=10)
        
        self.btn_run = tk.Button(frame_btn, text="🚀 开始转换", command=self.start_thread, 
                                 bg="#007bff", fg="white", font=("微软雅黑", 12, "bold"), height=2)
        self.btn_run.pack(fill="x")

        # 3. 底部：日志显示
        frame_log = tk.LabelFrame(self.root, text="运行日志", padx=10, pady=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(frame_log, height=10, state='disabled', font=("Consolas", 10))
        self.log_area.pack(fill="both", expand=True)

    def log(self, msg):
        """往界面和控制台同时打印日志"""
        print(msg) 
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def select_file(self):
        filename = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if filename:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, filename)

    def start_thread(self):
        """启动后台线程防止界面卡死"""
        pdf_path = self.entry_path.get()
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showwarning("提示", "请先选择一个有效的 PDF 文件！")
            return

        # 锁定按钮
        self.btn_run.config(state="disabled", text="⏳ 正在玩命转换中...", bg="#6c757d")
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        
        # 开启新线程
        thread = threading.Thread(target=self.run_logic, args=(pdf_path,))
        thread.daemon = True
        thread.start()

    def run_logic(self, pdf_path):
        try:
            # --- 智能判定 Poppler 路径 ---
            final_poppler = None
            
            # 优先级1: 找当前目录下的 poppler (适合打包后)
            if os.path.exists(self.dist_poppler):
                final_poppler = self.dist_poppler
                self.log(f"✅ 模式: 发布版 (使用内置 Poppler)")
            # 优先级2: 找 D 盘的开发路径 (适合你现在)
            elif os.path.exists(self.dev_poppler):
                final_poppler = self.dev_poppler
                self.log(f"✅ 模式: 开发版 (使用本地 Poppler)")
            else:
                self.log(f"❌ 错误: 找不到 Poppler 工具！\n请将 poppler 文件夹放入程序目录，或检查 D 盘路径。")
                return

            self.log(f"📂 正在读取: {os.path.basename(pdf_path)}")
            self.log("🔄 正在初始化 OCR 引擎 (可能需要几秒钟)...")
            
            # 初始化转换器
            converter = OcrConverter(poppler_path=final_poppler)
            
            # 确定输出路径 (在 PDF 同级目录下生成 output_html 文件夹)
            output_dir = os.path.join(os.path.dirname(pdf_path), "output_html")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            file_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_html = os.path.join(output_dir, f"{file_name}_ocr.html")

            # 开始转换
            success = converter.scanned_pdf_to_html(pdf_path, output_html)

            if success:
                self.log(f"\n🎉 转换成功！")
                self.log(f"💾 文件位置: {output_html}")
                messagebox.showinfo("成功", f"转换完成！\n已保存至: {output_html}")
                
                # 尝试自动打开文件夹
                try:
                    os.startfile(output_dir)
                except:
                    pass
            else:
                self.log("\n❌ 转换失败，请查看上方报错信息。")
                messagebox.showerror("失败", "转换过程中出现错误")

        except Exception as e:
            self.log(f"❌ 发生异常: {e}")
            import traceback
            self.log(traceback.format_exc())
        finally:
            # 恢复按钮
            self.root.after(0, lambda: self.btn_run.config(state="normal", text="🚀 开始转换", bg="#007bff"))

if __name__ == "__main__":
    root = tk.Tk()
    app = OcrApp(root)
    root.mainloop()