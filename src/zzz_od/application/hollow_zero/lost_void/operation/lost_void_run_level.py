import time

import cv2
from cv2.typing import MatLike
from typing import ClassVar, Optional

from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.base.screen import screen_utils
from one_dragon.utils import cv2_utils
from one_dragon.yolo.detect_utils import DetectFrameResult
from zzz_od.application.hollow_zero.lost_void.context.lost_void_detector import LostVoidDetector
from zzz_od.application.hollow_zero.lost_void.lost_void_challenge_config import LostVoidRegionType
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_bangboo_store import LostVoidBangbooStore
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_common import LostVoidChooseCommon
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_eval import LostVoidChooseEval
from zzz_od.application.hollow_zero.lost_void.operation.interact.lost_void_choose_gear import LostVoidChooseGear
from zzz_od.application.hollow_zero.lost_void.operation.lost_void_move_by_det import LostVoidMoveByDet
from zzz_od.auto_battle import auto_battle_utils
from zzz_od.auto_battle.auto_battle_operator import AutoBattleOperator
from zzz_od.context.zzz_context import ZContext
from zzz_od.operation.zzz_operation import ZOperation


class LostVoidRunLevel(ZOperation):

    STATUS_NEXT_LEVEL: ClassVar[str] = '进入下层'
    STATUS_COMPLETE: ClassVar[str] = '通关'

    IT_BATTLE: ClassVar[str] = 'xxxx-战斗'

    def __init__(self, ctx: ZContext, region_type: LostVoidRegionType):
        """
        层间移动

        非战斗区域
        1. 朝感叹号移动
        2. 朝距离白点移动
        3. 朝下层入口移动
        4. 1~3没有识别目标的话 识别右上角文本提示 看会不会进入战斗
        5. 1~3没有识别目标的话 角色血量条是否扣减 有的话代表进入了战斗

        朝距离白点移动后 可能会是进入了混合区域的下一个区域
        1. 看有没有识别目标 有的话回到非战斗区域逻辑
        2. 1没有识别目标的话 识别右上角文本提示 看会不会进入战斗
        3. 1没有识别目标的话 角色血量条是否扣减 有的话代表进入了战斗

        战斗区域
        1. 战斗
        2. 非战斗画面后的一次识别 进行一次目标识别 判断是否脱离了战斗

        成功则返回 data=下一个可能的区域类型
        @param ctx:
        @param region_type:
        """
        ZOperation.__init__(self, ctx, op_name='迷失之地-层间移动')

        self.region_type: LostVoidRegionType = region_type
        self.detector: LostVoidDetector = self.ctx.lost_void.detector
        self.auto_op: AutoBattleOperator = self.ctx.lost_void.auto_op
        self.nothing_times: int = 0  # 识别不到内容的次数
        self.target_interact_type: str = ''  # 目标交互类型
        self.interact_entry_name: str = ''  # 交互的下层入口名称

        self.last_frame_in_battle: bool = True  # 上一帧画面在战斗
        self.last_det_time: float = 0  # 上一次进行识别的时间
        self.no_in_battle_times: int = 0  # 识别到不在战斗的次数
        self.last_check_finish_time: float = 0  # 上一次识别结束的时间

    @operation_node(name='等待加载', node_max_retry_times=60, is_start_node=False)
    def wait_loading(self) -> OperationRoundResult:
        screen = self.screenshot()

        if self.in_normal_world(screen):
            return self.round_success('大世界')

        screen_name = self.check_and_update_current_screen(screen)
        if screen_name in ['迷失之地-武备选择', '迷失之地-通用选择']:
            self.target_interact_type = LostVoidDetector.CLASS_INTERACT
            return self.round_success(screen_name)

        # 挑战-限时 挑战-无伤都是这个 都是需要战斗
        result = self.round_by_find_and_click_area(screen, '迷失之地-大世界', '按钮-挑战-确认')
        if result.is_success:
            self.region_type = LostVoidRegionType.CHANLLENGE_TIME_TRAIL
            return self.round_wait(result.status)

        return self.round_retry('未找到攻击交互按键', wait=1)

    @node_from(from_name='等待加载')
    @operation_node(name='区域类型初始化')
    def init_for_region_type(self) -> OperationRoundResult:
        """
        根据区域类型 跳转到具体的识别逻辑
        @return:
        """
        if self.region_type == LostVoidRegionType.ENTRY:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.COMBAT_RESONIUM:
            return self.round_success('战斗区域')
        if self.region_type == LostVoidRegionType.COMBAT_GEAR:
            return self.round_success('战斗区域')
        if self.region_type == LostVoidRegionType.COMBAT_COIN:
            return self.round_success('战斗区域')
        if self.region_type == LostVoidRegionType.CHANLLENGE_FLAWLESS:
            return self.round_success('战斗区域')
        if self.region_type == LostVoidRegionType.CHANLLENGE_TIME_TRAIL:
            return self.round_success('战斗区域')
        if self.region_type == LostVoidRegionType.ENCOUNTER:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.PRICE_DIFFERENCE:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.REST:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.BANGBOO_STORE:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.FRIENDLY_TALK:
            return self.round_success('非战斗区域')
        if self.region_type == LostVoidRegionType.ELITE:
            return self.round_success('战斗区域')
        if self.region_type == LostVoidRegionType.BOSS:
            return self.round_success('战斗区域')

        return self.round_success('非战斗区域')

    @node_from(from_name='区域类型初始化', status='非战斗区域')
    @node_from(from_name='非战斗画面识别', status=LostVoidDetector.CLASS_DISTANCE)  # 朝白点移动后重新循环
    @node_from(from_name='交互后处理', status='大世界')  # 目前交互之后都不会有战斗
    @node_from(from_name='战斗中', status='识别需移动交互')  # 战斗后出现距离 或者下层入口
    @operation_node(name='非战斗画面识别')
    def non_battle_check(self) -> OperationRoundResult:
        now = time.time()
        screen = self.screenshot()

        frame_result: DetectFrameResult = self.ctx.lost_void.detector.run(screen, run_time=now)
        with_interact, with_distance, with_entry = self.ctx.lost_void.detector.is_frame_with_all(frame_result)

        if with_interact:
            self.nothing_times = 0
            self.target_interact_type = LostVoidDetector.CLASS_INTERACT
            op = LostVoidMoveByDet(self.ctx, LostVoidDetector.CLASS_INTERACT,
                                   stop_when_disappear=False)
            op_result = op.execute()
            if op_result.success:
                return self.round_success(LostVoidDetector.CLASS_INTERACT, wait=1)
            elif op_result.status == LostVoidMoveByDet.STATUS_IN_BATTLE:
                return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)
            else:
                return self.round_retry('移动失败')
        elif with_distance:
            self.nothing_times = 0
            self.target_interact_type = LostVoidDetector.CLASS_DISTANCE
            op = LostVoidMoveByDet(self.ctx, LostVoidDetector.CLASS_DISTANCE,
                                   stop_when_interact=False)
            op_result = op.execute()
            if op_result.success:
                return self.round_success(LostVoidDetector.CLASS_DISTANCE)
            elif op_result.status == LostVoidMoveByDet.STATUS_IN_BATTLE:
                return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)
            else:
                return self.round_retry('移动失败')
        elif with_entry:
            self.nothing_times = 0
            self.target_interact_type = LostVoidDetector.CLASS_ENTRY
            op = LostVoidMoveByDet(self.ctx, LostVoidDetector.CLASS_ENTRY,
                                   stop_when_disappear=False)
            op_result = op.execute()
            if op_result.success:
                self.interact_entry_name = op_result.data
                return self.round_success(LostVoidDetector.CLASS_ENTRY)
            elif op_result.status == LostVoidMoveByDet.STATUS_IN_BATTLE:
                return self.round_success(LostVoidMoveByDet.STATUS_IN_BATTLE)
            else:
                return self.round_retry('移动失败')
        else:
            in_battle = self.ctx.lost_void.check_battle_encounter(screen, now)
            if in_battle:
                self.last_det_time = time.time()
                self.last_check_finish_time = time.time()
                return self.round_success(status='进入战斗')

        self.ctx.controller.turn_by_distance(-100)
        self.nothing_times += 1
        return self.round_wait(status='转动识别目标', wait=0.5)

    @node_from(from_name='非战斗画面识别', status=LostVoidDetector.CLASS_INTERACT)
    @node_from(from_name='非战斗画面识别', status=LostVoidDetector.CLASS_ENTRY)
    @operation_node(name='尝试交互')
    def try_interact(self) -> OperationRoundResult:
        """
        走到了交互点后 尝试交互
        @return:
        """
        screen = self.screenshot()
        result = self.round_by_find_area(screen, '战斗画面', '按键-交互')
        if result.is_success:
            self.ctx.controller.interact(press=True, press_time=0.2, release=True)
            return self.round_retry('交互', wait=1)

        if not self.in_normal_world(screen):  # 按键消失 说明开始加载了
            return self.round_success('交互成功')

        # 没有交互按钮 可能走过头了 尝试往后走
        self.ctx.controller.move_s(press=True, press_time=0.2, release=True)
        time.sleep(0.2)
        self.ctx.controller.move_s(press=True, press_time=0.2, release=True)
        time.sleep(0.2)
        self.ctx.controller.move_w(press=True, press_time=0.2, release=True)
        time.sleep(0.2)

        return self.round_retry('未发现交互按键')

    @node_from(from_name='等待加载', status='迷失之地-武备选择')
    @node_from(from_name='等待加载', status='迷失之地-通用选择')
    @node_from(from_name='尝试交互', status='交互成功')
    @node_from(from_name='战斗中', status='识别正在交互')
    @node_from(from_name='交互后处理', status='迷失之地-通用选择')
    @operation_node(name='交互处理')
    def handle_interact(self) -> OperationRoundResult:
        """
        只有以下情况确认交互完成

        1. 返回大世界
        2. 出现挑战结果
        @return:
        """
        screen = self.screenshot()

        screen_name = self.check_and_update_current_screen(screen)
        interact_op: Optional[ZOperation] = None
        if screen_name == '迷失之地-武备选择':
            interact_op = LostVoidChooseGear(self.ctx)
        elif screen_name == '迷失之地-通用选择':
            interact_op = LostVoidChooseCommon(self.ctx)
        elif screen_name == '迷失之地-业绩选择':
            interact_op = LostVoidChooseEval(self.ctx)
        elif screen_name == '迷失之地-邦布商店':
            interact_op = LostVoidBangbooStore(self.ctx)
        elif screen_name == '迷失之地-大世界':
            return self.round_success('迷失之地-大世界')

        if interact_op is not None:
            # 出现选择的情况 交互到的不是下层入口 中途交互到其他内容了
            if self.target_interact_type == LostVoidDetector.CLASS_ENTRY:
                self.target_interact_type = LostVoidDetector.CLASS_INTERACT
            op_result = interact_op.execute()
            if op_result.success:
                return self.round_wait(op_result.status)
            else:
                return self.round_fail(op_result.status)

        talk_result = self.try_talk(screen)
        if talk_result is not None:
            # 对话的情况 说明交互到的不是下层入口 中途交互到其他内容了
            if self.target_interact_type == LostVoidDetector.CLASS_ENTRY:
                self.target_interact_type = None

            return talk_result

        if self.in_normal_world(screen):
            return self.round_success('迷失之地-大世界')

        result = self.round_by_find_area(screen, '迷失之地-挑战结果', '标题-挑战结果')
        if result.is_success:
            return self.round_success('迷失之地-挑战结果')

        return self.round_retry(status=f'未知画面', wait_round_time=0.3)

    def try_talk(self, screen: MatLike) -> OperationRoundResult:
        """
        判断是否在对话 并进行点击
        @return:
        """
        area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-对话角色名称')
        part = cv2_utils.crop_image_only(screen, area.rect)
        mask = cv2.inRange(part, (200, 200, 200), (255, 255, 255))
        mask = cv2_utils.dilate(mask, 2)
        to_ocr = cv2.bitwise_and(part, part, mask=mask)
        ocr_result_map = self.ctx.ocr.run_ocr(to_ocr)

        if len(ocr_result_map) > 0:  # 有可能在交互
            self.ctx.controller.click(area.center)
            return self.round_wait(f'尝试交互 {str(ocr_result_map.keys)}', wait=0.5)

    @node_from(from_name='交互处理', status='迷失之地-大世界')
    @node_from(from_name='交互处理', status='迷失之地-挑战结果')
    @node_from(from_name='交互处理', success=False, status='未知画面')
    @operation_node(name='交互后处理', node_max_retry_times=10)
    def after_interact(self) -> OperationRoundResult:
        """
        交互后
        1. 在大世界的 先退后 让交互按键消失 再继续后续寻路
        2. 不在大世界的 可能是战斗后结果画面 也可能是交互进入下层
        @return:
        """
        screen = self.screenshot()

        if self.in_normal_world(screen):
            if self.target_interact_type != LostVoidRunLevel.IT_BATTLE:  # 战斗后的交互 不需要往后走
                self.ctx.controller.move_s(press=True, press_time=1, release=True)
            return self.round_success(status='大世界')

        result = self.round_by_find_area(screen, '迷失之地-挑战结果', '标题-挑战结果')
        if result.is_success:
            # 这个标题出来之后 按钮还需要一段时间才能出来
            r2 = self.round_by_find_area(screen, '迷失之地-挑战结果', '按钮-确定')
            if r2.is_success:
                return self.round_success('挑战结果-确定', wait=2)

            r2 = self.round_by_find_area(screen, '迷失之地-挑战结果', '按钮-完成')
            if r2.is_success:
                return self.round_success('挑战结果-完成', wait=2)

        if self.target_interact_type == LostVoidDetector.CLASS_ENTRY:
            return self.round_success(LostVoidRunLevel.STATUS_NEXT_LEVEL, data=self.interact_entry_name)

        return self.round_retry('等待画面返回', wait=1)

    def in_normal_world(self, screen: MatLike) -> bool:
        """
        判断当前画面是否在大世界里
        @param screen: 游戏画面
        @return:
        """
        result = self.round_by_find_area(screen, '战斗画面', '按键-普通攻击')
        if result.is_success:
            return True

        result = self.round_by_find_area(screen, '战斗画面', '按键-交互')
        if result.is_success:
            return True

        result = self.round_by_find_area(screen, '迷失之地-大世界', '按键-交互-不可用')
        if result.is_success:
            return True

        return False

    @node_from(from_name='区域类型初始化', status='战斗区域')
    @node_from(from_name='非战斗画面识别', status='进入战斗')
    @node_from(from_name='非战斗画面识别', status=LostVoidMoveByDet.STATUS_IN_BATTLE)
    @operation_node(name='战斗中', mute=True)
    def in_battle(self) -> OperationRoundResult:
        if not self.auto_op.is_running:
            self.auto_op.start_running_async()

        screenshot_time = time.time()
        screen = self.screenshot()
        in_battle = self.auto_op.auto_battle_context.check_battle_state(screen, screenshot_time)

        if in_battle:  # 当前回到可战斗画面
            if (not self.last_frame_in_battle  # 之前在非战斗画面
                or screenshot_time - self.last_det_time >= 5  # 5秒识别一次
                or self.no_in_battle_times > 0  # 之前也识别到脱离战斗
            ):
                # 尝试识别目标
                self.last_det_time = screenshot_time
                no_in_battle = False
                try:
                    # 为了不随意打断战斗 这里的识别阈值要高一点
                    frame_result: DetectFrameResult = self.detector.run(screen, run_time=screenshot_time, conf=0.9)
                    with_interact, with_distance, with_entry = self.detector.is_frame_with_all(frame_result)
                    if with_interact or with_distance or with_entry:
                        no_in_battle = True
                except Exception as e:
                    # 刚开始可能有一段时间识别报错 不知道为什么
                    pass

                if not no_in_battle:
                    area = self.ctx.screen_loader.get_area('迷失之地-大世界', '区域-文本提示')
                    if screen_utils.find_by_ocr(self.ctx, screen, target_cn='千万下一个区域', area=area):
                        no_in_battle = True

                if no_in_battle:
                    self.no_in_battle_times += 1
                else:
                    self.no_in_battle_times = 0

                if self.no_in_battle_times >= 5:
                    if self.ctx.env_config.is_debug:
                        self.save_screenshot()
                    auto_battle_utils.stop_running(self.auto_op)
                    return self.round_success('识别需移动交互')

                return self.round_wait()
        else:  # 当前不在战斗画面
            if (screenshot_time - self.last_check_finish_time >= 5  # 5秒识别一次
                or self.no_in_battle_times > 0  # 之前也识别到脱离战斗
            ):
                self.last_check_finish_time = screenshot_time
                screen_name = self.check_and_update_current_screen(screen)
                if screen_name in ['迷失之地-武备选择', '迷失之地-通用选择']:
                    self.no_in_battle_times += 1
                else:
                    self.no_in_battle_times = 0

                if self.no_in_battle_times >= 5:
                    if self.ctx.env_config.is_debug:
                        self.save_screenshot()
                    auto_battle_utils.stop_running(self.auto_op)
                    self.target_interact_type = LostVoidRunLevel.IT_BATTLE
                    return self.round_success('识别正在交互')

                return self.round_wait()

        return self.round_wait(self.ctx.battle_assistant_config.screenshot_interval)

    @node_from(from_name='交互后处理', status='挑战结果-确定')
    @operation_node(name='挑战结果处理确定')
    def handle_challenge_result_confirm(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='迷失之地-挑战结果', area_name='按钮-确定',
                                                   until_not_find_all=[('迷失之地-挑战结果', '按钮-确定')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_success(LostVoidRunLevel.STATUS_NEXT_LEVEL, data=LostVoidRegionType.FRIENDLY_TALK.value.value)
        else:
            return result

    @node_from(from_name='交互后处理', status='挑战结果-确定')
    @operation_node(name='挑战结果处理完成')
    def handle_challenge_result_finish(self) -> OperationRoundResult:
        result = self.round_by_find_and_click_area(screen_name='迷失之地-挑战结果', area_name='按钮-完成',
                                                   until_not_find_all=[('迷失之地-挑战结果', '按钮-完成')],
                                                   success_wait=1, retry_wait=1)
        if result.is_success:
            return self.round_success(LostVoidRunLevel.STATUS_COMPLETE, data=LostVoidRegionType.FRIENDLY_TALK.value.value)
        else:
            return result

    def handle_pause(self) -> None:
        ZOperation.handle_pause(self)
        auto_battle_utils.stop_running(self.auto_op)


def __debug():
    ctx = ZContext()
    ctx.init_by_config()
    ctx.lost_void.init_before_run()
    ctx.ocr.init_model()
    ctx.start_running()

    op = LostVoidRunLevel(ctx, LostVoidRegionType.ENTRY)

    from one_dragon.utils import debug_utils
    screen = debug_utils.get_debug_image('_1735464006666')
    result = op.round_by_find_area(screen, '迷失之地-挑战结果', '标题-挑战结果')
    print(result.is_success)

    op.execute()


if __name__ == '__main__':
    __debug()
