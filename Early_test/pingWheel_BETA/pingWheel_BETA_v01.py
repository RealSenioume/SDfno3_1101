import sys, math, queue, signal, time, threading
from PyQt5.QtWidgets import QApplication, QWidget, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QIcon, QPixmap, QCursor
from pynput import keyboard, mouse

signal.signal(signal.SIGINT, signal.SIG_DFL)

SECTOR_NAMES = [
    "On My Way", "All-In", "Assist Me", "Need Vision",
    "Enemy Missing", "Enemy Vision", "Retreat", "Push",
]

def lerp(a, b, t):
    return a + (b - a) * t


class PingWheel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 鼠标穿透：轮盘显示期间底层应用仍能收到鼠标事件，
        # 扇区选择完全靠 pynput 全局监听，不依赖窗口事件。
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.hide()

        self.center = QPoint()
        self.current_sector = -1
        self.weights = [0.0] * 8

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.setInterval(16)
        self._last_tick = time.perf_counter()

    def start_at(self, global_pos):
        self.center = global_pos
        self.current_sector = -1
        self.weights = [0.0] * 8
        self._last_tick = time.perf_counter()

        # 关键：show 期间禁止绘制，避免露出旧的 backing store
        self.setUpdatesEnabled(False)
        self.show()
        self.raise_()
        self.setUpdatesEnabled(True)

        # 同步重绘：在窗口呈现前把新内容画完
        self.repaint()

        self.timer.start()

    def finish(self):
        self.timer.stop()

        sector = self.current_sector
        # 隐藏前把内容清空并同步绘制一次，
        # 下次 show() 时 backing store 就不会残留旧位置的画面
        self.weights = [0.0] * 8
        self.current_sector = -1
        self.repaint()
        self.hide()
        if 0 <= sector < 8:
            self.show_feedback(SECTOR_NAMES[sector])

    def show_feedback(self, name):
        print(f"Ping: {name}")

    def tick(self):
        now = time.perf_counter()
        dt = min(now - self._last_tick, 0.05)
        self._last_tick = now

        self.update_sector()

        tau = 0.035
        alpha = 1.0 - math.exp(-dt / tau)
        for i in range(8):
            target = 1.0 if i == self.current_sector else 0.0
            self.weights[i] += (target - self.weights[i]) * alpha
            if abs(self.weights[i] - target) < 0.005:
                self.weights[i] = target

        self.update()

    def update_sector(self):
        cursor = QCursor.pos()
        dx = cursor.x() - self.center.x()
        dy = cursor.y() - self.center.y()
        dist = math.hypot(dx, dy)
        if dist < 30:
            self.current_sector = -1
        else:
            angle = math.degrees(math.atan2(dy, dx)) % 360
            self.current_sector = int(((angle + 22.5) % 360) // 45)

    def paintEvent(self, event):
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        c = self.mapFromGlobal(self.center)
        base_r = 120
        extra = 8
        glow = 12
        radii = [base_r + extra * self.weights[i] for i in range(8)]

        # 光晕层
        for i in range(8):
            w = self.weights[i]
            if w < 0.02:
                continue
            r = radii[i] + glow
            rect = (c.x() - r, c.y() - r, r * 2, r * 2)
            start_deg = -(i * 45) - 22.5
            color = QColor(255, 220, 120)
            color.setAlphaF(0.35 * w)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawPie(*[int(v) for v in rect], int(start_deg * 16), 45 * 16)

        # 扇区本体（按权重升序，高亮在最上）
        order = sorted(range(8), key=lambda i: self.weights[i])
        for i in order:
            w = self.weights[i]
            r = radii[i]
            rect = (c.x() - r, c.y() - r, r * 2, r * 2)
            start_deg = -(i * 45) - 22.5

            gray = QColor(60, 60, 60)
            gold = QColor(220, 180, 60)
            fill = QColor(
                int(lerp(gray.red(),   gold.red(),   w)),
                int(lerp(gray.green(), gold.green(), w)),
                int(lerp(gray.blue(),  gold.blue(),  w)),
            )
            fill.setAlpha(int(lerp(110, 240, w)))

            pen_color = QColor(255, 255, 255)
            pen_color.setAlpha(int(lerp(80, 255, w)))
            pen_width = lerp(1.0, 3.0, w)

            painter.setBrush(fill)
            painter.setPen(QPen(pen_color, pen_width))
            painter.drawPie(*[int(v) for v in rect], int(start_deg * 16), 45 * 16)

        # 中心圆
        painter.setBrush(QColor(30, 30, 30, 230))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawEllipse(c, 42, 42)

        # 中心文字
        text = SECTOR_NAMES[self.current_sector] if self.current_sector >= 0 else "Caution"
        font = QFont("Arial", 10, QFont.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        max_w = 68
        while metrics.horizontalAdvance(text) > max_w and font.pointSize() > 6:
            font.setPointSize(font.pointSize() - 1)
            painter.setFont(font)
            metrics = painter.fontMetrics()

        painter.setPen(Qt.white)
        tw = metrics.horizontalAdvance(text)
        baseline_y = c.y() + (metrics.ascent() - metrics.descent()) // 2
        painter.drawText(c.x() - tw // 2, baseline_y, text)


def make_tray_icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(220, 180, 60))
    p.setPen(QPen(Qt.white, 3))
    p.drawEllipse(8, 8, 48, 48)
    p.end()
    return QIcon(pix)


app = QApplication(sys.argv)
wheel = PingWheel()

# ---------- 托盘 ----------
tray = QSystemTrayIcon(make_tray_icon(), app)
tray.setToolTip("LOL 桌面标记 —— Alt+左键唤醒，Esc 退出")
tray_menu = QMenu()
act_quit = QAction("退出", tray_menu)
tray_menu.addAction(act_quit)
tray.setContextMenu(tray_menu)
tray.show()

# ---------- 跨线程共享 Alt 状态 ----------
_state_lock = threading.Lock()
_alt_held = False

def set_alt_held(v: bool):
    global _alt_held
    with _state_lock:
        _alt_held = v

def is_alt_held() -> bool:
    with _state_lock:
        return _alt_held


# ---------- 事件队列（监听线程 → 主线程） ----------
action_queue = queue.Queue()
_listeners = []

def quit_all():
    for l in _listeners:
        try:
            l.stop()
        except Exception:
            pass
    app.quit()

act_quit.triggered.connect(quit_all)

def poll_actions():
    while True:
        try:
            action = action_queue.get_nowait()
        except queue.Empty:
            break
        if isinstance(action, tuple):
            kind = action[0]
            if kind == "start":
                _, x, y = action
                if not wheel.isVisible():
                    wheel.start_at(QPoint(int(x), int(y)))
            elif kind == "finish":
                if wheel.isVisible():
                    wheel.finish()
        elif action == "quit":
            quit_all()

poll_timer = QTimer()
poll_timer.timeout.connect(poll_actions)
poll_timer.start(16)

# ---------- 键盘：Alt 只记状态，不再单独唤醒 ----------
def on_press(key):
    if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
        set_alt_held(True)
    elif key == keyboard.Key.esc:
        action_queue.put("quit")

def on_release(key):
    if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
        set_alt_held(False)

keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
keyboard_listener.start()
_listeners.append(keyboard_listener)

# ---------- 鼠标：Alt 按住时左键按下 = 唤醒；松开左键 = 提交 ----------
def on_click(x, y, button, pressed):
    if button != mouse.Button.left:
        return
    if pressed:
        if is_alt_held():
            action_queue.put(("start", x, y))
    else:
        action_queue.put(("finish",))

mouse_listener = mouse.Listener(on_click=on_click)
mouse_listener.start()
_listeners.append(mouse_listener)

sys.exit(app.exec_())