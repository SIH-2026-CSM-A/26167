"""Declared SAR pixel-value scale for fusion tools."""

from enum import Enum


class SarScale(Enum):
    """The scale a caller asserts a SAR array is already in.

    Never inferred from pixel values — always stated explicitly by the caller
    that produced or loaded the array.
    """

    DB = "db"
    LINEAR = "linear"
