"""Parser package. Importing it registers built-in parsers."""

from app.lab.parsers.sequencing import SequencingSummaryParser
from app.lab.parsers.vicell import ViCellXrTabularParser

__all__ = ["SequencingSummaryParser", "ViCellXrTabularParser"]
