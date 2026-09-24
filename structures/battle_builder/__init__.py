"""A composable builder for L2BASM battle/AI scripts (monster & capsule attack/reaction, IP effects).

Two layers:

- **low-level** (:mod:`~structures.battle_builder.nodes`): one node per opcode plus label-aware control
  flow (``label``/``goto``/``on_chance``/``on_fail``/compares). Byte-exact; can reproduce any real script.
- **high-level sugar** (:mod:`~structures.battle_builder.sugar`): ``cast_spell``, ``cast_spell_free``,
  ``chance`` (inline guard), ``choose`` (ordered dispatch), ``target``, ``sequence``, ``Target``.

:func:`assemble` resolves labels to record-relative offsets; :func:`apply` writes in place. Example::

    from structures.battle_builder import apply, choose, chance, cast_spell_free, physical_attack, Target
    from lookups import Spells

    apply(foomy.attack_script, choose(
        chance(0.19, cast_spell_free(Spells.VALOR,    target=Target.ALL_ALLIES)),
        chance(0.69, cast_spell_free(Spells.FIREBIRD, target=Target.ONE_FOE)),
        default=physical_attack(target=Target.ONE_FOE),
    ), max_size=0x4F - 0x2B)
"""

from structures.battle_builder.assembler import apply, assemble, assemble_at
from structures.battle_builder.nodes import (
    Label,
    Node,
    Ref,
    apply_status,
    battle_anim,
    display_name,
    end,
    execute,
    goto,
    if_eq,
    if_ge,
    if_gt,
    if_le,
    if_lt,
    if_ne,
    label,
    learnable,
    magical_damage,
    on_chance,
    on_fail,
    physical_damage,
    raw,
    resist,
    set_reg,
    use_item,
)
from structures.battle_builder.sugar import (
    Target,
    cast_spell,
    cast_spell_free,
    chance,
    choose,
    defend,
    flee,
    physical_attack,
    sequence,
    target,
)


__all__ = [
    "Label",
    "Node",
    "Ref",
    "Target",
    "apply",
    "apply_status",
    "assemble",
    "assemble_at",
    "battle_anim",
    "cast_spell",
    "cast_spell_free",
    "chance",
    "choose",
    "defend",
    "display_name",
    "end",
    "execute",
    "flee",
    "goto",
    "if_eq",
    "if_ge",
    "if_gt",
    "if_le",
    "if_lt",
    "if_ne",
    "label",
    "learnable",
    "magical_damage",
    "on_chance",
    "on_fail",
    "physical_attack",
    "physical_damage",
    "raw",
    "resist",
    "sequence",
    "set_reg",
    "target",
    "use_item",
]
