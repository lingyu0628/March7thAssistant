from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSpacerItem, QScroller, QScrollerProperties, QFileDialog, QLineEdit, QHBoxLayout
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, InfoBarPosition, MessageBox, PushButton, ExpandSettingCard, SwitchButton, IndicatorPosition
from .card.pushsettingcard1 import PushSettingCardCode
from .card.autoplot_setting_card import AutoPlotSettingCard
from .common.style_sheet import StyleSheet
from .common.icon import UiIcon
import tasks.tool as tool
import base64
import subprocess
from utils import clipboard
from module.config import cfg
from tasks.base.tasks import start_task
import os
import sys
import traceback

# ================= 引入遗器助手 =================
from tasks.relic_enhance import RelicEnhanceV1
# ================================================

from module.localization import tr
from module.logger import log

# ================= 自定义按键捕获输入框 =================
class HotkeyEdit(QLineEdit):
    def __init__(self, default_key, parent=None):
        super().__init__(parent)
        self.setText(default_key)
        self.setPlaceholderText("点击后按键...")
        self.setFixedWidth(120)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.is_recording = False
        self.original_key = default_key
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)

    def mousePressEvent(self, event):
        if not self.is_recording:
            self.is_recording = True
            self.original_key = self.text()
            self.setText("请按键...")
            self.setStyleSheet("color: #00BFFF;")
            self.setFocus()
        super().mousePressEvent(event)

    def focusOutEvent(self, event):
        if self.is_recording:
            self.is_recording = False
            self.setText(self.original_key)
            self.setStyleSheet("")
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if self.is_recording:
            key_code = event.key()
            modifiers = event.modifiers()

            if key_code in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                return

            key_str = ""
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                key_str += "ctrl+"
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                key_str += "shift+"
            if modifiers & Qt.KeyboardModifier.AltModifier:
                key_str += "alt+"

            key_text = event.text().lower()

            if Qt.Key.Key_F1 <= key_code <= Qt.Key.Key_F12:
                key_text = f"f{key_code - Qt.Key.Key_F1 + 1}"
            elif key_code == Qt.Key.Key_Space:
                key_text = "space"
            elif key_code == Qt.Key.Key_Escape:
                self.is_recording = False
                self.setText(self.original_key)
                self.setStyleSheet("")
                self.clearFocus()
                return

            if not key_text:
                return

            key_str += key_text
            self.setText(key_str)
            self.is_recording = False
            self.setStyleSheet("")
            self.clearFocus()
            event.accept()
        else:
            super().keyPressEvent(event)
# ===========================================================

# ================= 自定义带开关的展开卡片 =================
class RelicEnhanceCard(ExpandSettingCard):
    def __init__(self, parent=None):
        super().__init__(FIF.CHAT, tr("遗器半自动助手"), tr("拦截鼠标侧键，实现自动置入/强化与快捷加锁/弃置"), parent)

        # 【核心复刻】创建开关，文字在左，开关在右
        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)

        # 【核心复刻】直接塞进 self.card 布局中，完美对齐
        self.card.addWidget(self.switchButton)

        # 绑定开关信号（用于启动/停止脚本）
        self.switchButton.checkedChanged.connect(self.__onSwitchChanged)

        # 布局输入框
        self.hLayout1 = QHBoxLayout()
        self.label1 = QLabel("强化键:")
        self.edit_enhance = HotkeyEdit("f9", self)
        self.hLayout1.addWidget(self.label1)
        self.hLayout1.addWidget(self.edit_enhance)
        self.hLayout1.addStretch(1)

        self.hLayout2 = QHBoxLayout()
        self.label2 = QLabel("接管键:")
        self.edit_toggle = HotkeyEdit("f12", self)
        self.hLayout2.addWidget(self.label2)
        self.hLayout2.addWidget(self.edit_toggle)
        self.hLayout2.addStretch(1)

        self.hLayout3 = QHBoxLayout()
        self.label3 = QLabel("前侧键映射(加锁):")
        self.edit_lock = HotkeyEdit("ctrl+c", self)
        self.hLayout3.addWidget(self.label3)
        self.hLayout3.addWidget(self.edit_lock)
        self.hLayout3.addStretch(1)

        self.hLayout4 = QHBoxLayout()
        self.label4 = QLabel("后侧键映射(弃置):")
        self.edit_trash = HotkeyEdit("ctrl+v", self)
        self.hLayout4.addWidget(self.label4)
        self.hLayout4.addWidget(self.edit_trash)
        self.hLayout4.addStretch(1)

        self.viewLayout.addLayout(self.hLayout1)
        self.viewLayout.addLayout(self.hLayout2)
        self.viewLayout.addLayout(self.hLayout3)
        self.viewLayout.addLayout(self.hLayout4)

        self.setExpand(False) # 默认折叠

    def __onSwitchChanged(self, isChecked: bool):
        """由工具箱界面接管开启/关闭逻辑，这里只负责转发信号"""
        # 因为外部的 ToolsInterface 需要监听这个信号来启动/停止脚本
        # 我们在这里将信号转发出去，外部的 __onRelicSwitchChanged 会处理
        # 但为了跟原生一样不报错，直接暴露即可，不需要自己写逻辑
        pass
