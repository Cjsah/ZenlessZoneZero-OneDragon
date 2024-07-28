from one_dragon.base.conditional_operation.atomic_op import AtomicOp
from zzz_od.context.battle_context import BattleEventEnum
from zzz_od.context.zzz_context import ZContext


class AtomicBtnSwitchNext(AtomicOp):

    def __init__(self, ctx: ZContext):
        AtomicOp.__init__(self, op_name=BattleEventEnum.BTN_SWITCH_NEXT.value)
        self.ctx: ZContext = ctx

    def execute(self):
        self.ctx.battle.switch_next()

    def stop(self) -> None:
        self.ctx.controller.release_switch_next()