import os
import sys
import winreg

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt, QUrl, pyqtProperty
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from app_ui import BubbleWidget, ChoicesWidget
from character_animator import ASSET_DIR, PoseAnimator, SpriteSheetAnimator, missing_pose_assets
from delete_engine import DELETE_MODE, delete_path


def get_resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def register_context_menu() -> None:
    try:
        exe_path = sys.executable
        if not exe_path.lower().endswith(".exe") or "python" in os.path.basename(exe_path).lower():
            script_path = os.path.abspath(__file__)
            command_str = f'"{exe_path}" "{script_path}" "%1"'
            icon_str = "shell32.dll,31"
        else:
            command_str = f'"{exe_path}" "%1"'
            icon_str = f'"{exe_path}",0'

        for key_path in (
            r"Software\Classes\*\shell\PhotoMonsterDelete",
            r"Software\Classes\Directory\shell\PhotoMonsterDelete",
        ):
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValue(key, "", winreg.REG_SZ, "召唤 AI 角色删除")
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_str)
            winreg.CloseKey(key)
            command_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\command")
            winreg.SetValue(command_key, "", winreg.REG_SZ, command_str)
            winreg.CloseKey(command_key)
    except Exception as exc:
        print(f"Context-menu registration failed: {exc}")


class MonsterDeleter(QWidget):
    def __init__(self, target_file: str | None):
        super().__init__()
        self.target_file = os.path.abspath(target_file) if target_file else None
        self.target_pos = None
        self._bg_opacity = 0.0
        self.sequence_started = False
        self.delete_result = ""
        self.explosion_triggered = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(QApplication.primaryScreen().geometry())

        self.animator = PoseAnimator(self)
        self.animator.hide()
        self.explosion_animator = SpriteSheetAnimator(self)
        self.explosion_animator.hide()
        self.bubble = BubbleWidget("")
        self.choices = ChoicesWidget()
        self.init_audio()
        self.init_targeting_ui()

    @pyqtProperty(float)
    def bg_opacity(self) -> float:
        return self._bg_opacity

    @bg_opacity.setter
    def bg_opacity(self, value: float) -> None:
        self._bg_opacity = value
        self.update()

    def init_audio(self) -> None:
        self.bgm_player = QMediaPlayer()
        self.bgm_audio = QAudioOutput()
        self.bgm_player.setAudioOutput(self.bgm_audio)
        self.bgm_audio.setVolume(0.45)

        self.sfx_player = QMediaPlayer()
        self.sfx_audio = QAudioOutput()
        self.sfx_player.setAudioOutput(self.sfx_audio)
        self.sfx_audio.setVolume(0.85)

        self.exp_player = QMediaPlayer()
        self.exp_audio = QAudioOutput()
        self.exp_player.setAudioOutput(self.exp_audio)
        self.exp_audio.setVolume(0.35)

        bgm_path = get_resource_path(r"assets\音频\bgm(1).mp3")
        speech_path = get_resource_path(r"assets\音频\怪兽说话.mp3")
        exp_path = get_resource_path(r"assets\音频\爆炸.MP4")
        if os.path.exists(bgm_path):
            self.bgm_player.setSource(QUrl.fromLocalFile(bgm_path))
            self.bgm_player.mediaStatusChanged.connect(self.loop_bgm)
        if os.path.exists(speech_path):
            self.sfx_player.setSource(QUrl.fromLocalFile(speech_path))
        if os.path.exists(exp_path):
            self.exp_player.setSource(QUrl.fromLocalFile(exp_path))

    def loop_bgm(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.bgm_player.setPosition(0)
            self.bgm_player.play()

    def init_targeting_ui(self) -> None:
        cursor_size = 40
        cursor_pixmap = QPixmap(cursor_size, cursor_size)
        cursor_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(cursor_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(255, 45, 45), 2))
        center, radius = cursor_size // 2, 12
        painter.drawEllipse(center - radius, center - radius, radius * 2, radius * 2)
        painter.drawLine(center, 0, center, center - 4)
        painter.drawLine(center, center + 4, center, cursor_size)
        painter.drawLine(0, center, center - 4, center)
        painter.drawLine(center + 4, center, cursor_size, center)
        painter.end()
        self.setCursor(QCursor(cursor_pixmap, center, center))

        self.fade_in_anim = QPropertyAnimation(self, b"bg_opacity")
        self.fade_in_anim.setDuration(500)
        self.fade_in_anim.setStartValue(0.0)
        self.fade_in_anim.setEndValue(0.38)
        self.fade_in_anim.start()

    def paintEvent(self, event) -> None:
        if self._bg_opacity <= 0.01:
            return
        painter = QPainter(self)
        painter.setOpacity(self._bg_opacity)
        painter.fillRect(self.rect(), QColor(10, 10, 12, 220))
        painter.setOpacity(min(1.0, self._bg_opacity / 0.38))
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)
        if self.target_file:
            filename = os.path.basename(self.target_file) or self.target_file
            text = f"点击屏幕上目标所在位置开始动画\n已锁定：{filename}"
        else:
            text = "演示模式：点击任意位置开始动画\n未通过右键菜单选择文件，因此不会删除任何内容"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.on_app_exit()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if not self.sequence_started and event.button() == Qt.MouseButton.LeftButton:
            self.target_pos = event.pos()
            self.sequence_started = True
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.fade_out_anim = QPropertyAnimation(self, b"bg_opacity")
            self.fade_out_anim.setDuration(350)
            self.fade_out_anim.setStartValue(self._bg_opacity)
            self.fade_out_anim.setEndValue(0.0)
            self.fade_out_anim.finished.connect(self.start_phase1_walk)
            self.fade_out_anim.start()

    def start_phase1_walk(self) -> None:
        self.bgm_player.play()
        if not self.animator.load_action("walk", target_height=470):
            self.show_missing_assets()
            return
        start_x = -self.animator.width()
        start_y = max(0, self.target_pos.y() - self.animator.height() // 2 + 90)
        end_x = max(0, self.target_pos.x() - self.animator.width() + 130)
        self.animator.move(start_x, start_y)
        self.animator.show()
        self.animator.play(fps=8, loop=True)

        self.move_anim = QPropertyAnimation(self.animator, b"pos")
        self.move_anim.setDuration(2600)
        self.move_anim.setStartValue(QPoint(start_x, start_y))
        self.move_anim.setEndValue(QPoint(end_x, start_y))
        self.move_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.move_anim.finished.connect(self.start_phase2_point)
        self.move_anim.start()

    def start_phase2_point(self) -> None:
        self.sfx_player.play()
        if not self.animator.load_action("point", target_height=470):
            self.show_missing_assets()
            return
        try:
            self.animator.animationFinished.disconnect()
        except TypeError:
            pass
        self.animator.animationFinished.connect(self.show_dialog)
        self.animator.play(fps=7, loop=False)

    def show_dialog(self) -> None:
        try:
            self.animator.animationFinished.disconnect()
        except TypeError:
            pass
        if self.target_file:
            name = os.path.basename(self.target_file) or self.target_file
            mode_text = "永久删除（不可恢复）" if DELETE_MODE == "permanent" else "移入回收站"
            self.bubble.set_text(f"确认对“{name}”执行：{mode_text}？")
        else:
            self.bubble.set_text("当前是演示模式：只播放 AI 动作动画，不会删除任何文件。")

        global_pos = self.mapToGlobal(self.animator.pos())
        self.bubble.adjustSize()
        bubble_x = global_pos.x() + max(20, self.animator.width() // 2 - self.bubble.width() // 2)
        bubble_y = max(20, global_pos.y() - 10)
        self.bubble.move(bubble_x, bubble_y)
        self.bubble.show()

        self.choices.configure(bool(self.target_file))
        self.choices.adjustSize()
        choices_x = bubble_x + max(0, (self.bubble.width() - self.choices.width()) // 2)
        choices_y = bubble_y + self.bubble.height() + 8
        self.choices.move(choices_x, choices_y)
        try:
            self.choices.choiceMade.disconnect()
        except TypeError:
            pass
        self.choices.choiceMade.connect(self.on_choice)
        self.choices.show()

    def on_choice(self, confirmed: bool) -> None:
        self.choices.hide()
        if not confirmed:
            self.bubble.hide()
            self.on_app_exit()
            return
        self.bubble.hide()
        self.start_phase3_kick()

    def start_phase3_kick(self) -> None:
        try:
            self.animator.animationFinished.disconnect()
            self.animator.frameChanged.disconnect()
        except TypeError:
            pass
        if not self.animator.load_action("kick", target_height=470):
            self.show_missing_assets()
            return
        self.explosion_triggered = False
        self.animator.frameChanged.connect(self.on_kick_frame)
        self.animator.animationFinished.connect(self.on_kick_finished)
        self.animator.play(fps=9, loop=False)

    def on_kick_frame(self, frame_idx: int) -> None:
        if self.explosion_triggered or not self.animator.frames:
            return
        impact_index = max(1, int(len(self.animator.frames) * 0.60))
        if frame_idx >= impact_index:
            self.explosion_triggered = True
            self.trigger_explosion()

    def trigger_explosion(self) -> None:
        self.exp_player.play()
        explosion_path = str(ASSET_DIR / "爆炸_spritesheet.png")
        if self.explosion_animator.load_spritesheet(explosion_path, target_height=180):
            exp_x = self.target_pos.x() - self.explosion_animator.width() // 2
            exp_y = self.target_pos.y() - self.explosion_animator.height() // 2 - 30
            self.explosion_animator.move(exp_x, exp_y)
            self.explosion_animator.show()
            try:
                self.explosion_animator.animationFinished.disconnect()
            except TypeError:
                pass
            self.explosion_animator.animationFinished.connect(self.explosion_animator.hide)
            self.explosion_animator.play(fps=9, loop=False)
        self.delete_target_file()

    def delete_target_file(self) -> None:
        if not self.target_file:
            self.delete_result = "演示模式：未删除文件。"
            return
        try:
            self.delete_result = delete_path(self.target_file)
            print(self.delete_result)
        except Exception as exc:
            self.delete_result = f"删除失败：{exc}"
            print(self.delete_result)

    def on_kick_finished(self) -> None:
        try:
            self.animator.animationFinished.disconnect()
            self.animator.frameChanged.disconnect()
        except TypeError:
            pass
        if not self.explosion_triggered:
            self.explosion_triggered = True
            self.trigger_explosion()
        self.start_phase4_result()

    def start_phase4_result(self) -> None:
        self.animator.load_action("point", target_height=420)
        self.animator.play(fps=4, loop=True)
        if self.delete_result:
            self.bubble.set_text(self.delete_result)
            global_pos = self.mapToGlobal(self.animator.pos())
            self.bubble.adjustSize()
            self.bubble.move(global_pos.x() + 20, max(20, global_pos.y() - 30))
            self.bubble.show()
        QTimer.singleShot(1200, self.start_phase5_leave)

    def start_phase5_leave(self) -> None:
        self.bubble.hide()
        self.animator.load_action("walk", target_height=470, mirror=True)
        self.animator.play(fps=8, loop=True)
        screen = QApplication.primaryScreen().geometry()
        self.move_anim2 = QPropertyAnimation(self.animator, b"pos")
        self.move_anim2.setDuration(1600)
        self.move_anim2.setStartValue(self.animator.pos())
        self.move_anim2.setEndValue(QPoint(screen.width() + 120, self.animator.pos().y()))
        self.move_anim2.setEasingCurve(QEasingCurve.Type.InCubic)
        self.move_anim2.finished.connect(self.on_app_exit)
        self.move_anim2.start()

    def show_missing_assets(self) -> None:
        missing = missing_pose_assets()
        QMessageBox.critical(
            self,
            "缺少 AI 动作资源",
            "缺少：" + "、".join(missing) + "\n\n先运行：\npython tools\\comfyui_generate_poses.py",
        )
        self.on_app_exit()

    def on_app_exit(self) -> None:
        self.bgm_player.stop()
        self.sfx_player.stop()
        self.exp_player.stop()
        self.bubble.hide()
        self.choices.hide()
        self.close()
        QApplication.quit()


def main() -> int:
    register_context_menu()
    app = QApplication(sys.argv)
    missing = missing_pose_assets()
    if missing:
        QMessageBox.critical(
            None,
            "缺少 AI 动作资源",
            "当前版本已经禁用旧的同图旋转/缩放伪动作。\n\n"
            f"缺少：{', '.join(missing)}\n\n"
            "请先运行：\npython tools\\comfyui_generate_poses.py\n\n"
            "生成 walk / point / kick 后再运行或打包。",
        )
        return 2

    target = sys.argv[1] if len(sys.argv) >= 2 else None
    window = MonsterDeleter(target)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