# ===========================================================

class ToolsInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.toolsLabel = QLabel(tr("工具箱"), self)

        self.ToolsGroup = SettingCardGroup(tr('工具箱'), self.scrollWidget)
        self.automaticPlotCard = AutoPlotSettingCard(
            FIF.CHAT,
            tr("自动对话"),
            tr("进入剧情页面后自动开始运行，支持大于等于 1920*1080 的 16:9 分辨率，不支持云·星穹铁道")
        )
        self.gameScreenshotCard = PushSettingCard(
            tr('捕获'),
            FIF.CAMERA,
            tr("游戏截图"),
            tr("检查程序获取的图像是否正确，支持OCR识别文字（可用于自行排查异常）")
        )
        self.unlockfpsCard = PushSettingCard(
            tr('解锁'),
            FIF.SPEED_HIGH,
            tr("解锁帧率"),
            tr("通过修改注册表解锁120帧率，如已解锁，再次点击将恢复60帧率（支持国服和国际服）")
        )
        self.redemptionCodeCard = PushSettingCardCode(
            tr('执行'),
            UiIcon.TICKET,
            tr("兑换码"),
            "redemption_code",
            self
        )
        self.cloudTouchCard = PushSettingCard(
            tr('启动'),
            UiIcon.TAP,
            tr("触屏模式"),
            tr("以云游戏移动端 UI 的方式启动游戏，可搭配 UU远程 平板触控模式，启动后会将命令复制到剪贴板内")
        )
        self.screenTestCard = PushSettingCard(
            tr('测试'),
            UiIcon.BEAKER,
            tr("界面可切换性测试"),
            tr("以最短路径遍历所有可达界面，验证界面切换是否正常")
        )
        self.characterExportCard = PushSettingCard(
            tr('导出'),
            FIF.PEOPLE,
            tr("角色面板导出"),
            tr("读取全部角色的属性、光锥、星魂、技能和遗器，保存到程序目录的 characters.json")
        )

        # ================= 遗器助手卡片实例化 =================
        self.relicEnhanceTask = RelicEnhanceV1()
        self.relicEnhanceCard = RelicEnhanceCard(self)
        # ========================================================

        self.__initWidget()

        if sys.platform == 'win32' and self.automaticPlotCard.getSwitchState():
            self.__startAutoPlot()

    def retranslateUi(self):
        """保留自动对话开关及其运行状态，不再次启动后台工具。"""
        StyleSheet.TOOLS_INTERFACE.apply(self)
        self.toolsLabel.setText(tr('工具箱'))
        self.toolsLabel.adjustSize()
        self.ToolsGroup.titleLabel.setText(tr('工具箱'))
        self.automaticPlotCard.card.setTitle(tr('自动对话'))
        self.automaticPlotCard.card.setContent(tr('进入剧情页面后自动开始运行，支持大于等于 1920*1080 的 16:9 分辨率，不支持云·星穹铁道'))
        self.automaticPlotCard.retranslateUi()
        self.gameScreenshotCard.setTitle(tr('游戏截图'))
        self.gameScreenshotCard.setContent(tr('检查程序获取的图像是否正确，支持OCR识别文字（可用于自行排查异常）'))
        self.gameScreenshotCard.button.setText(tr('捕获'))
        self.unlockfpsCard.setTitle(tr('解锁帧率'))
        self.unlockfpsCard.setContent(tr('通过修改注册表解锁120帧率，如已解锁，再次点击将恢复60帧率（支持国服和国际服）'))
        self.unlockfpsCard.button.setText(tr('解锁'))
        self.redemptionCodeCard.setTitle(tr('兑换码'))
        self.redemptionCodeCard.title = tr('兑换码')
        self.redemptionCodeCard.setContent(tr('批量使用兑换码，每行一个，自动过滤空格等无效字符'))
        self.redemptionCodeCard.button.setText(tr('执行'))
        self.cloudTouchCard.setTitle(tr('触屏模式'))
        self.cloudTouchCard.setContent(tr('以云游戏移动端 UI 的方式启动游戏，可搭配 UU远程 平板触控模式，启动后会将命令复制到剪贴板内'))
        self.cloudTouchCard.button.setText(tr('启动'))
        self.screenTestCard.setTitle(tr('界面可切换性测试'))
        self.screenTestCard.setContent(tr('以最短路径遍历所有可达界面，验证界面切换是否正常'))
        self.screenTestCard.button.setText(tr('测试'))
        self.characterExportCard.setTitle(tr('角色面板导出'))
        self.characterExportCard.setContent(tr('读取全部角色的属性、光锥、星魂、技能和遗器，保存到程序目录的 characters.json'))
        self.characterExportCard.button.setText(tr('导出'))

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('toolsInterface')

        self.scrollWidget.setObjectName('scrollWidget')
        self.toolsLabel.setObjectName('toolsLabel')
        StyleSheet.TOOLS_INTERFACE.apply(self)

        self.__initLayout()
        self.__connectSignalToSlot()

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __initLayout(self):
        self.toolsLabel.move(36, 30)

        self.ToolsGroup.addSettingCard(self.automaticPlotCard)
        self.ToolsGroup.addSettingCard(self.relicEnhanceCard)
        self.ToolsGroup.addSettingCard(self.gameScreenshotCard)
        self.ToolsGroup.addSettingCard(self.unlockfpsCard)
        self.ToolsGroup.addSettingCard(self.redemptionCodeCard)
        self.ToolsGroup.addSettingCard(self.cloudTouchCard)
        self.ToolsGroup.addSettingCard(self.screenTestCard)
        self.ToolsGroup.addSettingCard(self.characterExportCard)

        if sys.platform != 'win32':
            self.automaticPlotCard.setDisabled(True)
            self.unlockfpsCard.setDisabled(True)
            self.cloudTouchCard.setDisabled(True)

        self.ToolsGroup.titleLabel.setHidden(True)

        self.vBoxLayout.setSpacing(28)
        self.vBoxLayout.setContentsMargins(36, 10, 36, 0)
        self.vBoxLayout.addWidget(self.ToolsGroup)

        for i in range(self.ToolsGroup.vBoxLayout.count()):
            item = self.ToolsGroup.vBoxLayout.itemAt(i)
            if isinstance(item, QSpacerItem):
                self.ToolsGroup.vBoxLayout.removeItem(item)
                break

    def __onUnlockfpsCardClicked(self):
        from utils.registry.star_rail_setting import get_game_fps, set_game_fps, MissingFPSSettingError  # 延迟导入，避免非 Windows 平台报错
        try:
            fps = get_game_fps()
            if fps == 120:
                set_game_fps(60)
                InfoBar.info(
                    title=tr('恢复60成功 (＾∀＾●)'),
                    content="",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
            else:
                set_game_fps(120)
                InfoBar.success(
                    title=tr('解锁120成功 (＾∀＾●)'),
                    content="",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
        except Exception as e:
            if isinstance(e, MissingFPSSettingError):
                content = tr("请将游戏图像质量修改为自定义后重试")
                log.warning("解锁帧率失败：请将游戏图像质量修改为自定义后重试")
            else:
                log.error(f"解锁帧率失败：{e}\n{traceback.format_exc()}")
                error = f"{type(e).__name__}: {' '.join(str(e).split())}"
                if len(error) > 80:
                    error = error[:79] + "…"
                content = tr("{error}（详情见日志）").format(error=error)
            InfoBar.warning(
                title=tr('解锁失败'),
                content=content,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def __onCloudTouchCardClicked(self):
        exe_path = os.path.abspath(os.path.join(cfg.genshin_starRail_fps_unlocker_path, "unlocker.exe"))
        config_path = os.path.abspath(os.path.join(cfg.genshin_starRail_fps_unlocker_path, "hoyofps_config.ini"))
        game_path = os.path.abspath(cfg.game_path)
        try:
            if cfg.genshin_starRail_fps_unlocker_allow is False:
                from qfluentwidgets import MessageBox
                # 依次展示多次确认对话框，每次提示更严肃，任意一次取消即返回
                confirm_messages = [
                    (tr('此功能依赖第三方程序实现'),
                     tr('https://github.com/winTEuser/Genshin_StarRail_fps_unlocker\n使用本功能产生的所有问题与本项目与开发者团队无关，是否继续？')),
                    (tr('再次确认：可能存在风险'),
                     tr('工作原理是通过 WriteProcessMemory 把代码写进游戏，是否继续？')),
                    (tr('最终确认：请谨慎操作'),
                     tr('确认继续并允许启用触屏模式？')),
                ]

                for title, message in confirm_messages:
                    from qfluentwidgets import MessageBox
                    step_confirm = MessageBox(title, message, self.window())
                    step_confirm.yesButton.setText(tr('确认'))
                    step_confirm.cancelButton.setText(tr('取消'))
                    if not step_confirm.exec():
                        return

                cfg.set_value("genshin_starRail_fps_unlocker_allow", True)

            if not game_path or not os.path.exists(game_path):
                InfoBar.warning(
                    title=tr('游戏路径配置错误(╥╯﹏╰╥)'),
                    content=tr("请在“设置”→“程序”中配置正确的游戏路径"),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return

            if not os.path.exists(exe_path):
                start_task("mobileui_update")
                return

            config_dir = os.path.dirname(config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            import configparser
            cp = configparser.ConfigParser()

            if os.path.exists(config_path):
                cp.read(config_path, encoding='utf-16')
                if 'Setting' not in cp:
                    cp['Setting'] = {}
                old_path = cp['Setting'].get('HKSRPath', '')
                old_fps = cp['Setting'].get('FPS', '')
                if old_path != game_path or old_fps != '60':
                    cp['Setting']['HKSRPath'] = game_path
                    cp['Setting']['FPS'] = '60'
                    with open(config_path, 'w', encoding='utf-16') as f:
                        cp.write(f)
            else:
                cp['Setting'] = {'HKSRPath': game_path, 'FPS': '60'}
                with open(config_path, 'w', encoding='utf-16') as f:
                    cp.write(f)
            args = ["-HKSR", "-EnableMobileUI"]
            subprocess.Popen([exe_path] + args, cwd=config_dir)
            clipboard.copy(f'cd "{config_dir}" && "{exe_path}" {" ".join(args)}')
            InfoBar.success(
                title=tr('启动成功(＾∀＾●)'),
                content=tr("已将命令复制到剪贴板"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.warning(
                title=tr('启动失败'),
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def __onGameScreenshotCardClicked(self):
        """点击截图卡片后先选择来源：游戏窗口或本地图片。"""
        message_box = MessageBox(tr("截图来源"), tr("请选择截图方式"), self.window())
        message_box.contentLabel.setMinimumWidth(500)

        message_box.yesButton.setText(tr("捕获游戏窗口"))
        message_box.cancelButton.setText(tr("取消"))

        choose_file_button = PushButton(tr("手动选择图片"), message_box)
        message_box.buttonLayout.insertWidget(1, choose_file_button, 1, Qt.AlignmentFlag.AlignVCenter)

        action = {"value": None}

        def _choose_local_file():
            action["value"] = "file"
            message_box.reject()

        choose_file_button.clicked.connect(_choose_local_file)

        accepted = message_box.exec()

        if action["value"] == "file":
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                tr("选择图片"),
                "",
                "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)"
            )
            if file_path:
                tool.start_screenshot_from_file(file_path)
            return

        if accepted:
            tool.start("screenshot")

    def __connectSignalToSlot(self):
        self.gameScreenshotCard.clicked.connect(self.__onGameScreenshotCardClicked)
        self.automaticPlotCard.switchChanged.connect(self.__onAutoPlotSwitchChanged)
        self.automaticPlotCard.optionsChanged.connect(self.__onAutoPlotOptionsChanged)
        self.unlockfpsCard.clicked.connect(self.__onUnlockfpsCardClicked)
        self.cloudTouchCard.clicked.connect(self.__onCloudTouchCardClicked)
        self.screenTestCard.clicked.connect(self.__onScreenTestCardClicked)
        self.characterExportCard.clicked.connect(self.__onCharacterExportCardClicked)

        # ================= 绑定遗器助手开关事件 =================
        self.relicEnhanceCard.switchButton.checkedChanged.connect(self.__onRelicSwitchChanged)
        # ========================================================

    def __onScreenTestCardClicked(self):
        start_task("screen_test")

    def __onCharacterExportCardClicked(self):
        start_task("character_export")

    # ================= 遗器助手开关逻辑 =================
    def __onRelicSwitchChanged(self, isChecked: bool):
        # 让文字跟随开关状态变化
        self.relicEnhanceCard.switchButton.setText(tr('开') if isChecked else tr('关'))

        if isChecked:
            k_enhance = self.relicEnhanceCard.edit_enhance.text().strip().lower()
            k_toggle = self.relicEnhanceCard.edit_toggle.text().strip().lower()
            k_lock = self.relicEnhanceCard.edit_lock.text().strip().lower()
            k_trash = self.relicEnhanceCard.edit_trash.text().strip().lower()

            if not k_enhance or not k_toggle or not k_lock or not k_trash or "请按键" in k_enhance or "请按键" in k_toggle:
                InfoBar.warning(title=tr('错误'), content=tr("按键不能为空，请展开重新录制"), orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self)
                self.relicEnhanceCard.switchButton.setChecked(False) # 失败则恢复关闭状态
                return

            self.relicEnhanceTask.start_listen(k_enhance, k_toggle, k_lock, k_trash)
            self.relicEnhanceCard.setContent(tr(f"状态：运行中 (强化: {k_enhance.upper()} / 接管: {k_toggle.upper()})"))
            InfoBar.success(title=tr('启动成功'), content=tr(f"请在游戏内使用 {k_enhance.upper()} 和 {k_toggle.upper()}"), orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self)
        else:
            self.relicEnhanceTask.stop_listen()
            self.relicEnhanceCard.setContent(tr("拦截鼠标侧键，实现自动置入/强化与快捷加锁/弃置"))
            InfoBar.info(title=tr('已停止'), content=tr("遗器助手已停止运行"), orient=Qt.Orientation.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self)
    # ====================================================

    def __onAutoPlotSwitchChanged(self, isChecked: bool):
        """Handle auto plot switch state change"""
        cfg.set_value("autoplot_enable", isChecked and bool(cfg.get_value("autoplot_remember_enable", False)))
        if isChecked:
            self.__startAutoPlot()
            InfoBar.success(
                title=tr('自动对话已启动'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        else:
            # Stop auto plot
            tool.stop_plot()
            InfoBar.info(
                title=tr('自动对话已停止'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __startAutoPlot(self):
        tool.update_plot_options(self.automaticPlotCard.getOptions())
        tool.start("plot")

    def __onAutoPlotOptionsChanged(self, options: dict):
        """Handle auto plot options change"""
        # Update options if auto plot is running
        if self.automaticPlotCard.getSwitchState():
            tool.update_plot_options(options)

    def toggleAutoPlot(self):
        """切换自动对话状态（供全局热键调用）"""
        current_state = self.automaticPlotCard.getSwitchState()
        new_state = not current_state
        self.automaticPlotCard.setValue(new_state)