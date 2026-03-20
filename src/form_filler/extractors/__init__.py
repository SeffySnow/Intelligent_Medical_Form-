"""Extraction sub-package.

Public surface:
  BaseExtractor         — abstract base (Dependency Inversion target)
  DemographicsExtractor — extracts from demographics.json
  SOAPExtractor         — extracts from SOAP notes text
  LabExtractor          — extracts from lab result PDF
"""

from form_filler.extractors.base import BaseExtractor
from form_filler.extractors.demographics import DemographicsExtractor
from form_filler.extractors.lab import LabExtractor
from form_filler.extractors.soap import SOAPExtractor

__all__ = [
    "BaseExtractor",
    "DemographicsExtractor",
    "SOAPExtractor",
    "LabExtractor",
]
