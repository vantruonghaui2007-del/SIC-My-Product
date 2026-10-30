"""Local, rule-based music engine: prompt → recipe → composition → audio / stems / MIDI.

No generative AI model is involved; every step is deterministic music theory and synthesis.
"""
from .compose import Composition, compose
from .midi import to_midi
from .recipe import ParsedPrompt, Recipe, options, parse_prompt
from .render import STEM_LABELS, STEM_ORDER, render

__all__ = ["Composition", "ParsedPrompt", "Recipe", "STEM_LABELS", "STEM_ORDER", "compose", "options", "parse_prompt", "render", "to_midi"]
