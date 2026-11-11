import time
import os
import sys
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab
import keyboard
import threading

class RelicEnhanceV1:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(__file__))
        self.img_dir = os.path.join(base_dir, "assets", "enhance_imgs")
        
        self.unlock_btn_path = os.path.join(self.img_dir, "unlock_btn.png") 
        self.lock_btn_path = os.path.join(self.img_dir, "lock_btn.png")     
        self.trash_btn_path = os.path.join(self.img_dir, "trash_btn.png")   
        self.untrash_btn_path = os.path.join(self.img_dir, "untrash_btn.png") 
        self.auto_btn_path = os.path.join(self.img_dir, "auto_btn.png")
        self.enhance_btn_path = os.path.join(self.img_dir, "enhance_btn.png")
        self.details_btn_path = os.path.join(self.img_dir, "details_btn.png")
        
        self.confidence = 0.75  
        self.animation_time = 2.0 
        
        self.running = False
        self.is_macro_active = False
        
        # 默认鼠标侧键映射
        self.driver_lock_key = 'ctrl+c'
        self.driver_trash_key = 'ctrl+v'
        
        self.hk_enhance = None
        self.hk_toggle = None
        self.hk_lock = None
        self.hk_trash = None

    def _find(self, image_path, bbox=None):
        if not os.path.exists(image_path): return False
        try:
            if bbox:
                screen = ImageGrab.grab(bbox=bbox)
                offset_x, offset_y = bbox[0], bbox[1]
            else:
                screen = ImageGrab.grab()
                offset_x, offset_y = 0, 0
                
            screen_cv = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
            template = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if template is None: return False
            
            result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= self.confidence:
                return (max_loc[0] + offset_x, max_loc[1] + offset_y), template.shape[:-1]
            return False
        except Exception:
            return False

    def _find_and_click(self, image_path, bbox=None):
        res = self._find(image_path, bbox)
        if res:
            loc, shape = res
            h, w = shape
            pyautogui.click(loc[0] + w // 2, loc[1] + h // 2)
            return True
        return False

    def _is_in_inventory(self):
        w, h = pyautogui.size()
        bbox = (int(w * 0.75), int(h * 0.75), w, h)
        return True if self._find(self.details_btn_path, bbox) else False

    def _smart_next(self):
        time.sleep(0.4) 
        w, h = pyautogui.size()
        bbox = (int(w * 0.55), int(h * 0.2), int(w * 0.95), int(h * 0.8))
        
        img_before = np.array(ImageGrab.grab(bbox=bbox))
        pyautogui.press('d')
        time.sleep(0.3) 
        img_after = np.array(ImageGrab.grab(bbox=bbox))
        
        diff = np.mean(np.abs(img_before.astype(np.int16) - img_after.astype(np.int16)))
        
        if diff < 3.0:  
            pyautogui.press('s')  
            time.sleep(0.2)
            pyautogui.press('a', presses=15, interval=0.03) 
            print("[遗器助手] ↩️ 确实到了行末，已自动换行")
        else:
            print("[遗器助手] ➡️ 切换成功，向右切到下一个")

    def do_enhance(self):
        if self.running: return
        self.running = True
        try:
            print("\n[遗器助手] 自动置入 + 强化...")
            w, h = pyautogui.size()
            bottom_bbox = (int(w * 0.3), int(h * 0.5), int(w * 0.99), int(h * 0.99))
            
            if not self._find_and_click(self.auto_btn_path, bottom_bbox):
                print("[遗器助手] ❌ 未找到[自动置入]按钮")
                return
            time.sleep(0.2) 
            
            if not self._find_and_click(self.enhance_btn_path, bottom_bbox):
                print("[遗器助手] ❌ 未找到[强化]按钮")
                return
            
            print(f"[遗器助手] ✅ 强化指令已发送，等待动画 ({self.animation_time}秒)...")
            time.sleep(self.animation_time)
            
            pyautogui.click(int(w * 0.5), int(h * 0.8))
            time.sleep(0.5)
            pyautogui.click(int(w * 0.5), int(h * 0.8))
            
            print("[遗器助手] ✅ 本次强化完成，请查看词条。")
        finally:
            self.running = False

    def do_lock(self):
        print("[遗器助手] 尝试切换锁定状态...")
        w, h = pyautogui.size()
        right_bbox = (int(w * 0.5), int(h * 0.1), int(w * 0.99), int(h * 0.9))
        
        if self._find_and_click(self.unlock_btn_path, right_bbox):
            print("[遗器助手] 🔒 已成功锁定")
        elif self._find_and_click(self.lock_btn_path, right_bbox):
            print("[遗器助手] 🔓 已成功解锁")
        else:
            print("[遗器助手] ⚠️ 没找到锁定/解锁图标")
            return

        if self._is_in_inventory():
            self._smart_next()
        else:
            print("[遗器助手] 💡 强化界面，不切下一个。")

    def do_trash(self):
        print("[遗器助手] 尝试切换弃置状态...")
        w, h = pyautogui.size()
        right_bbox = (int(w * 0.5), int(h * 0.1), int(w * 0.99), int(h * 0.9))
        
        if self._find_and_click(self.trash_btn_path, right_bbox):
            print("[遗器助手] 🗑️ 已标记弃置")
        elif self._find_and_click(self.untrash_btn_path, right_bbox):
            print("[遗器助手] ♻️ 已取消弃置")
        else:
            print("[遗器助手] ⚠️ 没找到弃置/取消弃置图标")
            return

        if self._is_in_inventory():
            self._smart_next()
        else:
            print("[遗器助手] 💡 强化界面，不切下一个。")

    def toggle_macro(self):
        self.is_macro_active = not self.is_macro_active
        
        if self.is_macro_active:
            self.hk_lock = keyboard.add_hotkey(self.driver_lock_key, lambda: threading.Thread(target=self.do_lock).start(), suppress=True)
            self.hk_trash = keyboard.add_hotkey(self.driver_trash_key, lambda: threading.Thread(target=self.do_trash).start(), suppress=True)
            print(f"\n[遗器助手] 🟢 【游戏模式】已开启：侧键拦截为 [{self.driver_lock_key}] 和 [{self.driver_trash_key}]")
        else:
            if self.hk_lock: keyboard.remove_hotkey(self.hk_lock)
            if self.hk_trash: keyboard.remove_hotkey(self.hk_trash)
            self.hk_lock = None
            self.hk_trash = None
            print("\n[遗器助手] 🔴 【办公模式】已恢复：侧键变回复制粘贴")

    def start_listen(self, key_enhance='f9', key_toggle='f12', key_lock='ctrl+c', key_trash='ctrl+v'):
        """启动监听，支持自定义4个按键"""
        if self.hk_enhance is not None:
            return 
            
        self.driver_lock_key = key_lock
        self.driver_trash_key = key_trash
            
        print(f">>> 遗器辅助已启动！强化键: {key_enhance} | 接管键: {key_toggle} | 加锁映射: {key_lock} | 弃置映射: {key_trash}")
        
        self.hk_enhance = keyboard.add_hotkey(key_enhance, lambda: threading.Thread(target=self.do_enhance).start())
        self.hk_toggle = keyboard.add_hotkey(key_toggle, self.toggle_macro)

    def stop_listen(self):
        """停止监听"""
        if self.hk_enhance is None:
            return 
            
        print(">>> 正在停止遗器辅助...")
        
        keyboard.remove_hotkey(self.hk_enhance)
        keyboard.remove_hotkey(self.hk_toggle)
        self.hk_enhance = None
        self.hk_toggle = None
        
        if self.is_macro_active:
            self.toggle_macro()
            
        print(">>> 遗器辅助已安全停止。")