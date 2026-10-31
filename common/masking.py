# -*- coding: utf-8 -*-
"""
Data masking helpers for PII and sensitive citizen records.
"""

import re


def mask_bank_account(acc: str) -> str:
    """Mask bank account showing only the last 4 digits."""
    if not acc:
        return ""
    clean = re.sub(r"[\s-]", "", str(acc))
    if len(clean) <= 4:
        return clean
    return "*" * (len(clean) - 4) + clean[-4:]


def mask_mobile(mob: str) -> str:
    """Mask mobile number showing first 2 and last 2 digits."""
    if not mob:
        return ""
    clean = re.sub(r"[\s-]", "", str(mob))
    if len(clean) <= 4:
        return clean
    return clean[:2] + "*" * (len(clean) - 4) + clean[-2:]

