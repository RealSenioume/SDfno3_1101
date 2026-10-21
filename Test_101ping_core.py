import sys, math
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from pynput import keyboard

class PingWheel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.hide()

        self.center = QPoint()
        self.current_sector = -1
        self.sectors = ["On My Way", "Push", "Enemy Vision", "Retreat",
                        "Need Vision", "Enemy Missing", "Assist Me", "All-In"]

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sector)
        self.timer.setInterval(16)  # ~60fps

    def start_at(self, pos):
        self.center = pos
        self.current_sector = -1
        self.show()
        self.timer.start()

    def update_sector(self):
        cursor = self.mapFromGlobal(self.cursor().pos())  # 获取全局鼠标位置
        dx = cursor.x() - self.center.x()
        dy = cursor.y() - self.center.y()
        dist = math.hypot(dx, dy)

        if dist < 30:  # 死区
            self.current_sector = -1
        else:
            angle = math.degrees(math.atan2(dy, dx)) % 360
            # 将角度映射到8个扇区，东=0°，北=90°（注意屏幕Y轴向下）
            self.current_sector = int(((angle + 22.5) % 360) // 45)
        self.update()

    def paintEvent(self, event):
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = 120
        rect = (self.center.x() - radius, self.center.y() - radius,
                radius * 2, radius * 2)

        for i in range(8):
            start_angle = i * 45 - 22.5
            color = QColor(60, 60, 60, 200) if i != self.current_sector else QColor(220, 180, 60, 240)
            painter.setBrush(color)
            painter.setPen(QPen(Qt.white, 2))
            # drawPie 的角度单位是 1/16 度，且0°在3点钟方向
            painter.drawPie(*rect, int((start_angle) * 16), 45 * 16)

        # 绘制中心圆和文字
        painter.setBrush(QColor(30, 30, 30, 220))
        painter.drawEllipse(self.center, 35, 35)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 10))
        painter.drawText(self.center.x() - 30, self.center.y() + 5, "Caution")

    def finish(self):
        self.timer.stop()
        self.hide()
        if 0 <= self.current_sector < 8:
            signal_name = self.sectors[self.current_sector]
            self.show_feedback(signal_name)

    def show_feedback(self, name):
        # 这里可以实现：在鼠标位置短暂显示一个图标/文字，并播放音效
        print(f"Ping: {name}")
        # 例如使用 QLabel 或 QSoundEffect 做即时反馈

# 全局监听 Alt 键
wheel = None
alt_held = False

def on_press(key):
    global alt_held
    if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
        if not alt_held:
            alt_held = True
            from PyQt5.QtCore import QPoint
            wheel.start_at(QPoint(wheel.cursor().pos()))  # 在鼠标当前位置展开

def on_release(key):
    global alt_held
    if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
        alt_held = False
        wheel.finish()

app = QApplication(sys.argv)
wheel = PingWheel()
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()
sys.exit(app.exec_())